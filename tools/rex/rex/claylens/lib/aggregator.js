/**
 * lib/aggregator.js: Pure aggregation over extractCostFields() output.
 *
 * No I/O, no async, no side effects beyond logs.
 *
 * Public surface:
 *   aggregate(extractedCells, columnMeta) → { totals, byColumn, byRow, topRows }
 *   toCSV(byColumn) → string
 *
 * Critical rules:
 *   1. effective credits per cell = upfront_credit_total ?? credits
 *      (Clay-reported wins over actionKey lookup)
 *   2. Find People / Find Companies are explicit 0 in provider-costs.js; no
 *      special-case multiplication here.
 *   3. is_refunded === true → cost still counts in gross totals BUT also
 *      tracked separately under refunded_cost_usd / refunded_credits so the
 *      UI can show "$X charged, $Y refunded, $Z net".
 *   4. uncosted cells (extractor.uncosted === true) → counted in
 *      totals.uncosted_cells, never silently zeroed.
 */

import { classify } from './column-classifier.js';
import { CLAY_CREDIT_USD } from './provider-costs.js';

const LOG = '[claylens:aggregator]';

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Effective credit count for a cell.
 *
 * Clay-reported `upfront_credit_total` wins over the static
 * `credits` lookup from provider-costs.js. Either may be null.
 *
 * @param {object} cell - extractCostFields output
 * @returns {number|null}
 */
function effectiveCredits(cell) {
  if (cell == null) return null;
  if (cell.upfront_credit_total != null && Number.isFinite(cell.upfront_credit_total)) {
    return cell.upfront_credit_total;
  }
  if (cell.credits != null && Number.isFinite(cell.credits)) return cell.credits;
  return null;
}

/**
 * Sum that ignores null/undefined/non-finite values.
 */
function sumNumeric(arr) {
  let s = 0;
  for (const v of arr) {
    if (v != null && Number.isFinite(v)) s += v;
  }
  return s;
}

/**
 * Linearly-interpolated percentile, matching numpy default ("linear" method).
 *
 * Returns null on empty input, the single value for n=1. No special case
 * below n=3: the interpolation formula below already produces the correct
 * result for n=2: the old special case returned the larger of 2 samples
 * regardless of whether p50 or p95 was requested (OPEN-ISSUES #4 upstream).
 *
 * @param {number[]} vals - already-numeric, non-null
 * @param {number} p - 0..100
 */
function percentile(vals, p) {
  if (!vals.length) return null;
  if (vals.length === 1) return vals[0];
  const sorted = vals.slice().sort((a, b) => a - b);

  const idx = (p / 100) * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return sorted[lo];
  const frac = idx - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
}

/**
 * Pick the most-common actual_model across cells, fallback to columnMeta
 * configured model. Returns null if neither.
 */
function modeModel(cells, configuredModel) {
  const counts = new Map();
  for (const c of cells) {
    const m = c?.actual_model;
    if (m) counts.set(m, (counts.get(m) || 0) + 1);
  }
  if (counts.size === 0) return configuredModel || null;
  let best = null;
  let bestCount = -1;
  for (const [m, n] of counts) {
    if (n > bestCount) {
      best = m;
      bestCount = n;
    }
  }
  return best;
}

// ── Main aggregate ───────────────────────────────────────────────────────────

/**
 * Aggregate a flat array of extracted cells + column metadata into the
 * three-level summary used by the side panel (totals / byColumn / byRow).
 *
 * @param {Array<object>} extractedCells - each item has { record_id, field_id,
 *   ...extractCostFields output }
 * @param {Array<{field_id, field_name, type, model_configured?, action_key?,
 *   action_use_case?}>} columnMeta
 * @returns {{
 *   totals: object,
 *   byColumn: Array<object>,
 *   byRow: Array<object>,
 *   topRows: Array<object>,
 * }}
 */
