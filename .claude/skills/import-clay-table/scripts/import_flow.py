#!/usr/bin/env python3
"""Import one Clay flow blueprint (table JSON) into a held, non-running workbook.

This is a structural importer. It creates the workbook, tables, sources,
columns, cross-table bindings, table settings and views, then reads everything
back and compares it with the blueprint. It never creates records, never runs a
source or a column, and leaves auto-run off on every table.

Placeholders resolved at import time:
  ${workspace.id}                   the target workspace (config or --workspace)
  ${workbook.id}                    the workbook this import creates
  ${tables.<t>.id}, ${tables.<t>.fields.<slug>.id}, ${tables.<t>.views.<v>.id},
  ${tables.<t>.sources.<slug>.id}   objects created during the import
  ${bindings.authAccounts.<name>}   an auth account id from config "authAccounts"
                                    or --auth-account name=aa_...
  ${bindings.models.<name>}         a model id from config "models" or --model name=...

Usage:
  python3 .claude/skills/import-clay-table/scripts/import_flow.py --schema table.flow.json --dry-run
  python3 .claude/skills/import-clay-table/scripts/import_flow.py --schema table.flow.json \
      --receipt output/campaigns/<slug>/runs/import-receipt.json [--workspace 123] [--folder f_...] \
      [--auth-account llm=aa_...] [--model default=<model id>]
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Rex (clay_client.py, clay_flow.py, rex-config.json) lives in tools/rex/ at the starter-kit root:
# scripts/ -> <skill>/ -> skills/ -> .claude/ -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[4] / "tools" / "rex"
sys.path.insert(0, str(REPO_ROOT))

from clay_flow import (  # noqa: E402
    FlowClient, _extract_deps, _names_to_refs, formula_text_selects_mapped_path,
    load_config, resolve_settings,
)

UNRESOLVED_RE = re.compile(r"\$\{[^}]+\}|\{\{@[^}]+\}\}")
BINDING_RE = re.compile(r"\$\{bindings\.(authAccounts|models)\.([A-Za-z0-9_\-]+)\}")
EXACT_NAMED_REF_RE = re.compile(r"^\{\{@([^}]+)\}\}$")
EXACT_FIELD_REF_RE = re.compile(r"^\{\{(f_[^}]+)\}\}$")
NAMED_REF_RE = re.compile(r"\{\{@([^}]+)\}\}")
SYSTEM_FIELD_IDS = {"f_created_at", "f_updated_at"}
SYSTEM_FIELD_NAMES = {"Created At", "Updated At"}
# Actions that do not spend credits or provider money; everything else is treated as paid.
FREE_ACTION_KEYS = {"lookup-company-in-other-table", "trigger-find-people-source", "route-row"}


# ── Generic helpers ───────────────────────────────────────────────────────────

def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def resolve(value: Any, bindings: dict[str, str]) -> Any:
    if isinstance(value, str):
        for placeholder, actual in bindings.items():
            value = value.replace(placeholder, str(actual))
        return value
    if isinstance(value, list):
        return [resolve(item, bindings) for item in value]
    if isinstance(value, dict):
        return {resolve(k, bindings) if isinstance(k, str) else k: resolve(v, bindings)
                for k, v in value.items()}
    return value


def names_to_view_refs(value: Any, name_to_id: dict[str, str],
                       source_name_to_data_ref: dict[str, str] | None = None) -> Any:
    """Convert {{@Name}} references in view values and field-map keys to field ids."""
    source_name_to_data_ref = source_name_to_data_ref or {}
    if isinstance(value, str):
        m = EXACT_NAMED_REF_RE.fullmatch(value)
        if m and m.group(1) in name_to_id:
            return name_to_id[m.group(1)]
        converted = _names_to_refs(value, name_to_id, source_name_to_data_ref)
        fm = EXACT_FIELD_REF_RE.fullmatch(converted)
        return fm.group(1) if fm else converted
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            ck = names_to_view_refs(key, name_to_id, source_name_to_data_ref)
            ci = names_to_view_refs(item, name_to_id, source_name_to_data_ref)
            if key == "field" and isinstance(ci, str):
                ck = "fieldId"
            out[ck] = ci
        return out
    if isinstance(value, list):
        return [names_to_view_refs(i, name_to_id, source_name_to_data_ref) for i in value]
    return value


def inner_table(payload: dict) -> dict:
    return payload.get("table", payload)


def fields_by_name(client: FlowClient, table_id: str) -> dict[str, dict]:
    return {f["name"]: f for f in inner_table(client.get_table(table_id)).get("fields", [])}


def normalized_type_settings(value: Any) -> Any:
    """Drop Clay's non-semantic concurrency hint before comparing settings."""
    if isinstance(value, dict):
        return {k: normalized_type_settings(v) for k, v in value.items() if k != "concurrency"}
    if isinstance(value, list):
        return [normalized_type_settings(v) for v in value]
    return value


def _settings_error(field: dict) -> Any:
    return field.get("settingsError") or (field.get("typeSettings") or {}).get("settingsError")


def _without_settings_error(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_settings_error(v) for k, v in value.items() if k != "settingsError"}
    if isinstance(value, list):
        return [_without_settings_error(v) for v in value]
    return value


