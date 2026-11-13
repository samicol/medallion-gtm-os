#!/usr/bin/env python3
"""
clay_workspace_costs.py: read-only monthly cost audit of a whole Clay workspace.

What it answers: "what did my Clay workspace spend this month, by table and
by integration, and what did the AI columns cost on my own provider keys?"

It reports two billing axes and never adds them together:

1. Clay credits, from Clay's workspace credit reporting. The daily spend time
   series is the canonical total (one bucket per UTC day). The workspace,
   table and integration reports attribute that total, and each must cover a
   minimum share of it.
2. AI provider USD, from the cost Clay stores on every charged Use AI cell
   (`totalCostToAIProvider`). Refunded cells are excluded. This is what your
   own model provider key was billed through Clay.

Consistency gates fail closed: a duplicate identity, a missing or duplicate
daily bucket, an incomplete read or attribution coverage below the threshold
stops the run with an error code and writes no report.

The audit is strictly read-only. The HTTP session used here refuses any
method other than GET, so nothing in this module can change Clay.

Usage:
    python3 clay_workspace_costs.py --workspace 12345
    python3 clay_workspace_costs.py --workspace 12345 --month 2026-08
    python3 clay_workspace_costs.py --workspace 12345 --month 2026-08 --full-scan

Auth is Rex's normal cookie: clay-session.json next to clay_client.py (see
COOKIE_SETUP.md). The CLAY_SESSION environment variable, when set, wins.
Reports go to reports/ (gitignored) unless you pass --output-dir.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import clay_client
import clay_costs
from clay_client import ClayClient
from clay_flow import _declares_next_page

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_REPORTS_DIR = REPO_ROOT / "reports"

# Defaults.
DEFAULT_MIN_COVERAGE = Decimal("0.75")
DEFAULT_TOLERANCE = Decimal("0.000001")
DEFAULT_WORKERS = 20

OTHER_ID = "other-credit-usage"


class AuditError(RuntimeError):
    """A read or consistency gate failed. The message starts with an error code."""


# ── Small helpers ────────────────────────────────────────────────────────────

def current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def month_datetimes(month: str) -> tuple[datetime, datetime]:
    """UTC start and exclusive end of a YYYY-MM month."""
    if not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month):
        raise AuditError("MONTH_INVALID: expected YYYY-MM")
    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AuditError("MONTH_INVALID: expected YYYY-MM") from exc
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(start.year, start.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def to_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def iso(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def decimal(value) -> Decimal:
    """Exact decimal from a Clay number or money string. Empty counts as 0."""
    if value is None or value == "":
        return Decimal(0)
    try:
        result = Decimal(str(value).strip().replace("$", "").replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise AuditError(f"DECIMAL_INVALID: {value!r}") from exc
    if not result.is_finite():
        raise AuditError(f"DECIMAL_INVALID: {value!r}")
    return result


def optional_money(value) -> Decimal | None:
    """Like decimal(), but a missing or unreadable cost stays None (unpriced), never 0."""
    if value is None or value == "":
        return None
    try:
        return decimal(value)
    except AuditError:
        return None


def numeric(value: Decimal) -> float:
    return round(float(value), 6)


def _validate_declared_count(payload: Any, returned_count: int, error_code: str) -> None:
    """If Clay declares a total count, it must equal what it returned."""
    if not isinstance(payload, dict):
        return
    for key, value in payload.items():
        normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if normalized in {"pagination", "pageinfo"}:
            _validate_declared_count(value, returned_count, error_code)
            continue
        if normalized not in {"totalcount", "total", "count"}:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            raise AuditError(f"{error_code}: declared {key} must be an integer")
        if value != returned_count:
            raise AuditError(f"{error_code}: declared {key}={value} returned={returned_count}")


# ── Read-only client ─────────────────────────────────────────────────────────

class _GetOnlySession(clay_client._TimeoutSession):
    """HTTP session that refuses every method except GET, before any network call."""

    def request(self, method, url, **kwargs):
        if str(method).upper() != "GET":
            raise AuditError(f"READ_ONLY_VIOLATION: refused {method} {url}")
        return super().request(method, url, **kwargs)


class ReadOnlyClayClient(ClayClient):
    """ClayClient bound to one explicit workspace, with a GET-only session."""

    def __init__(self, workspace_id: int, timeout: float = 60):
        self.session = _GetOnlySession(timeout)
        self.session.headers.update(clay_client.HEADERS)
        self._load_cookies()
        self.user_id = self.me()["id"]
        self.workspace_id = int(workspace_id)

    def _load_cookies(self):
        env_session = os.environ.get("CLAY_SESSION", "").strip()
        if env_session:
            self.session.cookies.set("claysession", env_session, domain=".clay.com")
            return
        super()._load_cookies()


def ensure_workspace_visible(clay, workspace_id: int) -> None:
    """Refuse a workspace the session cannot open. Never fall back to another one."""
    visible = clay.get("/my-workspaces")
    visible = visible.get("results", visible) if isinstance(visible, dict) else visible
    ids = {int(w["id"]) for w in visible or [] if isinstance(w, dict) and w.get("id") is not None}
    if int(workspace_id) not in ids:
        raise AuditError(f"WORKSPACE_NOT_VISIBLE: workspace {workspace_id} is not visible to this Clay session")


def open_client(workspace_id: int) -> ReadOnlyClayClient:
    clay = ReadOnlyClayClient(workspace_id)
    ensure_workspace_visible(clay, workspace_id)
    return clay


# ── Clay credits: canonical credit reports ───────────────────────────────────

def flatten_entity(entity: dict, parents: list[dict] | None = None) -> list[dict]:
    """Flatten Clay's folder > workbook > table report tree. Keeps ids, kinds and names only."""
    parents = parents or []
    current = entity.get("entity") or {}
    ref = {"id": entity.get("id"), "kind": current.get("__kind"), "name": current.get("name")}
    lineage = [*parents, ref]
    rows = [{
        **ref,
        "credits": str(decimal(entity.get("credits"))),
        "action_executions": int(entity.get("actionExecutions") or 0),
        "lineage": lineage,
    }]
    for child in entity.get("subentities") or []:
        rows.extend(flatten_entity(child, lineage))
    return rows


