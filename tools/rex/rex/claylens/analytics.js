/**
 * ClayLens: full-page analytics dashboard (v0.2)
 *
 * Replaces the side-panel UI with a single, wider, multi-panel dashboard
 * opened as a normal Chrome tab via `chrome.action.onClicked` →
 * `chrome.tabs.create({ url: chrome.runtime.getURL('analytics.html') })`.
 *
 * The page reads its table context from URL query params (passed in by the
 * background worker when opening the tab) and falls back to
 * `chrome.storage.session.tableContext:srcTabId` if those are missing; same
 * shape `content.js` writes.
 *
 * Background actions consumed:
 *   - analyze        { force: bool, tableId, viewId, workspaceId }
 *                    → { ok, extraction? , cached? , error? }
 *
 * Events received:
 *   - { type: 'analyzeProgress', completed, total, partialAggregates? }
 *   - { type: 'sessionExpired' }
 *
 * Chart.js v4.4 is loaded as a UMD global (window.Chart) in analytics.html.
 *
 * All Clay-derived strings (column names, record IDs, model names, error
 * messages) MUST go through escapeHtml() before being interpolated into the
 * DOM. Search the file for `escapeHtml(` to confirm.
 */

const LOG = '[claylens:analytics]';

// ─── State ──────────────────────────────────────────────────────────────────
const state = {
  ctx: null,            // { tableId, viewId, workspaceId, sourceUrl } or null
  extraction: null,     // aggregator output enriched with { tableId, tableName, ... }
  lastAnalyzedAt: null, // ms epoch
  doughnut: null,       // Chart.js instance
  bar: null,            // Chart.js instance
  sort: { by: 'total_cost_usd', dir: 'desc' },
  filters: {
    model: '',
    status: '',
    search: '',
    rowSearch: '',
  },
  expandedRows: new Set(),  // record_ids of expanded rows
  busy: false,
  sourceUrl: '',        // best-effort link back to the Clay table
};

// ─── Boot ───────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  console.log(LOG, 'analytics page ready');
  wireRefresh();
  wireEmptyAnalyze();
  wireRetry();
  wireFilters();
  wireRowSearch();
  wireSortHeaders();
  wireExportCsv();
  wireRuntimeMessages();

  await resolveContext();
  if (state.ctx?.tableId && state.ctx?.workspaceId) {
    // Auto-trigger on load. Use cache-first so the page is instant on revisit.
    requestAnalyze({ force: false });
  } else {
    paintNoContextDebug();
    showState('no-context');
  }
});

// When we land on the no-context state, surface the actual params we received
// vs the params we needed. This converts the silent "Analyze does nothing" bug
// into an obvious diagnostic the moment the user opens DevTools or reads the
// hero copy.
function paintNoContextDebug() {
  const params = new URLSearchParams(window.location.search);
  const got = {
    tableId: params.get('tableId') || '',
    viewId: params.get('viewId') || '',
    workspaceId: params.get('workspaceId') || '',
    sourceUrl: params.get('sourceUrl') || '',
  };
  console.warn(LOG, 'no table context. URL params received:', got);
  const sub = document.querySelector('#state-no-context .empty-hero-sub');
  if (!sub) return;
  sub.innerHTML = `
    Couldn't read the table context from the page URL.<br>
    Expected: <code>?tableId=t_xxx&amp;workspaceId=N</code><br>
    Got: <code>tableId=${escapeHtml(got.tableId) || '(empty)'}</code>
    · <code>workspaceId=${escapeHtml(got.workspaceId) || '(empty)'}</code><br>
    Open <code>app.clay.com</code> on a table page (URL must match
    <code>/workspaces/N/.../tables/t_xxx/</code>) and click the ClayLens icon
    again.
  `;
}

// ─── Context resolution ─────────────────────────────────────────────────────

function parseClayUrl(url) {
  if (!url || typeof url !== 'string') return null;
  const t = url.match(/tables\/(t_[a-zA-Z0-9]+)/);
  if (!t) return null;
  const v = url.match(/views\/(gv_[a-zA-Z0-9]+)/);
  const w = url.match(/workspaces\/(\d+)/);
  return { tableId: t[1], viewId: v?.[1] || null, workspaceId: w?.[1] || null };
}

