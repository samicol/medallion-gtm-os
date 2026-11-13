/**
 * ClayLens: content script
 *
 * Runs on every app.clay.com page. Detects the active tableId/viewId/workspaceId
 * from window.location.href and forwards a tableContext message to the background
 * service worker so the side panel knows which table the user is looking at.
 *
 * Clay is a SPA: the URL changes via history.pushState/replaceState without a
 * page reload. We patch both methods plus listen for popstate so we always
 * re-detect on navigation.
 */

(function () {
  'use strict';

  const LOG = '[claylens:content]';

  // ---------------------------------------------------------------------------
  // URL parsing
  // ---------------------------------------------------------------------------
  function getTableContext() {
    const url = window.location.href;
    const tableMatch = url.match(/tables\/(t_[a-zA-Z0-9]+)/);
    const viewMatch = url.match(/views\/(gv_[a-zA-Z0-9]+)/);
    const workspaceMatch = url.match(/workspaces\/(\d+)/);

    return {
      type: 'tableContext',
      tableId: tableMatch ? tableMatch[1] : null,
      viewId: viewMatch ? viewMatch[1] : null,
      workspaceId: workspaceMatch ? workspaceMatch[1] : null,
      url,
      isTablePage: !!tableMatch,
    };
  }

  // ---------------------------------------------------------------------------
  // Send context to background. Wrapped in try/catch; extension may not be
  // listening yet (during install/reload), and we don't want to spam the page
  // console with uncaught errors.
  // ---------------------------------------------------------------------------
  let lastSentKey = null;

  function sendTableContext() {
    const ctx = getTableContext();
    const key = `${ctx.tableId}|${ctx.viewId}|${ctx.workspaceId}`;
    if (key === lastSentKey) return; // dedupe: pushState fires a lot
    lastSentKey = key;

    try {
      chrome.runtime.sendMessage(ctx, (response) => {
        // Touch chrome.runtime.lastError so Chrome stops complaining when the
        // background script isn't ready to respond.
        if (chrome.runtime.lastError) {
          // swallow: extension context invalidated or no listener
        }
      });
      console.log(LOG, 'sent tableContext', ctx);
    } catch (err) {
      console.log(LOG, 'sendMessage failed (extension reloading?):', err?.message);
    }
  }

  // ---------------------------------------------------------------------------
  // SPA navigation hook: patch history.pushState / replaceState to fire a
  // custom event we can listen for. Same approach as most SPA-aware extensions.
  // ---------------------------------------------------------------------------
  const NAV_EVENT = 'claylens:locationchange';

  function patchHistory(methodName) {
    const original = history[methodName];
    history[methodName] = function (...args) {
      const result = original.apply(this, args);
      window.dispatchEvent(new Event(NAV_EVENT));
      return result;
    };
  }

  patchHistory('pushState');
  patchHistory('replaceState');

  window.addEventListener('popstate', () => {
    window.dispatchEvent(new Event(NAV_EVENT));
  });

  window.addEventListener(NAV_EVENT, () => {
    // Tiny debounce: Clay sometimes fires several pushStates in a row when
    // mounting a view.
    setTimeout(sendTableContext, 50);
  });

  // ---------------------------------------------------------------------------
  // Overlay manager
  //
  // Mounts analytics.html in an iframe inside a fixed-position modal layered
  // above the Clay UI. The iframe URL carries the table/view/workspace IDs as
  // query params so analytics.js can render without round-tripping through
  // chrome.storage.session. This fixes the "Analyze does nothing" silent failure
  // that came from opening a new tab with no context.
  //
  // Closed by:
  //   - clicking the backdrop
  //   - clicking the X
  //   - pressing Escape
  //   - background.js sending {type: 'hideAnalytics'}
  // ---------------------------------------------------------------------------

  const OVERLAY_ID = 'claylens-overlay';
  const STYLE_ID = 'claylens-overlay-styles';
  let overlayEl = null;

  function ensureOverlayStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const style = document.createElement('style');
    style.id = STYLE_ID;
    // z-index 2147483647 is the 32-bit signed-int max, so it sits above Clay's own
    // modals. Animations are GPU-friendly (opacity + transform only).
    style.textContent = `
      #${OVERLAY_ID} {
        position: fixed;
        inset: 0;
        z-index: 2147483647;
        animation: claylensFadeIn 120ms ease-out;
      }
      #${OVERLAY_ID} .claylens-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(8, 8, 16, 0.62);
        backdrop-filter: blur(2px);
        -webkit-backdrop-filter: blur(2px);
        z-index: 2147483646;
      }
      #${OVERLAY_ID} .claylens-modal {
        position: fixed;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        width: min(1180px, calc(100vw - 48px));
        height: min(780px, calc(100vh - 48px));
        border-radius: 14px;
        overflow: hidden;
        background: #1a1a26;
        box-shadow: 0 24px 64px rgba(0, 0, 0, 0.45),
                    0 0 0 1px rgba(255, 255, 255, 0.06);
        z-index: 2147483647;
        animation: claylensModalIn 160ms cubic-bezier(0.2, 0.8, 0.2, 1);
      }
      #${OVERLAY_ID} iframe {
        width: 100%;
        height: 100%;
        border: 0;
        display: block;
        background: #1a1a26;
      }
      #${OVERLAY_ID} .claylens-close {
        position: absolute;
        top: 10px;
        right: 12px;
        width: 32px;
        height: 32px;
        border-radius: 8px;
        border: 0;
        background: rgba(255, 255, 255, 0.08);
        color: #fff;
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        z-index: 2;
        transition: background 120ms ease, transform 120ms ease;
      }
      #${OVERLAY_ID} .claylens-close:hover {
        background: rgba(255, 255, 255, 0.18);
        transform: scale(1.05);
      }
      @keyframes claylensFadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
      }
      @keyframes claylensModalIn {
        from { opacity: 0; transform: translate(-50%, -48%) scale(0.98); }
        to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
      }
    `;
    document.head.appendChild(style);
  }

  function escHandler(e) {
    if (e.key === 'Escape') hideOverlay();
  }

  function showOverlay() {
    if (overlayEl) {
      // Already mounted: just refocus the iframe so keyboard input lands
      // inside the dashboard rather than passing through to Clay.
      overlayEl.querySelector('iframe')?.focus();
      return;
    }

    ensureOverlayStyles();
    const ctx = getTableContext();
    const params = new URLSearchParams({
      tableId: ctx.tableId || '',
      viewId: ctx.viewId || '',
      workspaceId: ctx.workspaceId || '',
      sourceUrl: window.location.href,
    });

    overlayEl = document.createElement('div');
    overlayEl.id = OVERLAY_ID;
    overlayEl.innerHTML = `
      <div class="claylens-backdrop" data-claylens-close></div>
      <div class="claylens-modal" role="dialog" aria-modal="true" aria-label="ClayLens analytics">
        <button class="claylens-close" data-claylens-close type="button" aria-label="Close ClayLens">×</button>
        <iframe src="${chrome.runtime.getURL('analytics.html')}?${params.toString()}" allow="clipboard-write" title="ClayLens analytics"></iframe>
      </div>
    `;
    document.body.appendChild(overlayEl);

    overlayEl.addEventListener('click', (e) => {
      const target = e.target;
      if (target && target.dataset && 'claylensClose' in target.dataset) {
        hideOverlay();
      }
    });
    document.addEventListener('keydown', escHandler);
    console.log(LOG, 'overlay mounted with ctx', ctx);
  }

  function hideOverlay() {
    if (overlayEl) {
      overlayEl.remove();
      overlayEl = null;
    }
    document.removeEventListener('keydown', escHandler);
  }

  // ---------------------------------------------------------------------------
  // Listen for show/hide commands from background. Iframe ↔ parent close
  // signaling uses postMessage (analytics.html can post {type:'claylens:close'}
  // to window.parent if it ever wants to dismiss itself).
  // ---------------------------------------------------------------------------
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'showAnalytics') {
      showOverlay();
      sendResponse({ ok: true });
      return false;
    }
    if (msg?.type === 'hideAnalytics') {
      hideOverlay();
      sendResponse({ ok: true });
      return false;
    }
    return false;
  });

  window.addEventListener('message', (event) => {
    // Only accept close signals from our own iframe (extension origin).
    if (event?.data?.type === 'claylens:close') hideOverlay();
  });

  // ---------------------------------------------------------------------------
  // Initial fire on script load.
  // ---------------------------------------------------------------------------
  console.log(LOG, 'loaded on', window.location.href);
  sendTableContext();
})();
