"""
clay_costs.py: per-cell cost extraction and aggregation for Clay tables.

This is the Python side of the same cost math Rex's companion browser
extension (claylens/) uses: same field semantics, same provider-cost table,
same aggregation rules. Use it directly, or through
ClayClient.get_cell_costs() / ClayClient.print_cost_report() in
clay_client.py.

Field-name precedence for the LLM cost string:
    cost_str = fullValue.totalCostToAIProvider or costDetails.totalCostToAIProvider
Never silently zero an uncosted cell; extract_cost_fields() sets
uncosted=True and leaves total_cost_usd / credits as None instead.
"""

import re

# ── Provider / credit cost map ───────────────────────────────────────────────
#
# Credits per Clay action, by actionKey. `source` tells you how sure we are:
#   screenshot      verified from live Clay UI screenshots
#   published       Clay's public pricing / action catalog, not screenshot-verified
#   user-confirmed  confirmed verbally by the user who built this table; see note
#   guess           best-effort estimate; verify in Clay UI before relying on it
#
# credits_for_action_key() never returns 0 for an unknown key; it returns
# None so the caller flags the cell as uncosted instead of silently zeroing it.

PROVIDER_COSTS = {
    "_meta": {
        "clay_credit_usd": 0.014,
        "currency": "USD",
        "source_notes": {
            "screenshot": "verified from live Clay UI screenshots",
            "published": "Clay public pricing / action catalog, not screenshot-verified",
            "guess": "best-effort estimate; must be verified before relying on per-provider $/hit",
            "user-confirmed": "confirmed verbally by the user who built this table; see note for context",
        },
        "updated": "2026-04-23",
    },
    "finders": {
        "leadmagic-find-work-email":   {"provider": "LeadMagic",   "credits": 1.0, "source": "screenshot"},
        "findymail-find-work-email":   {"provider": "Findymail",   "credits": 2.0, "source": "screenshot"},
        "dropcontact-find-work-email": {"provider": "Dropcontact", "credits": 2.0, "source": "screenshot"},
        "find-email-v2":               {"provider": "Hunter",      "credits": 2.0, "source": "screenshot",
            "note": "Clay's internal alias for Hunter's work-email finder"},
        "prospeo-find-work-email-v2":  {"provider": "Prospeo",     "credits": 2.0, "source": "screenshot"},
        "datagma-find-work-email-v3":  {"provider": "Datagma",     "credits": 2.0, "source": "screenshot"},
        "icypeas-find-email-v2":       {"provider": "Icypeas",     "credits": 0.5, "source": "screenshot"},
        "enrow-find-work-email":       {"provider": "Enrow",       "credits": 1.0, "source": "screenshot"},
        "kitt-find-work-email":        {"provider": "Kitt",        "credits": 1.0, "source": "user-confirmed",
            "note": "1 Clay credit per email via the Clay-native integration. With a direct Kitt plan (BYOK), the effective rate is roughly 1/3 of this."},
        "fullenrich-find-work-email":  {"provider": "FullEnrich",  "credits": 2.0, "source": "guess",
            "note": "not screenshot-verified; verify via Clay UI before citing per-provider $/hit"},
        "wiza-find-work-email":        {"provider": "Wiza",        "credits": 3.0, "source": "guess",
            "note": "not screenshot-verified; verify via Clay UI before citing per-provider $/hit"},
    },
    "validators": {
        "findymail-validate-email":   {"provider": "Findymail",   "credits": 1.0, "source": "screenshot"},
        "kitt-validate-email":        {"provider": "Kitt",        "credits": 0.4, "source": "screenshot"},
        "listmint-validate-email":    {"provider": "Listmint",    "credits": 0.5, "source": "screenshot"},
        "zerobounce-validate-email":  {"provider": "ZeroBounce",  "credits": 1.0, "source": "screenshot"},
        "debounce-validate-email":    {"provider": "Debounce",    "credits": 1.0, "source": "screenshot"},
        "hunter-validate-email":      {"provider": "Hunter",      "credits": 1.0, "source": "screenshot"},
        "enrichley-validate-email":   {"provider": "Enrichley",   "credits": 1.0, "source": "screenshot"},
        "leadmagic-validate-email":   {"provider": "LeadMagic",   "credits": 1.0, "source": "screenshot"},
        "enrow-validate-email":       {"provider": "Enrow",       "credits": 1.0, "source": "screenshot"},
        "neverbounce-validate-email": {"provider": "NeverBounce", "credits": 0.0, "source": "screenshot",
            "note": "bring-your-own-API-key; zero Clay credits per call"},
    },
    "validators_ext": {
        "kitt-verify-email": {"provider": "Kitt", "credits": 0.4, "source": "guess",
            "note": "Same provider as kitt-validate-email. Verify pricing in Clay UI before citing per-hit $."},
    },
    "enrichment": {
        "enrich-person-from-linkedin-url": {"provider": "Clay",      "credits": 1.0, "source": "guess",
            "note": "Clay person-enrichment from LinkedIn URL; verify in your workspace"},
        "enrich-company-from-domain":      {"provider": "Clay",      "credits": 1.0, "source": "guess",
            "note": "Clay company-enrichment from domain; verify in your workspace"},
        "find-people-v2":                  {"provider": "Clay",      "credits": 0.0, "source": "user-confirmed",
            "note": "Find People (search/source action) is FREE in Clay. Downstream enrich-person costs credits separately. Explicit 0 != unknown; keep the entry so the aggregator doesn't flag these cells as uncosted."},
        "find-companies-v2":               {"provider": "Clay",      "credits": 0.0, "source": "user-confirmed",
            "note": "Find Companies (search/source action) is FREE in Clay. Downstream enrich-company costs credits separately."},
        "built-with-tech-lookup":          {"provider": "BuiltWith", "credits": 1.0, "source": "guess",
            "note": "Tech-stack lookup via BuiltWith integration; verify via Clay UI before citing per-call $"},
        "http-api-v2":                     {"provider": "Clay (HTTP)", "credits": 0.0, "source": "screenshot",
            "note": "Generic Clay HTTP column: Clay charges 1 action execution but 0 basic credits per call. If a workspace-specific config charges credits, Clay reports it via cell.upfrontCreditUsage.totalCost, which this module already prefers."},
    },
    "phone_finders": {
        "leadmagic-find-mobile-phone": {"provider": "LeadMagic", "credits": 1.0, "source": "guess",
            "note": "Mobile phone finder via LeadMagic; verify via Clay UI"},
        "datagma-find-mobile-phone":   {"provider": "Datagma",   "credits": 2.0, "source": "guess",
            "note": "Mobile phone finder via Datagma; verify via Clay UI"},
    },
    "signals": {
        "predictleads-job-postings": {"provider": "PredictLeads", "credits": 1.0, "source": "guess",
            "note": "Job-postings signal via PredictLeads; verify via Clay UI"},
        "intellizence-funding":      {"provider": "Intellizence", "credits": 1.0, "source": "guess",
            "note": "Funding events via Intellizence; verify via Clay UI"},
    },
    "claygent": {
        "clay-argon-research": {"provider": "Clay (Argon)", "credits": 0.0, "source": "guess",
            "note": "Argon research agent: Clay action credits are 0; LLM token cost is charged separately and surfaces via cell.totalCostToAIProvider"},
        "use-ai": {"provider": "Clay (use-ai)", "credits": 0.0, "source": "guess",
            "note": "Plain use-ai column: Clay credits are 0; LLM cost flows via cell.externalContent.fullValue.totalCostToAIProvider. Entry exists so the lookup doesn't warn on this common actionKey."},
    },
}