async function resolveContext() {
  const params = new URLSearchParams(window.location.search);
  const srcTabId = params.get('srcTabId');
  let ctx = {
    tableId: params.get('tableId') || '',
    viewId: params.get('viewId') || '',
    workspaceId: params.get('workspaceId') || '',
    sourceUrl: params.get('sourceUrl') || '',
  };

  // Fallback: if any required field is missing but the source tab is still
  // open, read the freshest context from session storage (content.js stashes
  // it on URL change).
  if ((!ctx.tableId || !ctx.workspaceId) && srcTabId) {
    try {
      const key = `tableContext:${srcTabId}`;
      const stored = await chrome.storage.session.get(key);
      const fresh = stored?.[key];
      if (fresh) {
        ctx = {
          tableId: ctx.tableId || fresh.tableId || '',
          viewId: ctx.viewId || fresh.viewId || '',
          workspaceId: ctx.workspaceId || fresh.workspaceId || '',
          sourceUrl: ctx.sourceUrl || fresh.url || '',
        };
      }
    } catch (err) {
      console.log(LOG, 'session context read failed:', err?.message);
    }
  }

  // Last-ditch: try parsing whatever sourceUrl we got.
  if ((!ctx.tableId || !ctx.workspaceId) && ctx.sourceUrl) {
    const parsed = parseClayUrl(ctx.sourceUrl);
    if (parsed) {
      ctx = {
        tableId: ctx.tableId || parsed.tableId,
        viewId: ctx.viewId || parsed.viewId || '',
        workspaceId: ctx.workspaceId || parsed.workspaceId || '',
        sourceUrl: ctx.sourceUrl,
      };
    }
  }

  state.sourceUrl = ctx.sourceUrl || '';

  if (!ctx.tableId || !ctx.workspaceId) {
    state.ctx = null;
    paintContextHeader(null);
    return;
  }

  state.ctx = {
    tableId: ctx.tableId,
    viewId: ctx.viewId || null,
    workspaceId: ctx.workspaceId,
  };
  paintContextHeader({ ...state.ctx, sourceUrl: state.sourceUrl });
}

function paintContextHeader(ctx) {
  const titleEl = document.getElementById('ctx-title');
  const metaEl = document.getElementById('ctx-meta');
  if (!ctx) {
    titleEl.textContent = 'No table connected';
    metaEl.textContent = 'Open ClayLens from a Clay table tab.';
    return;
  }
  const tableName =
    state.extraction?.tableName?.trim() || 'Untitled table';
  titleEl.textContent = tableName;
  const parts = [];
  parts.push(`<span class="ctx-mono">${escapeHtml(ctx.tableId)}</span>`);
  if (ctx.workspaceId) {
    parts.push(`workspace <span class="ctx-mono">${escapeHtml(ctx.workspaceId)}</span>`);
  }
  if (ctx.viewId) {
    parts.push(`view <span class="ctx-mono">${escapeHtml(ctx.viewId)}</span>`);
  }
  metaEl.innerHTML = parts.join(' <span class="ctx-sep">·</span> ');
}

// ─── State machine (which top-level section is visible) ─────────────────────

function showState(stateName) {
  const map = {
    'no-context': 'state-no-context',
    'empty': 'state-empty',
    'loading': 'state-loading',
    'error': 'state-error',
    'dashboard': 'dashboard',
  };
  for (const [k, id] of Object.entries(map)) {
    document.getElementById(id).hidden = (k !== stateName);
  }
}

function showError(message) {
  document.getElementById('state-error-msg').textContent = message;
  showState('error');
}

// ─── Wire UI ────────────────────────────────────────────────────────────────

function wireRefresh() {
  document.getElementById('btn-refresh').addEventListener('click', () => {
    if (!state.ctx) {
      showToast('No table connected.', { variant: 'warn' });
      return;
    }
    requestAnalyze({ force: true });
  });
}

function wireEmptyAnalyze() {
  document.getElementById('btn-empty-analyze').addEventListener('click', () => {
    requestAnalyze({ force: true });
  });
}

function wireRetry() {
  document.getElementById('btn-error-retry').addEventListener('click', () => {
    requestAnalyze({ force: true });
  });
}

function wireFilters() {
  const modelSel = document.getElementById('filter-model');
  const statusSel = document.getElementById('filter-status');
  const search = document.getElementById('filter-search');

  modelSel.addEventListener('change', () => {
    state.filters.model = modelSel.value;
    if (state.extraction) renderColumnsTable(state.extraction.byColumn || []);
  });
  statusSel.addEventListener('change', () => {
    state.filters.status = statusSel.value;
    if (state.extraction) renderColumnsTable(state.extraction.byColumn || []);
  });
  search.addEventListener('input', () => {
    state.filters.search = search.value.trim().toLowerCase();
    if (state.extraction) renderColumnsTable(state.extraction.byColumn || []);
  });
}

function wireRowSearch() {
  const el = document.getElementById('rows-search');
  el.addEventListener('input', () => {
    state.filters.rowSearch = el.value.trim().toLowerCase();
    if (state.extraction) renderTopRows(state.extraction.topRows || []);
  });
}