def expected_native_field_settings(column: dict, bindings: dict[str, str], name_to_id: dict[str, str],
                                   source_name_to_data_ref: dict[str, str] | None = None) -> dict:
    expected = _names_to_refs(resolve(copy.deepcopy(column.get("typeSettings") or {}), bindings),
                              name_to_id, source_name_to_data_ref)
    if column.get("type") == "formula" and expected.get("formulaText"):
        expected.setdefault("dataTypeSettings", {"type": "text"})
        expected.setdefault("formulaType", "text")
    return expected


def native_field_settings_equivalent(column: dict, expected: dict, actual: dict) -> tuple[bool, dict]:
    """Compare exactly, allowing only Clay's observed defaults on a new action.

    Clay appends actionVersion=1 and its default rate-limit policy to a new
    action column. Anything else that differs (prompt, model, schema, auth,
    run condition) is a real difference.
    """
    defaults: dict = {}
    live = copy.deepcopy(_without_settings_error(actual))
    if column.get("type") == "action":
        if "actionVersion" not in expected:
            if live.get("actionVersion") != 1:
                return False, defaults
            defaults["actionVersion"] = live.pop("actionVersion")
        if "customRateLimitRules" not in expected and "customRateLimitRules" in live:
            # Clay's default throughput policy; its numbers differ between workspaces.
            defaults["customRateLimitRules"] = live.pop("customRateLimitRules")
    if (column.get("type") == "formula" and "mappedResultPath" in expected
            and live.get("mappedResultPath") is None
            and formula_text_selects_mapped_path(expected.get("formulaText"), expected.get("mappedResultPath"))):
        live["mappedResultPath"] = copy.deepcopy(expected["mappedResultPath"])
    return normalized_type_settings(live) == normalized_type_settings(expected), defaults


def field_has_action_or_source(field: dict) -> bool:
    s = field.get("typeSettings") or {}
    return (field.get("type") in {"action", "source"} or bool(s.get("sourceIds"))
            or bool(s.get("actionKey")) or bool(s.get("actionPackageId")))


# ── Resume support ────────────────────────────────────────────────────────────

def resume_column_repairs(client: FlowClient, table_id: str, columns: list[dict],
                          bindings: dict[str, str]) -> dict[str, set[str]]:
    """Classify columns that already exist before a resumed import touches them.

    A half-created formula (a text shell) is repaired in place. An action with a
    native settings error is rebuilt with its dependants. Any other existing
    column must already match the blueprint exactly, or the import stops.
    """
    live = fields_by_name(client, table_id)
    name_to_id = {n: f["id"] for n, f in live.items() if f.get("id")}
    shells: set[str] = set()
    rebuilds: set[str] = set()
    for column in columns:
        field = live.get(column["name"])
        if field is None:
            continue
        expected_type = column.get("type", "text")
        expected = expected_native_field_settings(column, bindings, name_to_id)
        if expected_type == "text":
            expected.setdefault("dataTypeSettings", {"type": "text"})
        actual = field.get("typeSettings") or {}
        error = _settings_error(field)
        if expected_type == "formula":
            if (field.get("type") == "text" and expected.get("formulaText")
                    and "formulaText" not in actual and set(actual) <= {"dataTypeSettings"}):
                shells.add(column["name"])
                continue
            if field.get("type") != "formula" or not actual.get("formulaText"):
                raise RuntimeError(f"Existing field is not a formula or a repairable shell: {column['name']}")
        elif field.get("type") != expected_type:
            raise RuntimeError(f"Existing field type differs for {column['name']}: "
                               f"live={field.get('type')!r} expected={expected_type!r}")
        if expected_type == "action" and error:
            if not native_field_settings_equivalent(column, expected, actual)[0]:
                raise RuntimeError(f"Errored action is not this blueprint's action: {column['name']}")
            rebuilds.add(column["name"])
            continue
        if error:
            raise RuntimeError(f"Existing field has a native settings error: {column['name']}: {error!r}")
        if not native_field_settings_equivalent(column, expected, actual)[0]:
            raise RuntimeError(f"Existing field settings differ from the blueprint: {column['name']}")
    return {"formulaShells": shells, "actionRebuilds": rebuilds}


def remove_repair_columns(client: FlowClient, table_id: str, blueprint: dict, requested: list[str]) -> list[str]:
    """Delete a broken column and everything in this table that depends on it, so it can be recreated."""
    affected = set(requested)
    changed = True
    while changed:
        changed = False
        for column in blueprint.get("columns", []):
            if column["name"] not in affected and set(_extract_deps(column.get("typeSettings") or {})) & affected:
                affected.add(column["name"])
                changed = True
    live = fields_by_name(client, table_id)
    removed = []
    for column in reversed(blueprint.get("columns", [])):
        if column["name"] in affected and column["name"] in live:
            client.delete_column(table_id, live[column["name"]]["id"])
            removed.append(column["name"])
    return removed


# ── Views ─────────────────────────────────────────────────────────────────────

def native_view_counts(payload: dict) -> dict[str, int]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid Clay view count payload: {payload!r}")
    if {"viewTotalRecordsCount", "tableTotalRecordsCount"} <= set(payload):
        view_count, table_count = payload["viewTotalRecordsCount"], payload["tableTotalRecordsCount"]
    else:
        legacy = [payload[k] for k in ("count", "total") if k in payload]
        if not legacy or len(set(legacy)) != 1:
            raise RuntimeError(f"Missing or conflicting Clay view counts: {payload!r}")
        view_count = table_count = legacy[0]
    for v in (view_count, table_count):
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise RuntimeError(f"Invalid Clay view count: {payload!r}")
    if view_count > table_count:
        raise RuntimeError(f"Impossible Clay view count: view={view_count} table={table_count}")
    return {"viewCount": view_count, "tableCount": table_count}


