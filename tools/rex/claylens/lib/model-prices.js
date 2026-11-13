// LLM provider pricing snapshot: April 2026.
//
// Sourced from: OpenRouter, Artificial Analysis, Vellum Leaderboard, pricepertoken.com
//
// All prices are USD per 1M tokens.
//
// Canonical keys are the `actualModel` values Clay reports (what actually ran).
// We also accept common aliases the `requestedModel` / column config uses.
//
// Update this table periodically: LLM pricing moves fast and this is a
// point-in-time snapshot, not a live feed.

/**
 * @typedef {Object} ModelPrice
 * @property {string} name
 * @property {number} input_per_m   USD per 1M input tokens
 * @property {number} output_per_m  USD per 1M output tokens
 * @property {string} provider
 * @property {string} tier          flagship | high | mid | compact | budget | reasoning | standard
 * @property {string} family        openai | anthropic | google | deepseek | kimi
 */

function mp(name, input_per_m, output_per_m, provider, tier, family) {
  return Object.freeze({ name, input_per_m, output_per_m, provider, tier, family });
}

export const MODEL_PRICES = Object.freeze({
  // --- OpenAI ---
  "gpt-5.4": mp("gpt-5.4", 2.50, 15.00, "openai", "flagship", "openai"),
  "gpt-5.2": mp("gpt-5.2", 1.75, 14.00, "openai", "high", "openai"),
  "gpt-5.1": mp("gpt-5.1", 1.25, 10.00, "openai", "mid", "openai"),
  "gpt-5-mini": mp("gpt-5-mini", 0.63, 5.00, "openai", "compact", "openai"),
  "gpt-5-nano": mp("gpt-5-nano", 0.50, 2.00, "openai", "budget", "openai"),
  "gpt-4.1-nano": mp("gpt-4.1-nano", 0.10, 0.40, "openai", "budget", "openai"),
  "gpt-4o-mini": mp("gpt-4o-mini", 0.15, 0.60, "openai", "compact", "openai"),
  // legacy gpt-4o: only for de-mapping stale Clay runs
  "gpt-4o": mp("gpt-4o", 2.50, 10.00, "openai", "high", "openai"),
  "gpt-4o-2024-11-20": mp("gpt-4o-2024-11-20", 2.50, 10.00, "openai", "high", "openai"),
  "gpt-4.1": mp("gpt-4.1", 2.00, 8.00, "openai", "high", "openai"),
  "gpt-4.1-mini": mp("gpt-4.1-mini", 0.40, 1.60, "openai", "compact", "openai"),

  // --- Google ---
  "gemini-3.1-pro": mp("gemini-3.1-pro", 3.00, 15.00, "google", "flagship", "google"),
  "gemini-3-flash": mp("gemini-3-flash", 0.50, 3.00, "google", "mid", "google"),
  "gemini-2.5-flash": mp("gemini-2.5-flash", 0.15, 0.60, "google", "budget", "google"),
  "gemini-2.5-flash-lite": mp("gemini-2.5-flash-lite", 0.10, 0.40, "google", "budget", "google"),

  // --- Anthropic ---
  "claude-opus-4-7": mp("claude-opus-4-7", 5.00, 25.00, "anthropic", "flagship", "anthropic"),
  "claude-opus-4-6": mp("claude-opus-4-6", 5.00, 25.00, "anthropic", "high", "anthropic"),
  "claude-sonnet-4-6": mp("claude-sonnet-4-6", 3.00, 15.00, "anthropic", "mid", "anthropic"),
  "claude-haiku-4-5": mp("claude-haiku-4-5", 0.25, 1.25, "anthropic", "budget", "anthropic"),

  // --- Kimi ---
  "kimi-k2.6": mp("kimi-k2.6", 0.75, 3.50, "moonshot", "flagship", "kimi"),
  "kimi-k2.5": mp("kimi-k2.5", 0.60, 3.00, "moonshot", "standard", "kimi"),
  "kimi-k2-thinking": mp("kimi-k2-thinking", 0.60, 2.50, "moonshot", "reasoning", "kimi"),

  // --- DeepSeek ---
  "deepseek-v4": mp("deepseek-v4", 0.30, 0.50, "deepseek", "flagship", "deepseek"),
  "deepseek-v3.2": mp("deepseek-v3.2", 0.28, 0.42, "deepseek", "standard", "deepseek"),
  "deepseek-r1": mp("deepseek-r1", 0.55, 2.19, "deepseek", "reasoning", "deepseek"),
});

const _ALIASES = Object.freeze({
  "claude-sonnet-4-5": "claude-sonnet-4-6", // treat older 4.5 like 4.6; same tier, similar price
  "claude-3-5-sonnet": "claude-sonnet-4-6",
  "claude-3-5-haiku": "claude-haiku-4-5",
  "claude-3-opus": "claude-opus-4-6",
});

