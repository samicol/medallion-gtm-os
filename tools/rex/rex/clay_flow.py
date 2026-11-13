"""
clay_flow.py - workbook-scoped Clay client and config for Rex's campaign pipeline.

The campaign pipeline (campaign-contract -> design-clay-table-json ->
import-clay-table -> save-clay-schema) imports whole workbooks, triggers
sources and runs paid columns. Those are writes, so this module adds three
things on top of clay_client.ClayClient:

1. An explicit workspace. FlowClient never falls back to "the first workspace
   the cookie can see". The workspace comes from rex-config.json or a CLI flag,
   and it must be one the session can open.
2. A workbook boundary. After approve_workbook(wb_id), every write re-reads the
   target table immediately before the request and refuses when the table is
   not in that workbook. A table id copied from a URL or remembered from another
   session is never permission to write.
3. The native routes the importer needs (views, sources, source runs,
   workbook creation) plus a hardened import_schema that repairs half-created
   formula columns and stops at the first failed column.

Auth is Rex's normal cookie: clay-session.json next to clay_client.py (see
COOKIE_SETUP.md). The CLAY_SESSION environment variable, when set, wins.

Config (rex-config.json, gitignored; copy rex-config.example.json):
    {
      "workspaceId": 123456,
      "folderId": "",
      "authAccounts": {"llm": "aa_..."},
      "models": {"default": "<model id your workspace offers>"},
      "budgetUsd": 5
    }
"""

from __future__ import annotations

import copy
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from clay_client import ClayClient, _extract_deps, _names_to_refs, _sort_by_deps  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "rex-config.json"


# ── Config ────────────────────────────────────────────────────────────────────

def load_config(path: str | Path | None = None) -> dict:
    """Read rex-config.json (or the given path). Missing file -> empty config."""
    p = Path(path) if path else CONFIG_PATH
    if not p.exists():
        return {}
    cfg = json.loads(p.read_text())
    return {k: v for k, v in cfg.items() if not k.startswith("_")}


def parse_pairs(values: list[str] | None) -> dict[str, str]:
    """Turn ['llm=aa_x', 'search=aa_y'] into {'llm': 'aa_x', 'search': 'aa_y'}."""
    out = {}
    for item in values or []:
        if "=" not in item:
            raise SystemExit(f"Expected name=value, got {item!r}")
        k, v = item.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def resolve_settings(args, cfg: dict) -> dict:
    """Merge CLI flags over rex-config.json. CLI wins."""
    ws = getattr(args, "workspace", None) or cfg.get("workspaceId")
    return {
        "workspaceId": int(ws) if ws else None,
        "folderId": getattr(args, "folder", None) or cfg.get("folderId") or None,
        "authAccounts": {**(cfg.get("authAccounts") or {}), **parse_pairs(getattr(args, "auth_account", None))},
        "models": {**(cfg.get("models") or {}), **parse_pairs(getattr(args, "model", None))},
        "budgetUsd": getattr(args, "budget", None) if getattr(args, "budget", None) is not None else cfg.get("budgetUsd"),
    }


# ── Errors and strict-read helpers ────────────────────────────────────────────

class ClayScopeError(RuntimeError):
    """A write was attempted outside the approved workbook. Raised before the write."""


class ClayFlowError(RuntimeError):
    """A Clay read or write returned something the pipeline cannot trust."""


def formula_text_selects_mapped_path(formula_text: Any, mapped_path: Any) -> bool:
    """True when the formula text itself walks every component of mappedResultPath.

    Clay keeps mappedResultPath on some formula extractions and drops it on
    others. It is redundant only when the formula already selects that path.
    """
    if not isinstance(formula_text, str) or not formula_text:
        return False
    if not isinstance(mapped_path, list) or not mapped_path or any(
        not isinstance(part, str) or not part for part in mapped_path
    ):
        return False
    segments = []
    for part in mapped_path:
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", part):
            value = re.escape(part)
        else:
            value = r"\[\s*[\"']" + re.escape(part) + r"[\"']\s*\]"
        segments.append(r"(?:\?\.|\.)\s*" + value)
    return bool(re.search(r"\}\}\s*" + "".join(segments), formula_text))