def _cell_is_empty_scaffold(cell: Any, field: dict | None) -> bool:
    """True when a cell carries nothing a user, source or action put there.

    Clay keeps one empty scaffold row on a new basic table. Its formula cells
    can report SUCCESS with no value (and 'stale' because auto-run is off);
    that is still an empty row. Any real value, external payload, or an action
    or source status other than never-run means the row is real.
    """
    if field is None:
        return False
    if cell in (None, "", [], {}):
        return True
    if not isinstance(cell, dict):
        return False
    if cell.get("value") not in (None, "", [], {}):
        return False
    md = cell.get("metadata") or {}
    status = str(cell.get("status") or (md.get("status") if isinstance(md, dict) else "") or "").strip().upper()
    extra = [v for k, v in cell.items() if k not in {"value", "metadata", "status", "state"}]
    if any(v not in (None, "", [], {}) for v in extra):
        return False
    if field.get("type") == "formula" and status in {"", "SUCCESS"}:
        allowed = {"status", "isCoerced", "isComputed", "isEmpty", "isStale", "staleReason"}
        if isinstance(md, dict) and set(md) <= allowed and md.get("staleReason") in (None, "TABLE_AUTO_RUN_OFF"):
            return True
    return status in {"", "NOT_RUN", "NO_RUN", "NEVER_RUN", "EMPTY", "UNRUN"}


def count_user_records(client: FlowClient, table_id: str, table: dict, preferred_view_id: str | None) -> dict:
    """Count real rows, accepting only Clay's one empty scaffold row as 'no rows'."""
    views = table.get("views") or []
    if not views:
        raise RuntimeError(f"No views on {table_id}")
    view_counts, table_counts = {}, set()
    for view in views:
        counts = native_view_counts(client.get(f"/tables/{table_id}/views/{view['id']}/count"))
        view_counts[view["id"]] = counts["viewCount"]
        table_counts.add(counts["tableCount"])
    if len(table_counts) != 1:
        raise RuntimeError(f"Inconsistent table counts for {table_id}: {sorted(table_counts)}")
    total = table_counts.pop()
    proof = {"nativeTableRecordCount": total, "userRecordCount": 0, "recordIds": []}
    if total == 0:
        return proof
    if total > 1:
        proof["userRecordCount"] = total
        return proof
    readable = preferred_view_id if view_counts.get(preferred_view_id) == 1 else next(
        (vid for vid, c in view_counts.items() if c == 1), None)
    if readable is None:
        raise RuntimeError(f"Clay reports one row in {table_id} but no view shows it")
    ids = client.get_record_ids(table_id, readable)
    records = client.get_records(table_id, ids)
    fields = {f["id"]: f for f in table.get("fields", []) if f.get("id")}
    real = [fid for fid, cell in (records[0].get("cells") or {}).items()
            if fid not in SYSTEM_FIELD_IDS and not _cell_is_empty_scaffold(cell, fields.get(fid))]
    proof["recordIds"] = ids
    proof["userRecordCount"] = 1 if real else 0
    return proof


def is_blank_template_default(client: FlowClient, table_id: str, table: dict, view: dict) -> bool:
    """The default view may be adopted by position only on a still-empty basic table."""
    if view.get("filter") not in (None, {}) or view.get("sort") not in (None, []):
        return False
    fields = table.get("fields", [])
    if any(field_has_action_or_source(f) for f in fields):
        return False
    template = [f for f in fields if f.get("id") not in SYSTEM_FIELD_IDS]
    if len(template) > 1 or (template and template[0].get("name") != "New Column"):
        return False
    try:
        return count_user_records(client, table_id, table, view.get("id"))["userRecordCount"] == 0
    except RuntimeError:
        return False


def views_by_logical_id(client: FlowClient, table_id: str, table: dict, blueprint: dict,
                        bindings: dict[str, str]) -> dict[str, dict]:
    live_views = table.get("views", [])
    result, used = {}, set()

    def unique(cands: list[dict], label: str) -> dict | None:
        if len(cands) > 1:
            raise RuntimeError(f"Ambiguous live view match for {blueprint['logicalId']}.{label}")
        return cands[0] if cands else None

    for wanted in blueprint.get("views", []):
        bound_id = bindings.get(f"${{tables.{blueprint['logicalId']}.views.{wanted['logicalId']}.id}}")
        live = unique([v for v in live_views if v.get("id") == bound_id], wanted["logicalId"]) if bound_id else None
        if bound_id and live is None:
            raise RuntimeError(f"Bound view {bound_id} is missing for {blueprint['logicalId']}.{wanted['logicalId']}")
        pre = (wanted.get("typeSettings") or {}).get("preconfiguredType")
        by_type = unique([v for v in live_views if pre and (v.get("typeSettings") or {}).get("preconfiguredType") == pre],
                         wanted["logicalId"] + ".preconfigured")
        by_name = unique([v for v in live_views if v.get("name") == wanted.get("name")], wanted["logicalId"] + ".name")
        if not live and by_type and by_name and by_type.get("id") != by_name.get("id"):
            raise RuntimeError(f"View {wanted['logicalId']} matches two different live views")
        live = live or by_type or by_name
        if not live and wanted.get("logicalId") == "default_view":
            # A fresh table's default is called "Default view"; the blueprint may rename it.
            live = unique([v for v in live_views if v.get("id") == table.get("firstViewId")
                           or v.get("name") == "Default view"], "default")
            if live is not None and not is_blank_template_default(client, table_id, table, live):
                raise RuntimeError(f"Default view of {blueprint['logicalId']} is not a blank template")
        if not live:
            raise RuntimeError(f"No live view matches {blueprint['logicalId']}.{wanted['logicalId']}")
        if live["id"] in used:
            raise RuntimeError(f"Physical view {live['id']} matched twice in {blueprint['logicalId']}")
        used.add(live["id"])
        result[wanted["logicalId"]] = live
    return result