export function aggregate(extractedCells, columnMeta) {
  const cells = Array.isArray(extractedCells) ? extractedCells : [];
  const meta = Array.isArray(columnMeta) ? columnMeta : [];

  // field_id → meta lookup
  const metaById = new Map();
  for (const m of meta) {
    if (m && m.field_id) metaById.set(m.field_id, m);
  }

  // Pre-compute effective credits + cost-in-USD per cell once.
  // costUsdAll = LLM dollars + (credit cost × CLAY_CREDIT_USD).
  // Both are real spend the user incurred for this cell.
  const enriched = cells.map((c) => {
    const eff = effectiveCredits(c);
    const llmUsd = (c?.total_cost_usd != null && Number.isFinite(c.total_cost_usd))
      ? c.total_cost_usd : 0;
    const creditUsd = (eff != null) ? eff * CLAY_CREDIT_USD : 0;
    const costUsd = llmUsd + creditUsd;
    return {
      cell: c,
      effCredits: eff,
      costUsd,
      llmUsd,
      creditUsd,
    };
  });

  // ── Totals ────────────────────────────────────────────────────────────────
  let total_cost_usd = 0;
  let total_credits = 0;
  let total_runs = 0;
  let total_successes = 0;
  let total_errors = 0;
  let total_skipped = 0;
  let refunded_cost_usd = 0;
  let refunded_credits = 0;
  let uncosted_cells = 0;
  const uniqueRowIds = new Set();
  const successRowIds = new Set();

  for (const e of enriched) {
    const c = e.cell;
    if (!c) continue;
    if (c.record_id) uniqueRowIds.add(c.record_id);

    if (c.ran) {
      total_runs += 1;
      total_successes += 1;
      if (c.record_id) successRowIds.add(c.record_id);

      // Gross totals always include the cost; refunds are a separate line.
      total_cost_usd += e.costUsd;
      if (e.effCredits != null) total_credits += e.effCredits;

      if (c.is_refunded === true) {
        refunded_cost_usd += e.costUsd;
        if (e.effCredits != null) refunded_credits += e.effCredits;
      }

      if (c.uncosted) uncosted_cells += 1;
    } else if (c.skipped) {
      total_skipped += 1;
    } else if (c.status != null) {
      // any non-null, non-charged, non-skipped status is an error of some kind
      total_runs += 1;
      total_errors += 1;
    }
  }

  const success_rate = total_runs > 0 ? total_successes / total_runs : null;
  const success_rows = successRowIds.size;
  const net_cost_usd = total_cost_usd - refunded_cost_usd;
  const cost_per_success_row = success_rows > 0 ? net_cost_usd / success_rows : null;

  // ── Per-column rollup ────────────────────────────────────────────────────
  const byFieldId = new Map();
  for (const e of enriched) {
    const c = e.cell;
    if (!c || !c.field_id) continue;
    if (!byFieldId.has(c.field_id)) byFieldId.set(c.field_id, []);
    byFieldId.get(c.field_id).push(e);
  }

  const byColumn = [];
  for (const [fieldId, group] of byFieldId) {
    const m = metaById.get(fieldId) || {};
    const fieldName = m.field_name || fieldId;
    const { useCase, riskClass } = classify(fieldName, m.action_use_case);

    let runs = 0, successes = 0, errors = 0, skipped = 0, uncosted = 0;
    let cost_usd = 0;
    let credits = 0;
    const ranCells = [];

    for (const e of group) {
      const c = e.cell;
      if (c.ran) {
        runs += 1;
        successes += 1;
        cost_usd += e.costUsd;
        if (e.effCredits != null) credits += e.effCredits;
        if (c.uncosted) uncosted += 1;
        ranCells.push(e);
      } else if (c.skipped) {
        skipped += 1;
      } else if (c.status != null) {
        runs += 1;
        errors += 1;
      }
    }

    // p50/p95 over ran cells with non-null cost (LLM dollars only; matches
    // the Python audit which percentiles on total_cost_usd).
    const costSamples = ranCells
      .map((e) => e.cell.total_cost_usd)
      .filter((v) => v != null && Number.isFinite(v));
    const p50 = percentile(costSamples, 50);
    const p95 = percentile(costSamples, 95);

    const cost_per_run = runs > 0 ? cost_usd / runs : null;
    const share_pct = total_cost_usd > 0 ? (cost_usd / total_cost_usd) * 100 : 0;
    const model = modeModel(ranCells.map((e) => e.cell), m.model_configured);

    byColumn.push({
      field_id: fieldId,
      field_name: fieldName,
      model,
      action_key: m.action_key || null,
      useCase,
      riskClass,
      runs,
      successes,
      errors,
      skipped,
      total_cost_usd: cost_usd,
      total_credits: credits,
      cost_per_run,
      p50_cost: p50,
      p95_cost: p95,
      uncosted,
      share_pct,
    });
  }

  byColumn.sort((a, b) => b.total_cost_usd - a.total_cost_usd);

  // ── Per-row rollup ───────────────────────────────────────────────────────
  const byRecordId = new Map();
  for (const e of enriched) {
    const c = e.cell;
    if (!c || !c.record_id) continue;
    if (!byRecordId.has(c.record_id)) byRecordId.set(c.record_id, []);
    byRecordId.get(c.record_id).push(e);
  }

  const byRow = [];
  for (const [recordId, group] of byRecordId) {
    let row_cost = 0;
    let row_credits = 0;
    const cellRows = [];
    for (const e of group) {
      const c = e.cell;
      if (c.ran) {
        row_cost += e.costUsd;
        if (e.effCredits != null) row_credits += e.effCredits;
      }
      const m = metaById.get(c.field_id) || {};
      cellRows.push({
        field_id: c.field_id,
        field_name: m.field_name || c.field_id,
        total_cost_usd: c.ran ? e.costUsd : 0,
        credits: c.ran ? (e.effCredits || 0) : 0,
        status: c.status,
        ran: !!c.ran,
        skipped: !!c.skipped,
        uncosted: !!c.uncosted,
        is_refunded: c.is_refunded === true,
      });
    }
    byRow.push({
      record_id: recordId,
      total_cost_usd: row_cost,
      total_credits: row_credits,
      cells: cellRows,
    });
  }

  byRow.sort((a, b) => b.total_cost_usd - a.total_cost_usd);
  const topRows = byRow.slice(0, 50);

  const totals = {
    total_cost_usd,
    total_credits,
    total_runs,
    total_successes,
    total_errors,
    total_skipped,
    refunded_cost_usd,
    refunded_credits,
    uncosted_cells,
    unique_rows: uniqueRowIds.size,
    success_rows,
    cost_per_success_row,
    success_rate,
    // Convenience: net (after refunds). The UI may surface either.
    net_cost_usd,
  };

  console.log(
    LOG,
    `aggregate: ${cells.length} cells → totals.total_cost_usd=${total_cost_usd.toFixed(4)} ` +
    `runs=${total_runs} successes=${total_successes} errors=${total_errors} skipped=${total_skipped} ` +
    `refunded=${refunded_cost_usd.toFixed(4)} uncosted=${uncosted_cells}`,
  );

  return { totals, byColumn, byRow, topRows };
}