function wireSortHeaders() {
  document.querySelectorAll('#columns-table thead th').forEach((th) => {
    th.addEventListener('click', () => {
      const by = th.dataset.sort;
      if (!by) return;
      if (state.sort.by === by) {
        state.sort.dir = state.sort.dir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sort.by = by;
        state.sort.dir = 'desc';
      }
      if (state.extraction) renderColumnsTable(state.extraction.byColumn || []);
    });
  });
}

function wireExportCsv() {
  document.getElementById('btn-export-csv').addEventListener('click', exportColumnsCsv);
}

function wireRuntimeMessages() {
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'analyzeProgress') {
      handleProgress(msg);
      sendResponse({ ok: true });
      return false;
    }
    if (msg?.type === 'sessionExpired') {
      showSessionExpiredModal();
      sendResponse({ ok: true });
      return false;
    }
    return false;
  });
}

// ─── Analyze flow ───────────────────────────────────────────────────────────

async function requestAnalyze({ force = false } = {}) {
  if (!state.ctx?.tableId || !state.ctx?.workspaceId) {
    showState('no-context');
    return;
  }
  if (state.busy) return;
  state.busy = true;

  // First-load behaviour: if we don't yet have an extraction, show the
  // loading hero. On re-analyze, keep the existing dashboard up but light
  // up the progress strip.
  if (!state.extraction) {
    showState('loading');
  }
  showProgress(0, 'Starting…', '');

  try {
    const res = await sendBackground({
      action: 'analyze',
      force,
      tableId: state.ctx.tableId,
      viewId: state.ctx.viewId,
      workspaceId: state.ctx.workspaceId,
    });

    hideProgress();

    if (!res?.ok) {
      const msg = res?.error || 'Analyze failed.';
      if (state.extraction) {
        showToast(msg, {
          variant: 'error',
          actionLabel: 'Retry',
          onAction: () => requestAnalyze({ force: true }),
        });
      } else {
        showError(msg);
      }
      return;
    }

    state.extraction = res.extraction || null;
    state.lastAnalyzedAt =
      state.extraction?.analyzedAt || res.analyzedAt || Date.now();

    if (!state.extraction) {
      showState('empty');
      return;
    }

    // Re-paint the title now that we have tableName.
    paintContextHeader({ ...state.ctx, sourceUrl: state.sourceUrl });

    const totalRuns = state.extraction?.totals?.total_runs || 0;
    const totalCells = state.extraction?.cellCount || 0;
    if (totalRuns === 0 && totalCells === 0) {
      // Connected but nothing to show yet.
      showState('empty');
      return;
    }

    showState('dashboard');
    renderDashboard(state.extraction);
  } catch (err) {
    console.log(LOG, 'analyze threw', err);
    hideProgress();
    if (state.extraction) {
      showToast(err?.message || String(err), { variant: 'error' });
    } else {
      showError(err?.message || String(err));
    }
  } finally {
    state.busy = false;
  }
}

function handleProgress(msg) {
  const completed = msg.completed ?? msg.processed ?? 0;
  const total = msg.total ?? 0;
  const stage = msg.stage ?? 'Analyzing';
  const partial = msg.partialAggregates?.totals ?? msg.partialTotals ?? null;
  const pct = total > 0 ? Math.round((completed / total) * 100) : 0;
  const stageStr = `${stage} ${completed.toLocaleString()}/${
    total ? total.toLocaleString() : '?'
  } records`;
  const partialStr = partial
    ? `Live: ${formatUsd(partial.total_cost_usd || 0)} · ${formatNumber(
        partial.total_runs || 0,
      )} runs`
    : '';
  showProgress(pct, stageStr, partialStr);
}

function showProgress(pct, stage, partial) {
  const bar = document.getElementById('progress-bar');
  bar.hidden = false;
  document.getElementById('progress-fill').style.width = `${pct}%`;
  document.getElementById('progress-pct').textContent = `${pct}%`;
  document.getElementById('progress-stage').textContent = stage || '';
  document.getElementById('progress-partial').textContent = partial || '';
}

function hideProgress() {
  document.getElementById('progress-bar').hidden = true;
}

// ─── Render: dashboard top-level ────────────────────────────────────────────

function renderDashboard(extraction) {
  if (!extraction) return;
  renderKpis(extraction.totals || {}, extraction);
  populateModelFilter(extraction.byColumn || []);
  renderDoughnut(extraction.byColumn || []);
  renderBarChart(extraction.byColumn || []);
  renderColumnsTable(extraction.byColumn || []);
  renderTopRows(extraction.topRows || []);
  renderFooterMeta(extraction);
  renderLastAnalyzed();
}

