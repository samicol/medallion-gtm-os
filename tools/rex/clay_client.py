"""
Clay Internal API Client
Authenticates using your existing Chrome session; no login required.

Usage:
    from clay_client import ClayClient
    clay = ClayClient()
    tables = clay.list_tables()
    clay.create_column(table_id, {...})
"""

import copy
import json
import os
import re
import time
import warnings
import requests
from typing import Any

import clay_costs

BASE = "https://api.clay.com/v3"

# Default timeout (seconds) for every HTTP call this client makes. A stale or
# expired session cookie can otherwise hang a request indefinitely.
# Override per client with ClayClient(timeout=...), or per call with timeout=.
DEFAULT_TIMEOUT = 30

# Package id for the "Send table data" (route-row) action.
ROUTE_ROW_PACKAGE_ID = "b1ab3d5d-b0db-4b30-9251-3f32d8b103c1"
# Package id shared by Clay's MixRank sources (Find People / Find Companies)
# and the MixRank enrichments.
MIXRANK_PACKAGE_ID = "e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "x-clay-frontend-version": "v20260227_221530Z_165b5326da",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "referer": "https://app.clay.com/",
    "origin": "https://app.clay.com",
}


class ClayColumnConfigError(RuntimeError):
    """Clay accepted the request but reported a broken column configuration."""


class ClayViewFilterError(RuntimeError):
    """Clay accepted a view filter but did not store it as sent (addition beyond upstream v2.1)."""


class ClayTableConfigError(RuntimeError):
    """Clay created a table but its name/settings did not stick (addition beyond upstream v2.1)."""


# Column colours: a per-VIEW field setting (LEARNINGS.md backlog #20, app bundle 2026-09-24).
COLUMN_COLORS = ("red", "yellow", "blue", "green", "violet", "orange", "pink", "grey")

# Lookup actions (Clay package). (LEARNINGS.md backlog #17)
CLAY_UTILITY_PACKAGE_ID = "4299091f-3cd3-4d68-b198-0143575f471d"
LOOKUP_OPERATORS = ("EQUAL", "CONTAIN")

# Find Jobs source record keys worth extracting (LEARNINGS.md backlog #21), as
# {suggested column name: payload key}.
FIND_JOBS_FIELDS = {
    "Company Name": "company_name",
    "Job Title": "title",
    "Company LinkedIn": "company_url",
    "Company Domain": "domain",
    "Posted On": "posted_at",
    "Seniority": "seniority",
    "Location": "location",
    "Job LinkedIn URL": "url",
}


# View filter operators, taken from Clay's front-end enum (app bundle, 2026-09-24).
# Clay answers 200 to an UNKNOWN operator but silently drops that condition, so the
# view shows every row. set_view_filter() rejects anything outside this set and
# reads the stored filter back. Verified live: EQUAL/NOT_EQUAL (case-sensitive),
# CONTAIN (case-insensitive), CONTAIN_ANY (list value), EMPTY/NOT_EMPTY, OR mode.
VIEW_FILTER_OPERATORS = frozenset({
    "EQUAL", "NOT_EQUAL", "SELECT_EQUAL", "SELECT_NOT_EQUAL", "USER_EQUAL", "USER_NOT_EQUAL",
    "GREATER_THAN", "GREATER_THAN_OR_EQUAL", "LESS_THAN", "LESS_THAN_OR_EQUAL",
    "CONTAIN", "CONTAIN_ANY", "NOT_CONTAIN", "NOT_CONTAIN_ANY", "EMPTY", "NOT_EMPTY",
    "CHECKED", "NOT_CHECKED", "SELECT_SOURCE", "SELECT_NOT_SOURCE",
    # run-status operators for action columns
    "HAS_ERROR", "NOT_ERRORED", "RESULTS", "NO_RESULTS", "QUEUED", "AWAITING_CALLBACK",
    "RETRY", "HAS_NOT_RUN", "RUN_CONDITION_NOT_MET", "MISSING_INPUT", "NOT_MISSING_INPUT",
    "IS_STALE", "IS_RUNNING", "IS_NOT_RUNNING",
})


# ── Additions beyond upstream v2.1, from the LEARNINGS.md backlog (2026-09-24) ──────

# AI column modes. "claygent" is a browsing agent; "use-ai" is a plain model call
# over data already on the row. (LEARNINGS.md backlog #1)
AI_USE_CASES = ("use-ai", "claygent")

# Envelope metrics Clay adds to an AI cell's fullValue next to the schema output.
AI_OUTPUT_METADATA_KEYS = frozenset({
    "stepsTaken", "timeTakenInSeconds", "forcedToFinishEarlyBecauseOfCost",
    "totalInputTokens", "totalOutputTokens", "totalCostToAIProvider",
    "tokensUsed", "inputTokens", "outputTokens",
})

# Data types verified live for retyping routed columns. (LEARNINGS.md backlog #4)
ROUTE_COLUMN_TYPES = frozenset({"text", "url", "email"})

_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")


def _refuse_hiding_lineage(table: dict, visible_field_ids: list) -> None:
    """Raise if action/source columns would be hidden (LEARNINGS.md backlog #19)."""
    lineage = [f"{f.get('name')} ({f['id']}, {f.get('type')})"
               for f in table.get("fields", [])
               if f.get("type") in ("action", "source") and f["id"] not in visible_field_ids]
    if lineage:
        raise ValueError(
            "this would hide action/source columns, which must stay visible: "
            f"{lineage}. Add them to visible_field_ids or pass allow_hide_actions=True.")


def lookup_extract_formula(lookup_field_id: str, column_name: str, multiple: bool = False) -> str:
    """
    Formula that reads one column out of a lookup cell (LEARNINGS.md backlog #17).
    A lookup's output is keyed by the target column NAME:
      single   -> {{lookup}}?.record?.["Col"]
      multiple -> ({{lookup}}?.records || []).map(r => r?.["Col"])   (a list; filter/join as needed)
    """
    key = json.dumps(column_name, ensure_ascii=False)
    if multiple:
        return f"({{{{{lookup_field_id}}}}}?.records || []).map(r => r?.[{key}])"
    return f"{{{{{lookup_field_id}}}}}?.record?.[{key}]"


def _use_case_of(type_settings: dict):
    """The unquoted useCase bound on an AI column, or None if it has none."""
    for b in (type_settings or {}).get("inputsBinding") or []:
        if isinstance(b, dict) and b.get("name") == "useCase":
            raw = b.get("formulaText")
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return (raw or "").strip("\"'") or None
    return None


def ai_key_variants(key: str) -> list[str]:
    """[key, camelCase, snake_case] without duplicates. claygent returns camelCase keys,
    use-ai returns snake_case for the same schema. (LEARNINGS.md backlog #2)
    Keys that are neither camelCase nor snake_case ("tier", "URL", "Full Name") are
    returned as-is."""
    if not _IDENT_RE.match(key) or not ("_" in key.strip("_") or re.search(r"[a-z0-9][A-Z]", key)):
        return [key]
    snake = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", key).lower()
    camel = re.sub(r"_([a-z0-9])", lambda m: m.group(1).upper(), snake)
    out = []
    for k in (key, camel, snake):
        if k not in out:
            out.append(k)
    return out


def ai_extract_formula(action_field_id: str, key: str) -> str:
    """
    Formula that extracts `key` from an AI column's output whatever the key casing:
        {{f_ai}}?.roleBucket ?? {{f_ai}}?.role_bucket
    A single-word key needs one path. Verified live: Clay supports `??`, and a
    camelCase-only formula on snake_case output reads back empty with status SUCCESS.
    """
    ref = "{{%s}}" % action_field_id

    def path(k):
        return f"{ref}?.{k}" if _IDENT_RE.match(k) else f"{ref}?.[{json.dumps(k)}]"

    return " ?? ".join(path(k) for k in ai_key_variants(key))


def guess_route_column_types(row_data: dict) -> dict:
    """{column name: type} for routed identity columns, inferred from the name:
    email -> email; domain / website / url / linkedin -> url. Others stay text."""
    types = {}
    for name in row_data or {}:
        low = name.lower()
        if "email" in low:
            types[name] = "email"
        elif any(w in low for w in ("domain", "website", "url", "linkedin")):
            types[name] = "url"
    return types


_LINK_WORDS = ("domain", "website", "url", "linkedin")
_NOT_LINK_WORDS = ("status", "count", "verdict", "gate", "check:", "note", "source", "match type", "type", "?")


def guess_column_data_type(name: str) -> "str | None":
    """Data type implied by a column NAME (LEARNINGS.md backlog #54, House rule
    2026-10-08: domain / link columns must be clickable). email -> "email";
    domain / website / url / linkedin -> "url"; None when the name is a status, count,
    verdict, gate or note about a link ("Website Status", "LinkedIn Found?")."""
    low = (name or "").lower()
    if any(w in low for w in _NOT_LINK_WORDS):
        return None
    if "email" in low:
        return "email"
    if any(w in low for w in _LINK_WORDS):
        return "url"
    return None


def view_filter(field_id: str, operator: str, value: Any = None) -> dict:
    """One view filter condition. value is omitted for EMPTY/NOT_EMPTY/CHECKED/status operators;
    CONTAIN_ANY / NOT_CONTAIN_ANY take a list. EQUAL is case-sensitive, CONTAIN is not."""
    item = {"type": operator, "fieldId": field_id}
    if value is not None:
        item["value"] = value
    return item


# ── Search DSL validation (LEARNINGS.md #25, #13; verified live 2026-09-29) ──

# The only values Clay accepts for company_size (LinkedIn buckets, comma thousands separators).
COMPANY_SIZE_BUCKETS = ("1", "2-10", "11-50", "51-200", "201-500", "501-1,000",
                        "1,001-5,000", "5,001-10,000", "10,001+")

# Keys that return 400 "Unknown field" in company scope. Only `domain` identifies a company
# (`select from companies`) and only `company.domain` inside people `experiences.count(...)`.
_DSL_BAD_COMPANY_KEYS = ("clay_company_id", "linkedin_url", "social_urls.linkedin", "url", "website",
                         "name", "company_name", "org_name", "linkedin_company_id", "id", "size",
                         "country", "country_name")
_DSL_KEY_HINT = ("Only `domain` (companies) / `company.domain` (people experiences) filter a company; "
                 "for a LinkedIn-scoped list use clay.filter_to_companies(@table(\"t:v:f\")) in a people "
                 "query. See action-registry.md > Search DSL > Filterable company keys.")


def _strip_count_blocks(query: str, collection: str) -> str:
    """Remove `<collection>.count( ... )` sub-expressions (balanced parens) from a DSL query."""
    out, i, tag = [], 0, collection + ".count("
    while True:
        j = query.find(tag, i)
        if j < 0:
            out.append(query[i:]); return "".join(out)
        out.append(query[i:j]); k, depth = j + len(tag), 1
        while k < len(query) and depth:
            depth += {"(": 1, ")": -1}.get(query[k], 0); k += 1
        i = k


def us_hq_filter(countries=("United States",), hq_only: bool = True) -> str:
    """Company-scope country filter for `select from companies` (LEARNINGS.md #58). hq_only=True
    keeps companies HEADQUARTERED in the countries; False = any location there (pulls foreign HQs)."""
    names = ", ".join(f'"{c}"' for c in countries)
    cond = f"country_name in ({names})" if len(countries) > 1 else f'country_name = "{countries[0]}"'
    if hq_only:
        cond += " and is_headquarters = true"
    return f"locations.count({cond}) >= 1"


def validate_dsl_query(query: str) -> None:
    """
    Raise ValueError before the call for Search DSL mistakes Clay only reports as a 400:
    a company_size value outside COMPANY_SIZE_BUCKETS ("501-1000" instead of "501-1,000"),
    or filtering a company by a key Clay does not index (LinkedIn URL, id, name).
    """
    for m in re.finditer(r"company_size\s*(?:not_in|in|=|!=)\s*(\([^)]*\)|\"[^\"]*\")", query):
        for value in re.findall(r"\"([^\"]*)\"", m.group(1)):
            if value not in COMPANY_SIZE_BUCKETS:
                raise ValueError(f"company_size {value!r} is not a Clay bucket; use one of "
                                 f"{', '.join(COMPANY_SIZE_BUCKETS)}")
    op = r"\s*(?:=|!=|\bin\b|\bnot_in\b|\bis_similar_to\b)"
    for key in _DSL_BAD_COMPANY_KEYS:
        if re.search(r"\bcompany\." + re.escape(key) + op, query):
            raise ValueError(f"'company.{key}' is not filterable in a Search DSL query. {_DSL_KEY_HINT}")
    if re.match(r"\s*select\s+from\s+companies\b", query, re.I):
        # country_name / is_headquarters ARE valid inside locations.count(...) (LEARNINGS.md #58,
        # verified 2026-10-13): drop those sub-expressions before checking top-level keys.
        top = _strip_count_blocks(query, "locations")
        for key in _DSL_BAD_COMPANY_KEYS:
            if re.search(r"(?<![\w.])" + re.escape(key) + op, top):
                raise ValueError(f"'{key}' is not filterable on companies. {_DSL_KEY_HINT}")


# Formula columns send_search_dsl_to_table(extra_columns=...) can add on a people source (#31).
DSL_EXTRA_COLUMNS = {
    "company_domain": ("Company Domain", ".matched_experience.company.domain"),
    "company_linkedin": ("Company LinkedIn", ".matched_experience.company.social_urls.linkedin"),
    "clay_company_id": ("Clay Company ID", ".matched_experience.company.clay_company_id"),
    "start_date": ("Start Date", ".matched_experience.start_date"),
    "clay_profile_id": ("Clay Profile ID", ".clay_metadata.clay_profile_id"),
}


# Cell statuses after which a run is finished (run_paced). Clay also sets ERROR_<REASON>
# statuses (live 2026-09-29: ERROR_RUN_CONDITION_NOT_MET, not the view-filter name
# RUN_CONDITION_NOT_MET; ERROR_OUT_OF_CREDITS), which are final too. See _run_finished().
RUN_TERMINAL_STATUSES = frozenset({"SUCCESS", "ERROR", "RUN_CONDITION_NOT_MET", "MISSING_INPUT"})


def _run_finished(status) -> bool:
    return status in RUN_TERMINAL_STATUSES or str(status or "").startswith("ERROR_")
CLAY_CREDIT_WARN_BALANCE = 100  # warn when a clay-* model column is cloned below this balance


def _binding_value(type_settings: dict, name: str):
    """Literal value of one inputsBinding (e.g. model '"clay-argon"' -> 'clay-argon')."""
    for b in (type_settings or {}).get("inputsBinding") or []:
        if b.get("name") == name and b.get("formulaText"):
            try:
                v = json.loads(b["formulaText"])
            except ValueError:
                return b["formulaText"]
            return v if isinstance(v, str) else b["formulaText"]
    return None


# DSL people preview rows are FLAT (LEARNINGS.md #31); matched_experiences entries are
# [company, title, location, start_date, end_date, is_current].
_PREVIEW_EXPERIENCE_KEYS = ("company", "title", "location", "start_date", "end_date", "is_current")


def parse_dsl_preview_row(row: dict) -> dict:
    """
    Name the fields of one search_dsl_preview() people row. Preview rows are not the
    table payload: there is no company domain, and the matched experience is a list,
    so table paths (matched_experience.company.domain) read None on preview data.
    """
    exps = [dict(zip(_PREVIEW_EXPERIENCE_KEYS, e)) for e in (row.get("matched_experiences") or [])
            if isinstance(e, (list, tuple))]
    first = exps[0] if exps else {}
    return {
        "clay_profile_id": row.get("id"),
        "name": row.get("name"),
        "linkedin_url": row.get("url"),
        "location": row.get("location_name"),
        "latest_company": row.get("latest_experience_company"),
        "latest_title": row.get("latest_experience_title"),
        "matched_company": first.get("company"),
        "matched_title": first.get("title"),
        "matched_start_date": first.get("start_date"),
        "matched_is_current": first.get("is_current"),
        "matched_experiences": exps,
    }


def best_company_for_domain(domain: str, companies: list[dict]):
    """
    Pick the likeliest real company among the entities Clay files under one domain
    (LEARNINGS.md #16): name or LinkedIn slug equal to the domain root first, then the
    larger company_size bucket. Returns None for an empty list.
    """
    if not companies:
        return None
    root = (domain or "").lower().split(".")[0]

    def norm(s):
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    def key(c):
        slug = (c.get("linkedin_url") or "").rstrip("/").rsplit("/", 1)[-1]
        exact = norm(c.get("name")) == norm(root) or norm(slug) == norm(root)
        size = COMPANY_SIZE_BUCKETS.index(c["size"]) if c.get("size") in COMPANY_SIZE_BUCKETS else -1
        return (exact, size)

    return max(companies, key=key)


# ── Formula lint + readers (LEARNINGS.md #35, #27) ──

def lint_clay_formula(formula_text: str) -> list[str]:
    """
    Problems Clay does not report. Spread syntax and `new Set` make a formula return
    EMPTY on every row with no error (LEARNINGS.md #35, Plant City: blank on 469 rows).
    """
    issues = []
    text = formula_text or ""
    if re.search(r"\bnew\s+Set\b", text):
        issues.append("uses `new Set`: Clay returns EMPTY silently. Dedupe with "
                      "arr.filter((v, i, a) => a.indexOf(v) === i)")
    if re.search(r"(?<![.\w])\.\.\.\s*[\w\[({]", text):
        issues.append("uses spread syntax (`...`): Clay returns EMPTY silently. Use "
                      "concat / Object.assign / arr.slice() instead")
    if re.search(r"\\u[0-9a-fA-F]{4}|\\u\{[0-9a-fA-F]+\}", text):
        issues.append("uses a \\uXXXX escape: Clay's parser rejects it "
                      "(INVALID_FORMULA_PARSING_FAILED, old values kept). Put the literal "
                      "character in instead; build text with json.dumps(ensure_ascii=False) "
                      "(LEARNINGS.md #56)")
    return issues


def formula_logic(type_settings: dict) -> str:
    """
    The logic a formula column actually runs, as text. Waterfall formulas
    (formulaType "waterfall") keep it in typeSettings.formulaWaterfall[] and have NO
    formulaText, so a reader that only looks at formulaText sees nothing (LEARNINGS.md #27).
    First non-empty branch wins.
    """
    ts = type_settings or {}
    branches = ts.get("formulaWaterfall")
    if ts.get("formulaType") == "waterfall" or branches:
        lines = []
        for i, b in enumerate(branches or [], 1):
            if not isinstance(b, dict):   # older UI waterfalls store bare formula strings (LEARNINGS #42)
                b = {"formula": str(b)}
            label = f"  # {b['prompt']}" if b.get("prompt") else ""
            lines.append(f"{i}. {b.get('formula', '')}{label}")
        return "WATERFALL (first non-empty wins):\n" + "\n".join(lines)
    return ts.get("formulaText") or ""


def _label_tokens(text: str) -> set:
    """Quoted literals and numbers in a formula or its English label, lowercased."""
    text = text or ""
    quoted = re.findall(r"[\"']([^\"']{2,})[\"']", text)
    numbers = re.findall(r"(?<![\w{])\d+(?:\.\d+)?(?![\w}])", text)
    return {t.strip().lower() for t in quoted + numbers if t.strip()}


