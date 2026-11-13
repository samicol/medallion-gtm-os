#!/usr/bin/env python3
"""Import, fill, prove, run and read back one Clay table built from a flow JSON.

A thin helper for the import-clay-table skill. It decides nothing about the
table: the JSON decides the columns, prompts and models. This script imports it
held (nothing runs), triggers sources with an explicit limit, runs every action
column on one chosen record, runs the rest only if the spend projected from the
real per-cell cost Clay recorded fits the budget (checked once, before the run),
and prints a view the way the viewer sees it.

Commands
  import   FLOW --receipt R          import held; file in the configured folder
  source   TABLE --limit N           trigger every source on TABLE (limit must be in the query), wait
  one-row  TABLE [--record R]        run each action column on one record, print every cell and its cost
  run      TABLE [--budget USD]      run action columns on the remaining rows if projected spend fits
  spend    TABLE [TABLE ...]         real spend so far: provider $ plus Clay credits
  read     TABLE [--view V]          print a view's visible columns, in view order, row by row

Settings come from rex-config.json (workspaceId, folderId, authAccounts, models,
budgetUsd) and can be overridden with --workspace, --folder, --auth-account,
--model and --budget. Auth is clay-session.json (see COOKIE_SETUP.md) or CLAY_SESSION.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Rex (clay_client.py, clay_flow.py, rex-config.json) lives in tools/rex/ at the starter-kit root:
# scripts/ -> <skill>/ -> skills/ -> .claude/ -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[4] / "tools" / "rex"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import clay_costs  # noqa: E402
from clay_flow import FlowClient, _sort_by_deps, load_config, resolve_settings  # noqa: E402
import import_flow  # noqa: E402

CREDIT_USD = clay_costs.PROVIDER_COSTS["_meta"]["clay_credit_usd"]


def full_value(cell: dict):
    if not isinstance(cell, dict):
        return None
    ext = cell.get("externalContent") or {}
    return ext.get("fullValue", cell.get("value"))


def status(cell: dict) -> str:
    return str(((cell or {}).get("metadata") or {}).get("status") or "")


def short(value, n=220) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[: n - 3] + "..."


def cell_spend(cell: dict, field: dict) -> dict:
    """Provider dollars and Clay credits one cell cost, from Rex's cost extractor.

    usd is an estimate: provider dollars plus credits converted at the fixed CREDIT_USD rate."""
    x = clay_costs.extract_cost_fields(cell, field_type="action",
                                       action_key=(field.get("typeSettings") or {}).get("actionKey"))
    credits = x.get("upfront_credit_total")
    if credits is None:
        credits = x.get("credits")
    provider = x.get("total_cost_usd") or 0.0
    credits = float(credits or 0.0)
    return {"providerUsd": provider, "credits": credits, "usd": provider + credits * CREDIT_USD,
            "uncosted": bool(x.get("uncosted"))}


def get_table(c: FlowClient, table_id: str) -> dict:
    d = c.get_table(table_id)
    t = d.get("table", d)
    ws = t.get("workspaceId")
    if ws is not None and int(ws) != int(c.workspace_id):
        sys.exit(f"REFUSED: table {table_id} is in workspace {ws}, not the configured {c.workspace_id}")
    return t


def approve(c: FlowClient, t: dict) -> None:
    c.approve_workbook(t["workbookId"])
    print(f"[workbook] {t['workbookId']} table '{t.get('name')}' -> {c.workbook_url(t['workbookId'], t['id'])}")


def action_fields(t: dict) -> list[dict]:
    """Action columns in dependency order, so a column never runs before its inputs."""
    actions = [f for f in t["fields"] if f["type"] == "action"]
    try:
        return _sort_by_deps(actions)
    except Exception:
        return actions


def unfiltered_view(t: dict) -> str:
    """A view that shows every row. The demo view is usually filtered to finished rows."""
    for v in t.get("views", []):
        if (v.get("typeSettings") or {}).get("preconfiguredType") == "all-rows":
            return v["id"]
    for v in t.get("views", []):
        if not (v.get("filter") or {}).get("items") and not (v.get("typeSettings") or {}).get("preconfiguredType"):
            return v["id"]
    sys.exit("No unfiltered view on this table; add an 'All rows' view in Clay or clear the default view filter.")


def all_record_ids(c: FlowClient, t: dict) -> list[str]:
    """Every row with data. Clay keeps one empty scaffold row on a new table; it is skipped
    so no paid column ever runs on a row with no input."""
    ids = c.get_record_ids(t["id"], unfiltered_view(t))
    inputs = [f["id"] for f in t["fields"] if f["type"] in ("source", "text", "url", "number")]
    if not ids or not inputs:
        return ids
    recs = c.get_records(t["id"], ids, inputs)
    return [r["id"] for r in recs
            if any((r.get("cells") or {}).get(fid, {}).get("value") not in (None, "", [], {}) for fid in inputs)]


def full_records(c: FlowClient, table_id: str, ids: list[str]) -> list[dict]:
    return [c.get_full_record(table_id, rid) for rid in ids]


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_import(a, c: FlowClient, settings: dict) -> None:
    r = import_flow.build(Path(a.flow), settings, client=c)
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n")
    keep = ("status", "workbookId", "workbookUrl", "folder", "error", "errors", "missingBindings")
    print(json.dumps({k: r[k] for k in keep if k in r}, indent=1))
    for lid, t in ((r.get("verification") or {}).get("tables") or {}).items():
        print(f"TABLE {lid} {t['id']} default view {t['defaultViewId']} {t['url']}")
    if r["status"] != "IMPORTED_HELD":
        sys.exit(1)


def cmd_source(a, c: FlowClient, settings: dict) -> None:
    t = get_table(c, a.table)
    approve(c, t)
    sources = [f for f in t["fields"] if f["type"] == "source"]
    if not sources:
        sys.exit("NO_SOURCE on this table")
    for f in sources:
        for sid in f["typeSettings"].get("sourceIds", []):
            src = c.get(f"/sources/{sid}")
            dsl = ((src.get("typeSettings") or {}).get("inputs") or {}).get("dslQuery")
            if dsl is not None:
                # Clay refuses a page size on search sources, and a trigger without a
                # limit imports every match. The limit must live in the query itself.
                if "limit" not in dsl.lower():
                    sys.exit(f"REFUSED: search source {sid} has no limit in its query; add 'limit {a.limit}' to the JSON")
                c.trigger_source(t["id"], sid)
            else:
                c.trigger_source(t["id"], sid, page_size=a.limit)
            run = c.wait_for_source_run(sid, timeout=600)
            print("SOURCE", f["name"], run.get("status"))
    print("ROWS", len(all_record_ids(c, t)))


def print_cells(rec: dict, fields: list[dict]) -> dict:
    total = {"usd": 0.0, "providerUsd": 0.0, "credits": 0.0}
    for f in fields:
        cell = (rec.get("cells") or {}).get(f["id"], {})
        s = cell_spend(cell, f)
        for k in total:
            total[k] += s[k]
        flag = " UNCOSTED" if s["uncosted"] else ""
        print(f"  {f['name']}: [{status(cell) or 'NOT RUN'}] ${s['usd']:.4f}{flag} {short(full_value(cell))}")
    return total


def cmd_one_row(a, c: FlowClient, settings: dict) -> None:
    t = get_table(c, a.table)
    approve(c, t)
    rid = a.record or all_record_ids(c, t)[0]
    fields = action_fields(t)
    for f in fields:
        try:
            c.run_and_wait(t["id"], [f["id"]], [rid], timeout=a.timeout, poll=4)
        except Exception as e:
            print("RUN_ERROR", f["name"], str(e)[:200])
    rec = c.get_full_record(t["id"], rid)
    print("RECORD", rid, f"({a.expect})" if a.expect else "")
    total = print_cells(rec, fields)
    for f in (x for x in t["fields"] if x["type"] == "formula"):
        print(f"  (formula) {f['name']}: {short(full_value((rec.get('cells') or {}).get(f['id'], {})), 160)}")
    print(json.dumps({"oneRowUsd": round(total["usd"], 4), "providerUsd": round(total["providerUsd"], 4),
                      "credits": round(total["credits"], 3)}))


def spend(c: FlowClient, table_ids: list[str]) -> dict:
    out = {"usd": 0.0, "providerUsd": 0.0, "credits": 0.0, "rows": 0, "rowsWithCost": 0, "uncostedCells": 0}
    for tid in table_ids:
        t = get_table(c, tid)
        fields = action_fields(t)
        for r in full_records(c, t["id"], all_record_ids(c, t)):
            row = 0.0
            for f in fields:
                s = cell_spend((r.get("cells") or {}).get(f["id"], {}), f)
                row += s["usd"]
                out["providerUsd"] += s["providerUsd"]
                out["credits"] += s["credits"]
                out["uncostedCells"] += s["uncosted"]
            out["usd"] += row
            out["rows"] += 1
            out["rowsWithCost"] += row > 0
    return out


def cmd_spend(a, c: FlowClient, settings: dict) -> None:
    s = spend(c, a.tables)
    print(json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}))


def cmd_run(a, c: FlowClient, settings: dict) -> None:
    budget = settings.get("budgetUsd")
    if budget is None:
        sys.exit("No budget. Pass --budget or set budgetUsd in rex-config.json.")
    t = get_table(c, a.table)
    approve(c, t)
    fields = action_fields(t)
    ids = a.records.split(",") if a.records else all_record_ids(c, t)
    recs = c.get_records(t["id"], ids, [f["id"] for f in fields])
    # A row is pending while any action cell has never run or ended in a plain error.
    pending = [r["id"] for r in recs
               if any(status((r.get("cells") or {}).get(f["id"], {})) in ("", "ERROR") for f in fields)]
    s = spend(c, a.spend_tables or [a.table])
    if not s["rowsWithCost"]:
        sys.exit("STOP: no row has a recorded cost yet. Run one-row first so the cap uses real cost.")
    per_row = s["usd"] / s["rowsWithCost"]
    projected = per_row * len(pending)
    print(json.dumps({"pendingRows": len(pending), "spentUsd": round(s["usd"], 4), "perRowUsd": round(per_row, 4),
                      "projectedUsd": round(projected, 4), "budgetUsd": budget,
                      "uncostedCells": s["uncostedCells"]}))
    if s["uncostedCells"]:
        print("WARNING: some cells ran without cost data; the projection may be low.")
    if s["usd"] + projected > budget:
        sys.exit("STOP: projected spend exceeds the budget. Lower the row count or agree a higher budget.")
    for f in fields:  # column by column so later columns see earlier results and run conditions
        for i in range(0, len(pending), 50):
            c.run_and_wait(t["id"], [f["id"]], pending[i:i + 50], timeout=900, poll=6)
        print("RAN", f["name"])
    after = spend(c, a.spend_tables or [a.table])
    print(json.dumps({"spentUsdAfter": round(after["usd"], 4), "rows": after["rows"]}))


def cmd_read(a, c: FlowClient, settings: dict) -> None:
    t = get_table(c, a.table)
    view = next((v for v in t["views"] if v["id"] == a.view), None) if a.view else \
        next((v for v in t["views"] if v["id"] == t.get("firstViewId")), t["views"][0])
    if view is None:
        sys.exit(f"View {a.view} is not on this table")
    names = {f["id"]: f["name"] for f in t["fields"]}
    vf = view.get("fields") or {}
    shown = sorted((fid for fid, s in vf.items() if (s or {}).get("isVisible", True) and fid in names
                    and fid not in ("f_created_at", "f_updated_at")), key=lambda fid: str(vf[fid].get("order")))
    all_ids = c.get_record_ids(t["id"], view["id"])
    print(f"VIEW '{view.get('name')}' {view['id']} ROWS {len(all_ids)}")
    print("COLUMNS", " > ".join(names[fid] for fid in shown))
    empty = 0
    for r in full_records(c, t["id"], all_ids[: a.limit]):
        print("---", r["id"])
        for fid in shown:
            v = full_value((r.get("cells") or {}).get(fid, {}))
            if v in (None, "", [], {}):
                empty += 1
            print(f"  {names[fid]}: {short(v, 160)}")
    print("EMPTY_CELLS_IN_SAMPLE", empty)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("import"); x.add_argument("flow"); x.add_argument("--receipt", required=True)
    x = s.add_parser("source"); x.add_argument("table"); x.add_argument("--limit", type=int, required=True)
    x = s.add_parser("one-row"); x.add_argument("table"); x.add_argument("--record")
    x.add_argument("--expect", choices=["qualify", "reject"], help="label for the record you picked")
    x.add_argument("--timeout", type=int, default=300)
    x = s.add_parser("run"); x.add_argument("table"); x.add_argument("--records")
    x.add_argument("--spend-tables", nargs="*", help="every table of this build, so the cap covers the whole build")
    x = s.add_parser("spend"); x.add_argument("tables", nargs="+")
    x = s.add_parser("read"); x.add_argument("table"); x.add_argument("--view"); x.add_argument("--limit", type=int, default=10)
    for sp in s.choices.values():
        import_flow.add_settings_args(sp)
        sp.add_argument("--budget", type=float, help="spend cap in USD (overrides config budgetUsd)")
    a = p.parse_args()
    settings = resolve_settings(a, load_config(a.config))
    c = FlowClient(settings["workspaceId"])
    {"import": cmd_import, "source": cmd_source, "one-row": cmd_one_row, "run": cmd_run,
     "spend": cmd_spend, "read": cmd_read}[a.cmd](a, c, settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
