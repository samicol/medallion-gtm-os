/**
 * ClayLens: background service worker
 *
 * Analytics-only: `analyze` fetches, extracts, and aggregates per-cell cost
 * data for the active table. Message router, side-panel-open, and
 * tableContext stash preserved.
 *
 * Runs as an ES module (`type: "module"` in manifest.json).
 */

import {
  getTable,
  getRecordIds,
  bulkFetchRecords, // re-exported for non-cost callers; analyze uses fetchRecordsParallel
  fetchRecordsParallel,
  cacheExtraction,
  loadExtraction,
  clearExtraction,
} from './lib/clay-api.js';
import { extractCostFields } from './lib/cost-extractor.js';
import { aggregate } from './lib/aggregator.js';

const LOG = '[claylens:background]';

// ---------------------------------------------------------------------------
// Toolbar icon → ask the active Clay tab's content script to mount the
// analytics dashboard as an in-page iframe overlay.
// ---------------------------------------------------------------------------
//
// We deliberately avoid chrome.tabs.create here; opening analytics.html in a
// new browser tab severed the link to the originating Clay tab (no tableId in
// URL, no way to read the source-tab session storage from the new tab's
// origin). The user also asked for an in-page popup, not a separate page.
//
// Flow:
//   1. Confirm we're on app.clay.com.
//   2. Send {type: 'showAnalytics'} to the tab's content script.
//   3. content.js parses tableId/viewId/workspaceId from window.location.href
//      itself and injects the iframe with the params baked into the URL.
//   4. If the content script isn't loaded (extension was installed/updated
//      after the tab was opened), inject content.js on demand via
//      chrome.scripting.executeScript and retry.
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;
  const url = tab.url || '';
  if (!/^https:\/\/app\.clay\.com\//.test(url)) {
    console.log(LOG, 'icon clicked outside Clay, ignoring (url:', url, ')');
    return;
  }
  try {
    await chrome.tabs.sendMessage(tab.id, { type: 'showAnalytics' });
  } catch (err) {
    console.log(LOG, 'sendMessage to content failed:', err?.message,
      '(attempting on-demand inject)');
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js'],
      });
      await chrome.tabs.sendMessage(tab.id, { type: 'showAnalytics' });
    } catch (e2) {
      console.log(LOG, 'fallback inject failed:', e2?.message);
    }
  }
});

// ---------------------------------------------------------------------------
// Per-tab tableContext cache
//
// content.js sends `{type: 'tableContext', ...}` whenever the URL changes.
// We stash the latest context per tabId in chrome.storage.session so the side
// panel can read it on open without round-tripping through the content script.
// ---------------------------------------------------------------------------

async function stashTableContext(tabId, payload) {
  if (typeof tabId !== 'number') return;
  const key = `tableContext:${tabId}`;
  try {
    await chrome.storage.session.set({ [key]: payload });
    console.log(LOG, 'stashed tableContext for tab', tabId, payload);
  } catch (err) {
    console.log(LOG, 'storage.session.set failed:', err?.message);
  }
}