// ─── KPI cards ──────────────────────────────────────────────────────────────

function renderKpis(totals, extraction) {
  const cost = totals.total_cost_usd || 0;
  const refunded = totals.refunded_cost_usd || totals.total_refunded || 0;
  const net = totals.net_cost_usd != null ? totals.net_cost_usd : cost - refunded;

  setText('kpi-cost', formatUsd(cost));
  if (refunded > 0) {
    document.getElementById('kpi-cost-sub').innerHTML =
      `Net <strong>${escapeHtml(formatUsd(net))}</strong> after ${escapeHtml(formatUsd(refunded))} refunded`;
  } else {
    setText('kpi-cost-sub', 'Gross spend across all action cells');
  }

  setText('kpi-credits', formatNumber(Math.round(totals.total_credits || 0)));
  const refundedCredits = totals.refunded_credits || 0;
  if (refundedCredits > 0) {
    setText(
      'kpi-credits-sub',
      `${formatNumber(Math.round(refundedCredits))} refunded credits`,
    );
  } else {
    setText('kpi-credits-sub', 'Across all action cells');
  }

  const totalRows = extraction?.recordCount ?? totals.unique_rows ?? 0;
  const successRows = totals.success_rows || 0;
  const successRate = (totals.success_rate ?? 0) * 100;
  setText('kpi-rows', formatNumber(totalRows));
  setText(
    'kpi-rows-sub',
    `${formatNumber(successRows)} with successes · ${successRate.toFixed(1)}% cell success`,
  );

  const cps = totals.cost_per_success_row;
  setText('kpi-cps', cps != null ? formatUsd(cps, 4) : '-');
  const errCount = totals.total_errors || 0;
  const uncosted = totals.uncosted_cells || 0;
  const subParts = [];
  if (errCount > 0) subParts.push(`<span class="warn">${formatNumber(errCount)} errors</span>`);
  if (uncosted > 0) subParts.push(`<span class="warn">${formatNumber(uncosted)} uncosted</span>`);
  if (subParts.length === 0) subParts.push('Net of refunds');
  document.getElementById('kpi-cps-sub').innerHTML = subParts.join(' · ');
}

// ─── Filters ────────────────────────────────────────────────────────────────

function populateModelFilter(byColumn) {
  const sel = document.getElementById('filter-model');
  const current = sel.value;
  const models = new Set();
  for (const c of byColumn) {
    if (c.model) models.add(c.model);
  }
  // Preserve "All models" option, replace rest.
  const sorted = [...models].sort();
  sel.innerHTML = '<option value="">All models</option>' +
    sorted.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join('');
  // Restore prior selection if still valid.
  if (current && sorted.includes(current)) {
    sel.value = current;
  } else if (current && current !== '') {
    state.filters.model = '';
  }
}

function applyColumnFilters(rows) {
  const { model, status, search } = state.filters;
  let out = rows;
  if (model) out = out.filter((r) => r.model === model);
  if (status === 'errors') out = out.filter((r) => (r.errors || 0) > 0);
  if (status === 'uncosted') out = out.filter((r) => (r.uncosted || 0) > 0);
  if (search) {
    out = out.filter((r) =>
      String(r.field_name || '').toLowerCase().includes(search) ||
      String(r.model || '').toLowerCase().includes(search) ||
      String(r.action_key || '').toLowerCase().includes(search),
    );
  }
  return out;
}

// ─── Doughnut (cost share by column) ────────────────────────────────────────

const PALETTE = [
  '#7c5fff', '#9277ff', '#5fc4ff', '#3fb950', '#d29922',
  '#f85149', '#bc8cff', '#56d4dd', '#a371f7', '#ff8e72',
];