/**
 * Look up a ModelPrice for a Clay-reported model id.
 *
 * Falls back to a version-stripped two-token base, e.g.
 * "gpt-4o-2024-11-20" → "gpt-4o".
 *
 * @param {string|null|undefined} model
 * @returns {ModelPrice|null}
 */
export function lookup(model) {
  if (!model) return null;
  const m = String(model).trim().toLowerCase();
  if (Object.prototype.hasOwnProperty.call(MODEL_PRICES, m)) {
    return MODEL_PRICES[m];
  }
  if (Object.prototype.hasOwnProperty.call(_ALIASES, m)) {
    return MODEL_PRICES[_ALIASES[m]];
  }
  // version-stripped fallback, e.g. "gpt-4o-2024-11-20" → "gpt-4o"
  const parts = m.split("-");
  const base = parts.slice(0, 2).join("-");
  if (Object.prototype.hasOwnProperty.call(MODEL_PRICES, base)) {
    return MODEL_PRICES[base];
  }
  return null;
}

// For each (current_model, risk_class) pick a reasonable cheaper replacement.
// Separate choices for copy (HIGH) vs research (MEDIUM) vs classification (LOW).
//
// Stored as a Map keyed by `${canonical_model}|${risk_class}` for JS-friendly
// composite-key lookup.
const CHEAPER_CANDIDATE = new Map([
  // classification / cleaning: aggressive
  ["gpt-5.1|LOW", "gpt-4.1-nano"],
  ["gpt-5-mini|LOW", "gpt-4.1-nano"],
  ["gpt-4.1-mini|LOW", "gpt-4.1-nano"],
  ["gpt-4o|LOW", "gpt-4.1-nano"],
  ["claude-sonnet-4-6|LOW", "claude-haiku-4-5"],
  ["claude-opus-4-6|LOW", "claude-haiku-4-5"],
  ["claude-opus-4-7|LOW", "claude-haiku-4-5"],
  // research / claygent: moderate
  ["gpt-5.1|MEDIUM", "gpt-5-mini"],
  ["gpt-5-mini|MEDIUM", "gpt-5-nano"],
  ["gpt-4.1|MEDIUM", "gpt-4.1-mini"],
  ["gpt-4.1-mini|MEDIUM", "gpt-4.1-nano"],
  ["gpt-4o|MEDIUM", "gpt-5-mini"],
  ["claude-sonnet-4-6|MEDIUM", "claude-haiku-4-5"],
  ["claude-opus-4-6|MEDIUM", "claude-sonnet-4-6"],
  ["claude-opus-4-7|MEDIUM", "claude-sonnet-4-6"],
  // copy: conservative, stay in family
  ["claude-opus-4-7|HIGH", "claude-sonnet-4-6"],
  ["claude-opus-4-6|HIGH", "claude-sonnet-4-6"],
  ["claude-sonnet-4-6|HIGH", "claude-haiku-4-5"],
  ["gpt-5.1|HIGH", "gpt-5-mini"],
  ["gpt-5-mini|HIGH", "gpt-5-nano"],
  ["gpt-4o|HIGH", "gpt-5-mini"],
]);

/**
 * Return the recommended cheaper ModelPrice for a current model + risk class,
 * or null if no candidate is defined / no price info available.
 *
 * @param {string|null|undefined} currentModel
 * @param {string} riskClass  LOW | MEDIUM | HIGH
 * @returns {ModelPrice|null}
 */
export function bestCheaperTier(currentModel, riskClass) {
  if (!currentModel) return null;
  const cur = lookup(currentModel);
  if (!cur) return null;
  // walk aliases to canonical name
  const canonical = cur.name;
  const key = `${canonical}|${riskClass}`;
  if (CHEAPER_CANDIDATE.has(key)) {
    return lookup(CHEAPER_CANDIDATE.get(key));
  }
  // fallback: find the cheapest model in the same family at a lower or equal tier
  return null;
}

/**
 * Fractional savings if we swap `current` → `candidate` at the given
 * per-run token profile. Returns e.g. 0.85 meaning 85% cheaper.
 *
 * Returns null when any input is missing.
 *
 * @param {string|null|undefined} currentModel
 * @param {string|null|undefined} candidateModel
 * @param {number|null|undefined} inputTokens
 * @param {number|null|undefined} outputTokens
 * @returns {number|null}
 */
export function estimatedSavingsRatio(currentModel, candidateModel, inputTokens, outputTokens) {
  const cur = lookup(currentModel);
  const cand = lookup(candidateModel);
  if (!cur || !cand || inputTokens == null || outputTokens == null) return null;

  const curCost =
    (inputTokens / 1_000_000) * cur.input_per_m + (outputTokens / 1_000_000) * cur.output_per_m;
  const candCost =
    (inputTokens / 1_000_000) * cand.input_per_m + (outputTokens / 1_000_000) * cand.output_per_m;
  if (curCost <= 0) return null;
  return Math.max(0.0, (curCost - candCost) / curCost);
}