// ── CSV export ───────────────────────────────────────────────────────────────

const CSV_HEADERS = [
  'column', 'model', 'action_key',
  'runs', 'successes', 'errors',
  'total_cost_usd', 'total_credits',
  'cost_per_run', 'p50', 'p95', 'share_pct',
];

function csvEscape(v) {
  if (v == null) return '';
  const s = typeof v === 'number' ? String(v) : String(v);
  if (/[",\n\r]/.test(s)) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function fmtNum(v, decimals) {
  if (v == null || !Number.isFinite(v)) return '';
  return v.toFixed(decimals);
}

/**
 * Render the byColumn array as a CSV string suitable for clipboard/download.
 */
export function toCSV(byColumn) {
  const rows = Array.isArray(byColumn) ? byColumn : [];
  const lines = [CSV_HEADERS.join(',')];
  for (const c of rows) {
    lines.push([
      csvEscape(c.field_name),
      csvEscape(c.model),
      csvEscape(c.action_key),
      csvEscape(c.runs),
      csvEscape(c.successes),
      csvEscape(c.errors),
      csvEscape(fmtNum(c.total_cost_usd, 6)),
      csvEscape(fmtNum(c.total_credits, 4)),
      csvEscape(fmtNum(c.cost_per_run, 6)),
      csvEscape(fmtNum(c.p50_cost, 6)),
      csvEscape(fmtNum(c.p95_cost, 6)),
      csvEscape(fmtNum(c.share_pct, 2)),
    ].join(','));
  }
  return lines.join('\n');
}