function renderDoughnut(byColumn) {
  const canvas = document.getElementById('chart-doughnut');
  if (!canvas || typeof Chart === 'undefined') return;

  const sorted = [...byColumn].sort(
    (a, b) => (b.total_cost_usd || 0) - (a.total_cost_usd || 0),
  );
  const top = sorted.slice(0, 8);
  const rest = sorted.slice(8);
  const labels = top.map((c) => c.field_name || c.field_id || '-');
  const data = top.map((c) => c.total_cost_usd || 0);
  if (rest.length > 0) {
    labels.push(`Other (${rest.length})`);
    data.push(rest.reduce((s, c) => s + (c.total_cost_usd || 0), 0));
  }
  const total = data.reduce((s, v) => s + v, 0) || 1;
  const colors = labels.map((_, i) => PALETTE[i % PALETTE.length]);

  if (state.doughnut) state.doughnut.destroy();
  state.doughnut = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors,
        borderColor: '#1e1e2e',
        borderWidth: 2,
        hoverBorderColor: '#7c5fff',
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '58%',
      plugins: {
        legend: {
          position: 'right',
          align: 'center',
          labels: {
            color: '#cccccc',
            font: { size: 11 },
            boxWidth: 12,
            padding: 10,
          },
        },
        tooltip: {
          backgroundColor: '#1e1e2e',
          borderColor: '#3a3a4e',
          borderWidth: 1,
          titleColor: '#fff',
          bodyColor: '#cccccc',
          padding: 10,
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed || 0;
              const pct = ((v / total) * 100).toFixed(1);
              return `${formatUsd(v)} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

// ─── Horizontal bar chart (top 10 columns) ──────────────────────────────────

function renderBarChart(byColumn) {
  const canvas = document.getElementById('chart-bar');
  if (!canvas || typeof Chart === 'undefined') return;

  const sorted = [...byColumn].sort(
    (a, b) => (b.total_cost_usd || 0) - (a.total_cost_usd || 0),
  );
  const top = sorted.slice(0, 10);
  const labels = top.map((c) => c.field_name || c.field_id || '-');
  const successCost = top.map((c) => Math.max(0, (c.total_cost_usd || 0)));
  // For now we don't have a clean errored-cost series broken out per column;
  // we visualize successful cost (the dollar value) and overlay error count
  // via tooltip. Stacking refunded would require aggregator changes.
  const colors = labels.map((_, i) => PALETTE[i % PALETTE.length]);

  if (state.bar) state.bar.destroy();
  state.bar = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Cost (USD)',
        data: successCost,
        backgroundColor: colors,
        borderColor: colors,
        borderWidth: 0,
        borderRadius: 4,
        barThickness: 16,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e1e2e',
          borderColor: '#3a3a4e',
          borderWidth: 1,
          titleColor: '#fff',
          bodyColor: '#cccccc',
          padding: 10,
          callbacks: {
            label: (ctx) => {
              const c = top[ctx.dataIndex];
              const lines = [`Cost: ${formatUsd(c.total_cost_usd || 0)}`];
              lines.push(`Runs: ${formatNumber(c.runs || 0)}`);
              if ((c.errors || 0) > 0) lines.push(`Errors: ${formatNumber(c.errors)}`);
              if (c.cost_per_run != null) {
                lines.push(`$/run: ${formatUsd(c.cost_per_run, 5)}`);
              }
              return lines;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: '#888',
            callback: (v) => formatUsd(v, 2),
          },
          grid: { color: '#3a3a4e' },
        },
        y: {
          ticks: {
            color: '#cccccc',
            font: { size: 11 },
            callback: function (val) {
              const lbl = this.getLabelForValue(val);
              return lbl.length > 28 ? lbl.slice(0, 27) + '…' : lbl;
            },
          },
          grid: { color: 'transparent' },
        },
      },
    },
  });
}

// ─── Columns table ──────────────────────────────────────────────────────────

function renderColumnsTable(byColumn) {
  const tbody = document.getElementById('columns-tbody');
  const emptyEl = document.getElementById('columns-empty');
  tbody.innerHTML = '';
  const { by, dir } = state.sort;

  // Header sort indicators.
  document.querySelectorAll('#columns-table thead th').forEach((th) => {
    th.classList.remove('sort-asc', 'sort-desc');
    const ind = th.querySelector('.sort-indicator');
    if (ind) ind.textContent = '';
    if (th.dataset.sort === by) {
      th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
      if (ind) ind.textContent = dir === 'asc' ? '▲' : '▼';
    }
  });

  const enriched = byColumn.map((c) => ({
    ...c,
    success_pct: c.runs > 0 ? (c.successes || 0) / c.runs : 0,
    cost_per_run:
      c.cost_per_run != null
        ? c.cost_per_run
        : c.runs > 0
        ? (c.total_cost_usd || 0) / c.runs
        : 0,
  }));

  const filtered = applyColumnFilters(enriched);

  filtered.sort((a, b) => {
    const av = a[by];
    const bv = b[by];
    if (typeof av === 'string' || typeof bv === 'string') {
      const cmp = String(av || '').localeCompare(String(bv || ''));
      return dir === 'asc' ? cmp : -cmp;
    }
    const an = av == null ? -Infinity : av;
    const bn = bv == null ? -Infinity : bv;
    const cmp = an - bn;
    return dir === 'asc' ? cmp : -cmp;
  });

  if (filtered.length === 0) {
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;

  for (const r of filtered) {
    const tr = document.createElement('tr');
    tr.className = 'row-main';
    tr.dataset.id = r.field_id || '';

    const successPct = (r.success_pct * 100).toFixed(1);
    const successClass = r.success_pct >= 0.95 ? 'ok'
      : r.success_pct >= 0.8 ? 'warn'
      : 'fail';

    tr.innerHTML = `
      <td class="cell-name">
        <span class="chev">▶</span>
        <span class="col-name">${escapeHtml(r.field_name || '-')}</span>
      </td>
      <td><span class="model-pill">${escapeHtml(r.model || '-')}</span></td>
      <td class="numeric">${formatNumber(r.runs || 0)}</td>
      <td class="numeric"><span class="success-${successClass}">${successPct}%</span></td>
      <td class="numeric">${(r.errors || 0) > 0 ? `<span class="text-fail">${formatNumber(r.errors)}</span>` : '<span class="muted">0</span>'}</td>
      <td class="numeric"><strong>${formatUsd(r.total_cost_usd || 0)}</strong></td>
      <td class="numeric">${formatUsd(r.cost_per_run || 0, 5)}</td>
      <td class="numeric">${r.p50_cost != null ? formatUsd(r.p50_cost, 5) : '<span class="muted">-</span>'}</td>
      <td class="numeric">${r.p95_cost != null ? formatUsd(r.p95_cost, 5) : '<span class="muted">-</span>'}</td>
      <td class="numeric">
        <div class="share-bar-wrap" title="${(r.share_pct || 0).toFixed(1)}% of total">
          <div class="share-bar" style="width:${Math.min(100, r.share_pct || 0).toFixed(1)}%"></div>
          <span class="share-label">${(r.share_pct || 0).toFixed(1)}%</span>
        </div>
      </td>
    `;
    tbody.appendChild(tr);

    const detail = document.createElement('tr');
    detail.className = 'row-detail';
    detail.hidden = true;
    const badges = [];
    if (r.useCase) badges.push(`<span class="badge">${escapeHtml(r.useCase)}</span>`);
    if (r.riskClass) {
      badges.push(`<span class="badge badge-${escapeHtml(r.riskClass.toLowerCase())}">${escapeHtml(r.riskClass)}</span>`);
    }
    if (r.action_key) {
      badges.push(`<span class="badge">action: ${escapeHtml(r.action_key)}</span>`);
    }
    if ((r.uncosted || 0) > 0) {
      badges.push(`<span class="badge badge-warn">${formatNumber(r.uncosted)} uncosted</span>`);
    }
    if ((r.skipped || 0) > 0) {
      badges.push(`<span class="badge">${formatNumber(r.skipped)} skipped</span>`);
    }

    detail.innerHTML = `
      <td colspan="10" class="row-detail-inner">
        <div class="rd-grid">
          <div class="rd-block">
            <div class="rd-label">Field ID</div>
            <code class="rd-value">${escapeHtml(r.field_id || '-')}</code>
          </div>
          <div class="rd-block">
            <div class="rd-label">Successes</div>
            <div class="rd-value">${formatNumber(r.successes || 0)} / ${formatNumber(r.runs || 0)}</div>
          </div>
          <div class="rd-block">
            <div class="rd-label">Total credits</div>
            <div class="rd-value">${formatNumber(Math.round(r.total_credits || 0))}</div>
          </div>
          <div class="rd-block">
            <div class="rd-label">Share of spend</div>
            <div class="rd-value">${(r.share_pct || 0).toFixed(2)}%</div>
          </div>
        </div>
        ${badges.length ? `<div class="rd-badges">${badges.join('')}</div>` : ''}
      </td>
    `;
    tbody.appendChild(detail);

    tr.addEventListener('click', () => {
      const open = !detail.hidden;
      detail.hidden = open;
      tr.classList.toggle('expanded', !open);
    });
  }
}

// ─── Top rows ───────────────────────────────────────────────────────────────

function renderTopRows(topRows) {
  const list = document.getElementById('rows-list');
  const count = document.getElementById('top-rows-count');
  const emptyEl = document.getElementById('rows-empty');
  list.innerHTML = '';

  const filter = state.filters.rowSearch;
  const filtered = filter
    ? topRows.filter((r) => String(r.record_id || '').toLowerCase().includes(filter))
    : topRows;

  count.textContent = `${formatNumber(filtered.length)} rows shown · top ${formatNumber(topRows.length)} by cost`;

  if (filtered.length === 0) {
    emptyEl.hidden = false;
    return;
  }
  emptyEl.hidden = true;

  // Pre-compute models per row (for the inline summary line).
  filtered.forEach((row, idx) => {
    const wrap = document.createElement('div');
    wrap.className = 'row-card';
    wrap.dataset.recordId = row.record_id || '';

    const ranCells = (row.cells || []).filter((c) => c.ran);
    const modelCounts = new Map();
    for (const c of ranCells) {
      const m = c.actual_model || c.model || (state.extraction?.columnMeta?.find((mm) => mm.field_id === c.field_id)?.model_configured) || null;
      if (m) modelCounts.set(m, (modelCounts.get(m) || 0) + 1);
    }
    const modelStr = [...modelCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([m, n]) => `${escapeHtml(shortModel(m))}×${n}`)
      .join(' ');
    const totalCells = (row.cells || []).length;
    const ranCount = ranCells.length;

    const isExpanded = state.expandedRows.has(row.record_id);

    wrap.innerHTML = `
      <div class="row-card-head">
        <span class="row-rank">${idx + 1}</span>
        <code class="row-id">${escapeHtml(row.record_id || '-')}</code>
        <span class="row-cells">${ranCount}/${totalCells} cells</span>
        <span class="row-models">${modelStr || '<span class="muted">no model data</span>'}</span>
        <span class="row-cost">${formatUsd(row.total_cost_usd || 0)}</span>
        <span class="row-chev ${isExpanded ? 'open' : ''}">▶</span>
      </div>
      <div class="row-card-body" ${isExpanded ? '' : 'hidden'}></div>
    `;

    const head = wrap.querySelector('.row-card-head');
    const body = wrap.querySelector('.row-card-body');
    const chev = wrap.querySelector('.row-chev');

    const renderBody = () => {
      const cells = (row.cells || []).slice().sort(
        (a, b) => (b.total_cost_usd || 0) - (a.total_cost_usd || 0),
      );
      if (!cells.length) {
        body.innerHTML = '<div class="muted" style="padding:12px 16px;">No cell data.</div>';
        return;
      }
      body.innerHTML = `
        <table class="data data-cells">
          <thead>
            <tr>
              <th>Field</th>
              <th>Status</th>
              <th>Model</th>
              <th class="numeric">Cost</th>
              <th class="numeric">Credits</th>
            </tr>
          </thead>
          <tbody>
            ${cells.map((c) => {
              const model = c.actual_model || c.model || (state.extraction?.columnMeta?.find((mm) => mm.field_id === c.field_id)?.model_configured) || null;
              const statusClass = c.is_refunded ? 'warn'
                : c.uncosted ? 'warn'
                : c.ran ? 'ok'
                : c.skipped ? 'muted'
                : c.status ? 'fail'
                : 'muted';
              const statusLabel = c.is_refunded ? 'REFUNDED'
                : c.uncosted ? 'UNCOSTED'
                : c.ran ? 'OK'
                : c.skipped ? 'SKIPPED'
                : c.status || 'NO DATA';
              return `
                <tr>
                  <td>${escapeHtml(c.field_name || c.field_id || '-')}</td>
                  <td><span class="status-pill status-${statusClass}">${escapeHtml(statusLabel)}</span></td>
                  <td>${model ? escapeHtml(shortModel(model)) : '<span class="muted">-</span>'}</td>
                  <td class="numeric">${c.ran ? formatUsd(c.total_cost_usd || 0, 5) : '<span class="muted">-</span>'}</td>
                  <td class="numeric">${(c.credits || 0) > 0 ? formatNumber(c.credits) : '<span class="muted">-</span>'}</td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `;
    };

    if (isExpanded) renderBody();

    head.addEventListener('click', () => {
      const willOpen = body.hidden;
      if (willOpen) {
        renderBody();
        body.hidden = false;
        chev.classList.add('open');
        state.expandedRows.add(row.record_id);
      } else {
        body.hidden = true;
        chev.classList.remove('open');
        state.expandedRows.delete(row.record_id);
      }
    });

    list.appendChild(wrap);
  });
}

function shortModel(m) {
  if (!m) return '';
  // Strip provider prefix and version tail for compactness; show enough to disambiguate.
  return String(m)
    .replace(/^anthropic\//, '')
    .replace(/^openai\//, '')
    .replace(/^google\//, '');
}

// ─── Footer / timestamp ─────────────────────────────────────────────────────

function renderFooterMeta(extraction) {
  const el = document.getElementById('footer-meta');
  const parts = [];
  if (extraction.cellCount != null) parts.push(`${formatNumber(extraction.cellCount)} cells scored`);
  if (extraction.recordCount != null) parts.push(`${formatNumber(extraction.recordCount)} records`);
  if (extraction.byColumn) parts.push(`${formatNumber(extraction.byColumn.length)} cost columns`);
  if (state.sourceUrl) {
    parts.push(`<a href="${escapeHtml(state.sourceUrl)}" target="_blank" rel="noopener">Open in Clay ↗</a>`);
  }
  el.innerHTML = parts.join(' <span class="ctx-sep">·</span> ');
}

function renderLastAnalyzed() {
  const wrap = document.getElementById('last-analyzed-wrap');
  if (!state.lastAnalyzedAt) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  const ageMs = Date.now() - state.lastAnalyzedAt;
  const ageMin = Math.floor(ageMs / 60000);
  const label =
    ageMin < 1
      ? 'Analyzed just now'
      : ageMin === 1
      ? 'Analyzed 1m ago'
      : ageMin < 60
      ? `Analyzed ${ageMin}m ago`
      : `Analyzed ${Math.floor(ageMin / 60)}h ago`;
  document.getElementById('last-analyzed').textContent = label;
}

// Refresh "Xm ago" every minute so it doesn't get stale.
setInterval(renderLastAnalyzed, 60_000);

// ─── CSV export ─────────────────────────────────────────────────────────────

function exportColumnsCsv() {
  if (!state.extraction?.byColumn?.length) {
    showToast('Nothing to export. Run Analyze first.', { variant: 'warn' });
    return;
  }
  // We re-implement here (rather than importing toCSV from lib/aggregator)
  // because that helper uses different field names (p50/p95 vs p50_cost/p95_cost).
  const headers = [
    'field_id', 'field_name', 'model', 'action_key',
    'runs', 'successes', 'errors',
    'total_cost_usd', 'total_credits',
    'cost_per_run', 'p50_cost', 'p95_cost', 'share_pct',
  ];
  const escape = (v) => {
    if (v == null) return '';
    const s = typeof v === 'number' ? String(v) : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(',')];
  for (const c of state.extraction.byColumn) {
    lines.push(headers.map((h) => escape(c[h])).join(','));
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `claylens-${state.ctx?.tableId || 'columns'}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ─── Toast / modal ──────────────────────────────────────────────────────────

function showToast(message, { variant = 'info', actionLabel = null, onAction = null, duration = 6000 } = {}) {
  const stack = document.getElementById('toast-stack');
  const t = document.createElement('div');
  t.className = `toast toast-${variant}`;
  t.innerHTML = `
    <span class="toast-msg">${escapeHtml(message)}</span>
    <span class="toast-actions"></span>
  `;
  const actions = t.querySelector('.toast-actions');
  if (actionLabel && typeof onAction === 'function') {
    const b = document.createElement('button');
    b.className = 'btn btn-sm btn-secondary';
    b.textContent = actionLabel;
    b.addEventListener('click', () => {
      onAction();
      t.remove();
    });
    actions.appendChild(b);
  }
  const dismiss = document.createElement('button');
  dismiss.className = 'btn btn-sm btn-secondary';
  dismiss.textContent = '✕';
  dismiss.setAttribute('aria-label', 'Dismiss notification');
  dismiss.addEventListener('click', () => t.remove());
  actions.appendChild(dismiss);
  stack.appendChild(t);
  if (duration > 0) setTimeout(() => t.remove(), duration);
}

function showSessionExpiredModal() {
  const host = document.getElementById('modal-host');
  if (host.querySelector('.modal-backdrop')) return;
  host.innerHTML = `
    <div class="modal-backdrop" role="dialog" aria-modal="true">
      <div class="modal">
        <h3>Clay session expired</h3>
        <p>
          Your Clay session expired. Refresh
          <code>app.clay.com</code> in another tab and try again.
        </p>
        <div class="modal-actions">
          <button class="btn btn-secondary" id="modal-dismiss">Dismiss</button>
        </div>
      </div>
    </div>
  `;
  host.querySelector('#modal-dismiss').addEventListener('click', () => {
    host.innerHTML = '';
  });
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function sendBackground(payload) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(payload, (resp) => {
        if (chrome.runtime.lastError) {
          resolve({
            ok: false,
            error: chrome.runtime.lastError.message || 'no response',
          });
          return;
        }
        resolve(resp || { ok: false, error: 'empty response' });
      });
    } catch (err) {
      resolve({ ok: false, error: err?.message || String(err) });
    }
  });
}

function setText(id, txt) {
  const el = document.getElementById(id);
  if (el) el.textContent = txt;
}

function escapeHtml(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function formatUsd(n, decimals = 2) {
  if (typeof n !== 'number' || !isFinite(n)) return '$0.00';
  if (Math.abs(n) >= 1) return `$${n.toFixed(decimals)}`;
  // Smaller amounts get more precision so $0.0001 doesn't render as "$0.00".
  const d = decimals < 4 ? 4 : decimals;
  return `$${n.toFixed(d)}`;
}

function formatNumber(n) {
  if (typeof n !== 'number' || !isFinite(n)) return '0';
  return n.toLocaleString('en-US');
}
