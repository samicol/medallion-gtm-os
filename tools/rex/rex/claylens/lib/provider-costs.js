// Provider/credit cost map for Clay action columns.
//
// The `finders`/`validators` entries are screenshot-verified ground truth
// as of 2026-04-23. Extension entries below cover the broader Clay action
// catalog (LinkedIn enrichment, phone finders, tech-stack, funding/news).
// Anything not screenshot-verified is marked source: "guess"; for unknown
// actionKeys `creditsForActionKey` returns null (never fabricate a credit
// count).

const LOG_PREFIX = "[claylens:provider-costs]";

export const PROVIDER_COSTS = Object.freeze({
  _meta: {
    clay_credit_usd: 0.014,
    currency: "USD",
    source_notes: {
      screenshot: "verified from live Clay UI screenshots",
      published: "Clay public pricing / action catalog, not screenshot-verified in this workspace",
      guess: "best-effort estimate; must be verified before relying on per-provider $/hit",
      "user-confirmed": "confirmed verbally by the user who built this table; see note for context",
    },
    updated: "2026-04-23",
  },

  // ---- Email finders (verbatim from provider_costs.json) ----
  finders: {
    "leadmagic-find-work-email":   { provider: "LeadMagic",   credits: 1.0, source: "screenshot" },
    "findymail-find-work-email":   { provider: "Findymail",   credits: 2.0, source: "screenshot" },
    "dropcontact-find-work-email": { provider: "Dropcontact", credits: 2.0, source: "screenshot" },
    "find-email-v2":               { provider: "Hunter",      credits: 2.0, source: "screenshot",
      note: "Clay internal alias for Hunter's work-email finder: confirmed by cell imagePreview=hunter.svg" },
    "prospeo-find-work-email-v2":  { provider: "Prospeo",     credits: 2.0, source: "screenshot" },
    "datagma-find-work-email-v3":  { provider: "Datagma",     credits: 2.0, source: "screenshot" },
    "icypeas-find-email-v2":       { provider: "Icypeas",     credits: 0.5, source: "screenshot" },
    "enrow-find-work-email":       { provider: "Enrow",       credits: 1.0, source: "screenshot" },
    "kitt-find-work-email":        { provider: "Kitt",        credits: 1.0, source: "user-confirmed",
      note: "Confirmed 2026-04-23: 1 Clay credit per email via Clay-native integration. With a direct Kitt plan (BYOK), the effective rate is ~1/3 of this (~0.33 credit-equivalent)." },
    "fullenrich-find-work-email":  { provider: "FullEnrich",  credits: 2.0, source: "guess",
      note: "not in attached screenshots; verify via Clay UI before citing per-provider $/hit" },
    "wiza-find-work-email":        { provider: "Wiza",        credits: 3.0, source: "guess",
      note: "not in attached screenshots; verify via Clay UI before citing per-provider $/hit" },
  },

  // ---- Email validators (verbatim from provider_costs.json) ----
  validators: {
    "findymail-validate-email":   { provider: "Findymail",   credits: 1.0, source: "screenshot" },
    "kitt-validate-email":        { provider: "Kitt",        credits: 0.4, source: "screenshot" },
    "listmint-validate-email":    { provider: "Listmint",    credits: 0.5, source: "screenshot" },
    "zerobounce-validate-email":  { provider: "ZeroBounce",  credits: 1.0, source: "screenshot" },
    "debounce-validate-email":    { provider: "Debounce",    credits: 1.0, source: "screenshot" },
    "hunter-validate-email":      { provider: "Hunter",      credits: 1.0, source: "screenshot" },
    "enrichley-validate-email":   { provider: "Enrichley",   credits: 1.0, source: "screenshot" },
    "leadmagic-validate-email":   { provider: "LeadMagic",   credits: 1.0, source: "screenshot" },
    "enrow-validate-email":       { provider: "Enrow",       credits: 1.0, source: "screenshot" },
    "neverbounce-validate-email": { provider: "NeverBounce", credits: 0.0, source: "screenshot",
      note: "bring-your-own-API-key; zero Clay credits per call" },
  },

  // ---- LinkedIn / company / contact enrichment (extension) ----
  enrichment: {
    "enrich-person-from-linkedin-url": { provider: "Clay",      credits: 1.0, source: "guess",
      note: "Clay person-enrichment from LinkedIn URL; verify in your workspace" },
    "enrich-company-from-domain":      { provider: "Clay",      credits: 1.0, source: "guess",
      note: "Clay company-enrichment from domain; verify in your workspace" },
    "find-people-v2":                  { provider: "Clay",      credits: 0.0, source: "user-confirmed",
      note: "Find People (search/source action) is FREE in Clay, user-confirmed 2026-04-23. Downstream enrich-person costs credits separately. Explicit 0 ≠ unknown; keep entry so aggregator does not flag cells as uncosted." },
    "find-companies-v2":               { provider: "Clay",      credits: 0.0, source: "user-confirmed",
      note: "Find Companies (search/source action) is FREE in Clay, user-confirmed 2026-04-23. Downstream enrich-company costs credits separately." },
    "built-with-tech-lookup":          { provider: "BuiltWith", credits: 1.0, source: "guess",
      note: "Tech-stack lookup via BuiltWith integration; verify via Clay UI before citing per-call $" },
    "http-api-v2":                     { provider: "Clay (HTTP)", credits: 0.0, source: "screenshot",
      note: "Generic Clay HTTP column: Clay charges 1 action execution but 0 basic credits per call. If a workspace-specific config charges credits, Clay reports it via cell.upfrontCreditUsage.totalCost which the aggregator already prefers." },
  },

  // ---- Email validators: extension entries beyond the screenshot seed ----
  validators_ext: {
    "kitt-verify-email": { provider: "Kitt", credits: 0.4, source: "guess",
      note: "Same provider as kitt-validate-email. Verify pricing in Clay UI before citing per-hit $." },
  },

  // ---- Phone finders (extension) ----
  phone_finders: {
    "leadmagic-find-mobile-phone": { provider: "LeadMagic", credits: 1.0, source: "guess",
      note: "Mobile phone finder via LeadMagic; verify via Clay UI" },
    "datagma-find-mobile-phone":   { provider: "Datagma",   credits: 2.0, source: "guess",
      note: "Mobile phone finder via Datagma; verify via Clay UI" },
  },

  // ---- Funding / news / signals (extension) ----
  signals: {
    "predictleads-job-postings": { provider: "PredictLeads", credits: 1.0, source: "guess",
      note: "Job-postings signal via PredictLeads; verify via Clay UI" },
    "intellizence-funding":      { provider: "Intellizence", credits: 1.0, source: "guess",
      note: "Funding events via Intellizence; verify via Clay UI" },
  },

  // ---- Claygent / agentic / LLM columns (extension) ----
  claygent: {
    "clay-argon-research": { provider: "Clay (Argon)", credits: 0.0, source: "guess",
      note: "Argon research agent: Clay action credits are 0; LLM token cost charged separately and surfaces via cell.totalCostToAIProvider" },
    "use-ai": { provider: "Clay (use-ai)", credits: 0.0, source: "inferred",
      note: "Plain use-ai column: Clay credits = 0; LLM cost flows via cell.externalContent.fullValue.totalCostToAIProvider. Entry exists to silence the unknown-actionKey warning." },
  },

  // ---- Hypothesis bucket (verbatim from provider_costs.json) ----
  hypothesis: {
    millionverifier: {
      usd_per_call_native: 0.0015,
      assumed_clay_credits_scenarios: { integrated: 0.0, conservative: 1.0 },
      note: "User stated MV can be called cheaply; reporting both 0c (integrated) and 1c (HTTP column) scenarios until user confirms integration path",
    },
  },
});