def validate_daily_series(series: object, start: datetime, end: datetime,
                          allow_missing_days: bool = False) -> tuple[list[dict], list[str]]:
    """Prove one unique UTC-midnight bucket per requested day.

    Returns (rows, missing_days). Duplicates, malformed rows and buckets
    outside the period always fail. Missing days fail unless
    allow_missing_days is set; the caller must then prove those days were
    zero against the independent workspace report (see merge_cost_model).
    """
    if not isinstance(series, list):
        raise AuditError("CREDIT_TIME_SERIES_INVALID: expected a list")
    expected = []
    cursor = start
    while cursor < end:
        expected.append(iso(cursor))
        cursor += timedelta(days=1)
    actual = []
    rows = []
    for index, row in enumerate(series):
        if not isinstance(row, dict) or not isinstance(row.get("timestamp"), str):
            raise AuditError(f"CREDIT_TIME_SERIES_INVALID: row={index} timestamp missing")
        try:
            stamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError as exc:
            raise AuditError(f"CREDIT_TIME_SERIES_INVALID: row={index} timestamp invalid") from exc
        if stamp.time() != datetime.min.time():
            raise AuditError(f"CREDIT_TIME_SERIES_INVALID: row={index} not UTC midnight")
        try:
            spent = Decimal(str(row["creditsSpent"]))
        except (KeyError, InvalidOperation, ValueError) as exc:
            raise AuditError(f"CREDIT_TIME_SERIES_INVALID: row={index} creditsSpent invalid") from exc
        if not spent.is_finite() or spent < 0:
            raise AuditError(f"CREDIT_TIME_SERIES_INVALID: row={index} creditsSpent invalid")
        actual.append(iso(stamp))
        rows.append({
            "date": iso(stamp)[:10],
            "timestamp": iso(stamp),
            "credits": spent,
            "action_execution_credits": decimal(row.get("actionExecutionCreditsSpent")),
        })
    if len(actual) != len(set(actual)):
        raise AuditError("CREDIT_TIME_SERIES_DUPLICATE_BUCKET")
    outside = sorted(set(actual) - set(expected))
    if outside:
        raise AuditError(f"CREDIT_TIME_SERIES_INVALID: buckets outside the period {outside[:3]}")
    missing = [stamp[:10] for stamp in expected if stamp not in set(actual)]
    if actual != sorted(actual) or (missing and not allow_missing_days):
        raise AuditError(
            "CREDIT_TIME_SERIES_INCOMPLETE: "
            f"expected {len(expected)} daily buckets, got {len(actual)}, first missing {missing[:5]}. "
            "Clay omits days with no activity on quiet "
            "workspaces; rerun with --allow-missing-days to accept them only when the "
            "workspace report proves they were zero.")
    return rows, missing


def validate_unique_entity_ids(rows: object, label: str) -> list[dict]:
    if not isinstance(rows, list):
        raise AuditError(f"CREDIT_{label.upper()}_INVALID: expected a list")
    ids = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AuditError(f"CREDIT_{label.upper()}_INVALID: row={index}")
        entity_id = str(row.get("id") or "").strip()
        if not entity_id:
            raise AuditError(f"CREDIT_{label.upper()}_INVALID: row={index} id missing")
        ids.append(entity_id)
    if len(ids) != len(set(ids)):
        raise AuditError(f"DUPLICATE_CREDIT_{label.upper()}_ID")
    return rows


def credit_report(clay, workspace_id: int, month: str, *, now: datetime | None = None,
                  allow_missing_days: bool = False) -> dict:
    """Read the workspace, integration and daily credit reports for one UTC month."""
    start, month_end = month_datetimes(month)
    now = now or datetime.now(timezone.utc)
    end = min(month_end, now)
    if end <= start:
        raise AuditError(f"CREDIT_PERIOD_NOT_STARTED: month={month}")
    params = {"timeRange[startTime]": iso(start), "timeRange[endTime]": iso(end)}
    base = f"/credit-reporting/{int(workspace_id)}"

    workspace = clay.get(f"{base}/creditReportType/workspace", params=params, timeout=60)
    series_raw = clay.get(f"{base}/spendTimeSeries", params={"interval": "day", **params}, timeout=60)
    integration = clay.get(f"{base}/creditReportType/integration", params=params, timeout=60)
    if not isinstance(workspace, dict) or not isinstance(integration, dict):
        raise AuditError("CREDIT_REPORT_INVALID: expected objects")

    series, missing_days = validate_daily_series(series_raw, start, end, allow_missing_days)
    workspace_entities = validate_unique_entity_ids(workspace.get("entities"), "workspace_entity")
    integration_entities = validate_unique_entity_ids(integration.get("entities"), "integration")

    entities: list[dict] = []
    for entity in workspace_entities:
        entities.extend(flatten_entity(entity))
    unattributed = decimal(workspace.get("unattributedCredits"))
    report_total = sum((decimal(row.get("credits")) for row in workspace_entities), Decimal(0)) + unattributed
    series_total = sum((row["credits"] for row in series), Decimal(0))

    integrations = [{
        "integration_id": row.get("id"),
        "integration_name": (row.get("entity") or {}).get("name") or row.get("id"),
        "credits": str(decimal(row.get("credits"))),
        "action_executions": int(row.get("actionExecutions") or 0),
    } for row in integration_entities]
    integrations.sort(key=lambda row: decimal(row["credits"]), reverse=True)

    return {
        "workspace_id": int(workspace_id),
        "month": month,
        "readback_at": iso(now),
        "data_through": iso(end),
        "period_utc": {"start": iso(start), "end_exclusive_or_data_through": iso(end)},
        "totals": {
            "credit_spend_time_series": str(series_total),
            "credit_report_top_level_plus_unattributed": str(report_total),
            "unattributed_credits": str(unattributed),
            "action_execution_credits": str(sum((r["action_execution_credits"] for r in series), Decimal(0))),
        },
        "daily": [{**row, "credits": str(row["credits"]),
                   "action_execution_credits": str(row["action_execution_credits"])} for row in series],
        "missing_days": missing_days,
        "entities": entities,
        "integrations": integrations,
    }


# ── AI provider USD: stored cost on Use AI cells ─────────────────────────────