def _declares_next_page(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    keys = {"hasmore", "hasnextpage", "nextpage", "nextpagetoken", "nextcursor"}
    for key, value in payload.items():
        k = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if k in keys and value:
            return True
        if k in {"pagination", "pageinfo"} and _declares_next_page(value):
            return True
    return False


# Cell states that mean "this cell will not change without another run".
PENDING_STATUSES = {"QUEUED", "RUNNING", "PENDING", "AWAITING_CALLBACK"}


class FlowClient(ClayClient):
    """ClayClient with an explicit workspace and a workbook-scoped write boundary."""

    approved_workbook_id: str | None = None

    def __init__(self, workspace_id: int, approved_workbook_id: str | None = None):
        if not workspace_id:
            raise ClayScopeError(
                "No Clay workspace id. Set workspaceId in rex-config.json or pass --workspace. "
                "The pipeline never guesses a workspace.")
        super().__init__(workspace_id=int(workspace_id))
        visible = self.get("/my-workspaces")
        visible = visible.get("results", visible) if isinstance(visible, dict) else visible
        if int(workspace_id) not in {int(w["id"]) for w in visible}:
            raise ClayScopeError(f"Workspace {workspace_id} is not visible to this Clay session.")
        self.approved_workbook_id = approved_workbook_id

    def _load_cookies(self):
        env_session = os.environ.get("CLAY_SESSION", "").strip()
        if env_session:
            self.session.cookies.set("claysession", env_session, domain=".clay.com")
            return
        super()._load_cookies()

    # ── Workbook boundary ────────────────────────────────────────────────────

    def approve_workbook(self, workbook_id: str) -> str:
        if not workbook_id or not isinstance(workbook_id, str):
            raise ClayScopeError(f"approve_workbook needs an exact workbook id, got {workbook_id!r}")
        self.approved_workbook_id = workbook_id
        return workbook_id

    def _guard_write(self, table_id: str, view_id: str | None = None) -> None:
        """Re-read the table right before a write and refuse if it left the workbook."""
        approved = self.approved_workbook_id
        if not approved:
            raise ClayScopeError("REFUSED: call approve_workbook(<workbook id>) before writing.")
        try:
            raw = self.get_table(table_id)
        except Exception as e:
            raise ClayScopeError(f"REFUSED: cannot read table {table_id!r} to prove workbook membership: {e}") from e
        inner = raw.get("table", raw) if isinstance(raw, dict) else {}
        live = inner.get("workbookId")
        if live != approved:
            raise ClayScopeError(
                f"REFUSED: table {table_id!r} is in workbook {live!r}, not the approved {approved!r}.")
        if view_id and view_id not in {v.get("id") for v in inner.get("views") or []}:
            raise ClayScopeError(f"REFUSED: view {view_id!r} is not a view of table {table_id!r}.")

    # ── Workbooks ────────────────────────────────────────────────────────────

    def create_workbook(self, name: str) -> dict:
        wb = self.post("/workbooks", {"name": name, "workspaceId": int(self.workspace_id),
                                      "settings": {"isAutoRun": False}})
        return wb.get("workbook", wb)

    def get_workbook(self, workbook_id: str) -> dict:
        wb = self.get(f"/workspaces/{self.workspace_id}/workbooks/{workbook_id}")
        return wb.get("workbook", wb)

    def move_workbook(self, workbook_id: str, folder_id: str) -> dict:
        if workbook_id != self.approved_workbook_id:
            raise ClayScopeError(f"REFUSED: workbook {workbook_id!r} is not the approved workbook.")
        return self.patch(f"/workspaces/{self.workspace_id}/workbooks/{workbook_id}",
                          {"parentFolderId": folder_id})

    def workbook_url(self, workbook_id: str, table_id: str | None = None, view_id: str | None = None) -> str:
        url = f"https://app.clay.com/workspaces/{self.workspace_id}/workbooks/{workbook_id}"
        if table_id:
            url += f"/tables/{table_id}"
            if view_id:
                url += f"/views/{view_id}"
        return url

    # ── Tables, views, sources (guarded writes) ──────────────────────────────

    def create_blank_table(self, workbook_id: str) -> dict:
        if workbook_id != self.approved_workbook_id:
            raise ClayScopeError(f"REFUSED: workbook {workbook_id!r} is not the approved workbook.")
        res = self.post("/tables", {
            "icon": {"emoji": "🪄"}, "workspaceId": str(self.workspace_id), "type": "spreadsheet",
            "template": "basic", "workbookId": workbook_id, "callerName": "rex-flow-importer",
            "sourceSettings": {},
        })
        return res.get("table", res)

    def update_table(self, table_id: str, updates: dict) -> dict:
        self._guard_write(table_id)
        return self.patch(f"/tables/{table_id}", updates)

    def update_view(self, table_id: str, view_id: str, updates: dict) -> dict:
        self._guard_write(table_id, view_id)
        return self.patch(f"/tables/{table_id}/views/{view_id}", updates)

    def update_view_field(self, table_id: str, view_id: str, field_id: str, settings: dict) -> dict:
        """Per-field view settings. Clay ignores order and visibility in a whole-view PATCH."""
        self._guard_write(table_id, view_id)
        return self.patch(f"/tables/{table_id}/views/{view_id}/fields/{field_id}", settings)

    def update_view_filter(self, table_id: str, view_id: str, filter_settings) -> dict:
        self._guard_write(table_id, view_id)
        return self.patch(f"/workspaces/{self.workspace_id}/tables/{table_id}/views/{view_id}/filter",
                          filter_settings)

    def update_view_sort(self, table_id: str, view_id: str, sort_settings) -> dict:
        self._guard_write(table_id, view_id)
        return self.patch(f"/workspaces/{self.workspace_id}/tables/{table_id}/views/{view_id}/sort",
                          sort_settings)

    def _source_feeds(self, source_id: str, table_id: str) -> dict:
        source = self.get(f"/sources/{source_id}")
        if table_id not in {s.get("tableId") for s in source.get("sourceSubscriptions", [])}:
            raise ClayScopeError(f"REFUSED: source {source_id!r} does not feed table {table_id!r}")
        return source

    def update_source(self, table_id: str, source_id: str, updates: dict) -> dict:
        self._guard_write(table_id)
        self._source_feeds(source_id, table_id)
        return self.patch(f"/sources/{source_id}", updates)

    def trigger_source(self, table_id: str, source_id: str, page_size: int | None = None) -> dict:
        self._guard_write(table_id)
        self._source_feeds(source_id, table_id)
        suffix = f"?pageSize={int(page_size)}" if page_size else ""
        return self.post(f"/workspaces/{self.workspace_id}/sources/sendTrigger/{source_id}{suffix}", {})

    def get_source_runs(self, source_id: str) -> dict:
        return self.get(f"/workspaces/{self.workspace_id}/sources/{source_id}/runs")

    def wait_for_source_run(self, source_id: str, timeout: int = 180, poll: int = 3) -> dict:
        started = time.time()
        while time.time() - started < timeout:
            payload = self.get_source_runs(source_id)
            runs = payload.get("runs", []) if isinstance(payload, dict) else []
            if runs:
                latest = runs[0]
                if latest.get("status") == "SUCCESS":
                    return latest
                if latest.get("status") in {"ERROR", "FAILED", "CANCELLED"}:
                    raise ClayFlowError(f"SOURCE_RUN_FAILED: {source_id} {latest}")
            time.sleep(poll)
        raise ClayFlowError(f"SOURCE_RUN_TIMEOUT: {source_id}")

    def delete_column(self, table_id: str, field_id: str) -> dict:
        self._guard_write(table_id)
        return self.delete(f"/tables/{table_id}/fields/{field_id}")

    # ── Records (strict reads) ───────────────────────────────────────────────

    def get_record_ids(self, table_id: str, view_id: str) -> list[str]:
        res = self.get(f"/tables/{table_id}/views/{view_id}/records/ids")
        if _declares_next_page(res) or not isinstance(res, dict) or not isinstance(res.get("results"), list):
            raise ClayFlowError(f"INCOMPLETE_RECORD_ID_LIST: table={table_id} view={view_id}")
        ids = [rid for rid in res["results"] if rid != "search"]
        if len(ids) != len(set(ids)):
            raise ClayFlowError(f"DUPLICATE_RECORD_IDS: table={table_id} view={view_id}")
        return ids

    def get_records(self, table_id: str, record_ids: list[str], field_ids: list[str] | None = None) -> list[dict]:
        """Bulk-fetch every requested record, retrying transient errors, or fail."""
        results = []
        for offset in range(0, len(record_ids), 500):
            requested = record_ids[offset:offset + 500]
            body = {"recordIds": requested}
            if field_ids:
                body["fieldIds"] = field_ids
            for attempt in range(6):
                try:
                    res = self.post(f"/tables/{table_id}/bulk-fetch-records", body)
                    break
                except requests.HTTPError as exc:
                    code = exc.response.status_code if exc.response is not None else None
                    if code not in {429, 500, 502, 503, 504} or attempt == 5:
                        raise
                    time.sleep(min(2 ** (attempt + 1), 30))
                except requests.exceptions.RequestException:
                    if attempt == 5:
                        raise
                    time.sleep(min(2 ** (attempt + 1), 30))
            chunk = res.get("results", res.get("records")) if isinstance(res, dict) else None
            if not isinstance(chunk, list):
                raise ClayFlowError(f"INCOMPLETE_BULK_FETCH: table={table_id}")
            if {r.get("id") for r in chunk} != set(requested):
                raise ClayFlowError(f"INCOMPLETE_BULK_FETCH: table={table_id} requested={len(requested)} got={len(chunk)}")
            results.extend(chunk)
        return results

    def get_full_record(self, table_id: str, record_id: str) -> dict:
        """Single-record GET: the only route that returns full cell payloads with cost data."""
        return self.get(f"/tables/{table_id}/records/{record_id}")

    # ── Running ──────────────────────────────────────────────────────────────

    def run_column(self, table_id: str, field_ids: list[str], record_ids: list[str] = None,
                   view_id: str = None) -> dict:
        self._guard_write(table_id, view_id)
        body = {"fieldIds": field_ids, "callerName": "rex-flow"}
        if record_ids:
            body["runRecords"] = {"recordIds": record_ids}
        elif view_id:
            body["runRecords"] = {"viewId": view_id}
        return self.patch(f"/tables/{table_id}/run", body)

    def run_and_wait(self, table_id: str, field_ids: list[str], record_ids: list[str],
                     timeout: int = 300, poll: int = 4) -> list[dict]:
        """Run columns on records and poll until every cell settles or the timeout passes.

        A cell settles when it has a final status (SUCCESS, an ERROR_* status,
        including ERROR_RUN_CONDITION_NOT_MET for a row the run condition skips).
        A cell with no status and no value after the first poll window is also
        treated as settled, so a skipped row cannot hold the loop for the full
        timeout.
        """
        self.run_column(table_id, field_ids, record_ids=record_ids)
        start = time.time()
        records = []
        while time.time() - start < timeout:
            time.sleep(poll)
            records = self.get_records(table_id, record_ids)
            waiting = False
            for rec in records:
                for fid in field_ids:
                    cell = (rec.get("cells") or {}).get(fid) or {}
                    status = (cell.get("metadata") or {}).get("status") or ""
                    if status in PENDING_STATUSES:
                        waiting = True
                    elif status == "" and cell.get("value") in (None, "") and time.time() - start < 30:
                        waiting = True
            if not waiting:
                return records
        return records or self.get_records(table_id, record_ids)

    # ── Schema import (hardened) ─────────────────────────────────────────────

    def _create_field(self, table_id: str, view_id: str, field_def: dict) -> dict:
        self._guard_write(table_id, view_id)
        return self.post(f"/tables/{table_id}/fields", {**field_def, "activeViewId": view_id})

    def _require_formula_readback(self, table_id: str, field_id: str, expected: dict) -> None:
        """Reject a 2xx formula PATCH that left a plain text column behind."""
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        field = next((f for f in table.get("fields", []) if f.get("id") == field_id), None)
        actual = (field or {}).get("typeSettings") or {}
        mismatched = []
        for key in ("formulaText", "formulaType", "dataTypeSettings", "mappedResultPath"):
            if key not in expected or actual.get(key) == expected.get(key):
                continue
            if (key == "mappedResultPath" and actual.get(key) is None
                    and formula_text_selects_mapped_path(expected.get("formulaText"), expected.get(key))):
                continue
            mismatched.append(key)
        if field is None or field.get("type") != "formula" or mismatched:
            raise ClayFlowError(f"Formula did not persist for {field_id}: "
                                f"type={(field or {}).get('type')!r} mismatched={mismatched}")

    def import_schema(self, table_id: str, schema: dict, dry_run: bool = False) -> list[dict]:
        """Create portable columns in dependency order. Stops at the first failure.

        Differences from ClayClient.import_schema: every write is workbook-guarded,
        a half-created formula (text shell) is repaired instead of duplicated,
        source-field settings are carried through, and the loop stops at the
        first failed column so no later column binds to a missing reference.
        """
        self._guard_write(table_id)
        raw = self.get_table(table_id)
        table = raw.get("table", raw)
        existing = table.get("fields", [])
        views = table.get("gridViews", table.get("views", []))
        view_id = views[0]["id"] if views else table.get("firstViewId")
        name_to_id = {f["name"]: f["id"] for f in existing}
        existing_by_name = {f["name"]: f for f in existing}
        source_name_to_data_ref: dict[str, str] = {}
        sorted_cols = _sort_by_deps(schema.get("columns", []))
        if dry_run:
            for c in sorted_cols:
                print(f"  {c['type']:8s} | {c['name']}")
            return []

        results = []
        print(f"[clay] importing {len(sorted_cols)} columns into {table_id}...")
        for col in sorted_cols:
            col_type = col.get("type", "text")
            try:
                existing_field = existing_by_name.get(col["name"])
                if existing_field is not None:
                    ts = _names_to_refs(copy.deepcopy(col.get("typeSettings") or {}),
                                        name_to_id, source_name_to_data_ref)
                    live_ts = existing_field.get("typeSettings") or {}
                    is_shell = (col_type == "formula" and bool(ts.get("formulaText"))
                                and existing_field.get("type") == "text"
                                and "formulaText" not in live_ts
                                and set(live_ts) <= {"dataTypeSettings"}
                                and isinstance(live_ts.get("dataTypeSettings"), dict))
                    if not is_shell:
                        raise ClayFlowError(f"Existing field is not a repairable formula shell: {col['name']}")
                    formula_ts = copy.deepcopy(ts)
                    formula_ts.setdefault("dataTypeSettings", copy.deepcopy(live_ts["dataTypeSettings"]))
                    formula_ts.setdefault("formulaType", "text")
                    self._guard_write(table_id)
                    self.patch(f"/tables/{table_id}/fields/{existing_field['id']}", {"typeSettings": formula_ts})
                    self._require_formula_readback(table_id, existing_field["id"], formula_ts)
                    results.append({"success": True, "name": col["name"], "resumed": True})
                    print(f"  [repaired] {col['name']}")
                    continue

                if col_type == "source" and col.get("sourceDetails"):
                    created = []
                    for sd in col["sourceDetails"]:
                        ts = _names_to_refs(copy.deepcopy(sd.get("typeSettings", {})),
                                            name_to_id, source_name_to_data_ref)
                        self._guard_write(table_id)
                        src = self.post("/sources", {
                            "workspaceId": int(self.workspace_id), "tableId": table_id,
                            "name": sd["name"], "type": sd.get("type", "v3-action"), "typeSettings": ts,
                        })
                        sid = src.get("id") or (src.get("source") or {}).get("id")
                        if sid:
                            created.append(sid)
                            dfid = src.get("dataFieldId") or (src.get("source") or {}).get("dataFieldId")
                            if not dfid:
                                try:
                                    dfid = self.get(f"/sources/{sid}").get("dataFieldId")
                                except Exception:
                                    pass
                            if dfid:
                                source_name_to_data_ref[col["name"]] = dfid
                        time.sleep(0.15)
                    if not created:
                        raise ClayFlowError("No sources created")
                    field_ts = _names_to_refs(copy.deepcopy(col.get("typeSettings") or {}),
                                              name_to_id, source_name_to_data_ref)
                    field_ts["sourceIds"] = created
                    field_ts.setdefault("canCreateRecords", True)
                    result = self._create_field(table_id, view_id, {
                        "name": col["name"], "type": "source", "typeSettings": field_ts})
                else:
                    ts = (_names_to_refs(copy.deepcopy(col["typeSettings"]), name_to_id, source_name_to_data_ref)
                          if col.get("typeSettings") else None)
                    field_def = {"name": col["name"], "type": col_type}
                    if ts:
                        field_def["typeSettings"] = ts
                    if col_type == "text":
                        field_def.setdefault("typeSettings", {}).setdefault("dataTypeSettings", {"type": "text"})
                    if col_type == "formula" and ts and ts.get("formulaText"):
                        # Clay creates formulas as a text column first, then PATCHes the formula.
                        formula_ts = copy.deepcopy(ts)
                        formula_ts.setdefault("dataTypeSettings", {"type": "text"})
                        formula_ts.setdefault("formulaType", "text")
                        field_def["type"] = "text"
                        field_def["typeSettings"] = {"dataTypeSettings": copy.deepcopy(formula_ts["dataTypeSettings"])}
                        result = self._create_field(table_id, view_id, field_def)
                        fid = (result.get("field") or result).get("id")
                        if fid:
                            self._guard_write(table_id)
                            self.patch(f"/tables/{table_id}/fields/{fid}", {"typeSettings": formula_ts})
                            self._require_formula_readback(table_id, fid, formula_ts)
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
            except ClayScopeError:
                raise
            except Exception as e:
                detail = str(e)
                resp = getattr(e, "response", None)
                if resp is not None:
                    detail += " | " + resp.text[:400]
                results.append({"success": False, "name": col["name"], "error": detail})
                print(f"  [FAIL] {col['name']}: {detail}")
                break
            time.sleep(0.15)
        return results