// Categories that hold actionKey → entry maps. `_meta` and `hypothesis` are
// not actionKey-indexed and are intentionally excluded from the lookup walk.
const _ACTION_CATEGORIES = ["finders", "validators", "validators_ext", "enrichment", "phone_finders", "signals", "claygent"];

/**
 * Return the credit cost for a given Clay actionKey, or null if unknown.
 *
 * Never returns 0 for an unknown key; null forces the aggregator to flag
 * the cell as `uncosted` rather than silently zeroing it.
 *
 * @param {string|null|undefined} actionKey
 * @returns {number|null}
 */
export function creditsForActionKey(actionKey) {
  if (!actionKey) return null;
  const key = String(actionKey).trim();
  if (!key) return null;

  for (const cat of _ACTION_CATEGORIES) {
    const bucket = PROVIDER_COSTS[cat];
    if (bucket && Object.prototype.hasOwnProperty.call(bucket, key)) {
      const entry = bucket[key];
      if (entry && typeof entry.credits === "number") return entry.credits;
      // entry exists but credits unknown → caller must treat as uncosted
      console.log(LOG_PREFIX, "actionKey present but credits non-numeric:", key, entry);
      return null;
    }
  }
  console.log(LOG_PREFIX, "unknown actionKey:", key);
  return null;
}

/**
 * Return the full provider entry for an actionKey (includes provider name +
 * source + note), or null if unknown. Useful for UI tooltips.
 *
 * @param {string|null|undefined} actionKey
 * @returns {{provider: string, credits: number, source: string, note?: string}|null}
 */
export function entryForActionKey(actionKey) {
  if (!actionKey) return null;
  const key = String(actionKey).trim();
  if (!key) return null;
  for (const cat of _ACTION_CATEGORIES) {
    const bucket = PROVIDER_COSTS[cat];
    if (bucket && Object.prototype.hasOwnProperty.call(bucket, key)) {
      return bucket[key];
    }
  }
  return null;
}

export const CLAY_CREDIT_USD = PROVIDER_COSTS._meta.clay_credit_usd;
