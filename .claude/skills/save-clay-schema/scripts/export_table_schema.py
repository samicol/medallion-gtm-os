#!/usr/bin/env python3
"""Export one live Clay workbook as a portable table JSON (flow blueprint). Read-only.

The export is the table as it is in Clay now, including every manual edit made
after import. It contains no rows or cell values. Live ids are replaced with
placeholders (${workbook.id}, ${tables.<t>.fields.<slug>.id}, ...) and auth
accounts with ${bindings.authAccounts.<name>}, named after rex-config.json's
authAccounts where the id matches and auth_1, auth_2, ... otherwise. The output is
the format design-clay-table-json writes and import-clay-table imports, and it is
dry-run re-imported before it is written.

Example:
  python3 .claude/skills/save-clay-schema/scripts/export_table_schema.py \
    --slug us-independent-breweries --name "US independent breweries" \
    --pattern account-first --workbook wb_x \
    --table companies:t_a:gv_demo --table people:t_b:gv_demo \
    --out tools/rex/registry/schemas/us-independent-breweries.json
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Rex (clay_client.py, clay_flow.py, rex-config.json) lives in tools/rex/ at the starter-kit root:
# scripts/ -> <skill>/ -> skills/ -> .claude/ -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[4] / "tools" / "rex"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "import-clay-table" / "scripts"))

from clay_flow import FlowClient, load_config, resolve_settings  # noqa: E402
import import_flow  # noqa: E402

# Row-derived state Clay keeps on a source; never part of a reusable schema.
TRANSIENT_SOURCE_KEYS = {"previous_entities_bitmap", "attribution_record_ids_by_clay_company_id", "hasEvaluatedInputs"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unnamed"


def replace_ids(value: Any, id_bindings: dict[str, str]) -> Any:
    if isinstance(value, str):
        for live_id, binding in sorted(id_bindings.items(), key=lambda x: -len(x[0])):
            value = value.replace(live_id, binding)
        return value
    if isinstance(value, list):
        return [replace_ids(v, id_bindings) for v in value]
    if isinstance(value, dict):
        return {replace_ids(k, id_bindings): replace_ids(v, id_bindings) for k, v in value.items()}
    return value


# Clay auth account ids, wherever they appear (key values, formula text, nested settings).
AUTH_ID = re.compile(r"\baa_[A-Za-z0-9]+")


def collect_auth_ids(value: Any, found: list[str]) -> None:
    """Append every auth account id in value to found, in first-seen order."""
    if isinstance(value, str):
        for match in AUTH_ID.findall(value):
            if match not in found:
                found.append(match)
    elif isinstance(value, list):
        for v in value:
            collect_auth_ids(v, found)
    elif isinstance(value, dict):
        for k, v in value.items():
            collect_auth_ids(k, found)
            if k == "authAccountId" and isinstance(v, str) and v.startswith("aa_"):
                if v not in found:
                    found.append(v)  # the whole value, even if it has characters the pattern stops at
                continue
            collect_auth_ids(v, found)


def auth_account_bindings(auth_ids: list[str], auth_names: dict[str, str]) -> tuple[dict[str, dict], dict[str, str]]:
    """Name each auth account: the rex-config.json name when the id matches, else auth_1, auth_2, ...

    Returns (requiredBindings.authAccounts, {live id: placeholder}). The generated names never
    contain the live id, so stripping origins removes every trace of it.
    """
    bindings: dict[str, dict] = {}
    replacements: dict[str, str] = {}
    unmatched = 0
    for live_id in auth_ids:
        name = auth_names.get(live_id)
        if not name:
            unmatched += 1
            name = f"auth_{unmatched}"
            while name in bindings or name in auth_names.values():
                unmatched += 1
                name = f"auth_{unmatched}"
        placeholder = "${bindings.authAccounts." + name + "}"
        bindings.setdefault(name, {
            "placeholder": placeholder, "originId": live_id,
            "resolution": "Map to an auth account in the destination workspace (rex-config.json authAccounts).",
        })
        replacements[live_id] = placeholder
    return bindings, replacements


def sanitize(value: Any) -> Any:
    """Drop row-derived source state Clay keeps on a source."""
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if not isinstance(value, dict):
        return value
    return {key: sanitize(item) for key, item in value.items() if key not in TRANSIENT_SOURCE_KEYS}


def view_blueprint(view: dict, field_names: dict[str, str], demo_view_id: str) -> dict:
    """A view in portable form. Fields are listed in on-screen order, which the importer re-applies."""
    ordered = sorted(((fid, s) for fid, s in (view.get("fields") or {}).items()
                      if fid not in {"f_created_at", "f_updated_at"}),
                     key=lambda x: str((x[1] or {}).get("order")))
    fields = {"{{@" + field_names.get(fid, fid) + "}}": s for fid, s in ordered}
    flt = copy.deepcopy(view.get("filter"))
    if isinstance(flt, dict):
        for item in flt.get("items") or []:
            if item.get("fieldId") in field_names:
                item["field"] = "{{@" + field_names[item.pop("fieldId")] + "}}"
    is_demo = view.get("id") == demo_view_id
    return {
        "logicalId": "default_view" if is_demo else slug(view.get("name") or "view"),
        "name": view.get("name"), "description": view.get("description"),
        "isAcceptedDemoView": is_demo, "fields": fields, "filter": flt, "sort": view.get("sort"),
        "limit": view.get("limit"), "offset": view.get("offset"), "typeSettings": view.get("typeSettings") or {},
        "origin": {"viewId": view.get("id")},
    }


def export_flow(clay: FlowClient, definition: dict, auth_names: dict[str, str]) -> dict:
    raw_tables, portable = {}, {}
    id_bindings = {definition["workbookId"]: "${workbook.id}"}
    for td in definition["tables"]:
        lid = td["logicalId"]
        raw = clay.get_table(td["tableId"])
        table = raw.get("table", raw)
        raw_tables[lid] = table
        portable[lid] = clay.export_schema(td["tableId"])
        id_bindings[table["id"]] = "${tables." + lid + ".id}"
        for f in table.get("fields") or []:
            if f.get("id") and f.get("name"):
                id_bindings[f["id"]] = "${tables." + lid + ".fields." + slug(f["name"]) + ".id}"
            for sid in (f.get("typeSettings") or {}).get("sourceIds") or []:
                id_bindings[sid] = "${tables." + lid + ".sources." + slug(f.get("name") or sid) + ".id}"
        for v in table.get("views") or []:
            vslug = "default_view" if v["id"] == td["demoViewId"] else slug(v.get("name") or v["id"])
            id_bindings[v["id"]] = "${tables." + lid + ".views." + vslug + ".id}"

    auth_ids: list[str] = []
    for td in definition["tables"]:
        collect_auth_ids(portable[td["logicalId"]]["columns"], auth_ids)
        collect_auth_ids(raw_tables[td["logicalId"]].get("views") or [], auth_ids)
        collect_auth_ids(raw_tables[td["logicalId"]].get("tableSettings") or {}, auth_ids)
    auth_bindings, auth_replacements = auth_account_bindings(auth_ids, auth_names)
    id_bindings.update(auth_replacements)

    tables = []
    first = definition["tables"][0]["logicalId"]
    for td in definition["tables"]:
        lid = td["logicalId"]
        table = raw_tables[lid]
        names = {f["id"]: f["name"] for f in table.get("fields") or [] if f.get("id") and f.get("name")}
        p = portable[lid]
        columns = replace_ids(sanitize(p["columns"]), id_bindings)
        views = []
        for v in table.get("views") or []:
            bp = view_blueprint(v, names, td["demoViewId"])
            origin = bp.pop("origin")
            bp = replace_ids(bp, id_bindings)
            bp["origin"] = origin
            views.append(bp)
        settings = replace_ids(copy.deepcopy(table.get("tableSettings") or {}), id_bindings)
        settings["AUTO_RUN_ON"] = False  # a saved schema must never arrive running
        tables.append({
            "logicalId": lid, "name": table.get("name"), "description": table.get("description"),
            "icon": table.get("icon"), "tableSettings": settings,
            "buildAfter": [] if lid == first else [first], "columns": columns, "views": views,
            "origin": {"tableId": table.get("id"), "demoViewId": td["demoViewId"]},
        })
    return {
        "$schema": "../../../../.claude/skills/design-clay-table-json/references/flow-blueprint.schema.json",
        "schemaVersion": "rex.clay.flow/v1",
        "kind": "approved-live-export",
        "exportedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dataPolicy": "Configuration only. No Clay rows or cell values are exported.",
        "flow": {
            "slug": definition["slug"], "name": definition["name"], "pattern": definition["pattern"],
            "workspace": {"originId": str(clay.workspace_id), "binding": "${workspace.id}"},
            "workbook": {"originId": definition["workbookId"], "binding": "${workbook.id}",
                         "create": {"name": definition["name"], "settings": {"isAutoRun": False}}},
            "buildOrder": [t["logicalId"] for t in definition["tables"]],
        },
        "requiredBindings": {"workspace": {"placeholder": "${workspace.id}", "originId": str(clay.workspace_id)},
                             "authAccounts": auth_bindings},
        "tables": tables,
    }


def strip_origins(value: Any) -> Any:
    """Remove workspace, workbook, table, view and account ids of the source workspace."""
    if isinstance(value, dict):
        return {k: strip_origins(v) for k, v in value.items() if k not in {"origin", "originId"}}
    if isinstance(value, list):
        return [strip_origins(v) for v in value]
    return value


def build_export(clay: Any, definition: dict, auth_names: dict[str, str], keep_origin: bool = False) -> dict:
    """The portable flow. Without keep_origin, no source workspace, workbook, table, view or
    auth account id is left in it."""
    flow = export_flow(clay, definition, auth_names)
    if keep_origin:
        return flow
    flow = strip_origins(flow)
    leftover = AUTH_ID.findall(json.dumps(flow))
    if leftover:
        raise RuntimeError(f"Export still contains {len(leftover)} auth account id(s); refusing to write it.")
    return flow


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--pattern", required=True, help="people-first, account-first or signal-first")
    p.add_argument("--workbook", required=True)
    p.add_argument("--table", action="append", required=True, help="logicalId:tableId[:demoViewId], in build order")
    p.add_argument("--out", required=True)
    p.add_argument("--keep-origin", action="store_true",
                   help="keep the source workspace/workbook/table/view/account ids (private use only; never commit to a public repo)")
    p.add_argument("--config")
    p.add_argument("--workspace", type=int)
    a = p.parse_args()
    cfg = load_config(a.config)
    settings = resolve_settings(a, cfg)
    clay = FlowClient(settings["workspaceId"])
    auth_names = {v: k for k, v in (cfg.get("authAccounts") or {}).items()}

    tables = []
    for spec in a.table:
        parts = spec.split(":")
        lid, tid = parts[0], parts[1]
        raw = clay.get_table(tid)
        t = raw.get("table", raw)
        if t.get("workbookId") != a.workbook:
            sys.exit(f"Table {tid} is not in workbook {a.workbook}")
        view = parts[2] if len(parts) > 2 and parts[2] else t["firstViewId"]
        tables.append({"logicalId": lid, "tableId": tid, "demoViewId": view})

    flow = build_export(clay, {"slug": a.slug, "name": a.name, "pattern": a.pattern,
                               "workbookId": a.workbook, "tables": tables}, auth_names, a.keep_origin)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(flow, indent=2, ensure_ascii=False) + "\n")
    check = import_flow.dry_run(out, {"authAccounts": {k: "x" for k in flow["requiredBindings"]["authAccounts"]},
                                      "models": {}})
    print(json.dumps({"out": str(out), "tables": [t["name"] for t in flow["tables"]],
                      "columns": sum(len(t["columns"]) for t in flow["tables"]),
                      "reimportDryRun": check["status"], "errors": check["errors"],
                      "warnings": check["warnings"]}, indent=1))
    return 0 if check["status"] == "DRY_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