// Clean up when a tab closes so we don't accumulate stale entries.
chrome.tabs.onRemoved.addListener(async (tabId) => {
  try {
    await chrome.storage.session.remove(`tableContext:${tabId}`);
  } catch (err) {
    // session storage may not be available in some Chrome builds
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Best-effort send of a message to the side panel. The panel may not be open;
 * we swallow the resulting "no receiving end" error.
 */
function broadcast(message) {
  try {
    chrome.runtime.sendMessage(message).catch(() => {});
  } catch (err) {
    // sendMessage can throw synchronously if the runtime is shutting down.
  }
}

/**
 * Unwrap `getTable()` response: Clay sometimes returns { table: {...} }, sometimes flat.
 */
function unwrapTable(raw) {
  if (raw && typeof raw === 'object' && raw.table && typeof raw.table === 'object') {
    return raw.table;
  }
  return raw || {};
}

/**
 * Pull the configured AI model out of a `use-ai` action's inputsBinding.
 */
function modelFromUseAi(field) {
  const ts = field?.typeSettings || {};
  const inputs = (ts.inputsBinding || []).reduce((acc, i) => {
    if (i && i.name) acc[i.name] = i;
    return acc;
  }, {});
  const formula = inputs.model?.formulaText;
  if (!formula) return null;
  const s = String(formula).trim();
  if (s.startsWith('"') && s.endsWith('"')) return s.slice(1, -1);
  return s;
}

function actionUseCaseFromUseAi(field) {
  const ts = field?.typeSettings || {};
  const inputs = (ts.inputsBinding || []).reduce((acc, i) => {
    if (i && i.name) acc[i.name] = i;
    return acc;
  }, {});
  const formula = inputs.useCase?.formulaText;
  if (!formula) return null;
  const s = String(formula).trim();
  if (s.startsWith('"') && s.endsWith('"')) return s.slice(1, -1);
  return s;
}

/**
 * Filter table fields to those that can carry cost data.
 *
 * - action columns (any actionKey; providers, use-ai, claygent, lookup-*)
 * - source columns (Find People, etc.; explicit 0 credits per provider-costs)
 *
 * Returns columnMeta in the shape the aggregator expects.
 */
function buildColumnMeta(tableObj) {
  const fields = tableObj.fields || [];
  const meta = [];
  for (const f of fields) {
    const type = f.type;
    if (type !== 'action' && type !== 'source') continue;

    const ts = f.typeSettings || {};
    const actionKey = ts.actionKey || null;
    let model = null;
    let actionUseCase = null;
    if (actionKey === 'use-ai') {
      model = modelFromUseAi(f);
      actionUseCase = actionUseCaseFromUseAi(f);
    }

    meta.push({
      field_id: f.id,
      field_name: f.name,
      type,
      model_configured: model,
      action_key: actionKey,
      action_use_case: actionUseCase,
    });
  }
  return meta;
}

/**
 * Pick the best view ID for record enumeration. Prefer 'All rows' over
 * 'Default view' (the latter silently caps at 500 records).
 */
function pickViewId(tableObj, hint = null) {
  const views = tableObj.views || tableObj.gridViews || [];
  for (const v of views) {
    if (((v.name || '').trim().toLowerCase()) === 'all rows') return v.id;
  }
  if (hint) return hint;
  return tableObj.firstViewId || (views[0] && views[0].id) || null;
}

/**
 * Attach a cell's context (record_id, field_id) onto the extractCostFields
 * output. The aggregator keys off these.
 */
function attachContext(extracted, recordId, fieldId) {
  return { ...extracted, record_id: recordId, field_id: fieldId };
}

/**
 * Process a batch of records → flat array of enriched extracted cells.
 *
 * Skips fields without a metaById entry (e.g. the user added a new field
 * between getTable and the per-record fetch).
 *
 * Self-debug: if EVERY cell in this batch has neither cost nor credit nor
 * status data, emit a one-time warning per process. This is the canary for
 * the "wrong endpoint shape" bug class; bulk-fetch-records returns slim
 * cells without externalContent.fullValue, so cost/credits/status all come
 * back null. analyze() now uses fetchRecord (per-record GET) which returns
 * the full payload. If a future caller swaps endpoints, this will fire.
 */
let _emptyShapeWarned = false;
function extractPage(records, metaById) {
  const out = [];
  let inspected = 0;
  let allEmpty = true;
  for (const rec of records) {
    const rid = rec.id || rec.recordId;
    if (!rid) continue;
    const cells = rec.cells || {};
    for (const [fieldId, cell] of Object.entries(cells)) {
      const m = metaById.get(fieldId);
      if (!m) continue; // not a cost-bearing column
      const extracted = extractCostFields(cell, m.type, m.action_key);
      out.push(attachContext(extracted, rid, fieldId));
      inspected++;
      if (extracted.total_cost_usd != null || extracted.credits != null ||
          extracted.status != null) {
        allEmpty = false;
      }
    }
  }
  if (!_emptyShapeWarned && inspected >= 10 && allEmpty) {
    _emptyShapeWarned = true;
    console.warn(
      LOG,
      'every cell came back with no cost data; externalContent may be missing. ' +
      'Check Network tab for the actual response shape.',
    );
  }
  return out;
}

// ---------------------------------------------------------------------------
// Action handlers
// ---------------------------------------------------------------------------

// Per-record GET fan-out width. Mirrors fetch_all_records_full default
// (clay_client.py, workers=20). Trades latency for politeness.
const FETCH_WORKERS = 20;

/**
 * Run the full table analysis pipeline.
 *
 * Stages:
 *   1. cache hit (unless force) → return immediately
 *   2. getTable + filter to cost-bearing columns
 *   3. getRecordIds → fetchRecordsParallel (20 workers, per-record GET)
 *   4. per cell → extractCostFields
 *   5. emit `analyzeProgress` periodically via onProgress
 *   6. aggregate → cacheExtraction → respond with extraction
 *
 * IMPORTANT: we use per-record GET (`fetchRecordsParallel` →
 * `GET /tables/{id}/records/{rid}`) instead of the bulk-fetch endpoint.
 * `bulk-fetch-records` returns the slim grid-render shape and OMITS
 * `externalContent.fullValue` where cost/token data lives; it caused every
 * cell to report $0 in an earlier version of this extension. Rex's own
 * clay_client.py:fetch_all_records_full / get_cell_costs use the same
 * per-record endpoint for this exact reason.
 */
async function doAnalyze(message) {
  const { tableId, viewId: viewHint, workspaceId, force } = message;
  if (!tableId) throw new Error('analyze: tableId is required');
  if (!workspaceId) throw new Error('analyze: workspaceId is required');

  if (!force) {
    try {
      const cached = await loadExtraction(workspaceId, tableId);
      if (cached) {
        console.log(LOG, 'analyze: cache hit for', tableId, '(isStale=', cached.isStale, ')');
        // Strip byRow before sending: the iframe only renders topRows +
        // totals + byColumn, and on a 5k+ row table with ~5 AI columns byRow
        // can be tens of MB, which chokes chrome.runtime.sendMessage.
        // byRow stays in IndexedDB for any future feature that needs it.
        const { byRow, ...trimmed } = cached;
        return { ok: true, extraction: trimmed, cached: true };
      }
    } catch (err) {
      console.log(LOG, 'analyze: cache read failed:', err.message);
    }
  } else {
    try { await clearExtraction(workspaceId, tableId); } catch { /* ignore */ }
  }

  const rawTable = await getTable(tableId);
  const tableObj = unwrapTable(rawTable);
  const viewId = pickViewId(tableObj, viewHint);
  if (!viewId) throw new Error('analyze: no view ID could be resolved for table');

  const columnMeta = buildColumnMeta(tableObj);
  const metaById = new Map(columnMeta.map((m) => [m.field_id, m]));
  const fieldIds = columnMeta.map((m) => m.field_id);

  if (fieldIds.length === 0) {
    console.log(LOG, 'analyze: no cost-bearing columns on table');
    const empty = aggregate([], columnMeta);
    const extraction = {
      tableId,
      viewId,
      workspaceId,
      tableName: tableObj.name || null,
      columnMeta,
      analyzedAt: Date.now(),
      ...empty,
    };
    await cacheExtraction(workspaceId, tableId, extraction);
    return { ok: true, extraction, cached: false };
  }

  const recordIds = await getRecordIds(tableId, viewId);
  const total = recordIds.length;
  console.log(LOG, `analyze: ${total} records × ${fieldIds.length} cost columns (per-record GET, ${FETCH_WORKERS} workers)`);

  if (total === 0) {
    const empty = aggregate([], columnMeta);
    const extraction = {
      tableId,
      viewId,
      workspaceId,
      tableName: tableObj.name || null,
      columnMeta,
      analyzedAt: Date.now(),
      ...empty,
    };
    await cacheExtraction(workspaceId, tableId, extraction);
    return { ok: true, extraction, cached: false };
  }

  const allCells = [];

  // Per-record fan-out. fetchRecordsParallel calls onProgress periodically
  // (every ~5% or every 25 records, whichever is sooner) with a *delta* batch
  // of newly-fetched records: we extract them, append to allCells, then
  // recompute partial aggregates and broadcast.
  await fetchRecordsParallel(tableId, recordIds, fieldIds, {
    workers: FETCH_WORKERS,
    onProgress: ({ completed, total: t, partialRecords }) => {
      if (partialRecords && partialRecords.length) {
        const cells = extractPage(partialRecords, metaById);
        allCells.push(...cells);
      }
      let partial = null;
      try {
        partial = aggregate(allCells, columnMeta);
      } catch (err) {
        console.log(LOG, 'partial aggregate failed:', err.message);
      }
      broadcast({
        type: 'analyzeProgress',
        tableId,
        completed,
        total: t,
        partialAggregates: partial ? {
          totals: partial.totals,
          byColumn: partial.byColumn,
        } : null,
      });
    },
  });

  const aggregated = aggregate(allCells, columnMeta);
  const extraction = {
    tableId,
    viewId,
    workspaceId,
    tableName: tableObj.name || null,
    columnMeta,
    cellCount: allCells.length,
    recordCount: total,
    analyzedAt: Date.now(),
    ...aggregated,
  };

  try {
    await cacheExtraction(workspaceId, tableId, extraction);
  } catch (err) {
    console.log(LOG, 'cacheExtraction failed:', err.message);
  }

  // Same byRow-size fix as the cache-hit path above; full extraction (with
  // byRow) is now safely in IndexedDB via cacheExtraction; the wire response
  // only needs to trigger the iframe's render.
  const { byRow, ...trimmed } = extraction;
  return { ok: true, extraction: trimmed, cached: false };
}

// ---------------------------------------------------------------------------
// In-flight dedup + service-worker keep-alive
//
// A big table's analyze can run 5-30s. A double-click, or Chrome re-firing
// chrome.tabs.onActivated on tab refocus, used to start a second parallel
// fetch against the same table; both wrote IndexedDB at the end, second
// wins, and the UI could briefly show a half-finished result.
//
// MV3 service workers also terminate after ~30s of inactivity. A big enough
// table (50k+ rows) can outlive that window mid-fetch; the response promise
// silently drops and the iframe hangs forever with no error. A chrome.alarms
// heartbeat during the run keeps the worker alive until doAnalyze settles.
// ---------------------------------------------------------------------------

const inFlightAnalyze = new Map();
const HEARTBEAT_ALARM = 'claylens-analyze-heartbeat';

async function handleAnalyze(message) {
  const key = `${message.workspaceId}:${message.tableId}`;
  if (inFlightAnalyze.has(key)) {
    console.log(LOG, 'analyze: already in flight for', key, '(joining existing run)');
    return inFlightAnalyze.get(key);
  }

  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 0.4 }); // ~24s, under the 30s MV3 idle timeout
  const p = doAnalyze(message).finally(() => {
    inFlightAnalyze.delete(key);
    if (inFlightAnalyze.size === 0) chrome.alarms.clear(HEARTBEAT_ALARM);
  });
  inFlightAnalyze.set(key, p);
  return p;
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === HEARTBEAT_ALARM) {
    console.log(LOG, 'heartbeat: keeping service worker alive during analyze');
  }
});