def label_drift(label: str, formula: str, column_names: list = None) -> list[str]:
    """
    Things the plain-English label (conditionalRunFormulaPrompt / waterfall prompt) names
    that the formula does not use: quoted values, numbers and column names. Clay does not
    keep the label in sync when the formula is edited (LEARNINGS.md #27). Heuristic: an
    empty list is not proof the two agree.
    """
    if not label or not formula:
        return []
    f_low = formula.lower()
    missing = sorted(t for t in _label_tokens(label) if t not in f_low)
    for name in column_names or []:
        if name and len(name) > 2 and re.search(r"\b" + re.escape(name.lower()) + r"\b", label.lower()) \
                and "{{@" + name.lower() + "}}" not in f_low and name.lower() not in f_low:
            missing.append(f"column '{name}'")
    return missing


def _validation_action_config(sequence_steps: list):
    """Group-level validationActionConfig (the waterfall v2 body key, LEARNINGS.md #87) read back
    from the steps' `validation` slots: one validation provider for every step, input "email"."""
    for s in sequence_steps or []:
        v = s.get("validation")
        if v and v.get("actionKey"):
            email_input = next((b["name"] for b in v.get("inputsBinding") or []), "email")
            return {"actionKey": v["actionKey"], "actionPackageId": v["actionPackageId"],
                    "inputName": email_input, "authAccountId": v.get("authAccountId")}
    return None


# Addition beyond upstream v2.1 (LEARNINGS.md backlog #86): the plain-English box above a formula in
# Clay ("Reference data from a column, use a formula...") is typeSettings.formulaPrompt, a JS
# string expression: quoted text joined with + to {{f_id}} refs (shown as column chips). Clay
# never regenerates it when formulaText changes, so Rex writes it with every formula.
_FIELD_REF = re.compile(r"\{\{(f_[A-Za-z0-9_]+)\}\}")


def build_formula_prompt(parts, name_to_id: dict = None) -> str:
    """
    formulaPrompt from plain parts. parts is a string or a list of strings; a part that is
    "[Column Name]" (looked up in name_to_id) or "{{f_id}}" becomes a column chip, anything
    else is literal text. A string that already starts with '"' is returned as-is (a raw
    prompt expression).
        build_formula_prompt(["True if ", "[Verdict]", " is \"GTG\""], {"Verdict": "f_1"})
        -> '"True if "+{{f_1}}+" is \\"GTG\\""'
    """
    if isinstance(parts, str):
        if parts.lstrip().startswith('"'):
            return parts
        parts = [parts]
    out = []
    for p in parts:
        m = re.fullmatch(r"\[(.+)\]", p)
        if m:
            fid = (name_to_id or {}).get(m.group(1))
            if not fid:
                raise ValueError(f"formula prompt: unknown column {m.group(1)!r}")
            out.append("{{%s}}" % fid)
        elif _FIELD_REF.fullmatch(p):
            out.append(p)
        else:
            out.append('"' + p.replace("\\", "\\\\").replace('"', '\\"') + '"')
    return "+".join(out)


def formula_prompt_gaps(formula_text: str, formula_prompt: str) -> list[str]:
    """Field ids the formula references that its prompt never names (stale prompt)."""
    return sorted(set(_FIELD_REF.findall(formula_text or "")) - set(_FIELD_REF.findall(formula_prompt or "")))


# Addition beyond upstream v2.1 (LEARNINGS.md #35): which Clay billing model each workspace is on.
# "legacy" = old plan, consumes NO Clay actions (only data credits), so action-heavy work (HTTP API
# on your own endpoints, own-key and provider enrichments; lookups are free on every plan) can run inside Clay with full lineage.
# "actions" = new plan, 1 action per row per action run: propose running action-heavy work OUTSIDE
# Clay and writing results back with update_records(). Only add a workspace here once you have
# confirmed its plan; anything missing is "unknown" and must be asked, never assumed.
# create_records() refuses more rows than this per call without allow_bulk_api_rows=True
# (lineage rule, LEARNINGS.md #15/#48). Small enough for a 2-row test of a new table.
API_ROW_WRITE_LIMIT = 2

# Add your own workspaces here (the id is the number in app.clay.com/workspaces/<id>/...), e.g.
#     123456: "legacy",   # main workspace, old plan
#     234567: "actions",  # new Clay plan
WORKSPACE_BILLING: dict = {}


def workspace_billing(workspace_id) -> str:
    """'legacy' | 'actions' | 'unknown' for a Clay workspace id (see WORKSPACE_BILLING)."""
    try:
        return WORKSPACE_BILLING.get(int(workspace_id), "unknown")
    except (TypeError, ValueError):
        return "unknown"