def update_views(client: FlowClient, table_id: str, blueprint: dict, bindings: dict[str, str]) -> None:
    table = inner_table(client.get_table(table_id))
    name_to_id = {f["name"]: f["id"] for f in table.get("fields", []) if f.get("name") and f.get("id")}
    live_views = views_by_logical_id(client, table_id, table, blueprint, bindings)
    for wanted in blueprint.get("views", []):
        live = live_views[wanted["logicalId"]]
        preconfigured = bool((wanted.get("typeSettings") or {}).get("preconfiguredType"))
        system = {fid: s for fid, s in (live.get("fields") or {}).items() if fid in SYSTEM_FIELD_IDS}
        fields = names_to_view_refs(resolve(copy.deepcopy(wanted.get("fields", {})), bindings), name_to_id)
        flt = names_to_view_refs(resolve(copy.deepcopy(wanted.get("filter")), bindings), name_to_id)
        srt = names_to_view_refs(resolve(copy.deepcopy(wanted.get("sort")), bindings), name_to_id)
        client.update_view(table_id, live["id"], {
            "name": wanted["name"], "description": wanted.get("description"),
            "fields": {**system, **fields}, "limit": wanted.get("limit"), "offset": wanted.get("offset"),
            "typeSettings": copy.deepcopy(wanted.get("typeSettings") or {}),
        })
        if not preconfigured:
            if flt is not None:
                client.update_view_filter(table_id, live["id"], flt)
            if srt is not None:
                client.update_view_sort(table_id, live["id"], srt)
        # Clay ignores order and visibility inside the whole-view PATCH above.
        # Apply them per field, in the blueprint's order: that order is what the viewer sees.
        prev = None
        for field_id, cfg in fields.items():
            if field_id not in name_to_id.values():
                continue
            body = {"isVisible": bool((cfg or {}).get("isVisible", True)), "width": (cfg or {}).get("width", 200)}
            if prev:
                body["afterFieldId"] = prev
            client.update_view_field(table_id, live["id"], field_id, body)
            prev = field_id


# ── Tables, columns, sources ─────────────────────────────────────────────────

def add_table_bindings(client: FlowClient, blueprint: dict, table_id: str, bindings: dict[str, str]) -> None:
    logical_id = blueprint["logicalId"]
    table = inner_table(client.get_table(table_id))
    bindings[f"${{tables.{logical_id}.id}}"] = table_id
    for vid, view in views_by_logical_id(client, table_id, table, blueprint, bindings).items():
        bindings[f"${{tables.{logical_id}.views.{vid}.id}}"] = view["id"]
    live_fields = {f["name"]: f for f in table.get("fields", [])}
    for column in blueprint.get("columns", []):
        live = live_fields.get(column["name"])
        if live:
            bindings[f"${{tables.{logical_id}.fields.{slug(column['name'])}.id}}"] = live["id"]
        if column.get("type") != "source" or not live:
            continue
        source_ids = (live.get("typeSettings") or {}).get("sourceIds", [])
        if len(source_ids) != len(column.get("sourceDetails", [])):
            raise RuntimeError(f"Source count mismatch for {logical_id}.{column['name']}")
        declared = (column.get("typeSettings") or {}).get("sourceIds", [])
        for i, sid in enumerate(source_ids):
            if i < len(declared) and str(declared[i]).startswith("${"):
                bindings[declared[i]] = sid


def import_columns(client: FlowClient, table_id: str, columns: list[dict], bindings: dict[str, str]) -> list[dict]:
    existing = fields_by_name(client, table_id)
    names = [c["name"] for c in columns]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise RuntimeError(f"Duplicate column names in blueprint: {dupes}")
    repairs = resume_column_repairs(client, table_id, columns, bindings)
    pending = [c for c in columns if c["name"] not in existing or c["name"] in repairs["formulaShells"]]
    if not pending:
        return [{"success": True, "name": c["name"], "resumed": True} for c in columns]
    results = client.import_schema(table_id, {"version": "1.0", "columns": resolve(copy.deepcopy(pending), bindings)})
    failed = [r for r in results if not r.get("success")]
    if failed or len(results) < len(pending):
        raise RuntimeError(f"Column import failed: {json.dumps(failed, ensure_ascii=False)}")
    after = fields_by_name(client, table_id)
    errors = {c["name"]: _settings_error(after.get(c["name"], {})) for c in pending
              if _settings_error(after.get(c["name"], {}))}
    if errors:
        raise RuntimeError(f"Clay reported settings errors after import: {errors}")
    return results