def list_tables_strict(clay) -> list[dict]:
    """Every active table in the workspace, or fail closed on any sign of a partial list."""
    res = clay.get(f"/workspaces/{clay.workspace_id}/tables", timeout=60)
    if _declares_next_page(res):
        raise AuditError("INCOMPLETE_TABLE_LIST: workspace table pagination present")
    tables = res.get("results", res) if isinstance(res, dict) else res
    if not isinstance(tables, list) or any(not isinstance(row, dict) for row in tables):
        raise AuditError("INCOMPLETE_TABLE_LIST: results must be objects")
    _validate_declared_count(res, len(tables), "INCOMPLETE_TABLE_LIST")
    ids = [str(row.get("id") or "").strip() for row in tables]
    if any(not table_id for table_id in ids):
        raise AuditError("INCOMPLETE_TABLE_LIST: invalid table id")
    if len(ids) != len(set(ids)):
        raise AuditError("DUPLICATE_TABLE_IDS_FROM_WORKSPACE")
    return tables


def list_auth_accounts_strict(clay) -> list[dict]:
    res = clay.get(f"/workspaces/{clay.workspace_id}/app-accounts", timeout=60)
    if _declares_next_page(res):
        raise AuditError("INCOMPLETE_AUTH_ACCOUNT_LIST: pagination present")
    accounts = res if isinstance(res, list) else (res or {}).get("accounts", [])
    if not isinstance(accounts, list) or any(not isinstance(row, dict) for row in accounts):
        raise AuditError("INCOMPLETE_AUTH_ACCOUNT_LIST: accounts must be objects")
    _validate_declared_count(res, len(accounts), "INCOMPLETE_AUTH_ACCOUNT_LIST")
    ids = [row.get("id") for row in accounts]
    if len(ids) != len(set(ids)):
        raise AuditError("DUPLICATE_AUTH_ACCOUNT_IDS")
    return accounts


def get_record_ids_strict(clay, table_id: str, view_id: str) -> tuple[list[str], dict]:
    """All record ids of a view, minus Clay's "search" placeholder, with a receipt."""
    res = clay.get(f"/tables/{table_id}/views/{view_id}/records/ids")
    if _declares_next_page(res):
        raise AuditError(f"INCOMPLETE_RECORD_ID_LIST: table={table_id} pagination present")
    if not isinstance(res, dict) or not isinstance(res.get("results"), list):
        raise AuditError(f"INCOMPLETE_RECORD_ID_LIST: table={table_id} invalid results")
    ids = res["results"]
    if any(not isinstance(rid, str) or not rid.strip() for rid in ids):
        raise AuditError(f"INCOMPLETE_RECORD_ID_LIST: table={table_id} invalid id")
    filtered = [rid for rid in ids if rid != "search"]
    try:
        _validate_declared_count(res, len(filtered), "INCOMPLETE_RECORD_ID_LIST")
    except AuditError:
        if len(filtered) == len(ids):
            raise
        _validate_declared_count(res, len(ids), "INCOMPLETE_RECORD_ID_LIST")
    if len(filtered) != len(set(filtered)):
        raise AuditError(f"DUPLICATE_RECORD_IDS_FROM_VIEW: table={table_id}")
    return filtered, {"raw_count": len(ids), "search_placeholder_count": ids.count("search")}


def get_view_count(clay, table_id: str, view_id: str) -> dict:
    payload = clay.get(f"/tables/{table_id}/views/{view_id}/count")
    if not isinstance(payload, dict):
        raise AuditError(f"INVALID_VIEW_COUNT: table={table_id}")
    result = {}
    for key in ("viewTotalRecordsCount", "tableTotalRecordsCount"):
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AuditError(f"INVALID_VIEW_COUNT: table={table_id} {key}={value!r}")
        result[key] = value
    return result


def fetch_record_cells(clay, table_id: str, record_id: str, retries: int = 3) -> dict | None:
    """One authoritative full-record read. Returns None after the last failed attempt."""
    for attempt in range(retries):
        try:
            payload = clay.get(f"/tables/{table_id}/records/{record_id}", timeout=30)
            if (not isinstance(payload, dict) or not isinstance(payload.get("cells"), dict)
                    or (payload.get("id") is not None and str(payload["id"]) != str(record_id))):
                raise AuditError(f"INVALID_RECORD_RESPONSE: table={table_id} record={record_id}")
            return payload["cells"]
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(0.4 * (attempt + 1))
    return None


