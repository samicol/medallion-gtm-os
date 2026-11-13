// Extract cost + telemetry fields from a Clay cell.
//
// Same field semantics as clay_costs.extract_cost_fields() in Rex's Python
// SDK (../../clay_costs.py): this is the JS side of the same cost math,
// extended with:
//   - { ran, skipped, uncosted } boolean flags derived from the cell's status
//   - per-actionKey credit lookup via provider-costs.js for action cells
//
// Field-name precedence:
//   cost_str = fullValue.totalCostToAIProvider || costDetails.totalCostToAIProvider
//   in_tok   = fullValue.totalInputTokens || fullValue.inputTokens || costDetails.inputTokens
//   out_tok  = fullValue.totalOutputTokens || fullValue.outputTokens || costDetails.outputTokens
//
// Never silently zero an uncosted cell; set uncosted: true and leave
// total_cost_usd / credits as null.

import { creditsForActionKey } from "./provider-costs.js";

const LOG_PREFIX = "[claylens:cost-extractor]";

// Status sets: keep in sync with CHARGED_STATUSES / SKIPPED_STATUSES in clay_costs.py
export const CHARGED_STATUSES = new Set(["SUCCESS", "SUCCESS_NO_DATA"]);
export const SKIPPED_STATUSES = new Set(["ERROR_RUN_CONDITION_NOT_MET"]);
export const NEVER_STATUSES = new Set(["NO_STATUS"]);

/**
 * Coerce a Clay cost-string into a float, or null if unparseable.
 *
 * Handles: numbers, "$0.0067", "0.0067", "1,234.56".
 *
 * @param {*} v
 * @returns {number|null}
 */
export function moneyToFloat(v) {
  if (v == null) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = String(v).trim().replace(/^\$+/, "").replace(/,/g, "");
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function isPlainObject(x) {
  return x != null && typeof x === "object" && !Array.isArray(x);
}

function safeObj(x) {
  return isPlainObject(x) ? x : {};
}

function safeArr(x) {
  return Array.isArray(x) ? x : [];
}

function firstNonNull(...vals) {
  for (const v of vals) {
    if (v != null) return v;
  }
  return null;
}

/**
 * Flatten a Clay cell into a row of cost / telemetry fields.
 *
 * Safe on unrun / errored / empty cells; missing fields come back as null.
 *
 * @param {object|null|undefined} cell        a single value from record.cells[fieldId]
 * @param {string|null|undefined} fieldType   'action' | 'use-ai' | 'formula' | 'source' | 'text' | 'lookup-...'
 * @param {string|null|undefined} actionKey   typeSettings.actionKey (for action cells)
 * @returns {object}
 */
export function extractCostFields(cell, fieldType, actionKey) {
  if (cell !== null && cell !== undefined && !isPlainObject(cell)) {
    throw new Error(
      `[claylens:cost-extractor] cell must be an object or null/undefined, got ${typeof cell}`,
    );
  }

  const c = cell || {};
  const md = safeObj(c.metadata);
  const ec = safeObj(c.externalContent);
  const xc = safeObj(c.extendedContent);
  const fvRaw = ec.fullValue;
  const fv = isPlainObject(fvRaw) ? fvRaw : null;
  const hv = safeObj(ec.hiddenValue);
  const cd = safeObj(hv.costDetails);
  const upfront = safeObj(ec.upfrontCreditUsage);

  const fvD = isPlainObject(fv) ? fv : {};

  // Cost field: fullValue first, then costDetails (as in clay_costs.py).
  const costStr = firstNonNull(fvD.totalCostToAIProvider, cd.totalCostToAIProvider);

  // Token fields: Claygent uses totalInputTokens/totalOutputTokens; plain
  // use-ai stores inputTokens/outputTokens at the top level of fullValue.
  const inTok = firstNonNull(fvD.totalInputTokens, fvD.inputTokens, cd.inputTokens);
  const outTok = firstNonNull(fvD.totalOutputTokens, fvD.outputTokens, cd.outputTokens);

  const tools = safeArr(hv.toolsUsed);
  const steps = safeArr(fvD.stepsTaken);

  const q = xc.queuedAt;
  const fi = xc.finishedAt;

  const status = md.status ?? null;
  const ran = status != null && CHARGED_STATUSES.has(status);
  const skipped = status != null && SKIPPED_STATUSES.has(status);

  const totalCostUsd = moneyToFloat(costStr);

  // Action-credit lookup: only for action cells with an actionKey, and only
  // when the cell actually ran (status in CHARGED_STATUSES).
  let credits = null;
  if (fieldType === "action" && actionKey && ran) {
    credits = creditsForActionKey(actionKey);
  }

  // uncosted = ran but neither LLM cost nor credit data is available.
  // Never silently set total_cost_usd to 0; leave it null and flag it.
  const uncosted = ran && totalCostUsd == null && credits == null;

  return {
    status,
    is_stale: md.isStale ?? null,
    stale_reason: md.staleReason ?? null,
    run_id: firstNonNull(ec.runId, xc.runId),
    inputs_hash: firstNonNull(ec.inputsHash, xc.inputsHash),
    is_refunded: ec.isRefunded ?? null,
    queued_at_ms: q ?? null,
    finished_at_ms: fi ?? null,
    duration_ms: q != null && fi != null ? fi - q : null,
    requested_model: hv.requestedModel ?? null,
    actual_model: hv.actualModel ?? null,
    provider: hv.provider ?? null,
    response_type: hv.responseType ?? null,
    total_cost_usd_str: costStr ?? null,
    total_cost_usd: totalCostUsd,
    credits,
    input_tokens: inTok ?? null,
    output_tokens: outTok ?? null,
    tokens_used: firstNonNull(cd.tokensUsed, fvD.tokensUsed),
    time_seconds: moneyToFloat(fvD.timeTakenInSeconds),
    steps_taken_count: steps.length,
    steps_taken_json: steps.length > 0 ? JSON.stringify(steps) : null,
    tools_used_count: tools.length,
    tools_used_json: tools.length > 0 ? JSON.stringify(tools) : null,
    forced_early_cost: fvD.forcedToFinishEarlyBecauseOfCost ?? null,
    upfront_credit_total: upfront.totalCost ?? null,
    upfront_basic_credits: upfront.basicCreditsUsed ?? null,
    upfront_action_executions: upfront.actionExecutionsUsed ?? null,
    additional_credit_cost: ec.additionalCreditCost ?? null,
    lang_smith_trace_url: hv.langSmithTraceURL ?? null,
    mezmo_url: safeObj(ec.logInfo).mezmoUrl ?? null,
    full_value: fvRaw ?? null,
    // Status-derived flags
    ran,
    skipped,
    uncosted,
  };
}

// COST_ROW_FIELDS: column order for tabular output.
export const COST_ROW_FIELDS = Object.freeze([
  "status", "is_stale", "stale_reason",
  "run_id", "inputs_hash", "is_refunded",
  "queued_at_ms", "finished_at_ms", "duration_ms",
  "requested_model", "actual_model", "provider", "response_type",
  "total_cost_usd", "total_cost_usd_str",
  "credits",
  "input_tokens", "output_tokens", "tokens_used",
  "time_seconds",
  "steps_taken_count", "tools_used_count",
  "forced_early_cost",
  "upfront_credit_total", "upfront_basic_credits", "upfront_action_executions",
  "additional_credit_cost",
  "lang_smith_trace_url", "mezmo_url",
  "ran", "skipped", "uncosted",
]);