def hold_table(client: FlowClient, table_id: str) -> None:
    client.update_table(table_id, {"tableSettings": {"AUTO_RUN_ON": False}})
    if (inner_table(client.get_table(table_id)).get("tableSettings") or {}).get("AUTO_RUN_ON") is not False:
        raise RuntimeError(f"Could not switch auto-run off on {table_id}")


def update_table_settings(client: FlowClient, table_id: str, blueprint: dict, bindings: dict[str, str]) -> None:
    desired = resolve(copy.deepcopy(blueprint.get("tableSettings") or {"AUTO_RUN_ON": False}), bindings)
    if desired.get("AUTO_RUN_ON") is not False:
        raise RuntimeError(f"Refusing table settings with auto-run on for {blueprint['logicalId']}")
    client.update_table(table_id, {"tableSettings": desired})


def reconcile_sources(client: FlowClient, table_id: str, blueprint: dict, bindings: dict[str, str]) -> None:
    """Re-apply source definitions once every cross-table id exists."""
    live = {f["name"]: f for f in inner_table(client.get_table(table_id)).get("fields", [])}
    for column in blueprint.get("columns", []):
        if column.get("type") != "source":
            continue
        source_ids = (live[column["name"]].get("typeSettings") or {}).get("sourceIds", [])
        for sid, detail in zip(source_ids, column.get("sourceDetails", [])):
            desired = resolve(copy.deepcopy(detail), bindings)
            client.update_source(table_id, sid, {"name": desired["name"], "typeSettings": desired.get("typeSettings") or {}})


def remove_blank_template_fields(client: FlowClient, table_id: str, blueprint: dict) -> list[str]:
    desired = {c["name"] for c in blueprint.get("columns", [])}
    removed = []
    for f in inner_table(client.get_table(table_id)).get("fields", []):
        if f.get("id") not in SYSTEM_FIELD_IDS and f.get("name") not in desired:
            client.delete_column(table_id, f["id"])
            removed.append(f["name"])
    return removed


# ── Readback ──────────────────────────────────────────────────────────────────

def verify_live_flow(client: FlowClient, schema: dict, table_ids: dict[str, str], workbook_id: str,
                     bindings: dict[str, str]) -> dict:
    out = {"workbookId": workbook_id, "tables": {}, "recordCount": 0}
    for blueprint in schema["tables"]:
        logical_id = blueprint["logicalId"]
        table_id = table_ids[logical_id]
        table = inner_table(client.get_table(table_id))
        live_by_name = {f["name"]: f for f in table.get("fields", [])}
        names = [c["name"] for c in blueprint["columns"]]
        missing = [n for n in names if n not in live_by_name]
        extras = [f["name"] for f in table.get("fields", [])
                  if f.get("id") not in SYSTEM_FIELD_IDS and f.get("name") not in names]
        if missing or extras:
            raise RuntimeError(f"Schema mismatch in {logical_id}: missing={missing} extras={extras}")
        if table.get("workbookId") != workbook_id:
            raise RuntimeError(f"Workbook mismatch for {table_id}")
        if (table.get("tableSettings") or {}).get("AUTO_RUN_ON") is not False:
            raise RuntimeError(f"Auto-run is not off on {table_id}")
        errors = {n: _settings_error(live_by_name[n]) for n in names if _settings_error(live_by_name[n])}
        if errors:
            raise RuntimeError(f"Clay settings errors in {logical_id}: {errors}")
        unresolved = [n for n in names if UNRESOLVED_RE.search(json.dumps(live_by_name[n], ensure_ascii=False))]
        if unresolved:
            raise RuntimeError(f"Unresolved placeholders or references in {logical_id}: {unresolved}")

        by_name = {c["name"]: c for c in blueprint["columns"]}
        sources, source_refs = [], {}
        for n in names:
            field = live_by_name[n]
            if field.get("type") != "source":
                continue
            details = by_name[n].get("sourceDetails", [])
            ids = (field.get("typeSettings") or {}).get("sourceIds", [])
            if len(ids) != len(details):
                raise RuntimeError(f"Source count mismatch for {logical_id}.{n}")
            for i, sid in enumerate(ids):
                src = client.get(f"/sources/{sid}")
                if src.get("dataFieldId"):
                    source_refs[n] = src["dataFieldId"]
                st = src.get("typeSettings") or {}
                if st.get("disableTriggerOnCreate") is not True or st.get("disableTriggerOnUpdate") is not True:
                    raise RuntimeError(f"Source {sid} can trigger on its own; set disableTriggerOnCreate/Update")
                expected = resolve(copy.deepcopy(details[i]), bindings)
                if (src.get("name"), src.get("type"), st) != (expected.get("name"), expected.get("type"),
                                                              expected.get("typeSettings") or {}):
                    raise RuntimeError(f"Source {sid} differs from the blueprint")
                sources.append({"id": sid, "name": src.get("name"), "fieldName": n})

        name_to_id = {n: live_by_name[n]["id"] for n in names}
        diffs, defaults = [], {}
        for n in names:
            if live_by_name[n].get("type") != by_name[n].get("type", "text"):
                diffs.append(f"{n} (type)")
                continue
            expected = expected_native_field_settings(by_name[n], bindings, name_to_id, source_refs)
            ok, d = native_field_settings_equivalent(by_name[n], expected, live_by_name[n].get("typeSettings") or {})
            if d:
                defaults[n] = d
            if not ok:
                diffs.append(n)
        if diffs:
            raise RuntimeError(f"Live columns differ from the blueprint in {logical_id}: {diffs}")

        live_views = views_by_logical_id(client, table_id, table, blueprint, bindings)
        view_errors = []
        for wanted in blueprint.get("views", []):
            live = live_views[wanted["logicalId"]]
            pre = bool((wanted.get("typeSettings") or {}).get("preconfiguredType"))
            if live.get("name") != wanted["name"]:
                view_errors.append(f"{wanted['logicalId']}.name")
            for key in ("filter", "sort"):
                exp = names_to_view_refs(resolve(copy.deepcopy(wanted.get(key)), bindings), name_to_id, source_refs)
                if not pre and live.get(key) != exp:
                    view_errors.append(f"{wanted['logicalId']}.{key}")
            exp_fields = names_to_view_refs(resolve(copy.deepcopy(wanted.get("fields", {})), bindings),
                                            name_to_id, source_refs)
            live_fields = live.get("fields") or {}
            for fid, s in exp_fields.items():
                if fid not in live_fields:
                    view_errors.append(f"{wanted['logicalId']}.fields.{fid}.missing")
                elif bool((live_fields[fid] or {}).get("isVisible", True)) != bool((s or {}).get("isVisible", True)):
                    view_errors.append(f"{wanted['logicalId']}.fields.{fid}.visibility")
            declared = [fid for fid in exp_fields if fid in live_fields]
            if declared and all((live_fields[fid] or {}).get("order") is not None for fid in declared):
                if sorted(declared, key=lambda fid: str(live_fields[fid]["order"])) != declared:
                    view_errors.append(f"{wanted['logicalId']}.fields.order")
        if view_errors:
            raise RuntimeError(f"Live views differ from the blueprint in {logical_id}: {view_errors}")

        default_view = live_views.get("default_view")
        if default_view is None:
            raise RuntimeError(f"{logical_id} declares no default_view")
        records = count_user_records(client, table_id, table, default_view["id"])
        if records["userRecordCount"]:
            raise RuntimeError(f"Expected zero rows in {logical_id}, found {records['userRecordCount']}")
        out["tables"][logical_id] = {
            "id": table_id, "name": table.get("name"), "defaultViewId": default_view["id"],
            "viewIds": {k: v["id"] for k, v in live_views.items()}, "columnCount": len(names),
            "fieldIds": name_to_id,
            "actionCount": sum(1 for n in names if live_by_name[n].get("type") == "action"),
            "sources": sources, "recordCount": 0, "autoRun": False, "nativeActionDefaults": defaults,
            "url": client.workbook_url(workbook_id, table_id, default_view["id"]),
        }
    return out