CLAY_CREDIT_USD = PROVIDER_COSTS["_meta"]["clay_credit_usd"]

# Categories that hold actionKey -> entry maps. `_meta` is not actionKey-indexed.
_ACTION_CATEGORIES = [
    "finders", "validators", "validators_ext", "enrichment",
    "phone_finders", "signals", "claygent",
]


def credits_for_action_key(action_key):
    """Return the credit cost for a Clay actionKey, or None if unknown/unpriced."""
    if not action_key:
        return None
    key = str(action_key).strip()
    if not key:
        return None
    for cat in _ACTION_CATEGORIES:
        bucket = PROVIDER_COSTS.get(cat, {})
        if key in bucket:
            credits = bucket[key].get("credits")
            return credits if isinstance(credits, (int, float)) else None
    return None


def entry_for_action_key(action_key):
    """Return the full provider entry (provider/credits/source/note) for an actionKey, or None."""
    if not action_key:
        return None
    key = str(action_key).strip()
    if not key:
        return None
    for cat in _ACTION_CATEGORIES:
        bucket = PROVIDER_COSTS.get(cat, {})
        if key in bucket:
            return bucket[key]
    return None


# ── Per-cell extraction ──────────────────────────────────────────────────────

CHARGED_STATUSES = {"SUCCESS", "SUCCESS_NO_DATA"}
SKIPPED_STATUSES = {"ERROR_RUN_CONDITION_NOT_MET"}