class _TimeoutSession(requests.Session):
    """requests.Session that applies a default timeout to every request."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        super().__init__()
        self.default_timeout = timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.default_timeout)
        return super().request(method, url, **kwargs)


def default_view_id(table: dict):
    """The table's Default view id. Use this, never views[0]: the views list comes back in no
    fixed order (a client's Oct 2026 tables listed "All rows", "Support view" or "Non enrichment
    columns" first), so views[0] put a GTG filter and a paid run on the wrong view
    (LEARNINGS.md 2026-10-20, backlog #71). Order: firstViewId, a view named "Default view",
    then the first view."""
    table = table.get("table", table)
    views = table.get("views") or table.get("gridViews") or []
    if table.get("firstViewId"):
        return table["firstViewId"]
    named = next((v["id"] for v in views if v.get("name") == "Default view"), None)
    return named or (views[0]["id"] if views else None)


class ClayClient:
    def __init__(self, workspace_id: int = None, timeout: float = DEFAULT_TIMEOUT):
        self.session = _TimeoutSession(timeout)
        self.session.headers.update(HEADERS)
        self._load_cookies()
        me = self.me()
        self.user_id = me["id"]
        self._table_ws: dict = {}
        self.workspace_id = workspace_id or self._default_workspace()
        print(f"[clay] logged in as {me.get('email')} | workspace {self.workspace_id} "
              f"(billing: {workspace_billing(self.workspace_id)})")

    def _load_cookies(self):
        session_file = os.path.join(os.path.dirname(__file__), "clay-session.json")
        with open(session_file) as f:
            data = json.load(f)
        value = data.get("claysession") or data.get("__Host-claysession")
        # Clay renamed the cookie to the host-only "__Host-claysession" (LEARNINGS #63, 2026-10-15);
        # the old name alone now gets 401 "You must be logged in". Send both so either works.
        self.session.cookies.set("__Host-claysession", value, domain="api.clay.com")
        self.session.cookies.set("claysession", value, domain=".clay.com")

    def _default_workspace(self) -> int:
        """First entry of /my-workspaces. That order can change when a workspace is added
        (LEARNINGS.md #30: it changed on 2026-09-29 when a workspace was added), so warn when
        there is more than one. Table-scoped helpers don't depend on it (see table_workspace)."""
        res = self.get("/my-workspaces")
        ws = res.get("results", res) if isinstance(res, dict) else res
        if len(ws) > 1:
            listed = ", ".join(f"{w['id']} ({w.get('name', '?')})" for w in ws)
            print(f"[clay] WARNING: no workspace_id given and you belong to {len(ws)} workspaces "
                  f"({listed}); defaulting to the first, {ws[0]['id']}. Pass workspace_id= "
                  f"for anything workspace-scoped (search DSL, list_tables, app accounts).")
        return ws[0]["id"]

    def billing_model(self, table_id: str = None) -> str:
        """Billing model of the table's own workspace (or the client default): 'legacy' (no
        actions consumed), 'actions' (new plan) or 'unknown' (ask before an action-heavy run).
        Addition beyond upstream v2.1, LEARNINGS.md #35."""
        ws = self.table_workspace(table_id) if table_id else self.workspace_id
        return workspace_billing(ws)

    def table_workspace(self, table_id: str) -> int:
        """
        The workspace a table actually lives in, read from the table itself (cached).

        Addition beyond upstream v2.1 (LEARNINGS.md #30): workspace-scoped table paths
        (/workspaces/{ws}/tables/{t}/...) 404 when {ws} is not the table's workspace,
        while plain /tables/{t} paths keep working, so a client on the wrong default
        workspace half-succeeds. Every table-scoped helper that needs a workspace in
        its path or body uses this instead of self.workspace_id.
        """
        if getattr(self, "_table_ws", None) is None:
            self._table_ws = {}
        if table_id not in self._table_ws:
            raw = self.get_table(table_id)
            table = raw.get("table", raw)
            ws = table.get("workspaceId")
            if ws is None:
                return self.workspace_id
            ws = int(ws)
            if str(ws) != str(self.workspace_id):
                print(f"[clay] note: table {table_id} is in workspace {ws}, client is on "
                      f"{self.workspace_id}; using {ws} for this table's workspace-scoped calls.")
            self._table_ws[table_id] = ws
        return self._table_ws[table_id]

    def _ws_table_path(self, table_id: str) -> str:
        return f"/workspaces/{self.table_workspace(table_id)}/tables/{table_id}"

    def _url(self, path: str) -> str:
        return f"{BASE}{path}"

    def get(self, path: str, **kwargs) -> Any:
        r = self.session.get(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict = None, **kwargs) -> Any:
        r = self.session.post(self._url(path), json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    def patch(self, path: str, body: dict = None, **kwargs) -> Any:
        r = self.session.patch(self._url(path), json=body, **kwargs)
        r.raise_for_status()
        return r.json()

    def delete(self, path: str, **kwargs) -> Any:
        r = self.session.delete(self._url(path), **kwargs)
        r.raise_for_status()
        return r.json()

    # ── Auth ──────────────────────────────────────────────────────────────────

    def me(self) -> dict:
        return self.get("/me")

    # ── Workspaces / Tables ───────────────────────────────────────────────────

    def list_tables(self, folder_id: str = None) -> list[dict]:
        """List all tables in the workspace, optionally filtered by folder."""
        params = {}
        if folder_id:
            params["parentFolderId"] = folder_id
        res = self.get(f"/workspaces/{self.workspace_id}/tables", params=params)
        return res.get("results", res)

    def list_folders(self) -> list[dict]:
        """List top-level folders and resources."""
        body = {"parentResource": None, "filters": {}, "isGlobalSearch": False}
        res = self.post(f"/workspaces/{self.workspace_id}/resources_v2/", body)
        return res.get("resources", [])

    # ── Folders + workbooks (LEARNINGS.md #34, #37, #26; verified live 2026-09-29) ──

    def create_folder(self, name: str, parent_folder_id: str = None) -> dict:
        """Create a folder (top level, or inside parent_folder_id). Returns the folder dict."""
        body = {"name": name}
        if parent_folder_id:
            body["parentFolderId"] = parent_folder_id
        folder = self.post(f"/workspaces/{self.workspace_id}/folders", body)
        if folder.get("name") != name or folder.get("parentFolderId") != parent_folder_id:
            raise ClayTableConfigError(f"folder {folder.get('id')}: wanted name {name!r} in "
                                       f"{parent_folder_id!r}, Clay has {folder.get('name')!r} in "
                                       f"{folder.get('parentFolderId')!r}")
        return folder

    def list_folder(self, folder_id: str) -> list[dict]:
        """
        Resources (folders, workbooks) inside one folder. The body needs
        {"parentResource": {"type": "FOLDER", "id": ...}}: a top-level parentFolderId
        key is ignored and returns the ROOT listing, which looks like 'not placed'.
        """
        body = {"parentResource": {"type": "FOLDER", "id": folder_id},
                "filters": {}, "isGlobalSearch": False}
        res = self.post(f"/workspaces/{self.workspace_id}/resources_v2/", body)
        return res.get("resources", [])

    def get_workbook(self, workbook_id: str) -> dict:
        """Workbook dict incl. name, description, parentFolderId, settings."""
        return self.get(f"/workspaces/{self.workspace_id}/workbooks/{workbook_id}")

    def create_workbook(self, name: str, folder_id: str = None, auto_run: bool = False) -> dict:
        """Create a workbook, optionally inside folder_id; reads back its folder."""
        body = {"name": name, "workspaceId": self.workspace_id,
                "settings": {"isAutoRun": bool(auto_run)}}
        if folder_id:
            body["parentFolderId"] = folder_id
        wb = self.post("/workbooks", body)
        if folder_id:
            placed = self.get_workbook(wb["id"]).get("parentFolderId")
            if placed != folder_id:
                raise ClayTableConfigError(f"workbook {wb['id']}: wanted folder {folder_id}, "
                                           f"Clay has {placed!r}")
        return wb

    def set_workbook_description(self, workbook_id: str, description: str) -> dict:
        """
        Set the description Clay shows under Workbook settings -> Description (the place
        to put a workbook guide). A table-level description stores fine but is not shown
        where people look (LEARNINGS.md #26). Reads back.
        """
        self.patch(f"/workspaces/{self.workspace_id}/workbooks/{workbook_id}",
                   {"description": description})
        wb = self.get_workbook(workbook_id)
        if wb.get("description") != description:
            raise ClayTableConfigError(f"workbook {workbook_id}: description did not stick")
        return wb

    def get_table(self, table_id: str) -> dict:
        return self.get(f"/tables/{table_id}")

    def create_table(self, name: str, workbook_id: str = None,
                     auto_run: bool = False, remove_placeholder: bool = True,
                     folder_id: str = None) -> dict:
        """
        Create a new workbook + table. Returns the table dict (as read back).

        auto_run defaults to False. With auto-run on, Clay runs every paid
        column on every existing and new row as soon as the column is added,
        which can burn through a credit budget in minutes. Leave it off and
        trigger runs explicitly with run_column() / run_and_wait() on a few
        records first. Pass auto_run=True only when you really want it.

        Addition beyond upstream v2.1 (LEARNINGS.md backlog #14, #18), verified live
        2026-09-25: Clay ignores both the name and the workbook's isAutoRun.
        Every new table comes back named "Custom Table" (or "Custom Table (2)")
        with tableSettings.AUTO_RUN_ON true, plus a blank text column
        "New Column" and one blank row. So after the create this PATCHes the
        name and AUTO_RUN_ON, reads the table back (ClayTableConfigError if
        either still differs) and, unless remove_placeholder=False, deletes
        the blank row(s) and the empty "New Column".

        folder_id (LEARNINGS.md #34): put the NEW workbook in this folder. Only valid
        without workbook_id (an existing workbook keeps its folder).
        """
        if folder_id and workbook_id:
            raise ValueError("folder_id only applies when creating a new workbook; "
                             "omit workbook_id or folder_id")
        if not workbook_id:
            workbook_id = self.create_workbook(name, folder_id=folder_id, auto_run=auto_run)["id"]

        res = self.post("/tables", {
            "icon": {"emoji": "🪄"},
            "workspaceId": str(self.workspace_id),
            "type": "spreadsheet",
            "template": "basic",
            "workbookId": workbook_id,
            "callerName": "clay-client",
            "sourceSettings": {},
        })
        table_id = res["table"]["id"]
        table = self._settle_new_table(table_id, name, auto_run)
        if remove_placeholder:
            self._remove_placeholder(table)
            table = self.get_table(table_id)
            table = table.get("table", table)
        table["workbookId"] = table.get("workbookId") or workbook_id
        return table

    def _settle_new_table(self, table_id: str, name: str, auto_run: bool = False) -> dict:
        """PATCH name + AUTO_RUN_ON, read back, retry the name once, raise if still wrong."""
        wanted = {"AUTO_RUN_ON": bool(auto_run)}
        self.patch(f"/tables/{table_id}", {"name": name, "tableSettings": wanted})
        for attempt in range(2):
            table = self.get_table(table_id)
            table = table.get("table", table)
            name_ok = table.get("name") == name
            run_ok = (table.get("tableSettings") or {}).get("AUTO_RUN_ON") is bool(auto_run)
            if name_ok and run_ok:
                return table
            if attempt == 0:
                self.patch(f"/tables/{table_id}", {"name": name, "tableSettings": wanted})
        raise ClayTableConfigError(
            f"table {table_id}: wanted name {name!r} and AUTO_RUN_ON={bool(auto_run)}, Clay has "
            f"name {table.get('name')!r} and tableSettings {table.get('tableSettings')}")

    def _remove_placeholder(self, table: dict) -> None:
        """Delete the blank row(s) and the empty "New Column" Clay adds to a new table."""
        table_id = table["id"]
        system = {"f_created_at", "f_updated_at"}
        placeholder = [f["id"] for f in table.get("fields", [])
                       if f.get("type") == "text" and f.get("name") == "New Column"]
        views = table.get("views") or []
        view_id = table.get("firstViewId") or (views[0]["id"] if views else None)
        rows = self.list_records(table_id, view_id) if view_id else []

        def empty(cell):
            return not isinstance(cell, dict) or cell.get("value") in (None, "")

        blank = [r["id"] for r in rows
                 if all(empty(v) for fid, v in (r.get("cells") or {}).items() if fid not in system)]
        # Only a brand-new table (every row blank) loses its rows.
        if blank and len(blank) == len(rows):
            self.delete_records(table_id, blank)
        for field_id in placeholder:
            if all(empty((r.get("cells") or {}).get(field_id)) for r in rows):
                self.delete_column(table_id, field_id)

    # ── Fields (Columns) ──────────────────────────────────────────────────────

    def get_schema(self, table_id: str, view_id: str) -> dict:
        """Get table schema including all field definitions."""
        return self.get(f"/tables/{table_id}/views/{view_id}/table-schema-v2")

    def create_column(self, table_id: str, column_def: dict, view_id: str = None) -> dict:
        """
        Add a column to a table.
        column_def matches the Clay JSON schema format from clay-api-reference.md.

        Addition beyond upstream v2.1 (LEARNINGS.md backlog #12): Clay answers 400
        "Missing data type settings." to a text or formula column without
        typeSettings.dataTypeSettings, so it defaults to {"type": "text"}
        when omitted. Any value you pass is kept.

        Examples:
            # Text column (dataTypeSettings defaults to text)
            {"type": "text", "name": "Company Name"}

            # Formula column
            {"type": "formula", "name": "Email",
             "typeSettings": {"formulaText": "{{f_abc123}}?.email", "dataTypeSettings": {"type": "email"}}}

            # Action column (enrichment)
            {"type": "action", "name": "Find Work Email",
             "typeSettings": {
               "actionKey": "leadmagic-find-work-email",
               "actionPackageId": "edb58209-a62d-42be-992a-e41b87eeacc2",
               "inputsBinding": [...],
               "authAccountId": "aa_..."
             }}
        """
        body = copy.deepcopy(column_def)
        if body.get("type") in ("text", "formula"):
            ts = body["typeSettings"] = body.get("typeSettings") or {}
            if not ts.get("dataTypeSettings"):
                ts["dataTypeSettings"] = {"type": "text"}
            for issue in lint_clay_formula(ts.get("formulaText")):
                warnings.warn(f"formula column '{body.get('name')}': {issue} (LEARNINGS.md #35)")
        if view_id:
            body["activeViewId"] = view_id
        res = self.post(f"/tables/{table_id}/fields", body)
        field = res.get("field", res)
        if isinstance(field, dict) and field.get("settingsError"):
            raise ClayColumnConfigError(
                f"Clay rejected column '{column_def.get('name')}' ({field.get('id')}): "
                f"{field['settingsError']}"
            )
        return field

    def get_column(self, table_id: str, field_id: str) -> dict:
        """Return one column's live definition (including full typeSettings)."""
        raw = self.get_table(table_id)
        for f in raw.get("table", raw).get("fields", []):
            if f.get("id") == field_id:
                return f
        raise ValueError(f"Field {field_id} not found in table {table_id}")

    def _table_fields(self, table_id: str) -> list:
        raw = self.get_table(table_id)
        return raw.get("table", raw).get("fields", [])

    def audit_formula_prompts(self, table_id: str) -> list[dict]:
        """
        Formula columns whose plain-English prompt (formulaPrompt) is missing or stale, i.e.
        does not name every column the formula uses (LEARNINGS.md #86). Read-only.
        Returns [{"id", "name", "status": "missing"|"stale", "missing_columns": [names]}].
        Columns whose formula only reads one source/enrichment path are reported as
        "missing" too; decide per column whether a prompt is worth writing.
        """
        fields = self._table_fields(table_id)
        names = {f["id"]: f["name"] for f in fields}
        out = []
        for f in fields:
            ts = f.get("typeSettings") or {}
            if f.get("type") != "formula" or not ts.get("formulaText"):
                continue
            prompt = ts.get("formulaPrompt")
            if not prompt:
                out.append({"id": f["id"], "name": f["name"], "status": "missing", "missing_columns": []})
                continue
            gaps = formula_prompt_gaps(ts["formulaText"], prompt)
            if gaps:
                out.append({"id": f["id"], "name": f["name"], "status": "stale",
                            "missing_columns": [names.get(g, g) for g in gaps]})
        return out

    def update_column(self, table_id: str, field_id: str, updates: dict,
                      replace: bool = False, lint: bool = True,
                      require_prompt: bool = True) -> dict:
        """
        Rename or update a column's settings.

        Clay's PATCH replaces the whole typeSettings object. Sending only the
        keys you want to change silently wipes the rest (model, auth account,
        output schema, prompt bindings) and leaves an AI or enrichment column
        broken. To prevent that, when `updates` contains "typeSettings" this
        method reads the live column first and merges your changes into it:

          - nested dicts are merged key by key
          - inputsBinding is merged by input "name": for a listed input, only
            the keys you pass (e.g. formulaText, formulaMap) are replaced; an
            input with a new name is appended; unlisted inputs are kept
          - a value of None removes that key

        A new formulaText is linted first (lint_clay_formula, e.g. spread syntax): Clay
        accepts an unparseable formula, sets settingsError and keeps every cell's OLD
        value (LEARNINGS.md #53). lint=False skips it.
        A new formulaText on a formula column must come with a formulaPrompt (the
        plain-English box; a list of parts is built with build_formula_prompt, column
        names as "[Name]"), and the prompt must name every column the formula uses
        (LEARNINGS.md #86). require_prompt=False (or replace=True) skips this.
        Pass replace=True to send typeSettings exactly as given (full
        replacement). Updates without typeSettings (e.g. a rename) are sent
        as-is. Always read the column back afterwards and, for action
        columns, re-run one record before trusting the change.
        """
        body = dict(updates)
        formula = (body.get("typeSettings") or {}).get("formulaText")
        if formula and lint:
            issues = lint_clay_formula(formula)
            if issues:   # LEARNINGS.md #53: a formula Clay cannot parse keeps stale cells silently
                raise ValueError(f"formula update on {field_id}: " + "; ".join(issues))
        ts_in = body.get("typeSettings") or {}
        if isinstance(ts_in.get("formulaPrompt"), list):
            names = {f["name"]: f["id"] for f in self._table_fields(table_id)}
            body["typeSettings"] = ts_in = {**ts_in, "formulaPrompt": build_formula_prompt(ts_in["formulaPrompt"], names)}
        if formula and require_prompt and not replace and "formulaPrompt" not in ts_in \
                and not (ts_in.get("inputsBinding") or ts_in.get("actionKey")):
            raise ClayColumnConfigError(
                f"formula update on {field_id} without formulaPrompt: pass the plain-English "
                "prompt too (typeSettings.formulaPrompt, list of parts with '[Column]' chips), "
                "or require_prompt=False (LEARNINGS.md #86)")
        if formula and require_prompt and ts_in.get("formulaPrompt"):
            gaps = formula_prompt_gaps(formula, ts_in["formulaPrompt"])
            if gaps:
                raise ClayColumnConfigError(
                    f"formulaPrompt on {field_id} does not name columns the formula uses: {gaps}")
        if "typeSettings" in body and not replace:
            current = self.get_column(table_id, field_id).get("typeSettings") or {}
            body["typeSettings"] = merge_type_settings(current, body["typeSettings"])
        return self.patch(f"/tables/{table_id}/fields/{field_id}", body)

    def clone_column(self, source_table_id: str, source_field_id: str,
                     table_id: str, name: str,
                     input_overrides: dict = None,
                     condition: str = None,
                     view_id: str = None,
                     use_case: str = None) -> dict:
        """
        Create a new column by copying a known-good live column's full
        typeSettings, then swapping only the inputs you name.

        This is the safest way to build AI (Use AI / Claygent) columns: the
        model, auth account, output schema (answerSchemaType) and internal
        inputs come from a column you already know runs, instead of being
        hand-assembled. Hand-built AI configs can be accepted by Clay and then
        never run (cells stay queued).

        input_overrides: {input_name: formulaText}, e.g.
            {"prompt": '"Summarize: " + {{f_xxx}}'}
        condition: new "Only run if" formula. None keeps the source column's
            condition; "" removes it.

        Formula references ({{f_...}}) inside the copied settings still point
        at the SOURCE table's fields. When cloning across tables, override
        every input (and the condition) that references a field.

        use_case (LEARNINGS.md backlog #1): "use-ai" or "claygent" for
            AI columns. A clone silently inherits the source's use case, so
            cloning a Claygent (a browsing agent) REQUIRES an explicit use_case:
            "use-ai" when the prompt only works on data already on the row
            (classify, extract, score, rewrite), "claygent" only when it must
            research the live web. The bound use case is read back after create.
        """
        src = self.get_column(source_table_id, source_field_id)
        ts = copy.deepcopy(src.get("typeSettings") or {})
        src_use_case = _use_case_of(ts)
        explicit = use_case is not None or "useCase" in (input_overrides or {})
        if use_case is not None:
            if use_case not in AI_USE_CASES:
                raise ValueError(f"use_case must be one of {AI_USE_CASES}, got {use_case!r}")
            if src_use_case is None:
                raise ValueError(f"source column {source_field_id} has no useCase input; "
                                 f"use_case only applies to Use AI / Claygent columns")
        elif src_use_case == "claygent" and not explicit:
            raise ValueError(
                f"source column {source_field_id} is a Claygent (browsing agent) and the clone "
                f"would silently inherit that. Pass use_case='use-ai' if the prompt only works on "
                f"row data (classification, extraction, scoring), or use_case='claygent' only if "
                f"it must research the live web. See tools/rex/LEARNINGS.md backlog #1.")
        if input_overrides:
            ts = merge_type_settings(ts, {"inputsBinding": [
                {"name": k, "formulaText": v} for k, v in input_overrides.items()
            ]})
        if use_case is not None:
            ts = merge_type_settings(ts, {"inputsBinding": [
                {"name": "useCase", "formulaText": json.dumps(use_case)}]})
        if condition == "":
            ts.pop("conditionalRunFormulaText", None)
        elif condition is not None:
            ts["conditionalRunFormulaText"] = condition
        model = _binding_value(ts, "model")
        if model and model.startswith("clay-"):
            # Clay-native models bill Clay CREDITS, not the workspace model key: with ~0.1
            # credits every cell returned ERROR_OUT_OF_CREDITS (LEARNINGS.md AI-models row).
            try:
                balance = self.credit_balance()
            except Exception:
                balance = None
            if balance is None or balance < CLAY_CREDIT_WARN_BALANCE:
                warnings.warn(f"clone '{name}' uses {model}, which bills Clay credits; workspace "
                              f"balance is {balance if balance is not None else 'unknown'}. Cells will "
                              f"fail ERROR_OUT_OF_CREDITS when it runs out.")
        created = self.create_column(table_id, {
            "type": src.get("type", "action"), "name": name, "typeSettings": ts,
        }, view_id=view_id)
        intended = _use_case_of(ts)
        if intended is not None:
            field = created.get("field", created) if isinstance(created, dict) else {}
            bound_ts = field.get("typeSettings")
            if bound_ts is None:
                bound_ts = self.get_column(table_id, field["id"]).get("typeSettings")
            bound = _use_case_of(bound_ts)
            if bound != intended:
                raise ClayColumnConfigError(
                    f"clone '{name}' ({field.get('id')}): intended useCase {intended!r}, "
                    f"Clay bound {bound!r}")
            low = name.lower()
            if (intended == "use-ai" and "claygent" in low) or \
                    (intended == "claygent" and "use ai" in low):
                warnings.warn(f"column name '{name}' does not match its bound useCase "
                              f"{intended!r}; name AI columns after what is bound")
        return created

    # ── AI output: extraction + verification (LEARNINGS.md #2, #3) ──

    def create_ai_extraction_column(self, table_id: str, action_field_id: str, key: str,
                                    name: str = None, view_id: str = None,
                                    data_type: str = "text") -> dict:
        """Formula column that reads `key` from an AI column's output, tolerant of
        camelCase vs snake_case (see ai_extract_formula)."""
        return self.create_formula_column(table_id, name or key,
                                          ai_extract_formula(action_field_id, key),
                                          view_id=view_id, data_type=data_type,
                                          prompt=[f'The "{key}" value from ', "{{%s}}" % action_field_id, "'s output"])

    def read_ai_output(self, table_id: str, record_id: str, action_field_id: str) -> dict:
        """
        The REAL output of one AI (Use AI / Claygent) cell.

        Over the API the cell's `value` is the streaming placeholder "Response"
        even on success, and bulk-fetch omits the output entirely. The structured
        output only comes from the single-record endpoint's
        externalContent.fullValue. Returns
            {"status", "output": schema fields, "keys": sorted output keys, "metadata": metrics}
        """
        rec = self.get(f"/tables/{table_id}/records/{record_id}")
        cell = (rec.get("cells") or {}).get(action_field_id) or {}
        full = (cell.get("externalContent") or {}).get("fullValue")
        output, meta = {}, {}
        if isinstance(full, dict):
            for k, v in full.items():
                (meta if k in AI_OUTPUT_METADATA_KEYS else output)[k] = v
        elif full is not None:
            output = {"_value": full}
        return {"status": (cell.get("metadata") or {}).get("status"),
                "output": output, "keys": sorted(output), "metadata": meta}

    def verify_ai_column(self, table_id: str, action_field_id: str,
                         record_ids: list[str]) -> dict:
        """
        Prove an AI column works on a few records WITHOUT trusting the action cell.

        For each record: reads the real output (read_ai_output), then checks every
        formula column that extracts from this AI column (`{{f_ai}}?.key`). Flags:
          - action_not_success: the AI cell did not finish with SUCCESS
          - no_output: SUCCESS but no structured output stored
          - key_missing: a formula reads a key that is not in the output; if a
            casing variant IS present, `suggestion` names it (the claygent vs
            use-ai casing trap). Fix with ai_extract_formula().
          - extraction_empty: the key exists but the formula cell is empty
            (usually the formula has not been run on this record yet)
        Keep record_ids small (one GET per record). Returns
            {"ok": bool, "output_keys": [...], "consumers": {...}, "problems": [...]}
        """
        table = self.get_table(table_id)
        fields = table.get("table", table).get("fields", [])
        ref = "{{%s}}" % action_field_id
        path_re = re.compile(re.escape(ref) + r'\?\.(?:([A-Za-z_$][\w$]*)|\[\s*"([^"]+)"\s*\])')
        consumers = {}
        for f in fields:
            ftext = (f.get("typeSettings") or {}).get("formulaText") or ""
            if f.get("type") == "formula" and ref in ftext:
                keys = [a or b for a, b in path_re.findall(ftext)]
                if keys:
                    consumers[f["id"]] = {"name": f.get("name"), "keys": keys}
        cells_by_rec = {}
        if consumers:
            for r in self.get_records(table_id, record_ids):
                cells_by_rec[r.get("id")] = r.get("cells") or {}
        problems, all_keys = [], set()
        for rid in record_ids:
            out = self.read_ai_output(table_id, rid, action_field_id)
            if out["status"] != "SUCCESS":
                problems.append({"record": rid, "type": "action_not_success", "status": out["status"]})
                continue
            if not out["output"]:
                problems.append({"record": rid, "type": "no_output"})
                continue
            keys = set(out["keys"])
            all_keys |= keys
            for fid, c in consumers.items():
                if not any(k in keys for k in c["keys"]):
                    variants = {v for k in c["keys"] for v in ai_key_variants(k)}
                    problems.append({"record": rid, "type": "key_missing", "field": fid,
                                     "column": c["name"], "reads": c["keys"],
                                     "suggestion": sorted(variants & keys) or None})
                    continue
                value = ((cells_by_rec.get(rid) or {}).get(fid) or {}).get("value")
                if value in (None, ""):
                    problems.append({"record": rid, "type": "extraction_empty", "field": fid,
                                     "column": c["name"]})
        return {"ok": not problems, "output_keys": sorted(all_keys),
                "consumers": consumers, "problems": problems}

    # ── Field groups ──────────────────────────────────────────────────────────

    def get_field_groups(self, table_id: str) -> dict:
        """
        Return the table's column groups: {groupId: group}. Each member field
        also carries the same "groupId" on its own definition.
        """
        raw = self.get_table(table_id)
        return raw.get("table", raw).get("fieldGroupMap") or {}

    def create_field_group(self, table_id: str, field_ids: list[str], name: str,
                           output_field_ids: list[str] = None, color: str = None,
                           view_ids: list[str] = None) -> str:
        """
        Group columns together (the way Clay groups an enrichment with its
        outputs) and name the group. Returns the groupId.

        output_field_ids: members to mark as the group's output fields.
        color / view_ids: groups have no colour of their own (they only take
        name + fields). Colour is a per-view field setting, so with color set
        every member is coloured in each of view_ids via set_column_color()
        (default: every view of the table). LEARNINGS.md backlog #20.
        Verify afterwards: every member's field["groupId"] should equal the
        returned id (see get_field_groups()).
        """
        if color is not None and color not in COLUMN_COLORS:
            raise ValueError(f"color must be one of {COLUMN_COLORS}, got {color!r}")
        # Clay 400s on source columns ("is a source column and cannot be grouped"), LEARNINGS #61.
        # Refuse before any write so no half-built unnamed group is left behind.
        raw = self.get_table(table_id)
        sources = [f.get("name", f.get("id")) for f in raw.get("table", raw).get("fields", [])
                   if f.get("id") in field_ids and f.get("type") == "source"]
        if sources:
            raise ValueError(f"source columns cannot be grouped: {sources}; "
                             "colour them with set_column_color() instead")
        # Clay 400s "Cannot merge multiple groups into one" when the fields already sit in
        # 2+ groups (LEARNINGS #62). Refuse up front; set_group_members() moves fields instead.
        existing = {f.get("groupId") for f in raw.get("table", raw).get("fields", [])
                    if f.get("id") in field_ids and f.get("groupId")}
        if len(existing) > 1:
            raise ValueError(f"fields span {len(existing)} existing groups {sorted(existing)}; "
                             "use set_group_members(table_id, <one of them>, field_ids, name)")
        group_id = self.post(f"/tables/{table_id}/fields/group",
                             {"fieldIds": field_ids})["groupId"]
        outputs = set(output_field_ids or [])
        members = []
        for fid in field_ids:
            m = {"id": fid}
            if fid in outputs:
                m["isOutputField"] = True
            members.append(m)
        self.post(f"/tables/{table_id}/fields/group/{group_id}",
                  {"name": name, "fields": members})
        if color is not None:
            if view_ids is None:
                table = self.get_table(table_id)
                view_ids = [v["id"] for v in table.get("table", table).get("views", [])]
            for view_id in view_ids:
                self.set_column_color(table_id, view_id, field_ids, color)
        return group_id

    def set_group_members(self, table_id: str, group_id: str, field_ids: list[str], name: str,
                          color: str = None, view_ids: list[str] = None) -> dict:
        """
        Replace an existing group's members (and name), pulling fields out of whatever group
        they were in (LEARNINGS #62: create_field_group cannot merge 2+ groups). Reads back.
        """
        if color is not None and color not in COLUMN_COLORS:
            raise ValueError(f"color must be one of {COLUMN_COLORS}, got {color!r}")
        res = self.post(f"/tables/{table_id}/fields/group/{group_id}",
                        {"name": name, "fields": [{"id": f} for f in field_ids]})
        raw = self.get_table(table_id)
        wrong = [f["id"] for f in raw.get("table", raw).get("fields", [])
                 if f["id"] in field_ids and f.get("groupId") != group_id]
        if wrong:
            raise ClayTableConfigError(f"set_group_members: {wrong} not in {group_id} after update")
        if color is not None:
            if view_ids is None:
                view_ids = [v["id"] for v in raw.get("table", raw).get("views", [])]
            for view_id in view_ids:
                self.set_column_color(table_id, view_id, field_ids, color)
        return res

    def organize_table(self, table_id: str, layout: list[dict], view_ids: list[str] = None) -> dict:
        """
        Lay a table out in pipeline order (default since 2026-10-19: Rex groups, colours and
        orders every table it builds; LEARNINGS backlog #66). One call, read back.

        layout: [{"group": "Company", "color": "blue", "fields": ["Name", "Domain", ...]}, ...] in
          left-to-right order. Fields by name or id. "group": None colours/orders without grouping.
          Source columns are never grouped (Clay 400, #61); they are coloured and ordered only.
          Columns not listed keep their relative order after the listed ones.
        view_ids: default every view. Order is per view (PATCH views/{v}/fields/{f} afterFieldId, #47),
          groups are table-level, colour is per view (#20).
        Returns {"groups": {name: groupId}, "unlisted": [names]}. Raises if any name is unknown or the
        read-back order/groups differ.
        """
        raw = self.get_table(table_id); t = raw.get("table", raw)
        fields = t.get("fields", []); by_name = {f["name"]: f for f in fields}; by_id = {f["id"]: f for f in fields}
        def fid(x):
            if x in by_id: return x
            if x in by_name: return by_name[x]["id"]
            raise KeyError(f"organize_table: no column {x!r} in {table_id}")
        for b in layout:
            if b.get("color") is not None and b["color"] not in COLUMN_COLORS:
                raise ValueError(f"color must be one of {COLUMN_COLORS}, got {b['color']!r}")
        blocks = [dict(b, ids=[fid(x) for x in b["fields"]]) for b in layout]
        listed = [i for b in blocks for i in b["ids"]]
        if len(set(listed)) != len(listed):
            raise ValueError("organize_table: a column is listed twice")
        gv = {x["id"]: x for x in t.get("views", [])}
        # column order = view["fields"][fid]["order"], a lexicographic sort key (not a fieldOrder list)
        vorder = lambda view: [f for f, m in sorted((view.get("fields") or {}).items(), key=lambda kv: str(kv[1].get("order", "")))]
        views = view_ids or list(gv)
        # 1. order (per view): chain every listed field after the previous one, then unlisted after them
        for v in views:
            cur = vorder(gv.get(v, {}))
            want = listed + [f for f in cur if f not in listed and f in by_id]
            for prev, f in zip(want, want[1:]):
                self.patch(f"/tables/{table_id}/views/{v}/fields/{f}", {"afterFieldId": prev})
        # 2. groups (table level) + colour (per view)
        groups = {}
        for b in blocks:
            members = [i for i in b["ids"] if by_id[i].get("type") != "source"]
            if b.get("group") and members:
                have = {by_id[i].get("groupId") for i in members if by_id[i].get("groupId")}
                if len(have) == 1:
                    groups[b["group"]] = next(iter(have))
                    self.set_group_members(table_id, groups[b["group"]], members, b["group"])
                elif not have:
                    groups[b["group"]] = self.create_field_group(table_id, members, b["group"])
                else:   # spans groups: reuse the first, set_group_members pulls the rest in (#62)
                    groups[b["group"]] = sorted(have)[0]
                    self.set_group_members(table_id, groups[b["group"]], members, b["group"])
                raw = self.get_table(table_id); t2 = raw.get("table", raw)
                by_id = {f["id"]: f for f in t2.get("fields", [])}
            if b.get("color"):
                for v in views:
                    self.set_column_color(table_id, v, b["ids"], b["color"])
        # 3. read back
        raw = self.get_table(table_id); t3 = raw.get("table", raw)
        live = {f["id"]: f for f in t3.get("fields", [])}
        for b in blocks:
            if b.get("group") and b["group"] in groups:
                bad = [live[i]["name"] for i in b["ids"] if live[i].get("type") != "source" and live[i].get("groupId") != groups[b["group"]]]
                if bad:
                    raise ClayTableConfigError(f"organize_table: {bad} not in group {b['group']!r}")
        for v in t3.get("views", []):
            if v["id"] not in views: continue
            order = [f for f in vorder(v) if f in listed]
            if order != listed:
                raise ClayTableConfigError(f"organize_table: view {v.get('name')} order differs from the layout")
        return {"groups": groups, "unlisted": [by_id[f]["name"] for f in by_id if f not in listed]}

    def set_column_color(self, table_id: str, view_id: str, field_ids: list[str],
                         color: str) -> None:
        """
        Colour columns in one view (addition beyond upstream v2.1, backlog #20, verified live).
        Colour is a per-VIEW field setting: PATCH /tables/{t}/views/{v}/fields/{f}
        {"color": ...}. color: red|yellow|blue|green|violet|orange|pink|grey
        (Clay's enum; anything else is refused before any write).
        """
        if color not in COLUMN_COLORS:
            raise ValueError(f"color must be one of {COLUMN_COLORS}, got {color!r}")
        if isinstance(field_ids, str):
            field_ids = [field_ids]
        for field_id in field_ids:
            self.patch(f"/tables/{table_id}/views/{view_id}/fields/{field_id}", {"color": color})

    # ── Native waterfalls (addition beyond upstream v2.1, backlog #25, 2026-09-25) ──────
    # House rule: a waterfall is Clay's NATIVE waterfall group, never provider
    # columns chained by hand. Reference build: a production People table's
    # "Work Email" waterfall group, saved as templates/waterfall-work-email.json. Endpoint reverse-engineered from the
    # Clay web bundle (createWaterfallV2 / updateWaterfallV2 / deleteWaterfallV2).

    def export_waterfall(self, table_id: str, group_id: str) -> dict:
        """
        Read a native waterfall group into a reusable template: the provider steps
        (actionKey, actionPackageId, authAccountId, attributePath and inputsBinding
        as {{f_...}} formulas), the merged column name, attribute, run condition,
        required inputs and validation options. Feed it (after re-pointing field ids)
        to create_waterfall().
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        group = table["fieldGroupMap"][group_id]
        if group.get("type") != "waterfall":
            raise ValueError(f"group {group_id} is type {group.get('type')!r}, not a waterfall")
        fields = {f["id"]: f for f in table["fields"]}
        settings = group.get("settings") or {}
        steps = []
        for s in group["groupDetails"]["sequenceSteps"]:
            steps.append({
                "name": fields.get(s["fieldId"], {}).get("name") or s["actionKey"],
                "type": "actionConfig",
                "actionKey": s["actionKey"],
                "actionPackageId": s["actionPackageId"],
                "authAccountId": s.get("authAccountId"),
                "attributePath": s.get("attributePath"),
                "inputsBinding": s.get("inputsBinding", []),
            })
        merge_id = group["groupDetails"]["mergeField"]["fieldId"]
        return {
            "waterfallFieldName": fields[merge_id]["name"],
            "waterfallGroupName": group.get("name"),
            "attributeEnum": settings.get("attribute"),
            "runAsButton": settings.get("runAsButton", True),
            "conditionalRunFormulaText": settings.get("conditionalRunFormulaText"),
            "inputCombination": settings.get("inputCombination"),
            "requiredInputsBinding": settings.get("requiredInputsBinding", []),
            "customOptions": settings.get("customOptions") or {},
            "requireValidationSuccess": settings.get("requireValidationSuccess", False),
            "createDataProviderField": settings.get("createDataProviderField", False),
            "steps": steps,
            "validationActionConfig": _validation_action_config(group["groupDetails"]["sequenceSteps"])
        }

    def create_waterfall(self, table_id: str, template: dict, view_id: str = None,
                         field_name: str = None, condition: str = None) -> dict:
        """
        Create a native Clay waterfall (one group, one merged output column) from a
        template shaped like export_waterfall()'s output. Nothing is run: the group
        is created with runAsButton (default True) and the table's auto-run setting
        is left alone. Check tableSettings.AUTO_RUN_ON is False before calling.

        POST /workspaces/{ws}/tables/{t}/waterfall/v2
        body: waterfallConfigs [{name, type:"actionConfig", actionKey, actionPackageId,
        inputsBinding, attributePath, authAccountId}], waterfallFieldName, runAsButton,
        attributeEnum (e.g. "person/workEmail"), conditionalRunFormulaText,
        inputCombination, requiredInputsBinding, validationStrategy
        (conservative|balanced|aggressive|advanced), includeCatchAll, includeUnknown,
        excludeRoleBased, excludeDisposable, safeToSend,
        maxConsecutiveIdenticalNotFound, requireValidationSuccess,
        createDataProviderField, activeViewId, waterfallGroupName.
        Clay chains each later step's run condition ("earlier steps found nothing")
        by itself. Returns {"groupId", "mergeFieldId", "stepFieldIds", "response"}.
        """
        opts = template.get("customOptions") or {}
        body = {
            "waterfallConfigs": [
                {k: s[k] for k in ("name", "type", "actionKey", "actionPackageId",
                                   "inputsBinding", "attributePath", "authAccountId") if k in s}
                for s in template["steps"]
            ],
            "waterfallFieldName": field_name or template["waterfallFieldName"],
            "waterfallGroupName": template.get("waterfallGroupName") or field_name or template["waterfallFieldName"],
            "runAsButton": template.get("runAsButton", True),
            "attributeEnum": template.get("attributeEnum"),
            "conditionalRunFormulaText": condition if condition is not None else template.get("conditionalRunFormulaText"),
            "requiredInputsBinding": template.get("requiredInputsBinding", []),
            "requireValidationSuccess": template.get("requireValidationSuccess", False),
            "createDataProviderField": template.get("createDataProviderField", False),
        }
        if template.get("inputCombination"):
            body["inputCombination"] = template["inputCombination"]
        if template.get("validationActionConfig"):  # per-step validation provider (LEARNINGS #87)
            body["validationActionConfig"] = template["validationActionConfig"]
        for k in ("validationStrategy", "includeCatchAll", "includeUnknown", "excludeRoleBased",
                  "excludeDisposable", "safeToSend", "maxConsecutiveIdenticalNotFound"):
            if opts.get(k) is not None:
                body[k] = opts[k]
        if view_id:
            body["activeViewId"] = view_id
        for s in body["waterfallConfigs"]:
            s.setdefault("type", "actionConfig")
        before = self.get_table(table_id)
        before = set(((before.get("table", before)).get("fieldGroupMap") or {}).keys())
        res = self.post(f"{self._ws_table_path(table_id)}/waterfall/v2", body)
        groups = res.get("fieldGroupMap") or {}
        # Pick the group this call created. Matching by name alone returned an EXISTING
        # waterfall when the table already had one with the same group name
        # (LEARNINGS.md 2026-10-19: a client's fCTO table, returned the old 10-step "Work Email").
        new_ids = [g for g, v in groups.items() if g not in before and v.get("type") == "waterfall"]
        if len(new_ids) != 1:
            raise RuntimeError(f"create_waterfall: expected 1 new waterfall group, found {new_ids}; "
                               "inspect the table before wiring anything to the result")
        gid = new_ids[0]
        group = groups.get(gid, {})
        details = group.get("groupDetails") or {}
        return {
            "groupId": gid,
            "mergeFieldId": (details.get("mergeField") or {}).get("fieldId"),
            "stepFieldIds": [s["fieldId"] for s in details.get("sequenceSteps", [])],
            "response": res,
        }

    def create_http_auth_account(self, name: str, headers: dict, default_access: str = "can_use") -> dict:
        """
        Create an "HTTP API (Headers)" connection (appAccountTypeId "http-api") that stores
        request headers (e.g. {"Authorization": key}) server-side, so http-api-v2 columns can
        use authAccountId instead of a plaintext key in their headers input
        (LEARNINGS.md backlog #66, verified live 2026-10-14).
        POST /workspaces/{ws}/app-accounts {name, appAccountTypeId, auth: {headers}, ...}.
        Refuses a name that already exists. Never log `headers`.
        """
        if any(a.get("name") == name for a in self.list_auth_accounts()):
            raise ValueError(f"an app account named {name!r} already exists")
        return self.post(f"/workspaces/{self.workspace_id}/app-accounts",
                         {"name": name, "appAccountTypeId": "http-api", "auth": {"headers": headers},
                          "setAsDefault": False, "defaultAccess": default_access, "roles": []})

    def create_waterfall_from_template(self, table_id: str, template, inputs: dict,
                                       condition: str = None, view_id: str = None,
                                       field_name: str = None) -> dict:
        """
        Create a native waterfall from a saved template whose inputs are placeholders
        (LEARNINGS.md #87). Default: templates/waterfall-work-email.json = an example
        standard (2026-10-19, updated 2026-10-29): Prospeo -> LeadMagic -> Icypeas ->
        Findymail -> Wiza -> FullEnrich, LeadMagic validation on every step.

        template: dict or path. inputs maps each placeholder to a formula on THIS table, e.g.
          {"FULL_NAME": "{{f_src}}?.name", "COMPANY_DOMAIN": "{{f_src}}?.domain",
           "COMPANY_NAME": "{{f_co}}", "LINKEDIN_URL": "{{f_li}}"}
        Every {{PLACEHOLDER}} must be filled; condition is the group run-if (e.g.
        '{{f_elig}}===true'). The template ships with authAccountId = null on every step:
        set each to one of YOUR workspace's connections first (clay.list_auth_accounts()).

        Step validation comes from the template's top-level validationActionConfig (Clay adds a
        "Validate <step>" column per step and rewrites run-ifs + merge); it is read back and a
        missing one raises. Returns create_waterfall()'s result plus "validationFieldIds".
        """
        if isinstance(template, (str, os.PathLike)):
            with open(template) as fh:
                template = json.load(fh)
        text = json.dumps(template)
        for key, formula in (inputs or {}).items():
            text = text.replace("{{%s}}" % key, json.dumps(formula)[1:-1])
        left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", text)))
        if left:
            raise ValueError(f"create_waterfall_from_template: unfilled placeholders {left}")
        filled = json.loads(text)
        if condition is None and not filled.get("conditionalRunFormulaText"):
            raise ValueError("create_waterfall_from_template: pass condition= (the group run-if)")
        res = self.create_waterfall(table_id, filled, view_id=view_id, condition=condition, field_name=field_name)
        if filled.get("validationActionConfig"):
            table = self.get_table(table_id)
            table = table.get("table", table)
            seq = table["fieldGroupMap"][res["groupId"]]["groupDetails"]["sequenceSteps"]
            missing = [i for i, s in enumerate(seq) if not (s.get("validation") or {}).get("actionKey")]
            if missing:
                raise ClayColumnConfigError(f"waterfall {res['groupId']}: step validation missing on steps {missing} after create")
            res["validationFieldIds"] = [s["validation"]["fieldId"] for s in seq]
        return res

    def waterfall_steps_with_ids(self, table_id: str, group_id: str) -> list[dict]:
        """export_waterfall() steps, each with the existing step column's `fieldId` added
        (the shape update_waterfall() expects for steps to keep)."""
        tpl = self.export_waterfall(table_id, group_id)
        table = self.get_table(table_id)
        table = table.get("table", table)
        seq = ((table.get("fieldGroupMap") or {}).get(group_id, {}).get("groupDetails") or {}).get("sequenceSteps", [])
        return [dict(s, fieldId=st["fieldId"]) for s, st in zip(tpl["steps"], seq)]

    def update_waterfall(self, table_id: str, group_id: str, steps: list[dict],
                         allow_remove: bool = False, condition: str = None,
                         validation: dict = None) -> dict:
        """
        Add, reorder or remove steps of an EXISTING native waterfall in place
        (LEARNINGS.md backlog #64, verified live 2026-10-14).

        PATCH /workspaces/{ws}/tables/{t}/waterfall/v2/{groupId} with the full create body.
        steps: the new ordered list. Steps to keep carry their `fieldId` (get them from
        waterfall_steps_with_ids()); new steps have none. Kept step columns, their cell
        values and the merged column keep their ids; group settings (condition,
        validation, required inputs) are re-sent unchanged. A step left out is DELETED
        with its column and results, so that needs allow_remove=True. condition replaces
        the group's run condition (None keeps it). validation: a validationActionConfig
        ({actionKey, actionPackageId, inputName, authAccountId}) to put on every step; None
        keeps the current one, {} removes it. Nothing is run
        (skipActionFieldRuns). Returns {"groupId", "mergeFieldId", "stepFieldIds"}.
        """
        current = self.waterfall_steps_with_ids(table_id, group_id)
        kept = {s["fieldId"] for s in steps if s.get("fieldId")}
        removed = [s["name"] for s in current if s["fieldId"] not in kept]
        if removed and not allow_remove:
            raise ValueError(f"update would delete steps {removed} and their columns; pass allow_remove=True")
        tpl = self.export_waterfall(table_id, group_id)
        opts = tpl.get("customOptions") or {}
        keys = ("name", "type", "actionKey", "actionPackageId", "inputsBinding", "attributePath",
                "authAccountId", "fieldId")
        body = {
            "waterfallConfigs": [dict({k: s[k] for k in keys if k in s}, type=s.get("type") or "actionConfig")
                                 for s in steps],
            "waterfallFieldName": tpl["waterfallFieldName"],
            "waterfallGroupName": tpl.get("waterfallGroupName") or tpl["waterfallFieldName"],
            "runAsButton": tpl.get("runAsButton", True),
            "attributeEnum": tpl.get("attributeEnum"),
            "conditionalRunFormulaText": condition if condition is not None else tpl.get("conditionalRunFormulaText"),
            "requiredInputsBinding": tpl.get("requiredInputsBinding", []),
            "requireValidationSuccess": tpl.get("requireValidationSuccess", False),
            "createDataProviderField": tpl.get("createDataProviderField", False),
            "skipActionFieldRuns": True,
        }
        if tpl.get("inputCombination"):
            body["inputCombination"] = tpl["inputCombination"]
        if validation is not None:
            body["validationActionConfig"] = validation or None
        elif tpl.get("validationActionConfig"):  # keep the existing step validation (LEARNINGS #87)
            body["validationActionConfig"] = tpl["validationActionConfig"]
        for k in ("validationStrategy", "includeCatchAll", "includeUnknown", "excludeRoleBased",
                  "excludeDisposable", "safeToSend", "maxConsecutiveIdenticalNotFound"):
            if opts.get(k) is not None:
                body[k] = opts[k]
        self.patch(f"{self._ws_table_path(table_id)}/waterfall/v2/{group_id}", body)
        table = self.get_table(table_id)
        table = table.get("table", table)
        details = ((table.get("fieldGroupMap") or {}).get(group_id) or {}).get("groupDetails") or {}
        return {"groupId": group_id, "mergeFieldId": (details.get("mergeField") or {}).get("fieldId"),
                "stepFieldIds": [s["fieldId"] for s in details.get("sequenceSteps", [])]}

    def delete_waterfall(self, table_id: str, group_id: str) -> dict:
        """Delete a native waterfall group and its step + merged columns. No undelete."""
        return self.delete(f"{self._ws_table_path(table_id)}/waterfall/v2/{group_id}", json={})

    def generate_formula(self, table_id: str, prompt: str, column_name_map: dict = None) -> dict:
        """Ask Clay's AI to generate a formula from a natural language prompt."""
        body = {
            "id": self.user_id,
            "workspaceId": str(self.table_workspace(table_id)),
            "userPromptInput": prompt,
            "userProvidedCorrectedExamples": [],
            "columnNamesToIds": column_name_map or {},
            "mode": "basic",
            "rawExampleTableData": [],
            "formattedExampleTableData": [],
        }
        return self.post("/ai-generation/formula", body)

    # ── Export ───────────────────────────────────────────────────────────────

    def export_csv(self, table_id: str, view_id: str = None,
                   poll_interval: float = 2.0, timeout: int = 300) -> str:
        """
        Export a table (or view) as CSV and return the S3 download URL.

        Native CSV export: action ("Response") columns export as the literal
        string "Response". They do NOT contain the full enrichment JSON. To get full data,
        either add formula columns (JSON.stringify({{field_id}})) or use
        fetch_all_records_full() instead.

        If view_id is given, only view-filtered rows are exported.
        If view_id is omitted, ALL table rows are exported (ignores filters).

        Returns the signed S3 download URL (valid 24h).
        """
        url = f"/tables/{table_id}/views/{view_id}/export" if view_id else f"/tables/{table_id}/export"
        r = self.session.post(f"https://api.clay.com/v3{url}")
        r.raise_for_status()
        job = r.json()
        job_id = job["id"]
        total = job.get("totalRecordsInViewCount", "?")
        print(f"[clay] export job {job_id} | {total} records")

        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll_interval)
            sr = self.session.get(f"https://api.clay.com/v3/exports/{job_id}")
            sr.raise_for_status()
            data = sr.json()
            status = data.get("status")
            exported = data.get("recordsExportedCount", 0)
            if status == "FINISHED":
                print(f"[clay] export done: {exported}/{total} rows")
                return data["downloadUrl"]
            elif status == "FAILED":
                raise RuntimeError(f"Export job failed: {data}")

        raise TimeoutError(f"Export job {job_id} did not finish within {timeout}s")

    def export_tables(self, table_ids: list[str], out_dir: str = "./exports",
                      view_ids: dict[str, str] = None) -> dict:
        """
        Export multiple tables to CSV and download each one to disk.

        A thin loop over export_csv(); no workspace/folder auto-discovery,
        you pass the exact table_ids you want. export_csv() only returns a
        signed S3 URL; this actually downloads it to
        {out_dir}/{table_name}.csv (falls back to the table_id if the name
        can't be read or isn't filesystem-safe).

        view_ids: optional {table_id: view_id} map to export a filtered view
        instead of the whole table for specific tables.

        Returns {table_id: "ok (N bytes)"} on success or
        {table_id: "error: <message>"} on failure: always continues to the
        next table rather than aborting the whole batch on one failure.
        """
        view_ids = view_ids or {}
        os.makedirs(out_dir, exist_ok=True)
        results = {}

        for table_id in table_ids:
            try:
                name = table_id
                try:
                    name = self.get_table(table_id)["table"].get("name", table_id)
                except Exception:
                    pass
                safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip() or table_id

                url = self.export_csv(table_id, view_id=view_ids.get(table_id))
                r = self.session.get(url)
                r.raise_for_status()

                path = os.path.join(out_dir, f"{safe_name}.csv")
                with open(path, "wb") as f:
                    f.write(r.content)

                print(f"[clay] wrote {path} ({len(r.content)} bytes)")
                results[table_id] = f"ok ({len(r.content)} bytes) -> {path}"
            except Exception as e:
                print(f"[clay] export_tables: {table_id} failed: {e}")
                results[table_id] = f"error: {e}"

        return results

    def fetch_all_records_full(self, table_id: str, view_id: str,
                               field_id: str, workers: int = 20) -> list[dict]:
        """
        Fetch the full externalContent.fullValue for an action column across
        ALL records in a view, in parallel.

        Use this when you need the raw enrichment JSON that native CSV export
        omits (action columns export as "Response" only).

        Returns list of {record_id, value} dicts. ~27ms/record with 20 workers.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        record_ids = self.get_record_ids(table_id, view_id)
        print(f"[clay] fetching full values for {len(record_ids)} records ({workers} workers)...")

        def fetch_one(rec_id):
            r = self.session.get(f"https://api.clay.com/v3/tables/{table_id}/records/{rec_id}")
            r.raise_for_status()
            cell = r.json().get("cells", {}).get(field_id, {})
            return {
                "record_id": rec_id,
                "value": cell.get("externalContent", {}).get("fullValue"),
                "status": cell.get("metadata", {}).get("status"),
            }

        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(fetch_one, rid): rid for rid in record_ids}
            for f in as_completed(futures):
                results.append(f.result())

        print(f"[clay] done: {len(results)} records fetched")
        return results

    # ── Costs ────────────────────────────────────────────────────────────────

    def _action_column_meta(self, table_id: str, field_ids: list[str] = None) -> list[dict]:
        """
        Build column_meta for clay_costs.aggregate() from the table's live
        field definitions: one entry per action column, with its actionKey
        and configured useCase/model read from inputsBinding.
        """
        table = self.get_table(table_id)["table"]
        fields = table.get("fields", [])
        if field_ids:
            fields = [f for f in fields if f.get("id") in field_ids]
        else:
            fields = [f for f in fields if f.get("type") == "action"]

        meta = []
        for f in fields:
            settings = f.get("typeSettings", {}) or {}
            bound = {}
            for b in settings.get("inputsBinding", []) or []:
                name, text = b.get("name"), b.get("formulaText")
                if name and isinstance(text, str):
                    bound[name] = text.strip('"')
            meta.append({
                "field_id": f.get("id"),
                "field_name": f.get("name"),
                "action_key": settings.get("actionKey"),
                "action_use_case": bound.get("useCase"),
                "model_configured": bound.get("model"),
            })
        return meta

    def get_cell_costs(self, table_id: str, view_id: str = None,
                       field_ids: list[str] = None, workers: int = 20) -> list[dict]:
        """
        Fetch every record in a view and extract cost/telemetry fields from
        every action-column cell: same field semantics as the claylens/
        browser extension (clay_costs.extract_cost_fields).

        If field_ids is omitted, auto-detects all action-type columns from
        the live table schema. Returns a flat list of extract_cost_fields()
        dicts, each augmented with record_id + field_id, ready for
        clay_costs.aggregate().
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        table = self.get_table(table_id)["table"]
        view_id = view_id or table.get("firstViewId")
        meta = self._action_column_meta(table_id, field_ids)
        meta_by_id = {m["field_id"]: m for m in meta}

        record_ids = self.get_record_ids(table_id, view_id)
        print(f"[clay] costs: fetching {len(record_ids)} records x {len(meta)} action columns ({workers} workers)...")

        def fetch_one(rec_id):
            r = self.session.get(f"https://api.clay.com/v3/tables/{table_id}/records/{rec_id}")
            r.raise_for_status()
            cells = r.json().get("cells", {})
            out = []
            for field_id, m in meta_by_id.items():
                extracted = clay_costs.extract_cost_fields(
                    cells.get(field_id), field_type="action", action_key=m["action_key"])
                extracted["record_id"] = rec_id
                extracted["field_id"] = field_id
                out.append(extracted)
            return out

        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(fetch_one, rid): rid for rid in record_ids}
            for f in as_completed(futures):
                results.extend(f.result())

        print(f"[clay] costs: done, {len(results)} cells across {len(record_ids)} records")
        return results

    def print_cost_report(self, table_id: str, view_id: str = None, top_n: int = 10) -> dict:
        """
        Fetch, aggregate, and print a terminal cost report for a table:
        total $ spend, total Clay credits, cost by column, top-N most
        expensive rows. Returns the raw clay_costs.aggregate() summary dict.

        Some Clay credit costs in clay_costs.PROVIDER_COSTS are best-guess
        (source: "guess"): verify per-action $ in Clay's UI before citing
        these numbers to a client.
        """
        cells = self.get_cell_costs(table_id, view_id)
        meta = self._action_column_meta(table_id)
        summary = clay_costs.aggregate(cells, meta)
        t = summary["totals"]

        print(f"\n--- Cost report: {table_id} ---")
        print(f"  Total spend:      ${t['total_cost_usd']:.4f}  ({t['total_credits']:.2f} Clay credits)")
        print(f"  Net (post-refund): ${t['net_cost_usd']:.4f}")
        print(f"  Rows analyzed:    {t['unique_rows']}  ({t['success_rows']} with at least one success)")
        if t["cost_per_success_row"] is not None:
            print(f"  Cost / success row: ${t['cost_per_success_row']:.4f}")
        if t["uncosted_cells"]:
            print(f"  ⚠ {t['uncosted_cells']} uncosted cells (ran, but no cost data and no known actionKey price)")

        print(f"\n  By column (top {top_n} by spend):")
        for c in summary["by_column"][:top_n]:
            print(f"    {c['field_name']:<40} ${c['total_cost_usd']:.4f}  "
                  f"({c['runs']} runs, {c['share_pct']:.1f}% of spend, model={c['model']})")

        print(f"\n  Top {top_n} most expensive rows:")
        for row in summary["top_rows"][:top_n]:
            print(f"    {row['record_id']}: ${row['total_cost_usd']:.4f}")

        return summary

    # ── Records ───────────────────────────────────────────────────────────────

    def get_record_ids(self, table_id: str, view_id: str) -> list[str]:
        """
        List ALL record IDs in a table via its view.
        This is the correct endpoint. Do NOT use /views/{id}/records (it 404s).
        Filters out the "search" placeholder entry.
        """
        res = self.get(f"/tables/{table_id}/views/{view_id}/records/ids")
        ids = res.get("results", [])
        return [rid for rid in ids if rid != "search"]

    def list_records(self, table_id: str, view_id: str, field_ids: list[str] = None) -> list[dict]:
        """
        List ALL records in a table with their cell data.
        Two-step: get IDs, then bulk-fetch.
        Optionally filter to specific field_ids for performance.
        """
        record_ids = self.get_record_ids(table_id, view_id)
        if not record_ids:
            return []
        body = {"recordIds": record_ids}
        if field_ids:
            body["fieldIds"] = field_ids
        res = self.post(f"/tables/{table_id}/bulk-fetch-records", body)
        return res.get("results", [])

    def get_records(self, table_id: str, record_ids: list[str], field_ids: list[str] = None) -> list[dict]:
        """Fetch specific records by ID. Optionally filter to specific fields."""
        body = {"recordIds": record_ids}
        if field_ids:
            body["fieldIds"] = field_ids
        res = self.post(f"/tables/{table_id}/bulk-fetch-records", body)
        return res.get("results", [])

    def create_records(self, table_id: str, cells_list: list[dict],
                       allow_bulk_api_rows: bool = False) -> list[dict]:
        """
        Create records in a table.
        cells_list: list of {field_id: value} dicts.
        Returns list of record dicts.

        Guard (LEARNINGS.md backlog #15 / #48, House rule): rows written over the
        API carry no lineage, so nobody can see where they came from. Tables derived from
        another Clay table are built with a Send table data column
        (create_route_row_column) instead. More than API_ROW_WRITE_LIMIT rows per call is
        refused unless allow_bulk_api_rows=True, which is ONLY for an explicit request from
        the operator (the human running the build) or for data with no Clay origin (e.g. a CSV / sequencer export).
        """
        if len(cells_list) > API_ROW_WRITE_LIMIT and not allow_bulk_api_rows:
            raise ClayTableConfigError(
                f"create_records: refusing to write {len(cells_list)} rows into {table_id} over the API. "
                "Derived tables are built with a Send table data column (create_route_row_column) so "
                "they keep lineage. Pass allow_bulk_api_rows=True only when the operator explicitly asked for "
                "an API import or the data has no Clay origin (LEARNINGS.md #15/#48).")
        records = [{"cells": cells} for cells in cells_list]
        res = self.post(f"/tables/{table_id}/records", {"records": records})
        return res.get("records", [])

    def update_record(self, table_id: str, record_id: str, field_values: dict) -> dict:
        """Set cell values. field_values = {field_id: value}

        NOTE: the singular PATCH /records/{id} endpoint returns 200 "enqueued"
        but silently no-ops on this workspace (confirmed 2026-08-24). Use
        update_records (plural, batch) instead, it actually persists.
        """
        return self.patch(f"/tables/{table_id}/records/{record_id}", field_values)

    def update_records(self, table_id: str, updates: list[dict]) -> dict:
        """
        Bulk-update existing records. updates = [{"id": record_id, "cells": {field_id: value}}, ...]
        Uses the plural PATCH /records endpoint, which persists reliably
        (unlike the singular per-record PATCH, which no-ops silently).
        """
        return self.patch(f"/tables/{table_id}/records", {"records": updates})

    # ── Views (addition beyond upstream v2.1, verified live 2026-09-24) ─────────────

    def create_view(self, table_id: str, name: str, filter_items: list[dict] = None,
                    combination_mode: str = "AND", sort_items: list[dict] = None,
                    visible_field_ids: list[str] = None, description: str = None,
                    allow_hide_actions: bool = False, copy_colors: bool = True) -> dict:
        """
        Create a new view on a table, then optionally filter, sort and pick its columns.

        copy_colors (LEARNINGS.md backlog #50): column colours are per VIEW and a
        new view starts with none, so by default the colours of the table's "Default view"
        (else its first other view) are copied onto the new view. Pass False to skip.

        Clay ignores filter/sort in the create body, so they are applied with
        separate PATCHes afterwards. filter_items use view_filter() dicts, e.g.
            [view_filter(f_status, "EQUAL", "yes"), view_filter(f_email, "NOT_EMPTY")]
        sort_items: [{"fieldId": f_id, "direction": "ASC" | "DESC"}].
        visible_field_ids: show exactly these columns, in this order; hide the rest
        (action/source columns must be included unless allow_hide_actions=True; see
        set_view_columns()).
        Returns the view as stored after all changes.
        """
        if visible_field_ids and not allow_hide_actions:
            raw = self.get_table(table_id)  # refuse before creating anything
            _refuse_hiding_lineage(raw.get("table", raw), list(visible_field_ids))
        body = {"name": name}
        if description:
            body["description"] = description
        view = self.post(f"/tables/{table_id}/views", body)
        view_id = view["id"]
        try:
            if filter_items:
                view = self.set_view_filter(table_id, view_id, filter_items, combination_mode)
            if sort_items:
                view = self.set_view_sort(table_id, view_id, sort_items)
            if visible_field_ids:
                self.set_view_columns(table_id, view_id, visible_field_ids,
                                      allow_hide_actions=allow_hide_actions)
                view = self.get_view(table_id, view_id)
        except Exception:
            # LEARNINGS.md #30: never leave a half-configured (e.g. unfiltered) view behind.
            # The view was created by this call a moment ago, so removing it is safe.
            try:
                self.delete_view(table_id, view_id)
                print(f"[clay] create_view: configuring {view_id} failed; deleted it.")
            except Exception as cleanup_err:
                print(f"[clay] create_view: configuring {view_id} failed AND cleanup failed "
                      f"({cleanup_err}); delete it by hand.")
            raise
        if copy_colors:
            try:
                copied = self.copy_view_colors(table_id, view_id)
                if copied:
                    view = self.get_view(table_id, view_id)
            except Exception as err:
                print(f"[clay] create_view: {view_id} created but copying column colours failed ({err}); "
                      f"run copy_view_colors() again.")
        return view

    def copy_view_colors(self, table_id: str, target_view_id: str, source_view_id: str = None) -> int:
        """
        Copy column colours from source_view_id (default: the table's "Default view", else
        its first other view) onto target_view_id. Colours are per view (backlog #20, #50).
        Returns how many columns were coloured.
        """
        table = self.get_table(table_id)
        views = table.get("table", table).get("views", [])
        others = [v for v in views if v.get("id") != target_view_id]
        if source_view_id:
            src = next((v for v in views if v.get("id") == source_view_id), None)
        else:
            src = next((v for v in others if v.get("name") == "Default view"), None) or (others[0] if others else None)
        if not src:
            return 0
        by_color = {}
        for fid, cfg in (src.get("fields") or {}).items():
            color = (cfg or {}).get("color")
            if color in COLUMN_COLORS:
                by_color.setdefault(color, []).append(fid)
        for color, fids in by_color.items():
            self.set_column_color(table_id, target_view_id, fids, color)
        return sum(len(f) for f in by_color.values())

    def get_view(self, table_id: str, view_id: str) -> dict:
        """Read one view's stored config (name, fields, filter, sort) from the table."""
        table = self.get_table(table_id)
        table = table.get("table", table)
        for view in table.get("views", []):
            if view.get("id") == view_id:
                return view
        raise KeyError(f"view {view_id} not found on table {table_id}")

    def set_view_filter(self, table_id: str, view_id: str, filter_items: list[dict],
                        combination_mode: str = "AND") -> dict:
        """
        Replace a view's filter. Pass [] to clear it. Rejects unknown operators and
        raises ClayViewFilterError if Clay stored fewer conditions than were sent.
        """
        path = f"{self._ws_table_path(table_id)}/views/{view_id}/filter"
        if not filter_items:
            # {"items": []} returns 404; an empty body is what clears the filter.
            view = self.patch(path, None)
            if (view.get("filter") or {}).get("items"):
                raise ClayViewFilterError(f"view {view_id}: filter not cleared: {view.get('filter')}")
            return view
        mode = combination_mode.upper()
        if mode not in ("AND", "OR"):
            raise ValueError(f"combination_mode must be AND or OR, got {combination_mode!r}")
        for item in filter_items:
            if item.get("type") not in VIEW_FILTER_OPERATORS:
                raise ValueError(f"unknown view filter operator {item.get('type')!r}; "
                                 f"see VIEW_FILTER_OPERATORS")
            if "fieldId" not in item:
                raise ValueError(f"filter item needs 'fieldId' (not 'field'): {item}")
        self._check_filter_against_fields(table_id, filter_items)
        view = self.patch(path, {"items": filter_items, "combinationMode": mode})
        stored = (view.get("filter") or {}).get("items") or []
        if len(stored) != len(filter_items):
            raise ClayViewFilterError(
                f"view {view_id}: sent {len(filter_items)} filter conditions, Clay stored "
                f"{len(stored)}. The view is NOT filtered as intended: {stored}")
        return view

    def _check_filter_against_fields(self, table_id: str, filter_items: list[dict]) -> None:
        """
        Each field lists its own supportedFilterOperators [{operator, needsValue}]
        (LEARNINGS.md #10): a text column has no GREATER_THAN, a formula column no
        CONTAIN. Clay drops an unsupported condition silently, so refuse it here, and
        refuse a missing value where needsValue is true. Fields without the list pass.
        """
        table = self.get_table(table_id)
        table = table.get("table", table)
        fields = {f["id"]: f for f in table.get("fields") or []}
        if not fields:
            return  # table not readable here; the stored-count read-back still guards
        for item in filter_items:
            field = fields.get(item["fieldId"])
            if field is None:
                raise ValueError(f"filter field {item['fieldId']} is not a column of {table_id}")
            ops = field.get("supportedFilterOperators")
            if not ops:
                continue
            allowed = {o.get("operator"): o.get("needsValue") for o in ops}
            if item["type"] not in allowed:
                raise ValueError(f"column '{field.get('name')}' ({field.get('type')}) does not support "
                                 f"{item['type']}; it supports {sorted(allowed)}")
            if allowed[item["type"]] and item.get("value") in (None, "", []):
                raise ValueError(f"{item['type']} on '{field.get('name')}' needs a value")

    def set_view_sort(self, table_id: str, view_id: str, sort_items: list[dict]) -> dict:
        """Replace a view's sort. sort_items = [{"fieldId": f_id, "direction": "ASC"|"DESC"}]."""
        return self.patch(f"{self._ws_table_path(table_id)}/views/{view_id}/sort",
                          {"items": sort_items})

    def set_view_columns(self, table_id: str, view_id: str, visible_field_ids: list[str],
                         hide_others: bool = True, width: int = 200,
                         allow_hide_actions: bool = False) -> None:
        """
        Show visible_field_ids in this order and (by default) hide every other column.
        Clay ignores order/visibility in a whole-view PATCH, so this goes field by field.

        House rule (LEARNINGS.md backlog #19): action columns (lookups, enrichments,
        Send table data) and source columns must stay visible so the table shows how
        it was built. With hide_others=True, any action/source column missing from
        visible_field_ids raises ValueError before any write, listing them. Pass
        allow_hide_actions=True to hide them anyway.
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        view = next((v for v in table.get("views", []) if v.get("id") == view_id), None)
        if view is None:
            raise KeyError(f"view {view_id} not found on table {table_id}")
        wanted = list(visible_field_ids)
        if hide_others and not allow_hide_actions:
            _refuse_hiding_lineage(table, wanted)
        if hide_others:
            for field_id in (view.get("fields") or {}):
                if field_id not in wanted:
                    self.patch(f"/tables/{table_id}/views/{view_id}/fields/{field_id}",
                               {"isVisible": False})
        prev = None
        for field_id in wanted:
            body = {"isVisible": True, "width": width}
            if prev:
                body["afterFieldId"] = prev
            self.patch(f"/tables/{table_id}/views/{view_id}/fields/{field_id}", body)
            prev = field_id

    def set_view_order(self, table_id: str, view_ids: list[str]) -> None:
        """
        Put views in this order (LEARNINGS #64). PATCHing a view's `order` is silently ignored;
        PATCH {"afterViewId": <previous>} moves it. Chains each view after the one before it.
        """
        for prev, vid in zip(view_ids, view_ids[1:]):
            self.patch(f"/tables/{table_id}/views/{vid}", {"afterViewId": prev})

    def view_count(self, table_id: str, view_id: str) -> int:
        """Rows the view shows after its filter."""
        return self.get(f"/tables/{table_id}/views/{view_id}/count")["viewTotalRecordsCount"]

    def delete_view(self, table_id: str, view_id: str) -> dict:
        """Delete a view (rows are untouched). There is no undelete."""
        return self.delete(f"/tables/{table_id}/views/{view_id}")

    def delete_records(self, table_id: str, record_ids: list[str]) -> dict:
        """Delete specific records by ID."""
        r = self.session.delete(self._url(f"/tables/{table_id}/records"), json={"recordIds": record_ids})
        r.raise_for_status()
        return r.json()

    # ── Fields (delete) ────────────────────────────────────────────────────────

    def delete_column(self, table_id: str, field_id: str) -> dict:
        """Delete a column from a table."""
        return self.delete(f"/tables/{table_id}/fields/{field_id}")

    # ── Running ───────────────────────────────────────────────────────────────

    def run_column(self, table_id: str, field_ids: list[str],
                   record_ids: list[str] = None, view_id: str = None,
                   force: bool = False) -> dict:
        """
        Trigger enrichment run for specific columns.
        Prefer record_ids over view_id: viewId depends on UI row limits.

        force=True sends "forceRun": true, which re-runs cells that already have a
        result. Needed to refresh a lookup snapshot after the target table changed:
        a plain re-run keeps the old value (LEARNINGS.md backlog #23, verified live
        2026-09-25). On a paid column it re-spends credits on every cell it re-runs.
        """
        body = {"fieldIds": field_ids, "callerName": "clay-client"}
        if force:
            body["forceRun"] = True
        if record_ids:
            body["runRecords"] = {"recordIds": record_ids}
        elif view_id:
            body["runRecords"] = {"viewId": view_id}
        return self.patch(f"/tables/{table_id}/run", body)

    def run_and_wait(self, table_id: str, field_ids: list[str],
                     record_ids: list[str], timeout: int = 120, poll: int = 5,
                     force: bool = False) -> list[dict]:
        """
        Run columns on records and poll until done or timeout. force: see run_column().
        With force=True the first poll can still see the previous result, so compare
        values (or the cell's updatedAt) before trusting a forced re-run.
        """
        self.run_column(table_id, field_ids, record_ids=record_ids, force=force)
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(poll)
            records = self.get_records(table_id, record_ids)
            all_done = True
            for rec in records:
                for fid in field_ids:
                    cell = rec.get("cells", {}).get(fid, {})
                    status = cell.get("metadata", {}).get("status", "")
                    if status in ("QUEUED", "RUNNING", "PENDING", ""):
                        if not cell.get("value") and status != "ERROR":
                            all_done = False
                            break
                if not all_done:
                    break
            if all_done:
                return records
        return self.get_records(table_id, record_ids)

    def run_paced(self, table_id: str, field_id: str, record_ids: list[str],
                  batch_size: int = 25, pause: float = 15, retry_rounds: int = 3,
                  backoff: float = 90, batch_timeout: int = 300, poll: int = 5,
                  skip_success: bool = True) -> dict:
        """
        Run one action column over many rows in paced batches, read back every cell,
        and retry ONLY the ERROR cells with a growing backoff (LEARNINGS.md #36: the
        list-clean endpoint rate-limited a 1,121-row run; blind re-runs kept failing).

        skip_success: cells already SUCCESS are not re-run (safe to call again to resume).
        Returns {"success", "error", "rate_limited", "unfinished", "rounds": [...],
                 "errors": {record_id: message}}. Retries use forceRun on ERROR cells only,
        so successes are never re-spent.
        """
        def statuses(ids):
            out = {}
            for i in range(0, len(ids), 200):
                for rec in self.get_records(table_id, ids[i:i + 200], [field_id]):
                    cell = (rec.get("cells") or {}).get(field_id) or {}
                    meta = cell.get("metadata") or {}
                    out[rec["id"]] = (meta.get("status"), meta.get("errorMessagePreview") or "")
            return out

        ids = list(record_ids)
        state = statuses(ids)
        todo = [r for r in ids if not (skip_success and state.get(r, (None,))[0] == "SUCCESS")]
        rounds = []
        for rnd in range(retry_rounds + 1):
            if not todo:
                break
            if rnd:
                time.sleep(backoff * rnd)
            for i in range(0, len(todo), batch_size):
                batch = todo[i:i + batch_size]
                self.run_column(table_id, [field_id], record_ids=batch, force=True)
                start = time.time()
                while time.time() - start < batch_timeout:
                    time.sleep(poll)
                    st = statuses(batch)
                    if all(_run_finished(s) for s, _ in st.values()):
                        break
                state.update(statuses(batch))
                if i + batch_size < len(todo):
                    time.sleep(pause)
            failed = [r for r in todo if state[r][0] == "ERROR" or not _run_finished(state[r][0])]
            rounds.append({"round": rnd, "ran": len(todo), "failed": len(failed)})
            print(f"[clay] run_paced round {rnd}: ran {len(todo)}, not successful {len(failed)}")
            todo = [r for r in failed if state[r][0] == "ERROR"]
        errors = {r: m for r, (s, m) in state.items() if s == "ERROR"}
        other = {}
        for s, _ in state.values():
            if s not in (None, "SUCCESS", "ERROR") and _run_finished(s):
                other[s] = other.get(s, 0) + 1
        return {
            "success": sum(1 for s, _ in state.values() if s == "SUCCESS"),
            "error": len(errors),
            "rate_limited": sum(1 for m in errors.values() if re.search(r"rate.?limit|429", m, re.I)),
            "not_run": other,  # e.g. {"ERROR_RUN_CONDITION_NOT_MET": 2}; never retried
            "unfinished": sum(1 for s, _ in state.values() if not _run_finished(s)),
            "rounds": rounds,
            "errors": errors,
        }

    # ── Audits (LEARNINGS.md #27, #28, AI models) ────────────────────

    def describe_columns(self, table_id: str) -> list[dict]:
        """
        Every column with the logic it really runs (formulaWaterfall rendered, #27), its
        run condition and the condition's English label, with {{f_}} refs shown as names.
        """
        table = self.get_table(table_id)
        table = table.get("table", table)
        id_to_name = {f["id"]: f["name"] for f in table.get("fields", [])}
        out = []
        for f in table.get("fields", []):
            ts = f.get("typeSettings") or {}
            out.append({
                "id": f["id"], "name": f["name"], "type": f.get("type"),
                "logic": _refs_to_names(formula_logic(ts), id_to_name),
                "condition": _refs_to_names(ts.get("conditionalRunFormulaText") or "", id_to_name),
                "condition_label": ts.get("conditionalRunFormulaPrompt") or "",
                "waterfall": _refs_to_names(copy.deepcopy(ts.get("formulaWaterfall") or []), id_to_name),
            })
        return out

    def audit_formula_labels(self, table_id: str) -> list[dict]:
        """
        Columns whose plain-English label names something the formula does not use
        (condition label vs condition, waterfall branch prompt vs branch formula).
        Heuristic (quoted values, numbers, column names); read each hit by eye.
        """
        cols = self.describe_columns(table_id)
        names = [c["name"] for c in cols]
        hits = []
        for c in cols:
            drift = label_drift(c["condition_label"], c["condition"], names)
            if drift:
                hits.append({"column": c["name"], "where": "run condition",
                             "label": c["condition_label"], "formula": c["condition"], "missing": drift})
            for i, b in enumerate(c["waterfall"], 1):
                drift = label_drift(b.get("prompt"), b.get("formula"), names)
                if drift:
                    hits.append({"column": c["name"], "where": f"waterfall branch {i}",
                                 "label": b.get("prompt"), "formula": b.get("formula"), "missing": drift})
        return hits

    def audit_route_condition(self, table_id: str, route_field_id: str, view_id: str = None,
                              node_bin: str = "node", timeout: int = 120) -> dict:
        """
        Re-evaluate a Send-table-data column's CURRENT run condition over every source row
        and compare with what it actually routed (LEARNINGS.md #28: a rule edited after the
        run leaves routed rows it now blocks). Returns counts plus record ids for
        "routed_but_ineligible", "eligible_but_unrouted" and "unevaluable".

        The condition is JavaScript written in Clay. It is evaluated locally in node's `vm`
        with an empty context (no require/process/fs) and a per-row timeout; rows whose
        condition throws (e.g. Clay-only helpers) are reported as unevaluable, not guessed.
        Action/source columns the condition references are read from their full value.
        """
        import subprocess
        table = self.get_table(table_id)
        table = table.get("table", table)
        fields = {f["id"]: f for f in table.get("fields", [])}
        route = fields[route_field_id]
        cond = (route.get("typeSettings") or {}).get("conditionalRunFormulaText") or ""
        view_id = view_id or default_view_id(table)
        refs = sorted(set(_FIELD_RE.findall(cond)))
        recs = self.list_records(table_id, view_id)
        values = {r["id"]: {} for r in recs}
        for fid in refs:
            if fields.get(fid, {}).get("type") in ("action", "source"):
                for row in self.fetch_all_records_full(table_id, view_id, fid):
                    values.setdefault(row["record_id"], {})[fid] = row.get("value")
            else:
                for r in recs:
                    cell = (r.get("cells") or {}).get(fid) or {}
                    values[r["id"]][fid] = cell.get("value") if isinstance(cell, dict) else cell
        routed = {r["id"] for r in recs
                  if (((r.get("cells") or {}).get(route_field_id) or {}).get("metadata") or {}).get("status")
                  == "SUCCESS"}
        if not cond:
            eligible = {r["id"]: True for r in recs}
        else:
            js_cond = _FIELD_RE.sub(lambda m: f'__v[{json.dumps(m.group(1))}]', cond)
            script = ("const vm=require('vm');let d='';process.stdin.on('data',c=>d+=c);"
                      "process.stdin.on('end',()=>{const rows=JSON.parse(d);const out={};"
                      "const src='(function(){return ('+" + json.dumps(js_cond) + "+');})()';"
                      "for(const [id,v] of Object.entries(rows)){try{"
                      "out[id]=!!vm.runInNewContext(src,{__v:v},{timeout:200});}"
                      "catch(e){out[id]='ERR: '+String(e&&e.message||e).slice(0,120);}}"
                      "process.stdout.write(JSON.stringify(out));});")
            proc = subprocess.run([node_bin, "-e", script], input=json.dumps(values),
                                  capture_output=True, text=True, timeout=timeout)
            if proc.returncode:
                raise RuntimeError(f"node failed: {proc.stderr[:300]}")
            eligible = json.loads(proc.stdout)
        unevaluable = sorted(r for r, v in eligible.items() if not isinstance(v, bool))
        ok = {r for r, v in eligible.items() if v is True}
        return {
            "condition": _refs_to_names(cond, {k: v["name"] for k, v in fields.items()}),
            "rows": len(recs), "routed": len(routed), "eligible_now": len(ok),
            "routed_but_ineligible": sorted(routed - ok - set(unevaluable)),
            "eligible_but_unrouted": sorted(ok - routed),
            "unevaluable": unevaluable,
        }

    def list_ai_models_in_use(self, table_ids: list[str] = None) -> dict:
        """
        The use-ai model list is dynamic (no catalog), so the reliable list is what live
        columns already bind. Scans table_ids (default: every table in the workspace) and
        returns {"<useCase> | <model>": count}. Models starting "clay-" bill Clay credits,
        not the workspace model key.
        """
        if table_ids is None:
            table_ids = [t["id"] for t in self.list_tables()]
        counts = {}
        for tid in table_ids:
            table = self.get_table(tid)
            table = table.get("table", table)
            for f in table.get("fields", []):
                ts = f.get("typeSettings") or {}
                model = _binding_value(ts, "model")
                if model:
                    key = f"{_use_case_of(ts) or ts.get('actionKey')} | {model}"
                    counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    def credit_balance(self) -> float:
        return float(self.get(f"/workspaces/{self.workspace_id}/credit-balance").get("balance") or 0)

    # ── Column helpers ────────────────────────────────────────────────────────

    def create_action_column(self, table_id: str, name: str,
                             action_key: str, package_id: str,
                             inputs: dict[str, str],
                             view_id: str = None,
                             auth_account_id: str = None,
                             condition: str = None) -> dict:
        """
        Create an action column (enrichment, AI, HTTP API).

        inputs: {input_name: formula_text} e.g. {"person_identifier": "{{f_xxx}}"}
        condition: optional "Only run if" formula (conditionalRunFormulaText)

        Common action_key / package_id combos:
          enrich-person-with-mixrank-v2     / e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2
          enrich-company-with-mixrank-v2    / e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2
          use-ai                            / 67ba01e9-1898-4e7d-afe7-7ebe24819a57
          http-api-v2                       / 4299091f-3cd3-4d68-b198-0143575f471d
        """
        inputs_binding = [{"name": k, "formulaText": v} if v else {"name": k}
                          for k, v in inputs.items()]
        ts = {
            "dataTypeSettings": {"type": "json"},
            "actionKey": action_key,
            "actionVersion": 1,
            "actionPackageId": package_id,
            "inputsBinding": inputs_binding,
        }
        if auth_account_id:
            ts["authAccountId"] = auth_account_id
        if condition:
            ts["conditionalRunFormulaText"] = condition

        return self.create_column(table_id, {
            "type": "action", "name": name, "typeSettings": ts
        }, view_id=view_id)

    def create_formula_column(self, table_id: str, name: str,
                              formula_text: str, view_id: str = None,
                              data_type: str = None,
                              mapped_result_path: list[str] = None,
                              lint: bool = True, prompt=None) -> dict:
        """
        Create a formula column using the create-as-text-then-PATCH pattern.

        prompt (REQUIRED, LEARNINGS.md #86): the plain-English text Clay shows above the
          formula. A list of parts, column names as "[Name]" or "{{f_id}}" (chips), e.g.
          ["True if ", "[Verdict]", " is \"GTG\""]; must name every column the formula
          uses. prompt=False skips it (not recommended).

        data_type: None (default) infers it from the column name with
          guess_column_data_type(): domain / website / url / linkedin -> "url" (clickable),
          email -> "email", else "text" (LEARNINGS.md backlog #54). Pass it to override.

        mapped_result_path: required for nested enrichment data.
          e.g. ["experience", "0", "url"] to extract company LinkedIn URL
          from Enrich Person > experience > 0 > url.
          Without this, nested paths return empty even with the correct formula.

        Refuses formulas Clay would silently return EMPTY for (spread syntax, `new Set`,
        LEARNINGS.md #35; see lint_clay_formula). Pass lint=False to override. Either way,
        prove a new formula on one row you know should have a value before trusting counts.
        """
        issues = lint_clay_formula(formula_text) if lint else []
        if issues:
            raise ValueError(f"formula '{name}': " + "; ".join(issues))
        prompt_text = None
        if prompt is None:
            raise ClayColumnConfigError(
                f"formula '{name}': pass prompt=[...] (plain-English text with '[Column]' chips) "
                "so the column shows what it does in Clay, or prompt=False (LEARNINGS.md #86)")
        if prompt is not False:
            names = {f["name"]: f["id"] for f in self._table_fields(table_id)}
            prompt_text = build_formula_prompt(prompt, names)
            gaps = formula_prompt_gaps(formula_text, prompt_text)
            if gaps:
                raise ClayColumnConfigError(
                    f"formula '{name}': prompt does not name columns the formula uses: "
                    f"{[{v: k for k, v in names.items()}.get(g, g) for g in gaps]}")
        if data_type is None:
            data_type = guess_column_data_type(name) or "text"
        # Step 1: create as text
        field = self.create_column(table_id, {
            "type": "text",
            "name": name,
            "typeSettings": {"dataTypeSettings": {"type": data_type}},
        }, view_id=view_id)
        field_id = (field.get("field") or field).get("id") or field.get("id")

        # Step 2: PATCH with formula
        patch_ts = {
            "formulaText": formula_text,
            "formulaType": "text",
            "dataTypeSettings": {"type": data_type},
        }
        if prompt_text:
            patch_ts["formulaPrompt"] = prompt_text
        if mapped_result_path:
            patch_ts["mappedResultPath"] = mapped_result_path
            patch_ts["formula"] = formula_text

        self.update_column(table_id, field_id, {"typeSettings": patch_ts}, require_prompt=False)
        return {"id": field_id, "name": name}

    def create_lookup_column(self, table_id: str, name: str, target_table_id: str,
                             target_field_id: str, row_value_field_id: str,
                             multiple: bool = False, limit: int = None,
                             view_id: str = None, operator: str = "EQUAL") -> str:
        """
        Create a "Lookup row in other table" column (multiple=True: "Lookup multiple
        rows"). Returns the new field id. addition beyond upstream v2.1, backlog #17.

        Matches rows of target_table_id where target_field_id <operator> this row's
        row_value_field_id. limit (multiple only, 0-100) caps the rows returned.
        Lookups cost 0 Clay credits but still only run when triggered: prove it on
        one row with run_and_wait(), then read the output with read_ai_output()
        (the API cell value is only "✅ Record Found").

        Output shape, keyed by target column NAME (text and formula columns both cross):
          single   -> {"record": {"Col": value, ...}}   extractor {{f}}?.record?.["Col"]
          multiple -> {"records": [{...}, ...]}          extractor ({{f}}?.records || []).filter(...)
        lookup_extract_formula(field_id, "Col", multiple) builds the extractor.
        A lookup keeps its snapshot when the target table changes; refresh it with
        run_column(..., force=True).
        """
        if operator not in LOOKUP_OPERATORS:
            raise ValueError(f"operator must be one of {LOOKUP_OPERATORS}, got {operator!r}")
        if limit is not None and not multiple:
            raise ValueError("limit only applies to multiple=True lookups")
        if limit is not None and not 0 <= int(limit) <= 100:
            raise ValueError("limit must be between 0 and 100")
        binding = [
            {"name": "tableId", "formulaText": json.dumps(target_table_id)},
            {"name": "fields|targetColumn", "formulaText": json.dumps(target_field_id)},
            {"name": "fields|filterOperator", "formulaText": json.dumps(operator)},
            {"name": "fields|rowValue", "formulaText": f"{{{{{row_value_field_id}}}}}"},
        ]
        if limit is not None:
            binding.append({"name": "fields|limit", "formulaText": str(int(limit))})
        field = self.create_column(table_id, {
            "type": "action", "name": name,
            "typeSettings": {
                "dataTypeSettings": {"type": "json"},
                "actionKey": ("lookup-multiple-rows-in-other-table" if multiple
                              else "lookup-row-in-other-table"),
                "actionVersion": 1,
                "actionPackageId": CLAY_UTILITY_PACKAGE_ID,
                "inputsBinding": binding,
                "referencedTableId": target_table_id,
            },
        }, view_id=view_id)
        return field["id"]

    def set_condition(self, table_id: str, field_id: str, condition: str) -> dict:
        """
        Set "Only run if" condition on an action column.
        condition: formula expression, e.g. 'Number({{f_employees}}) > 5'
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        for f in table.get("fields", []):
            if f["id"] == field_id:
                ts = f.get("typeSettings", {})
                ts["conditionalRunFormulaText"] = condition
                return self.update_column(table_id, field_id, {"typeSettings": ts})
        raise ValueError(f"Field {field_id} not found in table {table_id}")

    # ── Sources ────────────────────────────────────────────────────────────────

    def get_source_field_id(self, table_id: str) -> str:
        """
        Return the id of the table's source column. API-created source tables
        get a generated id, so always look it up instead of hard-coding one.
        """
        raw = self.get_table(table_id)
        for f in raw.get("table", raw).get("fields", []):
            if f.get("type") == "source":
                return f["id"]
        raise ValueError(f"No source column in table {table_id}")

    def _create_cpj_source(self, kind: str, workbook_id: str, table_name: str,
                           inputs: dict, workbook_name: str = None) -> dict:
        is_people = kind == "people"
        type_settings = {
            "name": "Find people" if is_people else "Find companies",
            "idPath": "profile_id" if is_people else "linkedin_company_id",
            "iconType": "User" if is_people else "Buildings",
            "actionKey": f"find-lists-of-{kind}-with-mixrank-source",
            "actionPackageId": MIXRANK_PACKAGE_ID,
            "recordsPath": kind,
            "previewTextPath": "name",
            "previewActionKey": f"find-lists-of-{kind}-with-mixrank-source-preview",
            "defaultPreviewText": "Clay Profile" if is_people else "Profile",
            "workbookId": workbook_id,
            "createdFromWorkbookId": workbook_id,
            "scheduleConfig": {"runSettings": "once"},
            # The two sources differ here: people needs False, companies needs
            # True. The wrong value returns HTTP 400.
            "hasEvaluatedInputs": not is_people,
            "disableTriggerOnCreate": True,
            "disableTriggerOnUpdate": True,
            "inputs": inputs,
        }
        return self.post("/sources/create-cpj-table", {
            "workspaceId": str(self.workspace_id),
            "workbookId": workbook_id,
            "workbookName": workbook_name or table_name,
            "cpjConfig": {
                "type": kind,
                "clientSettings": {},
                "typeSettings": type_settings,
                "basicFields": [],
            },
            "tableName": table_name,
        })

    def create_find_companies_source(self, workbook_id: str, table_name: str,
                                     inputs: dict, workbook_name: str = None) -> dict:
        """
        Create a "Find Companies" (MixRank) source table in a workbook.
        Returns {"tableId", "viewId", "workbookId", "sourceId", ...}.

        inputs: search filters, e.g.
            {"sizes": ["200", "500"], "industries": ["Insurance"],
             "country_names": ["Germany"], "company_identifier": [],
             "exclude_entities_configuration": []}
        Source fields to extract afterwards: .name, .linkedin_url (not .url),
        .domain, .country, .size, .description, .industry, .location, .type
        See action-registry.md > Sources.
        """
        return self._create_cpj_source("companies", workbook_id, table_name,
                                       inputs, workbook_name)

    def create_find_people_source(self, workbook_id: str, table_name: str,
                                  inputs: dict, workbook_name: str = None) -> dict:
        """
        Create a "Find People" (MixRank) source table in a workbook.
        Returns {"tableId", "viewId", "workbookId", "sourceId", ...}.

        To limit people to the companies in a Companies table, inputs must set
        ALL of: company_table_id, company_table_view_id, company_table_field_id
        (the Domain COLUMN of that table, not its source column) and
        company_identifier (a non-empty list of real domain strings). Without
        them the search ignores your companies and returns people from
        anywhere who match the title keywords.
        This filters by company domain. When branches or franchisees share the
        brand's domain, a domain filter pulls people from every branch; scope
        by company LinkedIn URL instead with the DSL people search source
        described in .claude/skills/design-clay-table-json/SKILL.md (starter-kit root).
        Source fields to extract afterwards: .first_name, .last_name, .name,
        .latest_experience_title, .location_name, .domain, .url (profile URL)
        See action-registry.md > Sources.
        """
        return self._create_cpj_source("people", workbook_id, table_name,
                                       inputs, workbook_name)

    def create_find_jobs_source(self, workbook_id: str, table_name: str,
                                company_table_id: str, company_view_id: str,
                                company_linkedin_field_id: str = None,
                                company_record_ids: list[str] = None,
                                company_linkedin_urls: list[str] = None,
                                job_title_keywords: list[str] = None,
                                max_days_since_posted: int = 30,
                                limit_per_company: int = 1,
                                locations: list[str] = ("United States",),
                                employment_type: list[str] = ("Full-time",),
                                job_title_exclude_keywords: list[str] = None,
                                workbook_name: str = None,
                                total_limit: int = 25000,
                                company_identifier_field_id: str = None,
                                company_identifiers: list[str] = None) -> dict:
        """
        Create a Clay "Find Jobs" (MixRank) source table over the companies in one of
        your tables (addition beyond upstream v2.1, backlog #21; config copied from a table
        built in the Clay UI, verified live 2026-09-25).
        Returns {"tableId", "viewId", "workbookId", "sourceId", ...}.

        company_identifier_field_id (alias of company_linkedin_field_id): the column of
        the companies table that identifies each company, a company LinkedIn URL OR a
        company DOMAIN column (both verified live 2026-09-28: stripe.com by domain and by
        LinkedIn returned the same jobs; LEARNINGS.md #29). company_record_ids /
        company_identifiers (alias of company_linkedin_urls): the rows to search and their
        identifier values, same order (both non-empty, equal length). The old names still
        work; the new ones win when both are given.
        The source RUNS ON CREATE (0 credits so far). limit_per_company and the
        company list are the row cap, so keep both small for tests.
        Clay creates the table auto-run ON and auto-named; this renames it to
        table_name and turns auto-run off (ClayTableConfigError if either fails).

        Source fields to extract afterwards (FIND_JOBS_FIELDS): .company_name,
        .title, .company_url (company LinkedIn), .domain, .posted_at, .seniority,
        .location, .url (job posting). See action-registry.md > Find Jobs.
        """
        company_linkedin_field_id = company_identifier_field_id or company_linkedin_field_id
        if not company_linkedin_field_id:
            raise ValueError("pass company_identifier_field_id (LinkedIn or domain column)")
        if company_identifiers is not None:
            company_linkedin_urls = company_identifiers
        record_ids, urls = list(company_record_ids or []), list(company_linkedin_urls or [])
        if not record_ids or not urls:
            raise ValueError("company_record_ids and company_linkedin_urls must be non-empty")
        if len(record_ids) != len(urls):
            raise ValueError(f"{len(record_ids)} record ids vs {len(urls)} LinkedIn URLs: "
                             "pass them in matching order")
        if not job_title_keywords:
            raise ValueError("job_title_keywords must be non-empty")
        if int(limit_per_company) < 1:
            raise ValueError("limit_per_company must be >= 1")
        # Clay rejects the create with 400 "Your current plan provides up to 25,000 per search."
        # when limit/sourceRecordLimit exceed the plan cap (LEARNINGS 2026-09-28). Default 25,000.
        if not 1 <= int(total_limit) <= 25000:
            raise ValueError("total_limit must be 1..25000 (Clay plan cap per search)")
        inputs = {
            "name": "",
            "startFrom": "ClayTableOfCompanies",
            "company_table_id": company_table_id,
            "company_table_view_id": company_view_id,
            "company_table_field_id": company_linkedin_field_id,
            "company_identifier": urls,
            "company_record_id": record_ids,
            "job_title_keywords": list(job_title_keywords),
            "max_num_days_since_posted": int(max_days_since_posted),
            "min_num_days_since_posted": None,
            "limit_per_company": int(limit_per_company),
            "limit": int(total_limit),
            "locations": list(locations or []),
            "locations_exclude": [],
            "employment_type": list(employment_type or []),
            "seniority": [],
            "has_recruiter": False,
            "job_description_keywords": [],
            "job_title_exclude_keywords": list(job_title_exclude_keywords or []),
            "exclude_job_identifiers": [],
        }
        type_settings = {
            "name": "Find jobs",
            "idPath": "job_id",
            "iconType": "Briefcase",
            "actionKey": "find-lists-of-jobs-with-mixrank-source",
            "actionPackageId": MIXRANK_PACKAGE_ID,
            "recordsPath": "jobs",
            "previewTextPath": "title",
            "previewActionKey": "find-lists-of-jobs-with-mixrank-source-preview",
            "defaultPreviewText": "Profile",
            "sourceRecordLimit": int(total_limit),
            "workbookId": workbook_id,
            "createdFromWorkbookId": workbook_id,
            "scheduleConfig": {"runSettings": "once"},
            "hasEvaluatedInputs": True,
            "disableTriggerOnCreate": True,
            "disableTriggerOnUpdate": True,
            "inputs": inputs,
        }
        res = self.post("/sources/create-cpj-table", {
            "workspaceId": str(self.workspace_id),
            "workbookId": workbook_id,
            "workbookName": workbook_name or table_name,
            "cpjConfig": {
                "type": "jobs",
                "clientSettings": {},
                "typeSettings": type_settings,
                "basicFields": [],
            },
            "tableName": table_name,
        })
        self._settle_new_table(res["tableId"], table_name, auto_run=False)
        return res

    # ── Search DSL sources (addition beyond upstream v2.1, reverse-engineered 2026-09-24) ──

    def search_dsl_preview(self, query: str) -> dict:
        """
        Free preview of a Search DSL query. Imports nothing, costs nothing.
        Returns {"totalCount", "rowCount", "rows" (up to 250), "previewCoverage", "durationMs"}.
        People rows are FLAT, not the table payload: name them with parse_dsl_preview_row()
        (LEARNINGS.md #31). See action-registry.md > Search DSL source.
        """
        validate_dsl_query(query)
        return self.post(f"/workspaces/{self.workspace_id}/search-dsl/query",
                         {"query": query, "selectMode": "preview"})

    def send_search_dsl_to_table(self, query: str, table_name: str, workbook_id: str,
                                 extra_columns: list[str] = None) -> dict:
        """
        Create a table with a Search DSL source in an existing workbook and run it.
        Returns {"tableId", "viewId", "workbookId", "sourceId"} (+ "extraColumns").

        The run starts on creation, so the query's own `limit N` is the only row cap:
        a query without one raises. Clay creates the table with auto-run ON; this
        switches it off before returning.

        extra_columns (LEARNINGS.md #31): people tables get no Company Domain / Start Date
        column by default. Pass names from DSL_EXTRA_COLUMNS (e.g. ["company_domain",
        "start_date"]) to add them as formula columns on the source field.

        WARNING (LEARNINGS.md backlog #24, seen live 2026-09-25): a query using
        clay.filter_to_companies(@table(...)) makes Clay add a
        `trigger-find-people-source` ACTION column to the referenced companies
        table. Never run that column (it starts a people search per company). Leave
        it or delete it, and tell whoever owns that table it appeared.
        """
        if not re.search(r"\blimit\s+\d+", query, re.I):
            raise ValueError("Add 'limit N' to the DSL query: the source runs as soon as it is created.")
        validate_dsl_query(query)
        unknown = [c for c in extra_columns or [] if c not in DSL_EXTRA_COLUMNS]
        if unknown:
            raise ValueError(f"unknown extra_columns {unknown}; choose from {sorted(DSL_EXTRA_COLUMNS)}")
        res = self.post(f"/workspaces/{self.workspace_id}/search-dsl/send-to-table",
                        {"dslQuery": query, "tableName": table_name, "workbookId": workbook_id})
        self.patch(f"/tables/{res['tableId']}", {"tableSettings": {"AUTO_RUN_ON": False}})
        if extra_columns:
            source_field = self.get_source_field_id(res["tableId"])
            res["extraColumns"] = {}
            for key in extra_columns:
                name, path = DSL_EXTRA_COLUMNS[key]
                field = self.create_column(res["tableId"], {"type": "formula", "name": name, "typeSettings": {
                    "formulaType": "text", "formulaText": "{{" + source_field + "}}" + path,
                    "formulaPrompt": build_formula_prompt([f"{name} from ", "{{%s}}" % source_field]),
                    "dataTypeSettings": {"type": "text"}}}, view_id=res.get("viewId"))
                res["extraColumns"][name] = field["id"]
        return res

    def add_search_dsl_source(self, table_id: str, query: str) -> dict:
        """
        Add another Search DSL source to an EXISTING table (LEARNINGS.md #33): rows land in
        the same source column, so the table's formulas cover them. Sources do not dedupe
        against each other: call set_table_dedupe() on the person LinkedIn column first.
        Runs immediately; the query's `limit N` is the only cap.
        """
        if not re.search(r"\blimit\s+\d+", query, re.I):
            raise ValueError("Add 'limit N' to the DSL query: the source runs as soon as it is added.")
        validate_dsl_query(query)
        table = self.get_table(table_id)
        table = table.get("table", table)
        res = self.post(f"/workspaces/{self.table_workspace(table_id)}/search-dsl/send-to-table",
                        {"dslQuery": query, "destinationTableId": table_id,
                         "tableName": table.get("name"), "workbookId": table.get("workbookId")})
        if res.get("tableId") not in (None, table_id) or res.get("isNewTable"):
            raise ClayTableConfigError(f"Clay created a new table {res.get('tableId')} instead of "
                                       f"adding a source to {table_id}")
        return res

    def set_table_dedupe(self, table_id: str, field_id: str, keep: str = "keep_oldest") -> dict:
        """
        Table-level dedupe on one column (e.g. LinkedIn Profile). Collapses existing
        duplicates within seconds and applies to later imports (LEARNINGS.md #33). Reads back.
        """
        if keep not in ("keep_oldest", "keep_newest"):
            raise ValueError("keep must be 'keep_oldest' or 'keep_newest'")
        self.patch(f"/tables/{table_id}", {"tableSettings": {"DEDUPE_FIELD_ID": field_id,
                                                              "DEDUPE_KEEP_STRATEGY": keep}})
        table = self.get_table(table_id)
        table = table.get("table", table)
        ts = table.get("tableSettings") or {}
        if ts.get("DEDUPE_FIELD_ID") != field_id:
            raise ClayTableConfigError(f"table {table_id}: dedupe field did not stick: {ts}")
        return table

    def rename_source(self, source_id: str, name: str) -> dict:
        """
        Rename a source (LEARNINGS.md #59): Search DSL sources added with add_search_dsl_source()
        all inherit the TABLE name, so a multi-slice table shows N identical source names.
        Patches name + typeSettings.name, leaves the query untouched, reads back.
        """
        src = self.get(f"/sources/{source_id}")
        ts = dict(src.get("typeSettings") or {})
        ts["name"] = name
        self.patch(f"/sources/{source_id}", {"name": name, "typeSettings": ts})
        back = self.get(f"/sources/{source_id}")
        if back.get("name") != name:
            raise ClayTableConfigError(f"source {source_id}: rename did not stick ({back.get('name')!r})")
        return back

    def source_table_id(self, source_id: str) -> str:
        """The table a source writes into (sourceSubscriptions[0].tableId; the top-level tableId is null)."""
        src = self.get(f"/sources/{source_id}")
        subs = src.get("sourceSubscriptions") or []
        return (subs[0] if subs else {}).get("tableId") or src.get("tableId")

    def update_and_run_search_dsl_source(self, source_id: str, query: str, mode: str = "add",
                                         allow_row_loss: bool = False) -> dict:
        """
        Change the query on an existing Search DSL source and re-run it (verified live).
        mode "add": appends the next page, up to N people the source has not returned yet.
        mode "replace": DELETES every existing row, then imports from the new query, so
        values written into those rows are lost. Refused (LEARNINGS.md #9) when the table
        has text or action columns (written values, enrichment results) unless
        allow_row_loss=True; formula columns recompute and do not block it.
        Returns {"sourceRunId"}; poll /workspaces/{ws}/sources/{id}/runs for the result.
        """
        if mode not in ("add", "replace"):
            raise ValueError("mode must be 'add' or 'replace'")
        if not re.search(r"\blimit\s+\d+", query, re.I):
            raise ValueError("Add 'limit N' to the DSL query: the source re-runs immediately.")
        validate_dsl_query(query)
        if mode == "replace" and not allow_row_loss:
            table_id = self.source_table_id(source_id)
            table = self.get_table(table_id) if table_id else {}
            table = table.get("table", table)
            at_risk = [f"{f['name']} ({f['type']})" for f in table.get("fields", [])
                       if f.get("type") in ("text", "action")]
            if at_risk:
                raise ValueError(f"mode='replace' deletes every row of {table_id}, and these columns "
                                 f"hold values that would be lost: {at_risk}. Use mode='add', or pass "
                                 f"allow_row_loss=True if losing them is intended.")
        return self.post(f"/workspaces/{self.workspace_id}/search-dsl/sources/{source_id}/update-and-run",
                         {"dslQuery": query, "mode": mode})

    def compare_dsl_scopes(self, people_where: str, domains: list[str], table_ref: str) -> dict:
        """
        Preview one people search under both company scopes before importing
        (LEARNINGS.md #32): a literal `company.domain in (...)` list vs
        clay.filter_to_companies(@table("t:v:f")). Target-companies resolves each account
        to ONE Clay company entity, so brands with several entities lose people.
        people_where: conditions inside experiences.count(...), e.g.
            'job_title is_similar_to ("Head of Reliability")'
        Returns totals plus the (sampled, <=250 rows each) companies only one scope found.
        Free: previews import nothing.
        """
        doms = ", ".join(json.dumps(d.strip().lower()) for d in domains if d and d.strip())
        q_domain = (f"select from people where experiences.count(is_current = true and "
                    f"company.domain in ({doms}) and {people_where}) >= 1 limit 250")
        q_target = (f"select from people where clay.filter_to_companies(@table({json.dumps(table_ref)})) "
                    f"and experiences.count(is_current = true and {people_where}) >= 1 limit 250")
        out = {}
        for key, q in (("domain_list", q_domain), ("target_companies", q_target)):
            r = self.search_dsl_preview(q)
            cos = {(parse_dsl_preview_row(row).get("matched_company") or "").strip()
                   for row in r.get("rows") or []}
            out[key] = {"query": q, "total": r.get("totalCount"), "coverage": r.get("previewCoverage"),
                        "companies": sorted(c for c in cos if c)}
        a, b = set(out["domain_list"]["companies"]), set(out["target_companies"]["companies"])
        out["only_domain_list"] = sorted(a - b)
        out["only_target_companies"] = sorted(b - a)
        return out

    def lookup_companies_by_domain(self, domains: list[str], workbook_id: str,
                                   filters: str = None, table_name: str = None,
                                   timeout: int = 180) -> dict:
        """
        Resolve many domains to Clay company entities with ONE free import instead of one
        250-row preview per company (LEARNINGS.md #16: 5k previews ~3h, one import ~2 min).
        Creates a table in workbook_id (use a scratch workbook) with
        `select from companies where domain in (...) [and filters]`, waits for the rows and
        returns {"table_id", "by_domain": {domain: [company, ...]}, "missing": [...]}.
        One domain maps to MANY entities (live 2026-09-29: stripe.com -> 34, incl. "DanielTems"
        and an Andorra "Stripe"; clay.com -> 7, incl. "Clay University"), in no useful order.
        Never take the first match: "best" ranks each domain's list with
        best_company_for_domain() (name / LinkedIn slug = domain root, then larger size),
        and still deserves a look for brands whose name differs from their domain.
        """
        doms = sorted({d.strip().lower() for d in domains if d and d.strip()})
        if not doms:
            raise ValueError("no domains")
        where = f"domain in ({', '.join(json.dumps(d) for d in doms)})"
        if filters:
            where += f" and {filters}"
        query = f"select from companies where {where} limit {max(50, len(doms) * 50)}"
        res = self.send_search_dsl_to_table(query, table_name or f"Domain lookup {len(doms)}", workbook_id)
        table_id, view_id = res["tableId"], res["viewId"]
        source_field = self.get_source_field_id(table_id)
        start, last = time.time(), -1
        while time.time() - start < timeout:
            time.sleep(10)
            n = len(self.get_record_ids(table_id, view_id))
            if n and n == last:
                break
            last = n
        by_domain = {}
        for rec in self.fetch_all_records_full(table_id, view_id, source_field):
            v = rec.get("value") or {}
            d = (v.get("domain") or "").lower()
            by_domain.setdefault(d, []).append({
                "clay_company_id": (v.get("clay_metadata") or {}).get("clay_company_id"),
                "name": v.get("name"), "size": v.get("size"), "industry": v.get("industry"),
                "linkedin_url": (v.get("social_urls") or {}).get("linkedin"),
                "country": (v.get("primary_location") or {}).get("country"),
                "record_id": rec.get("record_id"),
            })
        return {"table_id": table_id, "by_domain": by_domain,
                "best": {d: best_company_for_domain(d, cos) for d, cos in by_domain.items()},
                "missing": [d for d in doms if d not in by_domain]}

    def create_webhook_source(self, table_id: str, name: str = "Webhook") -> dict:
        """Create a webhook source on a table. Returns source dict with webhook URL."""
        res = self.post("/sources", {
            "workspaceId": int(self.workspace_id),
            "tableId": table_id,
            "name": name,
            "type": "webhook",
            "typeSettings": {},
        })
        source = res.get("source", res)
        return source

    def create_route_row_column(self, table_id: str, name: str,
                                target_table_id: str, row_data: dict,
                                condition: str = None, list_data: str = None,
                                view_id: str = None, column_types="auto") -> dict:
        """
        Create a "Send table data" (route-row) action column that writes one
        row per source record into another table (e.g. Companies -> People).

        row_data: {target column name: formula}, e.g.
            {"Company Domain": "{{f_domain}}", "Company Name": "{{f_name}}"}
        list_data: optional formula returning a list; sends one row per list
            item (list mode) instead of one row per record.
        condition: optional "Only run if" formula. Use one: routing is a write
            into another table.
        column_types (LEARNINGS.md backlog #4): Clay creates every
            routed column in the target as text, which later breaks Enrich
            Person, LinkedIn scrapers and email finders. "auto" (default) retypes
            identity columns by name (see guess_route_column_types); pass a
            {column name: "url" | "email" | "text"} dict to choose, or None to skip.
        """
        bindings = [
            {"name": "tableId", "formulaText": json.dumps(target_table_id)},
            {"name": "rowData", "formulaMap": row_data},
        ]
        if list_data:
            bindings += [
                {"name": "type", "formulaText": '"list"'},
                {"name": "listData", "formulaText": list_data},
            ]
        ts = {
            "dataTypeSettings": {"type": "json"},
            "actionKey": "route-row",
            "actionVersion": 1,
            "actionPackageId": ROUTE_ROW_PACKAGE_ID,
            "inputsBinding": bindings,
            "referencedTableId": target_table_id,
        }
        if condition:
            ts["conditionalRunFormulaText"] = condition
        created = self.create_column(table_id, {
            "type": "action", "name": name, "typeSettings": ts,
        }, view_id=view_id)
        types = guess_route_column_types(row_data) if column_types == "auto" else column_types
        if types:
            self.retype_route_columns(target_table_id, types, skip_missing=(column_types == "auto"))
        return created

    def retype_route_columns(self, target_table_id: str, column_types: dict,
                             skip_missing: bool = False) -> dict:
        """
        Set the data type of routed columns in a route-row TARGET table, keeping
        their formulas. Clay creates them (as text) as soon as the route column
        exists, so this can run right after create_route_row_column().
        column_types: {column name: "url" | "email" | "text"}. Reads each back.
        Returns {column name: field_id}. (LEARNINGS.md backlog #4)
        """
        bad = {n: t for n, t in column_types.items() if t not in ROUTE_COLUMN_TYPES}
        if bad:
            raise ValueError(f"unsupported types {bad}; use one of {sorted(ROUTE_COLUMN_TYPES)}")
        table = self.get_table(target_table_id)
        by_name = {f.get("name"): f for f in table.get("table", table).get("fields", [])}
        missing = [n for n in column_types if n not in by_name]
        if missing and skip_missing:
            warnings.warn(f"retype_route_columns: {missing} not found in {target_table_id}, "
                          f"left as Clay created them; retype them once they exist")
            column_types = {n: t for n, t in column_types.items() if n in by_name}
        elif missing:
            raise KeyError(f"target table {target_table_id} has no columns {missing}; "
                           f"available: {sorted(by_name)}")
        done = {}
        for col, dtype in column_types.items():
            fid = by_name[col]["id"]
            self.update_column(target_table_id, fid, {"typeSettings": {"dataTypeSettings": {"type": dtype}}})
            done[col] = fid
        table = self.get_table(target_table_id)
        live = {f.get("id"): f for f in table.get("table", table).get("fields", [])}
        wrong = {c: ((live.get(fid) or {}).get("typeSettings") or {}).get("dataTypeSettings")
                 for c, fid in done.items()
                 if (((live.get(fid) or {}).get("typeSettings") or {}).get("dataTypeSettings") or {})
                 .get("type") != column_types[c]}
        if wrong:
            raise ClayColumnConfigError(f"routed columns not retyped as asked: {wrong}")
        return done

    # ── Enrichments / Actions ─────────────────────────────────────────────────

    def search_enrichments(self, query: str) -> list[dict]:
        """Search available enrichment actions by keyword."""
        body = {
            "userQuery": query,
            "types": ["action", "waterfall", "template", "source_action"],
        }
        res = self.post(f"/enrichment-search/{self.workspace_id}/query", body)
        return res.get("results", [])

    def list_actions(self) -> list[dict]:
        return self.get("/actions")

    def list_auth_accounts(self) -> list[dict]:
        """List all connected integration accounts (OpenAI, LeadMagic, etc.)"""
        res = self.get(f"/workspaces/{self.workspace_id}/app-accounts")
        return res if isinstance(res, list) else res.get("accounts", [])

    def list_subroutines(self) -> list[dict]:
        res = self.get(f"/workspaces/{self.workspace_id}/subroutines")
        return res.get("subroutines", res)

    # ── Portable Schema (ClayMate format) ─────────────────────────────────────

    def export_schema(self, table_id: str, column_names: list[str] = None) -> dict:
        """
        Export a table as a portable ClayMate-compatible schema.
        Field IDs are converted to {{@Column Name}} references.
        Optionally filter to specific column_names.
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        fields = table.get("fields", [])

        # Determine view-based field order
        grid_views = table.get("gridViews", [])
        view = grid_views[0] if grid_views else None
        view_order = view.get("fieldOrder", []) if view else []
        ordered_ids = view_order if view_order else [f["id"] for f in fields]

        # Build ordered field list (skip system fields)
        skip = {"f_created_at", "f_updated_at"}
        ordered_fields = []
        for fid in ordered_ids:
            if fid in skip:
                continue
            fd = next((f for f in fields if f["id"] == fid), None)
            if fd:
                ordered_fields.append(fd)

        # Filter to selected columns if specified
        if column_names:
            names_set = set(column_names)
            # Include dependencies too
            id_to_name = {f["id"]: f["name"] for f in ordered_fields}
            selected = [f for f in ordered_fields if f["name"] in names_set]
            # Also include any column referenced by selected columns
            for f in selected:
                ts_str = json.dumps(f.get("typeSettings", {}))
                for ref_id in re.findall(r"\{\{(f_[a-zA-Z0-9_]+)\}\}", ts_str):
                    dep_name = id_to_name.get(ref_id)
                    if dep_name:
                        names_set.add(dep_name)
            ordered_fields = [f for f in ordered_fields if f["name"] in names_set]

        # Build ID → name maps
        id_to_name = {f["id"]: f["name"] for f in ordered_fields}
        field_order = [f["id"] for f in ordered_fields]

        # Fetch source details for source columns
        for field in ordered_fields:
            if field.get("type") == "source":
                source_ids = (field.get("typeSettings") or {}).get("sourceIds", [])
                if source_ids:
                    try:
                        field["_sourceDetails"] = [
                            self.get(f"/sources/{sid}") for sid in source_ids
                        ]
                    except Exception:
                        pass

        # Build source data ref map
        source_data_ref_to_name = {}
        for f in ordered_fields:
            for sd in f.get("_sourceDetails", []):
                if sd.get("dataFieldId"):
                    source_data_ref_to_name[sd["dataFieldId"]] = f["name"]

        # Convert to portable format
        columns = []
        for idx, field in enumerate(ordered_fields):
            col = {
                "index": idx,
                "name": field["name"],
                "type": field["type"],
            }
            if field.get("typeSettings"):
                col["typeSettings"] = _refs_to_names(
                    copy.deepcopy(field["typeSettings"]),
                    id_to_name, source_data_ref_to_name,
                )
            if field.get("_sourceDetails"):
                col["sourceDetails"] = [
                    {
                        "name": sd["name"],
                        "type": sd.get("type", "webhook"),
                        "dataFieldId": sd.get("dataFieldId"),
                        "typeSettings": _refs_to_names(
                            copy.deepcopy(sd.get("typeSettings", {})),
                            id_to_name, source_data_ref_to_name,
                        ),
                    }
                    for sd in field["_sourceDetails"]
                ]
            columns.append(col)

        schema = {
            "version": "1.0",
            "exportedAt": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "tableId": table_id,
            "columnCount": len(columns),
            "columns": columns,
        }
        print(f"[clay] exported {len(columns)} columns from {table_id}")
        return schema

    def import_schema(self, table_id: str, schema: dict, dry_run: bool = False) -> list[dict]:
        """
        Import a portable ClayMate schema into a table.
        Resolves {{@Column Name}} refs to real field IDs.
        Creates columns in dependency order. Returns list of results.
        """
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        existing = table.get("fields", [])
        view_id = default_view_id(table)

        # Name → ID map (existing columns)
        name_to_id = {f["name"]: f["id"] for f in existing}
        source_name_to_data_ref = {}

        columns = schema.get("columns", [])
        sorted_cols = _sort_by_deps(columns)

        if dry_run:
            print(f"[clay] DRY RUN: would create {len(sorted_cols)} columns:")
            for c in sorted_cols:
                deps = _extract_deps(c.get("typeSettings"))
                dep_str = f" (depends on: {', '.join(deps)})" if deps else ""
                print(f"  {c['type']:8s} | {c['name']}{dep_str}")
            return []

        results = []
        print(f"[clay] importing {len(sorted_cols)} columns into {table_id}...")

        for col in sorted_cols:
            col_type = col.get("type", "text")
            try:
                if col_type == "source" and col.get("sourceDetails"):
                    created_source_ids = []
                    for sd in col["sourceDetails"]:
                        ts = _names_to_refs(
                            copy.deepcopy(sd.get("typeSettings", {})),
                            name_to_id, source_name_to_data_ref,
                        )
                        src = self.post("/sources", {
                            "workspaceId": int(self.workspace_id),
                            "tableId": table_id,
                            "name": sd["name"],
                            "type": sd.get("type", "v3-action"),
                            "typeSettings": ts,
                        })
                        sid = src.get("id") or (src.get("source") or {}).get("id")
                        if sid:
                            created_source_ids.append(sid)
                            dfid = src.get("dataFieldId") or (src.get("source") or {}).get("dataFieldId")
                            if not dfid:
                                try:
                                    dfid = self.get(f"/sources/{sid}").get("dataFieldId")
                                except Exception:
                                    pass
                            if dfid:
                                source_name_to_data_ref[col["name"]] = dfid
                        time.sleep(0.15)

                    if not created_source_ids:
                        raise Exception("No sources created")

                    result = self._create_field(table_id, view_id, {
                        "name": col["name"],
                        "type": "source",
                        "typeSettings": {
                            "sourceIds": created_source_ids,
                            "canCreateRecords": (col.get("typeSettings") or {}).get("canCreateRecords", True),
                        },
                    })
                else:
                    ts = None
                    if col.get("typeSettings"):
                        ts = _names_to_refs(
                            copy.deepcopy(col["typeSettings"]),
                            name_to_id, source_name_to_data_ref,
                        )

                    field_def = {"name": col["name"], "type": col_type}
                    if ts:
                        field_def["typeSettings"] = ts

                    # Text columns need dataTypeSettings
                    if col_type == "text":
                        field_def.setdefault("typeSettings", {})
                        field_def["typeSettings"].setdefault("dataTypeSettings", {"type": "text"})

                    # Formula columns: create as text, then PATCH formulaText
                    if col_type == "formula" and ts and ts.get("formulaText"):
                        formula_ts = ts
                        field_def["type"] = "text"
                        field_def["typeSettings"] = {"dataTypeSettings": ts.get("dataTypeSettings", {"type": "text"})}
                        result = self._create_field(table_id, view_id, field_def)
                        fid = (result.get("field") or result).get("id")
                        if fid:
                            self.patch(f"/tables/{table_id}/fields/{fid}", {"typeSettings": formula_ts})
                    elif col_type == "action" and ts:
                        ts.setdefault("dataTypeSettings", {"type": "text"})
                        field_def["typeSettings"] = ts
                        result = self._create_field(table_id, view_id, field_def)
                    else:
                        result = self._create_field(table_id, view_id, field_def)

                fid = (result.get("field") or result).get("id")
                if fid:
                    name_to_id[col["name"]] = fid
                results.append({"success": True, "name": col["name"]})
                print(f"  [ok] {col['name']}")

            except Exception as e:
                results.append({"success": False, "name": col["name"], "error": str(e)})
                print(f"  [FAIL] {col['name']}: {e}")

            time.sleep(0.15)

        ok = sum(1 for r in results if r["success"])
        fail = sum(1 for r in results if not r["success"])
        print(f"[clay] done: {ok} created, {fail} failed")
        return results

    def _create_field(self, table_id: str, view_id: str, field_def: dict) -> dict:
        """Internal: create field with view context."""
        body = {**field_def, "activeViewId": view_id}
        return self.post(f"/tables/{table_id}/fields", body)


# ── typeSettings merge ───────────────────────────────────────────────────────

def merge_type_settings(current: dict, updates: dict) -> dict:
    """
    Merge a partial typeSettings update into a column's current typeSettings.
    Returns a new dict; neither input is modified.

    - dicts merge recursively
    - "inputsBinding" lists merge by input "name"; within one input, the
      keys given replace the current ones and other keys are kept
    - a value of None deletes the key
    - anything else replaces the current value
    """
    merged = copy.deepcopy(current or {})
    for key, value in (updates or {}).items():
        if value is None:
            merged.pop(key, None)
        elif key == "inputsBinding" and isinstance(value, list):
            merged[key] = _merge_inputs_binding(merged.get(key) or [], value)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_type_settings(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _merge_inputs_binding(current: list, updates: list) -> list:
    result = [copy.deepcopy(b) for b in current]
    index = {b.get("name"): i for i, b in enumerate(result) if isinstance(b, dict)}
    for b in updates:
        name = b.get("name") if isinstance(b, dict) else None
        if name in index:
            # Update only the keys given for this input (e.g. formulaText);
            # keep its other keys. A key's value is replaced wholesale.
            existing = result[index[name]]
            existing.update(copy.deepcopy(b))
            for k in [k for k, v in b.items() if v is None]:
                existing.pop(k, None)
        else:
            result.append(copy.deepcopy(b))
            if name is not None:
                index[name] = len(result) - 1
    return result


# ── Portable schema helpers ──────────────────────────────────────────────────

_FIELD_RE = re.compile(r"\{\{(f_[a-zA-Z0-9_]+)\}\}")
_NAME_RE = re.compile(r"\{\{@([^}]+)\}\}")
_SOURCE_RE = re.compile(r"\{\{@source:([^}]+)\}\}")


def _refs_to_names(obj, id_to_name: dict, source_ref_to_name: dict = None):
    """Convert {{f_xxx}} → {{@Column Name}} in any nested structure."""
    if source_ref_to_name is None:
        source_ref_to_name = {}
    if isinstance(obj, str):
        def replace(m):
            fid = m.group(1)
            name = id_to_name.get(fid)
            if name:
                return "{{@" + name + "}}"
            sname = source_ref_to_name.get(fid)
            if sname:
                return "{{@source:" + sname + "}}"
            return m.group(0)
        return _FIELD_RE.sub(replace, obj)
    if isinstance(obj, list):
        return [_refs_to_names(item, id_to_name, source_ref_to_name) for item in obj]
    if isinstance(obj, dict):
        return {k: _refs_to_names(v, id_to_name, source_ref_to_name) for k, v in obj.items()}
    return obj


def _names_to_refs(obj, name_to_id: dict, source_name_to_ref: dict = None):
    """Convert {{@Column Name}} → {{f_xxx}} in any nested structure."""
    if source_name_to_ref is None:
        source_name_to_ref = {}
    if isinstance(obj, str):
        result = _SOURCE_RE.sub(
            lambda m: "{{" + source_name_to_ref.get(m.group(1), m.group(0)) + "}}"
            if m.group(1) in source_name_to_ref else m.group(0),
            obj,
        )
        result = _NAME_RE.sub(
            lambda m: "{{" + name_to_id[m.group(1)] + "}}"
            if m.group(1) in name_to_id else m.group(0),
            result,
        )
        return result
    if isinstance(obj, list):
        return [_names_to_refs(item, name_to_id, source_name_to_ref) for item in obj]
    if isinstance(obj, dict):
        return {k: _names_to_refs(v, name_to_id, source_name_to_ref) for k, v in obj.items()}
    return obj


def _extract_deps(type_settings) -> list[str]:
    """Extract column names referenced via {{@Name}} in typeSettings."""
    if not type_settings:
        return []
    deps = set()
    s = json.dumps(type_settings)
    for m in _SOURCE_RE.finditer(s):
        deps.add(m.group(1))
    for m in _NAME_RE.finditer(s):
        if not m.group(1).startswith("source:"):
            deps.add(m.group(1))
    return list(deps)


def _sort_by_deps(columns: list[dict]) -> list[dict]:
    """Topological sort: sources first, then by dependency order."""
    by_name = {c["name"]: c for c in columns}
    dep_map = {c["name"]: _extract_deps(c.get("typeSettings")) for c in columns}

    result = []
    visited = set()
    visiting = set()

    def visit(name):
        if name in visited or name not in by_name:
            return
        if name in visiting:
            return  # cycle: skip
        visiting.add(name)
        for dep in dep_map.get(name, []):
            visit(dep)
        visiting.discard(name)
        visited.add(name)
        result.append(by_name[name])

    # Sources first
    for c in columns:
        if c.get("type") == "source":
            visit(c["name"])
    for c in columns:
        visit(c["name"])

    return result


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    clay = ClayClient()

    print("\n--- Tables ---")
    tables = clay.list_tables()
    for t in tables[:10]:
        rtype = t.get("resourceType", "")
        name = t.get("name", "?")
        rid = t.get("id", "")
        print(f"  [{rtype}] {name} ({rid})")

    print("\n--- Auth Accounts ---")
    accounts = clay.list_auth_accounts()
    if isinstance(accounts, list):
        for a in accounts[:10]:
            print(f"  {a.get('name', a.get('displayName', '?'))} ({a.get('id')})")

    print("\n--- Formula generation test ---")
    # Use a real table id from the list above to test
    tables_only = [t for t in tables if t.get("resourceType") == "TABLE"]
    if tables_only:
        tid = tables_only[0]["id"]
        result = clay.generate_formula(tid, "If company name is empty, output 'Unknown'")
        print(f"  Prompt: 'If company name is empty, output Unknown'")
        print(f"  Formula: {result.get('formula')}")