def model_from(settings: dict) -> str | None:
    """The model an AI column is configured with: the model input first, then any model-like key."""
    for binding in settings.get("inputsBinding") or []:
        if str(binding.get("name") or "").lower() not in {"model", "modelname", "llmmodel"}:
            continue
        value = binding.get("formulaText") or binding.get("value")
        if isinstance(value, str):
            value = value.strip().strip('"').strip("'")
            if value:
                return value

    found: list[tuple[str, str]] = []

    def walk(value, path: str = "settings"):
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}"
                if (str(key).lower() in {"model", "modelname", "modelid", "llmmodel"}
                        and isinstance(child, str) and len(child) < 100):
                    candidate = child.strip().strip('"').strip("'")
                    if re.search(r"^(?:gpt-|claude-|gemini-|clay-|o\d)", candidate, re.I):
                        found.append((child_path, candidate))
                walk(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(settings)
    return sorted(found)[0][1] if found else None


def provider_name(account_type: str | None, account_id: str | None) -> str:
    return {
        "gpt-3": "openai",
        "anthropic": "anthropic",
        "google-gemini": "gemini",
        "xai": "xai",
    }.get(account_type, account_type or ("clay-managed" if not account_id else "unknown"))


def new_ai_stats() -> dict:
    return {"cells": 0, "priced": 0, "missing_cost": 0, "credit_billed": 0, "refunded": 0,
            "gross_usd": Decimal(0), "provider_usd": Decimal(0), "ai_cell_credits": Decimal(0)}


def accumulate_ai_cell(target: dict, cell: dict, start_ms: int, end_ms: int) -> bool:
    """Add one charged, in-period Use AI cell to a column total. Returns True if counted.

    Reuses clay_costs.extract_cost_fields() for the fields both tools read the
    same way: status (clay_costs.CHARGED_STATUSES, so a table's provider USD
    here matches calculate-costs), refund flag, and the provider-cost string
    (fullValue.totalCostToAIProvider, then costDetails.totalCostToAIProvider).
    Two things stay local, because clay_costs reads them differently:
    - finishedAt falls back to externalContent.finishedAt; the month boundary
      needs a timestamp and some cells only carry it there.
    - money stays Decimal (clay_costs converts to float) so per-dimension
      totals tie out exactly in the consistency checks.
    - AI-cell credits are upfrontCreditUsage.totalCost plus
      additionalCreditUsage.totalCost. They are a diagnostic subset only; the
      workspace credit total comes from credit reporting.
    Refunded cells stay visible in the counts but add neither provider USD
    nor AI-cell credits. A cell with no provider cost that ran on a
    Clay-managed key (target["billing"] == "clay_credits", or the cell says
    isPrivateKey false) is counted as credit_billed, not missing_cost: Clay
    billed it in credits, so there is no provider USD to miss.
    """
    fields = clay_costs.extract_cost_fields(cell)
    if not fields["ran"]:
        return False
    external = (cell or {}).get("externalContent") or {}
    finished_at = fields["finished_at_ms"] or external.get("finishedAt")
    if isinstance(finished_at, bool) or not isinstance(finished_at, (int, float)):
        return False
    if not start_ms <= finished_at < end_ms:
        return False

    cost = optional_money(fields["total_cost_usd_str"])
    refunded = fields["is_refunded"] is True
    target["cells"] += 1
    target["refunded"] += int(refunded)
    if not refunded:
        target["ai_cell_credits"] += (
            decimal((external.get("upfrontCreditUsage") or {}).get("totalCost"))
            + decimal((external.get("additionalCreditUsage") or {}).get("totalCost")))
    if cost is None:
        if target.get("billing") == "clay_credits" or external.get("isPrivateKey") is False:
            target["credit_billed"] += 1
        else:
            target["missing_cost"] += 1
        return True
    target["priced"] += 1
    target["gross_usd"] += cost
    if not refunded:
        target["provider_usd"] += cost
    return True


def unfiltered_view_id(root: dict) -> str | None:
    """A view with no filter and no row limit, so its record ids are every row."""
    views = sorted(
        (view for view in root.get("views") or []
         if view.get("filter") in (None, {})
         and not any("limit" in str(key).lower() and value not in (None, 0, "")
                     for key, value in view.items())),
        key=lambda view: view.get("id") or "",
    )
    return views[0]["id"] if views else None


def table_schema_signature(root: dict) -> tuple:
    fields = tuple(sorted(
        (str(f.get("id")), f.get("type"), f.get("name"), json.dumps(f.get("typeSettings") or {}, sort_keys=True))
        for f in root["fields"]))
    views = tuple(sorted(json.dumps(view, sort_keys=True) for view in root["views"]))
    return fields, views


def table_updated_since(table: dict, start_ms: int) -> bool:
    """Fast-scope selector. An unknown or unreadable updatedAt keeps the table in scope."""
    raw = table.get("updatedAt")
    if raw in (None, ""):
        return True
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value_ms = float(raw)
        if value_ms < 10_000_000_000:
            value_ms *= 1000
        return value_ms >= start_ms
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return to_ms(parsed) >= start_ms


def aggregate(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    result: dict[tuple, dict] = {}
    for source in rows:
        identity = tuple(source.get(key) for key in keys)
        target = result.setdefault(identity, {**{key: source.get(key) for key in keys}, **new_ai_stats()})
        for key in ("cells", "priced", "missing_cost", "credit_billed", "refunded"):
            target[key] += int(source.get(key) or 0)
        for key in ("gross_usd", "provider_usd", "ai_cell_credits"):
            target[key] += decimal(source.get(key))
    return list(result.values())


def serialize(rows: list[dict]) -> list[dict]:
    output = [{key: str(value) if isinstance(value, Decimal) else value for key, value in row.items()}
              for row in rows]
    return sorted(output, key=lambda row: (decimal(row.get("provider_usd")),
                                           decimal(row.get("ai_cell_credits")),
                                           int(row.get("cells") or 0)), reverse=True)


def audit_ai_usd(clay, month: str, *, workers: int = DEFAULT_WORKERS, full_scan: bool = False,
                 extra_table_ids: tuple[str, ...] = (), now: datetime | None = None,
                 log=None) -> dict:
    """Provider USD of every charged Use AI cell that finished in the month.

    Fast mode (default) reads tables updated since the month started, plus
    extra_table_ids (the caller passes tables with credits in the month and
    any --include-table ids). --full-scan reads every active table and
    re-reads table, schema and record inventories to prove nothing moved
    during the read.
    """
    log = log or (lambda message: print(message, file=sys.stderr))
    start, end = month_datetimes(month)
    start_ms, end_ms = to_ms(start), to_ms(end)

    def auth_signature(rows):
        return {str(r["id"]): (r.get("name"), r.get("appAccountTypeId")) for r in rows}

    first_accounts = list_auth_accounts_strict(clay)
    if full_scan and auth_signature(list_auth_accounts_strict(clay)) != auth_signature(first_accounts):
        raise AuditError("AUTH_ACCOUNT_INVENTORY_DRIFT")
    accounts = {str(row["id"]): row for row in first_accounts}

    workbook_payload = clay.get(f"/workspaces/{clay.workspace_id}/workbooks", timeout=60)
    workbook_list = workbook_payload.get("results", []) if isinstance(workbook_payload, dict) else workbook_payload
    workbooks = {row["id"]: row.get("name") or row["id"] for row in workbook_list or [] if isinstance(row, dict)}

    all_tables = list_tables_strict(clay)
    first_table_ids = sorted(str(t["id"]) for t in all_tables)
    if full_scan and sorted(str(t["id"]) for t in list_tables_strict(clay)) != first_table_ids:
        raise AuditError("INCOMPLETE_TABLE_INVENTORY: table list changed between two reads")
    active_ids = set(first_table_ids)
    extra_ids = {str(t) for t in extra_table_ids if str(t)}
    updated_ids = {str(t["id"]) for t in all_tables if table_updated_since(t, start_ms)}
    tables = all_tables if full_scan else [t for t in all_tables if str(t["id"]) in updated_ids | extra_ids]

    def table_snapshot(table_id: str) -> dict:
        for attempt in range(3):
            try:
                root = (clay.get_table(table_id) or {}).get("table", {})
                if (not isinstance(root, dict) or str(root.get("id")) != str(table_id)
                        or not isinstance(root.get("fields"), list) or not isinstance(root.get("views"), list)):
                    raise AuditError(f"INVALID_TABLE_DETAIL: table={table_id}")
                return root
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(0.5 * (attempt + 1))
        raise AuditError(f"INVALID_TABLE_DETAIL: table={table_id}")

    unlisted_accounts: set[str] = set()

    def inspect_table(table: dict):
        root = table_snapshot(table["id"])
        if full_scan:
            second = table_snapshot(table["id"])
            if table_schema_signature(root) != table_schema_signature(second):
                raise AuditError(f"TABLE_SCHEMA_DRIFT: table={table['id']}")
            root = second
        fields = []
        for field in root.get("fields", []):
            settings = field.get("typeSettings") or {}
            if field.get("type") != "action" or settings.get("actionKey") != "use-ai":
                continue
            account_id = settings.get("authAccountId")
            account = accounts.get(str(account_id), {}) if account_id else {}
            if account_id and not account:
                unlisted_accounts.add(f"{account_id}@{table['id']}:{field['id']}")
            fields.append({
                "field_id": field["id"],
                "field_name": field.get("name"),
                "account_id": account_id,
                "account_name": account.get("name") or ("Clay-managed" if not account_id else str(account_id)),
                "provider": provider_name(account.get("appAccountTypeId"), account_id),
                # Clay-managed keys (no account, or a shared public key) are billed in Clay
                # credits; your own key is billed by the provider in USD.
                "billing": "clay_credits" if not account_id or account.get("isSharedPublicKey") else "own_key",
                "model": model_from(settings) or "unknown",
            })
        if not fields:
            return None
        return table, root, fields, unfiltered_view_id(root)

    log(f"[ai] mode={'full_scan' if full_scan else 'fast'}; inspecting {len(tables)} of {len(all_tables)} active tables")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        inspected = [item for item in pool.map(inspect_table, tables) if item is not None]
    targets = [item for item in inspected if item[3]]
    without_view = [item[0]["id"] for item in inspected if not item[3]]
    log(f"[ai] {len(inspected)} tables have Use AI columns; {len(without_view)} without an unfiltered view")

    def record_inventory(table_id: str, view_id: str) -> tuple[list[str], dict]:
        last = None
        for attempt in range(4):
            try:
                count = get_view_count(clay, table_id, view_id)
                ids, receipt = get_record_ids_strict(clay, table_id, view_id)
                if (count["viewTotalRecordsCount"] == receipt["raw_count"]
                        and count["tableTotalRecordsCount"] == receipt["raw_count"]
                        and receipt["search_placeholder_count"] in {0, 1}):
                    return ids, {**count, **receipt}
                last = (f"ids={len(ids)} raw_ids={receipt['raw_count']} view={count['viewTotalRecordsCount']} "
                        f"table_total={count['tableTotalRecordsCount']}")
            except Exception:
                if attempt == 3:
                    raise
            if attempt < 3:
                time.sleep(1.0 * (2 ** attempt))
        raise AuditError(f"INCOMPLETE_RECORD_INVENTORY: table={table_id} {last}")

    column_rows: list[dict] = []
    failed_fetches = 0
    rows_read = 0
    for index, (table, root, fields, view_id) in enumerate(targets, 1):
        record_ids, before = record_inventory(table["id"], view_id)
        log(f"[ai {index}/{len(targets)}] {table.get('name')}: {len(record_ids)} rows")
        workbook_id = root.get("workbookId") or table.get("workbookId") or "standalone"
        stats = {f["field_id"]: {**f, "table_id": table["id"], "table_name": table.get("name"),
                                 "workbook_id": workbook_id, "workbook_name": workbooks.get(workbook_id, workbook_id),
                                 **new_ai_stats()} for f in fields}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for cells in pool.map(lambda rid: fetch_record_cells(clay, table["id"], rid), record_ids):
                if cells is None:
                    failed_fetches += 1
                    continue
                rows_read += 1
                for field in fields:
                    accumulate_ai_cell(stats[field["field_id"]], cells.get(field["field_id"]) or {}, start_ms, end_ms)
        if full_scan:
            if table_schema_signature(root) != table_schema_signature(table_snapshot(table["id"])):
                raise AuditError(f"TABLE_SCHEMA_DRIFT: table={table['id']}")
            after_ids, after = record_inventory(table["id"], view_id)
            if before != after or set(after_ids) != set(record_ids):
                raise AuditError(f"RECORD_INVENTORY_DRIFT: table={table['id']}")
        column_rows.extend(row for row in stats.values() if row["cells"])

    if full_scan:
        if sorted(str(t["id"]) for t in list_tables_strict(clay)) != first_table_ids:
            raise AuditError("WORKSPACE_TABLE_INVENTORY_DRIFT")
        if auth_signature(list_auth_accounts_strict(clay)) != auth_signature(first_accounts):
            raise AuditError("AUTH_ACCOUNT_INVENTORY_DRIFT")

    totals = {key: sum(int(r[key]) for r in column_rows)
              for key in ("cells", "priced", "missing_cost", "credit_billed", "refunded")}
    for key in ("gross_usd", "provider_usd", "ai_cell_credits"):
        totals[key] = str(sum((r[key] for r in column_rows), Decimal(0)))

    return {
        "workspace_id": int(clay.workspace_id),
        "month": month,
        "readback_at": iso(now or datetime.now(timezone.utc)),
        "period_utc": {"start": iso(start), "end_exclusive": iso(end)},
        "scope": {
            "audit_mode": "full_scan" if full_scan else "fast",
            "table_selection": ("every active table" if full_scan else
                                "active tables updated since the month started, plus tables with "
                                "credits in the month and any --include-table ids"),
            "listed_tables": len(all_tables),
            "selected_tables": len(tables),
            "selected_by_updated_at": len(updated_ids),
            "extra_table_ids_requested": len(extra_ids),
            "extra_table_ids_active": len(extra_ids & active_ids),
            "ai_tables": len(inspected),
            "ai_tables_read": len(targets),
            "ai_columns": sum(len(item[2]) for item in inspected),
            "rows_read": rows_read,
        },
        "totals": totals,
        "providers": serialize(aggregate(column_rows, ("provider",))),
        "accounts": serialize(aggregate(column_rows, ("account_id", "account_name", "provider"))),
        "models": serialize(aggregate(column_rows, ("provider", "model"))),
        "workbooks": serialize(aggregate(column_rows, ("workbook_id", "workbook_name"))),
        "tables": serialize(aggregate(column_rows, ("table_id", "workbook_id", "workbook_name", "table_name"))),
        "columns": serialize(column_rows),
        "diagnostics": {
            "failed_record_fetches": failed_fetches,
            "ai_tables_without_unfiltered_view": without_view,
            "ai_columns_with_unlisted_account": sorted(unlisted_accounts),
        },
    }


# ── Merge the two axes and run the consistency gates ─────────────────────────

def workbook_ref(lineage: list[dict]) -> dict | None:
    return next((item for item in reversed(lineage) if item.get("kind") == "workbook"), None)


def sum_decimal(rows: list[dict], key: str) -> Decimal:
    return sum((decimal(row.get(key)) for row in rows), Decimal(0))


def check(name: str, expected, actual, tolerance: Decimal = DEFAULT_TOLERANCE) -> dict:
    expected_d, actual_d = decimal(expected), decimal(actual)
    return {"check": name, "expected": numeric(expected_d), "actual": numeric(actual_d),
            "status": "PASS" if abs(expected_d - actual_d) <= tolerance else "FAIL"}


def merge_cost_model(ai: dict, credits: dict, *, min_coverage: Decimal = DEFAULT_MIN_COVERAGE,
                     tolerance: Decimal = DEFAULT_TOLERANCE) -> dict:
    """Join provider USD and Clay credits by workbook and table. Raises AuditError on any failed gate."""
    min_coverage = Decimal(str(min_coverage))
    tolerance = Decimal(str(tolerance))
    percent = f"{(min_coverage * 100).normalize():f}%"

    if ai["diagnostics"]["failed_record_fetches"]:
        raise AuditError(f"FAILED_RECORD_FETCHES: {ai['diagnostics']['failed_record_fetches']}")
    if ai["diagnostics"].get("ai_tables_without_unfiltered_view"):
        raise AuditError("AI_TABLES_WITHOUT_UNFILTERED_VIEW: "
                         + ",".join(ai["diagnostics"]["ai_tables_without_unfiltered_view"]))

    official = decimal(credits["totals"]["credit_spend_time_series"])
    report_total = decimal(credits["totals"]["credit_report_top_level_plus_unattributed"])
    report_gap = official - report_total
    if report_gap < -tolerance:
        raise AuditError(f"CREDIT_REPORT_EXCEEDS_SERIES: series={official} report={report_total}")
    if abs(report_gap) <= tolerance:
        report_gap = Decimal(0)
    missing_days = credits.get("missing_days") or []
    if missing_days and report_gap:
        raise AuditError(
            f"CREDIT_TIME_SERIES_INCOMPLETE: {len(missing_days)} days have no bucket and the series "
            f"({official}) does not equal the workspace report ({report_total}), so those days "
            "cannot be proven zero")

    def ratio(part: Decimal) -> Decimal:
        return Decimal(1) if official == 0 else max(Decimal(0), part / official)

    workspace_ratio = ratio(report_total)
    if workspace_ratio < min_coverage:
        raise AuditError(f"CREDIT_WORKSPACE_REPORT_COVERAGE_TOO_LOW: report={report_total} "
                         f"series={official} ratio={workspace_ratio:.4f} minimum={min_coverage}")

    credit_tables: dict[str, dict] = {}
    credit_workbooks: dict[str, dict] = {}
    table_credit_sum = Decimal(0)
    seen: set[str] = set()
    for entity in credits["entities"]:
        if entity.get("kind") != "table":
            continue
        if entity["id"] in seen:
            raise AuditError(f"DUPLICATE_CREDIT_TABLE_ID: {entity['id']}")
        seen.add(entity["id"])
        amount = decimal(entity.get("credits"))
        if amount == 0:
            continue
        wb = workbook_ref(entity.get("lineage") or [])
        wb_id = wb.get("id") if wb else "standalone-tables"
        wb_name = wb.get("name") if wb else "Standalone tables"
        credit_tables[entity["id"]] = {"table_id": entity["id"], "workbook_id": wb_id, "workbook_name": wb_name,
                                       "table_name": entity.get("name") or entity["id"], "credits": amount}
        target = credit_workbooks.setdefault(wb_id, {"workbook_id": wb_id, "workbook_name": wb_name,
                                                     "credits": Decimal(0)})
        target["credits"] += amount
        table_credit_sum += amount

    outside_tables = official - table_credit_sum
    if outside_tables < -tolerance:
        raise AuditError(f"TABLE_CREDITS_EXCEED_TOTAL: tables={table_credit_sum} series={official}")
    if abs(outside_tables) <= tolerance:
        outside_tables = Decimal(0)
    table_ratio = ratio(table_credit_sum)
    if table_ratio < min_coverage:
        raise AuditError(f"CREDIT_TABLE_ATTRIBUTION_TOO_LOW: tables={table_credit_sum} series={official} "
                         f"ratio={table_ratio:.4f} minimum={min_coverage}")
    if outside_tables:
        other = {"workbook_id": OTHER_ID, "workbook_name": "Other / non-table or unattributed",
                 "credits": outside_tables}
        credit_tables[OTHER_ID] = {**other, "table_id": OTHER_ID,
                                   "table_name": "Other / non-table or unattributed"}
        credit_workbooks[OTHER_ID] = other

    def joined(ai_rows: dict, credit_rows: dict, id_key: str, name_keys: tuple[str, ...]) -> list[dict]:
        out = []
        for key in set(ai_rows) | set(credit_rows):
            a, c = ai_rows.get(key, {}), credit_rows.get(key, {})
            row = {id_key: key}
            for name in name_keys:
                row[name] = a.get(name) or c.get(name) or ("unknown" if name.endswith("_id") else key)
            row.update({
                "credits": decimal(c.get("credits")),
                "provider_usd": decimal(a.get("provider_usd")),
                "ai_cells": int(a.get("cells") or 0),
                "ai_cells_priced": int(a.get("priced") or 0),
                "ai_cells_missing_cost": int(a.get("missing_cost") or 0),
                "ai_cells_credit_billed": int(a.get("credit_billed") or 0),
                "ai_cells_refunded": int(a.get("refunded") or 0),
            })
            out.append(row)
        out.sort(key=lambda r: (r["credits"], r["provider_usd"]), reverse=True)
        return out

    workbooks = joined({r["workbook_id"]: r for r in ai["workbooks"]}, credit_workbooks,
                       "workbook_id", ("workbook_name",))
    tables = joined({r["table_id"]: r for r in ai["tables"]}, credit_tables,
                    "table_id", ("workbook_id", "workbook_name", "table_name"))

    integrations = [dict(row) for row in credits["integrations"]]
    integration_ids = [row.get("integration_id") for row in integrations]
    if len(integration_ids) != len(set(integration_ids)):
        raise AuditError("DUPLICATE_CREDIT_INTEGRATION_ID")
    integration_sum = sum_decimal(integrations, "credits")
    outside_integrations = official - integration_sum
    if outside_integrations < -tolerance:
        raise AuditError(f"INTEGRATION_CREDITS_EXCEED_TOTAL: integrations={integration_sum} series={official}")
    integration_ratio = ratio(integration_sum)
    if integration_ratio < min_coverage:
        raise AuditError(f"CREDIT_INTEGRATION_ATTRIBUTION_TOO_LOW: integrations={integration_sum} "
                         f"series={official} ratio={integration_ratio:.4f} minimum={min_coverage}")
    if abs(outside_integrations) > tolerance:
        integrations.append({"integration_id": OTHER_ID, "integration_name": "Other / non-integration or unattributed",
                             "credits": str(outside_integrations), "action_executions": 0})
    for row in integrations:
        row["credits"] = decimal(row["credits"])
    integrations.sort(key=lambda row: row["credits"], reverse=True)

    totals = {
        "credits": numeric(official),
        "action_execution_credits": numeric(decimal(credits["totals"].get("action_execution_credits"))),
        "provider_usd": numeric(decimal(ai["totals"]["provider_usd"])),
        "ai_cells": int(ai["totals"]["cells"]),
        "ai_cells_priced": int(ai["totals"]["priced"]),
        "ai_cells_missing_cost": int(ai["totals"]["missing_cost"]),
        "ai_cells_credit_billed": int(ai["totals"].get("credit_billed") or 0),
        "ai_cells_refunded": int(ai["totals"]["refunded"]),
        "ai_cell_credits_subset": numeric(decimal(ai["totals"]["ai_cell_credits"])),
        "credits_outside_tables": numeric(outside_tables),
        "credits_outside_current_report_entities": numeric(report_gap),
        "workspace_report_coverage": numeric(workspace_ratio),
        "table_attribution_coverage": numeric(table_ratio),
        "integration_attribution_coverage": numeric(integration_ratio),
        "tables_with_cost": sum(1 for row in tables if row["table_id"] != OTHER_ID),
    }

    usd, cells = totals["provider_usd"], totals["ai_cells"]

    def cell_sum(rows, key="cells"):
        return sum(int(r.get(key) or 0) for r in rows)

    gates = [
        check("Daily credit series: one unique bucket per UTC day (missing days proven zero)", 1, 1, tolerance),
        check("No failed record reads", 0, ai["diagnostics"]["failed_record_fetches"], tolerance),
        check("Credit report does not exceed the daily series", 1, int(report_gap >= 0), tolerance),
        check(f"Workspace credit report coverage >= {percent}", 1, int(workspace_ratio >= min_coverage), tolerance),
        check(f"Table credit attribution >= {percent}", 1, int(table_ratio >= min_coverage), tolerance),
        check(f"Integration credit attribution >= {percent}", 1, int(integration_ratio >= min_coverage), tolerance),
        check("Auth accounts: provider USD", usd, sum_decimal(ai["accounts"], "provider_usd"), tolerance),
        check("Auth accounts: AI cells", cells, cell_sum(ai["accounts"]), tolerance),
        check("Models: provider USD", usd, sum_decimal(ai["models"], "provider_usd"), tolerance),
        check("Models: AI cells", cells, cell_sum(ai["models"]), tolerance),
        check("Workbooks: provider USD", usd, sum_decimal(workbooks, "provider_usd"), tolerance),
        check("Workbooks: AI cells", cells, cell_sum(workbooks, "ai_cells"), tolerance),
        check("Tables: provider USD", usd, sum_decimal(tables, "provider_usd"), tolerance),
        check("Tables: AI cells", cells, cell_sum(tables, "ai_cells"), tolerance),
        check("Tables: credits", official, sum_decimal(tables, "credits"), tolerance),
        check("Integrations: credits", official, sum_decimal(integrations, "credits"), tolerance),
    ]
    failed = [gate for gate in gates if gate["status"] != "PASS"]
    if failed:
        raise AuditError(f"MODEL_RECONCILIATION_FAILED: {failed}")

    # The checks above ran on exact decimals; round only for the report.
    for row in [*workbooks, *tables, *integrations]:
        for key in ("credits", "provider_usd"):
            if key in row:
                row[key] = numeric(row[key])

    limitations = [
        "Clay stores only the latest result per cell; the cost of overwritten reruns is not recoverable.",
        "Deleted tables and deleted columns are not readable, so their provider USD is missing. "
        "Their Clay credits stay in the credit reports under Other.",
        "AI cells on your own key without a stored provider cost are counted as missing_cost, so "
        "provider_usd is a confirmed minimum when ai_cells_missing_cost is above zero. Cells on a "
        "Clay-managed key are counted as credit_billed: their cost is in Clay credits.",
        "Clay credits come from credit reporting. ai_cell_credits_subset is a diagnostic only.",
        "The gates compare Clay's numbers with each other; they do not reconcile them with your invoice.",
    ]
    if ai["scope"]["audit_mode"] != "full_scan":
        limitations.append(
            "Fast mode reads tables updated since the month started plus tables with credits in the "
            "month. A Use AI table on your own key with no Clay credits and a stale updatedAt can be "
            "missed; run --full-scan now and then, or pass it with --include-table.")
    if missing_days:
        limitations.append(
            f"{len(missing_days)} days had no credit bucket. They were accepted as zero because the "
            "daily series equals the independent workspace report total.")

    return {
        "status": "PASS",
        "workspace_id": ai["workspace_id"],
        "month": ai["month"],
        "period_utc": ai["period_utc"],
        "credit_data_through": credits.get("data_through"),
        "ai_readback_at": ai["readback_at"],
        "credit_readback_at": credits["readback_at"],
        "totals": totals,
        "gates": gates,
        "gates_scope": "Internal consistency and minimum-coverage gates only; no invoice reconciliation.",
        "thresholds": {"min_coverage": str(min_coverage), "tolerance": str(tolerance)},
        "tables": tables,
        "workbooks": workbooks,
        "integrations": integrations,
        "daily": credits["daily"],
        "missing_days": missing_days,
        "ai_providers": ai["providers"],
        "ai_accounts": ai["accounts"],
        "ai_models": ai["models"],
        "ai_columns": ai["columns"],
        "scope": ai["scope"],
        "diagnostics": ai["diagnostics"],
        "limitations": limitations,
    }


def build_cost_model(clay, month: str, *, workers: int = DEFAULT_WORKERS, full_scan: bool = False,
                     include_tables: tuple[str, ...] = (), allow_missing_days: bool = False,
                     min_coverage: Decimal = DEFAULT_MIN_COVERAGE, tolerance: Decimal = DEFAULT_TOLERANCE,
                     log=None) -> dict:
    credits = credit_report(clay, clay.workspace_id, month, allow_missing_days=allow_missing_days)
    credit_table_ids = {str(e["id"]) for e in credits["entities"]
                        if e.get("kind") == "table" and e.get("id") and decimal(e.get("credits")) != 0}
    ai = audit_ai_usd(clay, month, workers=workers, full_scan=full_scan,
                      extra_table_ids=tuple(sorted(credit_table_ids | set(include_tables))), log=log)
    return merge_cost_model(ai, credits, min_coverage=min_coverage, tolerance=tolerance)


# ── Output ───────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def daily_rows(model: dict) -> list[dict]:
    """One row per day of the period; days Clay did not report are marked bucket_present=false."""
    present = {row["date"]: row for row in model["daily"]}
    start = datetime.fromisoformat(model["period_utc"]["start"].replace("Z", "+00:00"))
    through = datetime.fromisoformat(model["credit_data_through"].replace("Z", "+00:00"))
    rows, cursor = [], start
    while cursor < through:
        date = cursor.strftime("%Y-%m-%d")
        row = present.get(date)
        rows.append({"date": date, "credits": row["credits"] if row else "0",
                     "action_execution_credits": row["action_execution_credits"] if row else "0",
                     "bucket_present": bool(row)})
        cursor += timedelta(days=1)
    return rows


def write_reports(model: dict, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out_dir / "report.json",
        "tables": out_dir / "tables.csv",
        "integrations": out_dir / "integrations.csv",
        "daily": out_dir / "daily.csv",
        "ai_columns": out_dir / "ai_columns.csv",
        "ai_models": out_dir / "ai_models.csv",
    }
    paths["json"].write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(paths["tables"], model["tables"],
               ["table_id", "table_name", "workbook_id", "workbook_name", "credits", "provider_usd",
                "ai_cells", "ai_cells_priced", "ai_cells_missing_cost", "ai_cells_credit_billed",
                "ai_cells_refunded"])
    _write_csv(paths["integrations"], model["integrations"],
               ["integration_id", "integration_name", "credits", "action_executions"])
    _write_csv(paths["daily"], daily_rows(model), ["date", "credits", "action_execution_credits", "bucket_present"])
    _write_csv(paths["ai_columns"], model["ai_columns"],
               ["table_id", "table_name", "workbook_name", "field_id", "field_name", "provider", "model",
                "account_name", "billing", "cells", "priced", "missing_cost", "credit_billed", "refunded",
                "provider_usd", "gross_usd", "ai_cell_credits"])
    _write_csv(paths["ai_models"], model["ai_models"],
               ["provider", "model", "cells", "priced", "missing_cost", "credit_billed", "refunded",
                "provider_usd", "gross_usd", "ai_cell_credits"])
    return {key: str(path) for key, path in paths.items()}


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only monthly cost audit of one Clay workspace: Clay credits by table and "
                    "integration, and AI provider USD by table, column and model.")
    parser.add_argument("--workspace", type=int, required=True,
                        help="Clay workspace id (required; never guessed). Must be visible to your session.")
    parser.add_argument("--month", default=None, help="UTC month as YYYY-MM (default: the current UTC month)")
    parser.add_argument("--full-scan", action="store_true",
                        help="Read every active table and prove inventories did not move. Much slower.")
    parser.add_argument("--include-table", action="append", default=[], metavar="TABLE_ID",
                        help="Add a table to the fast scope (repeatable)")
    parser.add_argument("--allow-missing-days", action="store_true",
                        help="Accept days with no credit bucket, only when the daily series equals the "
                             "independent workspace report total")
    parser.add_argument("--min-coverage", type=Decimal, default=DEFAULT_MIN_COVERAGE,
                        help="Minimum share of credits the workspace, table and integration reports "
                             "must each explain (default 0.75)")
    parser.add_argument("--tolerance", type=Decimal, default=DEFAULT_TOLERANCE,
                        help="Allowed difference in the consistency checks (default 0.000001)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel record reads (default 20)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Where to write report.json and the CSVs "
                             "(default reports/workspace-costs-<workspace>-<month>/)")
    args = parser.parse_args(argv)
    if args.workspace <= 0:
        parser.error("--workspace must be a positive Clay workspace id")
    args.month = args.month or current_month()
    try:
        month_datetimes(args.month)
    except AuditError as exc:
        parser.error(str(exc))
    if not Decimal(0) <= args.min_coverage <= Decimal(1):
        parser.error("--min-coverage must be between 0 and 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    out_dir = args.output_dir or DEFAULT_REPORTS_DIR / f"workspace-costs-{args.workspace}-{args.month}"
    try:
        clay = open_client(args.workspace)
        model = build_cost_model(
            clay, args.month, workers=max(1, args.workers), full_scan=args.full_scan,
            include_tables=tuple(args.include_table), allow_missing_days=args.allow_missing_days,
            min_coverage=args.min_coverage, tolerance=args.tolerance)
    except AuditError as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc),
                          "runtime_seconds": round(time.monotonic() - started, 1)}, ensure_ascii=False))
        return 1
    model["runtime_seconds"] = round(time.monotonic() - started, 1)
    paths = write_reports(model, out_dir)
    t = model["totals"]
    print(json.dumps({
        "status": model["status"],
        "workspace_id": model["workspace_id"],
        "month": model["month"],
        "credit_data_through": model["credit_data_through"],
        "credits": t["credits"],
        "provider_usd": t["provider_usd"],
        "ai_cells": t["ai_cells"],
        "ai_cells_missing_cost": t["ai_cells_missing_cost"],
        "ai_cells_credit_billed": t["ai_cells_credit_billed"],
        "tables_with_cost": t["tables_with_cost"],
        "gates_passed": f"{sum(g['status'] == 'PASS' for g in model['gates'])}/{len(model['gates'])}",
        "audit_mode": model["scope"]["audit_mode"],
        "runtime_seconds": model["runtime_seconds"],
        "outputs": paths,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