def money_to_float(v):
    """Coerce a Clay cost value (a number, or a string like "$0.0067") to a float, or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lstrip("$").replace(",", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _first_non_null(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


def extract_cost_fields(cell: dict, field_type: str = None, action_key: str = None) -> dict:
    """
    Flatten a Clay cell (record["cells"][field_id], from
    GET /tables/{table_id}/records/{record_id}) into cost/telemetry fields.

    Safe on unrun, errored, or empty cells; missing fields come back as None.
    Pass field_type="action" and the column's typeSettings.actionKey to enable
    the Clay-credit lookup for action columns.
    """
    c = cell or {}
    md = c.get("metadata") or {}
    ec = c.get("externalContent") or {}
    xc = c.get("extendedContent") or {}
    fv_raw = ec.get("fullValue")
    hv = ec.get("hiddenValue") or {}
    cd = hv.get("costDetails") or {}
    upfront = ec.get("upfrontCreditUsage") or {}
    fv_d = fv_raw if isinstance(fv_raw, dict) else {}

    cost_str = _first_non_null(fv_d.get("totalCostToAIProvider"), cd.get("totalCostToAIProvider"))

    # Claygent uses totalInputTokens/totalOutputTokens; plain use-ai stores
    # inputTokens/outputTokens at the top level of fullValue.
    in_tok = _first_non_null(fv_d.get("totalInputTokens"), fv_d.get("inputTokens"), cd.get("inputTokens"))
    out_tok = _first_non_null(fv_d.get("totalOutputTokens"), fv_d.get("outputTokens"), cd.get("outputTokens"))

    tools = hv.get("toolsUsed") or []
    steps = fv_d.get("stepsTaken") or []
    queued_at = xc.get("queuedAt")
    finished_at = xc.get("finishedAt")

    status = md.get("status")
    ran = status is not None and status in CHARGED_STATUSES
    skipped = status is not None and status in SKIPPED_STATUSES
    total_cost_usd = money_to_float(cost_str)

    # Action-credit lookup: only for action cells with an actionKey, and only
    # when the cell actually ran.
    credits = None
    if field_type == "action" and action_key and ran:
        credits = credits_for_action_key(action_key)

    # uncosted = ran, but neither LLM cost nor credit data is available.
    # Never silently treat this as $0; flag it instead.
    uncosted = ran and total_cost_usd is None and credits is None

    return {
        "status": status,
        "is_stale": md.get("isStale"),
        "stale_reason": md.get("staleReason"),
        "run_id": _first_non_null(ec.get("runId"), xc.get("runId")),
        "is_refunded": ec.get("isRefunded"),
        "queued_at_ms": queued_at,
        "finished_at_ms": finished_at,
        "duration_ms": (finished_at - queued_at) if (queued_at is not None and finished_at is not None) else None,
        "requested_model": hv.get("requestedModel"),
        "actual_model": hv.get("actualModel"),
        "provider": hv.get("provider"),
        "total_cost_usd_str": cost_str,
        "total_cost_usd": total_cost_usd,
        "credits": credits,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "tokens_used": _first_non_null(cd.get("tokensUsed"), fv_d.get("tokensUsed")),
        "time_seconds": money_to_float(fv_d.get("timeTakenInSeconds")),
        "steps_taken_count": len(steps),
        "tools_used_count": len(tools),
        "forced_early_cost": fv_d.get("forcedToFinishEarlyBecauseOfCost"),
        "upfront_credit_total": upfront.get("totalCost"),
        "upfront_basic_credits": upfront.get("basicCreditsUsed"),
        "upfront_action_executions": upfront.get("actionExecutionsUsed"),
        "additional_credit_cost": ec.get("additionalCreditCost"),
        "full_value": fv_raw,
        "ran": ran,
        "skipped": skipped,
        "uncosted": uncosted,
    }


# ── Column classification (heuristic, for the by-column report) ─────────────

_COPY_RE = re.compile(
    r"\b(email|e-mail|mail|dm|message|msg|copy|reply|subject[_\s-]*line|subject|"
    r"intro|opener|icebreaker|ice-breaker|linkedin\s*dm|linkedin\s*message|"
    r"invite|invitation|follow[_\s-]*up)\b", re.IGNORECASE)

_CLASSIFY_RE = re.compile(
    r"\b(icp|qualify|qualification|qualified|classif|categor|normali[sz]|cleanup|"
    r"clean|clean[_\s-]*up|extract|parse|format|industry|segment|scor|scoring|"
    r"rating|rank|validate|validation)\b", re.IGNORECASE)

_RESEARCH_RE = re.compile(
    r"\b(signal|trigger|analysis|detect|detection|usage|research|intel|"
    r"intelligence|event|news|tech[_\s-]*stack|stack|pain|objection|competitor)\b",
    re.IGNORECASE)


def classify_column(column_name: str, action_use_case: str = None) -> dict:
    """Heuristic {use_case, risk_class} for a Clay AI column, from its name and config."""
    uc = str(action_use_case or "").strip().strip('"').lower()
    name = column_name or ""

    # Name-based copy match wins regardless of the configured useCase; some
    # copywriting columns are configured as "claygent" but are pure copy gen.
    if _COPY_RE.search(name):
        return {"use_case": "copy", "risk_class": "HIGH"}
    if uc == "claygent":
        return {"use_case": "claygent", "risk_class": "MEDIUM"}
    if _CLASSIFY_RE.search(name):
        return {"use_case": "classification", "risk_class": "LOW"}
    if _RESEARCH_RE.search(name):
        return {"use_case": "research", "risk_class": "MEDIUM"}
    return {"use_case": "ai", "risk_class": "MEDIUM"}


# ── Aggregation ───────────────────────────────────────────────────────────────

def _effective_credits(cell: dict):
    """Clay-reported upfront_credit_total wins over the static provider-cost lookup."""
    upfront_total = cell.get("upfront_credit_total")
    if upfront_total is not None:
        return upfront_total
    return cell.get("credits")


def _percentile(vals: list, p: float):
    """
    Linearly-interpolated percentile, matching numpy's default "linear" method.

    Returns None on empty input, the single value for n=1. No special case
    below n=3: the interpolation formula already produces the right answer
    for n=2 (the original JS special-cased n<3 and returned the larger of
    two samples regardless of whether p50 or p95 was requested; fixed here).
    """
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    sorted_vals = sorted(vals)
    idx = (p / 100) * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + (0 if idx == lo else 1), len(sorted_vals) - 1)
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _mode_model(cells: list, configured_model=None):
    """Most-common actual_model across cells, falling back to the configured model."""
    counts = {}
    for c in cells:
        m = c.get("actual_model")
        if m:
            counts[m] = counts.get(m, 0) + 1
    if not counts:
        return configured_model
    return max(counts.items(), key=lambda kv: kv[1])[0]


def aggregate(extracted_cells: list, column_meta: list = None) -> dict:
    """
    Aggregate a flat list of extract_cost_fields() outputs (each augmented
    with record_id + field_id) into totals / by-column / by-row summaries.

    column_meta: list of {field_id, field_name, action_key, action_use_case,
    model_configured}, one entry per action-type column in the table.

    Returns {totals, by_column, by_row, top_rows}; top_rows is by_row
    sorted by cost descending, capped at 50.
    """
    cells = extracted_cells or []
    meta_by_id = {m["field_id"]: m for m in (column_meta or []) if m.get("field_id")}

    enriched = []
    for c in cells:
        eff_credits = _effective_credits(c)
        llm_usd = c.get("total_cost_usd") or 0
        credit_usd = (eff_credits * CLAY_CREDIT_USD) if eff_credits is not None else 0
        enriched.append({"cell": c, "eff_credits": eff_credits, "cost_usd": llm_usd + credit_usd})

    total_cost_usd = total_credits = 0.0
    total_runs = total_successes = total_errors = total_skipped = 0
    refunded_cost_usd = refunded_credits = 0.0
    uncosted_cells = 0
    unique_row_ids, success_row_ids = set(), set()

    for e in enriched:
        c = e["cell"]
        record_id = c.get("record_id")
        if record_id:
            unique_row_ids.add(record_id)

        if c.get("ran"):
            total_runs += 1
            total_successes += 1
            if record_id:
                success_row_ids.add(record_id)
            total_cost_usd += e["cost_usd"]
            if e["eff_credits"] is not None:
                total_credits += e["eff_credits"]
            if c.get("is_refunded") is True:
                refunded_cost_usd += e["cost_usd"]
                if e["eff_credits"] is not None:
                    refunded_credits += e["eff_credits"]
            if c.get("uncosted"):
                uncosted_cells += 1
        elif c.get("skipped"):
            total_skipped += 1
        elif c.get("status") is not None:
            total_runs += 1
            total_errors += 1

    success_rate = (total_successes / total_runs) if total_runs > 0 else None
    success_rows = len(success_row_ids)
    net_cost_usd = total_cost_usd - refunded_cost_usd
    cost_per_success_row = (net_cost_usd / success_rows) if success_rows > 0 else None

    by_field = {}
    for e in enriched:
        fid = e["cell"].get("field_id")
        if fid:
            by_field.setdefault(fid, []).append(e)

    by_column = []
    for field_id, group in by_field.items():
        m = meta_by_id.get(field_id, {})
        field_name = m.get("field_name") or field_id
        cls = classify_column(field_name, m.get("action_use_case"))

        runs = successes = errors = skipped = uncosted = 0
        cost_usd = credits = 0.0
        ran_cells = []
        for e in group:
            c = e["cell"]
            if c.get("ran"):
                runs += 1
                successes += 1
                cost_usd += e["cost_usd"]
                if e["eff_credits"] is not None:
                    credits += e["eff_credits"]
                if c.get("uncosted"):
                    uncosted += 1
                ran_cells.append(e)
            elif c.get("skipped"):
                skipped += 1
            elif c.get("status") is not None:
                runs += 1
                errors += 1

        # p50/p95 over LLM-dollar cost of ran cells only (matches the source audit).
        cost_samples = [e["cell"]["total_cost_usd"] for e in ran_cells if e["cell"].get("total_cost_usd") is not None]

        by_column.append({
            "field_id": field_id,
            "field_name": field_name,
            "model": _mode_model([e["cell"] for e in ran_cells], m.get("model_configured")),
            "action_key": m.get("action_key"),
            "use_case": cls["use_case"],
            "risk_class": cls["risk_class"],
            "runs": runs,
            "successes": successes,
            "errors": errors,
            "skipped": skipped,
            "total_cost_usd": cost_usd,
            "total_credits": credits,
            "cost_per_run": (cost_usd / runs) if runs > 0 else None,
            "p50_cost": _percentile(cost_samples, 50),
            "p95_cost": _percentile(cost_samples, 95),
            "uncosted": uncosted,
            "share_pct": (cost_usd / total_cost_usd * 100) if total_cost_usd > 0 else 0,
        })

    by_column.sort(key=lambda c: c["total_cost_usd"], reverse=True)

    by_record = {}
    for e in enriched:
        rid = e["cell"].get("record_id")
        if rid:
            by_record.setdefault(rid, []).append(e)

    by_row = []
    for record_id, group in by_record.items():
        row_cost = row_credits = 0.0
        cell_rows = []
        for e in group:
            c = e["cell"]
            if c.get("ran"):
                row_cost += e["cost_usd"]
                if e["eff_credits"] is not None:
                    row_credits += e["eff_credits"]
            m = meta_by_id.get(c.get("field_id"), {})
            cell_rows.append({
                "field_id": c.get("field_id"),
                "field_name": m.get("field_name") or c.get("field_id"),
                "total_cost_usd": e["cost_usd"] if c.get("ran") else 0,
                "credits": (e["eff_credits"] or 0) if c.get("ran") else 0,
                "status": c.get("status"),
                "ran": bool(c.get("ran")),
                "uncosted": bool(c.get("uncosted")),
                "is_refunded": c.get("is_refunded") is True,
            })
        by_row.append({
            "record_id": record_id,
            "total_cost_usd": row_cost,
            "total_credits": row_credits,
            "cells": cell_rows,
        })

    by_row.sort(key=lambda r: r["total_cost_usd"], reverse=True)

    totals = {
        "total_cost_usd": total_cost_usd,
        "total_credits": total_credits,
        "total_runs": total_runs,
        "total_successes": total_successes,
        "total_errors": total_errors,
        "total_skipped": total_skipped,
        "refunded_cost_usd": refunded_cost_usd,
        "refunded_credits": refunded_credits,
        "uncosted_cells": uncosted_cells,
        "unique_rows": len(unique_row_ids),
        "success_rows": success_rows,
        "cost_per_success_row": cost_per_success_row,
        "success_rate": success_rate,
        "net_cost_usd": net_cost_usd,
    }

    return {"totals": totals, "by_column": by_column, "by_row": by_row, "top_rows": by_row[:50]}


def to_csv(by_column: list) -> str:
    """Render the by_column list as a CSV string (column, model, runs, cost, p50/p95, share)."""
    headers = ["column", "model", "action_key", "runs", "successes", "errors",
               "total_cost_usd", "total_credits", "cost_per_run", "p50", "p95", "share_pct"]

    def esc(v):
        if v is None:
            return ""
        s = str(v)
        if any(ch in s for ch in ',"\n\r'):
            return '"' + s.replace('"', '""') + '"'
        return s

    def fmt(v, decimals):
        return "" if v is None else f"{v:.{decimals}f}"

    lines = [",".join(headers)]
    for c in (by_column or []):
        lines.append(",".join([
            esc(c.get("field_name")), esc(c.get("model")), esc(c.get("action_key")),
            esc(c.get("runs")), esc(c.get("successes")), esc(c.get("errors")),
            esc(fmt(c.get("total_cost_usd"), 6)), esc(fmt(c.get("total_credits"), 4)),
            esc(fmt(c.get("cost_per_run"), 6)), esc(fmt(c.get("p50_cost"), 6)),
            esc(fmt(c.get("p95_cost"), 6)), esc(fmt(c.get("share_pct"), 2)),
        ]))
    return "\n".join(lines)