# ── Lint (dry run) ────────────────────────────────────────────────────────────

def _quotes_balanced(formula: str) -> bool:
    """A Clay prompt is a formula; an unescaped double quote inside a literal breaks it."""
    count, i = 0, 0
    while i < len(formula):
        ch = formula[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            count += 1
        i += 1
    return count % 2 == 0


def lint(schema: dict, available: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Check the rules that decide whether a table works. Returns (errors, warnings)."""
    errors, warnings = [], []
    wb = ((schema.get("flow") or {}).get("workbook") or {}).get("create") or {}
    if (wb.get("settings") or {}).get("isAutoRun") is not False:
        errors.append("flow.workbook.create.settings.isAutoRun must be false")
    order = (schema.get("flow") or {}).get("buildOrder") or []
    if sorted(order) != sorted(t["logicalId"] for t in schema.get("tables", [])):
        errors.append("flow.buildOrder must list every table logicalId exactly once")
    for name in sorted({m.group(0) for m in BINDING_RE.finditer(json.dumps(schema))}):
        kind, key = BINDING_RE.fullmatch(name).groups()
        if key not in available.get(kind, {}):
            warnings.append(f"{name} has no value yet (config '{kind}' or --{'auth-account' if kind == 'authAccounts' else 'model'})")
    for t in schema.get("tables", []):
        tid = t["logicalId"]
        if (t.get("tableSettings") or {}).get("AUTO_RUN_ON", False) is not False:
            errors.append(f"{tid}: tableSettings.AUTO_RUN_ON must be false")
        names = {c["name"] for c in t.get("columns", [])} | SYSTEM_FIELD_NAMES
        for c in t.get("columns", []):
            ts = c.get("typeSettings") or {}
            for ref in NAMED_REF_RE.findall(json.dumps(ts)):
                if ref not in names:
                    errors.append(f"{tid}.{c['name']}: references unknown column {{{{@{ref}}}}}")
            for sd in c.get("sourceDetails") or []:
                sts = sd.get("typeSettings") or {}
                dsl = (sts.get("inputs") or {}).get("dslQuery")
                if dsl is not None and not re.search(r"\blimit\s+\d+", dsl, re.I):
                    errors.append(f"{tid}.{c['name']}: search source has no 'limit N' in its query")
                if sts.get("disableTriggerOnCreate") is not True or sts.get("disableTriggerOnUpdate") is not True:
                    errors.append(f"{tid}.{c['name']}: source must set disableTriggerOnCreate/Update true")
            if c.get("type") == "action":
                key = ts.get("actionKey")
                if key not in FREE_ACTION_KEYS and not ts.get("conditionalRunFormulaText"):
                    warnings.append(f"{tid}.{c['name']}: paid column without a run condition "
                                    "(fine only for the first qualification step)")
                for b in ts.get("inputsBinding") or []:
                    if b.get("name") == "prompt" and isinstance(b.get("formulaText"), str) \
                            and not _quotes_balanced(b["formulaText"]):
                        errors.append(f"{tid}.{c['name']}: prompt has an unescaped double quote")
        views = t.get("views") or []
        for v in views:
            for ref in NAMED_REF_RE.findall(json.dumps(v)):
                if ref not in names:
                    errors.append(f"{tid} view {v.get('name')}: references unknown column {{{{@{ref}}}}}")
        demo = [v for v in views if v.get("isAcceptedDemoView")]
        if not any(v.get("logicalId") == "default_view" for v in views):
            errors.append(f"{tid}: declare the default view with logicalId 'default_view'")
        if len(demo) != 1 or demo[0].get("logicalId") != "default_view":
            warnings.append(f"{tid}: mark exactly the default_view as isAcceptedDemoView")
    return errors, warnings


def dry_run(schema_path: Path, available: dict[str, dict]) -> dict:
    schema = json.loads(schema_path.read_text())
    errors, warnings = lint(schema, available)
    cols = [c for t in schema["tables"] for c in t.get("columns", [])]
    return {
        "status": "DRY_RUN" if not errors else "DRY_RUN_FAILED",
        "schema": str(schema_path),
        "workbook": schema["flow"]["workbook"]["create"]["name"],
        "tables": [t["name"] for t in schema["tables"]],
        "columnCount": len(cols),
        "actionCount": sum(1 for c in cols if c.get("type") == "action"),
        "sourceCount": sum(len(c.get("sourceDetails", [])) for c in cols if c.get("type") == "source"),
        "autoRun": schema["flow"]["workbook"]["create"]["settings"]["isAutoRun"],
        "errors": errors,
        "warnings": warnings,
    }


# ── Build ─────────────────────────────────────────────────────────────────────

class StageTimer:
    def __init__(self, stages: list[dict], name: str):
        self.stages, self.name = stages, name

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stages.append({"name": self.name, "seconds": round(time.perf_counter() - self.started, 3),
                            "status": "FAILED" if exc else "PASS"})


def resume_state(workbook_id, table_ids: dict, schema: dict, bindings: dict) -> dict:
    views = {}
    for t in schema.get("tables", []):
        got = {v["logicalId"]: bindings[k] for v in t.get("views", [])
               if (k := f"${{tables.{t['logicalId']}.views.{v['logicalId']}.id}}") in bindings}
        if got:
            views[t["logicalId"]] = got
    return {"workbookId": workbook_id, "tableIds": dict(table_ids), "viewIds": views}


def build(schema_path: Path, settings: dict, resume_workbook_id: str | None = None,
          resume_table_ids: dict[str, str] | None = None, resume_view_ids: dict | None = None,
          repair_columns: dict[str, list[str]] | None = None, client: FlowClient | None = None) -> dict:
    schema = json.loads(schema_path.read_text())
    errors, _ = lint(schema, settings)
    missing = sorted({m.group(0) for m in BINDING_RE.finditer(json.dumps(schema))
                      if m.group(2) not in settings.get(m.group(1), {})})
    if errors or missing:
        return {"status": "REFUSED", "errors": errors, "missingBindings": missing}
    if (resume_table_ids or resume_view_ids) and not resume_workbook_id:
        return {"status": "REFUSED", "errors": ["resume ids need --resume-workbook"]}

    stages: list[dict] = []
    table_ids = dict(resume_table_ids or {})
    workbook_id = None
    bindings = {"${workspace.id}": str(settings["workspaceId"])}
    bindings.update({f"${{bindings.authAccounts.{k}}}": v for k, v in settings["authAccounts"].items()})
    bindings.update({f"${{bindings.models.{k}}}": v for k, v in settings["models"].items()})
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    client = client or FlowClient(settings["workspaceId"])
    tables_by_id = {t["logicalId"]: t for t in schema["tables"]}

    try:
        with StageTimer(stages, "create_or_resume_workbook"):
            workbook_id = resume_workbook_id or client.create_workbook(schema["flow"]["workbook"]["create"]["name"])["id"]
            bindings["${workbook.id}"] = workbook_id
            client.approve_workbook(workbook_id)

        with StageTimer(stages, "create_and_name_tables"):
            for bp in schema["tables"]:
                lid = bp["logicalId"]
                if table_ids.get(lid):
                    live = inner_table(client.get_table(table_ids[lid]))
                    if live.get("workbookId") != workbook_id:
                        raise RuntimeError(f"Resume table {table_ids[lid]} is outside {workbook_id}")
                    for vlid, vid in ((resume_view_ids or {}).get(lid) or {}).items():
                        if vid not in {v["id"] for v in live.get("views", [])}:
                            raise RuntimeError(f"Resume view {vid} is not in table {table_ids[lid]}")
                        bindings[f"${{tables.{lid}.views.{vlid}.id}}"] = vid
                else:
                    table_ids[lid] = client.create_blank_table(workbook_id)["id"]
                hold_table(client, table_ids[lid])
                updates = {"name": bp["name"]}
                if bp.get("description"):
                    updates["description"] = bp["description"]
                if bp.get("icon") is not None:
                    updates["icon"] = bp["icon"]
                client.update_table(table_ids[lid], updates)
            for bp in schema["tables"]:
                add_table_bindings(client, bp, table_ids[bp["logicalId"]], bindings)

        with StageTimer(stages, "repair_resumed_columns"):
            requested = {k: set(v) for k, v in (repair_columns or {}).items()}
            for bp in schema["tables"]:
                auto = resume_column_repairs(client, table_ids[bp["logicalId"]], bp.get("columns", []), bindings)
                if auto["actionRebuilds"]:
                    requested.setdefault(bp["logicalId"], set()).update(auto["actionRebuilds"])
            for lid, names in requested.items():
                remove_repair_columns(client, table_ids[lid], tables_by_id[lid], sorted(names))

        deferred: list[tuple[dict, dict]] = []
        for lid in schema["flow"]["buildOrder"]:
            bp = tables_by_id[lid]
            first = []
            for col in bp["columns"]:
                (deferred.append((bp, col)) if col.get("deferUntil") else first.append(col))
            with StageTimer(stages, f"import_{lid}"):
                import_columns(client, table_ids[lid], first, bindings)
                add_table_bindings(client, bp, table_ids[lid], bindings)

        with StageTimer(stages, "complete_cross_table_wiring"):
            for bp, col in deferred:
                import_columns(client, table_ids[bp["logicalId"]], [col], bindings)
                add_table_bindings(client, bp, table_ids[bp["logicalId"]], bindings)

        removed = {}
        with StageTimer(stages, "apply_table_settings_and_views"):
            for bp in schema["tables"]:
                tid = table_ids[bp["logicalId"]]
                removed[bp["logicalId"]] = remove_blank_template_fields(client, tid, bp)
                add_table_bindings(client, bp, tid, bindings)
                update_table_settings(client, tid, bp, bindings)
                update_views(client, tid, bp, bindings)

        with StageTimer(stages, "reconcile_sources"):
            for bp in schema["tables"]:
                reconcile_sources(client, table_ids[bp["logicalId"]], bp, bindings)

        with StageTimer(stages, "readback_verification"):
            verification = verify_live_flow(client, schema, table_ids, workbook_id, bindings)

        folder = {"requested": settings.get("folderId"), "moved": False}
        if settings.get("folderId"):
            try:
                client.move_workbook(workbook_id, settings["folderId"])
                folder["moved"] = client.get_workbook(workbook_id).get("parentFolderId") == settings["folderId"]
            except Exception as e:  # filing is useful, never worth failing the import over
                folder["error"] = str(e)[:200]

        return {
            "status": "IMPORTED_HELD", "schema": str(schema_path), "workspaceId": settings["workspaceId"],
            "workbookId": workbook_id, "workbookUrl": client.workbook_url(workbook_id), "folder": folder,
            "startedAt": started_at.isoformat(), "finishedAt": datetime.now(timezone.utc).isoformat(),
            "liveImportSeconds": round(time.perf_counter() - t0, 3), "stages": stages,
            "removedTemplateFields": removed, "verification": verification,
            "resumeState": resume_state(workbook_id, table_ids, schema, bindings),
            "activation": {"autoRun": False, "recordsRun": 0, "sourcesRun": 0},
        }
    except Exception as exc:
        return {
            "status": "FAILED_PARTIAL_IMPORT", "schema": str(schema_path), "workspaceId": settings["workspaceId"],
            "workbookId": workbook_id, "tableIds": table_ids,
            "resumeState": resume_state(workbook_id, table_ids, schema, bindings),
            "startedAt": started_at.isoformat(), "finishedAt": datetime.now(timezone.utc).isoformat(),
            "stages": stages, "error": f"{type(exc).__name__}: {exc}",
        }


def add_settings_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="path to rex-config.json (default: tools/rex/rex-config.json)")
    p.add_argument("--workspace", type=int, help="Clay workspace id (overrides config)")
    p.add_argument("--folder", help="Clay folder id to file the workbook in (overrides config)")
    p.add_argument("--auth-account", action="append", metavar="NAME=AA_ID",
                   help="bind ${bindings.authAccounts.NAME} (repeatable)")
    p.add_argument("--model", action="append", metavar="NAME=MODEL",
                   help="bind ${bindings.models.NAME} (repeatable)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--resume-workbook")
    p.add_argument("--resume-table-ids-json", help='{"companies": "t_..."} from a failed receipt')
    p.add_argument("--resume-view-ids-json", help='{"companies": {"default_view": "gv_..."}}')
    p.add_argument("--repair-columns-json", help='{"companies": ["Column name"]} to rebuild on resume')
    add_settings_args(p)
    a = p.parse_args()
    settings = resolve_settings(a, load_config(a.config))
    if a.dry_run:
        result = dry_run(a.schema, settings)
    else:
        loads = lambda s: json.loads(s) if s else None  # noqa: E731
        result = build(a.schema, settings, a.resume_workbook, loads(a.resume_table_ids_json),
                       loads(a.resume_view_ids_json), loads(a.repair_columns_json))
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if a.receipt:
        a.receipt.parent.mkdir(parents=True, exist_ok=True)
        a.receipt.write_text(rendered + "\n")
    return 0 if result["status"] in {"DRY_RUN", "IMPORTED_HELD"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