const ACTION_HANDLERS = {
  ping: async () => ({ ok: true, pong: true }),

  analyze: handleAnalyze,
};

// ---------------------------------------------------------------------------
// Message router
//
// All side-panel ↔ background traffic goes through this listener.
// Handlers that perform async work MUST `return true` from the listener to
// keep the message channel open until sendResponse is called.
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Content-script context updates are typed (`message.type`), not actioned.
  if (message?.type === 'tableContext') {
    const tabId = sender?.tab?.id;
    stashTableContext(tabId, message);
    // No response needed, but acknowledge to avoid lastError warnings.
    sendResponse({ ok: true });
    return false;
  }

  const action = message?.action;
  if (!action) {
    sendResponse({ ok: false, error: 'Missing action' });
    return false;
  }

  const handler = ACTION_HANDLERS[action];
  if (!handler) {
    sendResponse({ ok: false, error: `Unknown action: ${action}` });
    return false;
  }

  // Run handler async and return true so the channel stays open.
  Promise.resolve()
    .then(() => handler(message, sender))
    .then((result) => {
      console.log(LOG, 'action', action, '→', result?.ok ? 'ok' : 'fail');
      sendResponse(result);
    })
    .catch((err) => {
      console.log(LOG, 'action', action, 'threw:', err);
      const code = err?.code || null;
      if (code === 'SESSION_EXPIRED') {
        // Surface to the side panel so it can show a re-login toast.
        broadcast({ type: 'sessionExpired', message: err.message });
      }
      sendResponse({ ok: false, error: err?.message || String(err), code });
    });

  return true;
});

console.log(LOG, 'service worker booted');
