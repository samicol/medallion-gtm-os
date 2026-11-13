#!/usr/bin/env python3
"""Step 15 - append a results block to the deliverability sheet.

Results go into a new BLOCK appended below the previous round in the SAME tab,
never a new tab: title row, blank row, header row, one row per pool.

Before writing, read the previous block and mirror its formatting cell for cell.
That is the only way rounds stay consistent as the sheet grows.
`--peek` dumps the previous block's colors and structure so you can compare.

Auth is a short-lived OAuth access token in GOOGLE_ACCESS_TOKEN with the
spreadsheets scope (e.g. `gcloud auth print-access-token`). Stdlib only.

    python scripts/8_write_sheet.py --peek     # inspect the previous block
    python scripts/8_write_sheet.py            # dry run, prints the rows
    python scripts/8_write_sheet.py --write
"""
import sys, os, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import _request, env, load_config, die, confirm_flag, ROOT  # noqa: E402

API = "https://sheets.googleapis.com/v4/spreadsheets"
HEADERS = ["Date", "Bison C#", "Segment", "Inboxes", "Seeds", "MR public_id", "MR tag",
           "Seeds scanned", "Google Workspace /8 (work)", "Gmail Personal /6",
           "Office 365 /8 (work)", "Outlook Personal /6", "Work Inbox /16",
           "Overall Inbox /28", "Score", "Verdict"]
SLATE = {"red": 0.17, "green": 0.24, "blue": 0.31}
ZEBRA = {"red": 0.96, "green": 0.97, "blue": 0.98}
WHITE = {"red": 1, "green": 1, "blue": 1}
OUTCOME = {"KILL": {"red": 0.96, "green": 0.8, "blue": 0.8},
           "MARGINAL": {"red": 1, "green": 0.89, "blue": 0.6},
           "KEEP": {"red": 0.85, "green": 0.92, "blue": 0.83},
           "NO DATA": ZEBRA}


def sheets(method, path, body=None):
    token = env("GOOGLE_ACCESS_TOKEN")
    status, payload = _request(API + path, method,
                               {"Authorization": f"Bearer {token}",
                                "Content-Type": "application/json"}, body)
    if status != 200:
        die(f"Sheets {method} {path.split('?')[0]} failed ({status}): {payload.get('__error')}")
    return payload


def peek(cfg):
    """Print the previous block so the new one can mirror it."""
    sheet = cfg["sheet"]
    rng = f"{sheet['tab']}!A1:P{max(1, sheet['start_row'] - 1)}"
    fields = ("sheets(properties(sheetId,title),data(rowData(values("
              "formattedValue,userEnteredFormat(backgroundColor,textFormat(bold,foregroundColor)))))))")
    q = f"/{sheet['spreadsheet_id']}?ranges={rng.replace(' ', '%20').replace('!', '%21')}&includeGridData=true&fields={fields}"
    data = sheets("GET", q)
    for s in data.get("sheets", []):
        print("sheetId:", s["properties"]["sheetId"], "title:", s["properties"]["title"])
        for i, row in enumerate((s.get("data") or [{}])[0].get("rowData", []), start=1):
            cells = row.get("values") or []
            vals = [c.get("formattedValue", "") for c in cells[:4]]
            fmt = (cells[0].get("userEnteredFormat") or {}) if cells else {}
            bg = fmt.get("backgroundColor")
            bold = (fmt.get("textFormat") or {}).get("bold")
            if any(vals) or bg:
                print(f"  row {i:>3}  bold={bold}  bg={bg}  {vals}")


def build_rows(cfg, results):
    date = datetime.date.today().isoformat()
    title = (f"{cfg['sheet'].get('round_label', 'Round')} - {date} "
             f"Bison to MailReach full-campaign protocol")
    rows = [[title] + [""] * 15, [""] * 16, list(HEADERS)]
    host = env("EMAILBISON_BASE_URL").rstrip("/").removesuffix("/api")
    for r in results:
        label = f"C{r['campaign_id']}: {r['pool']}"
        rows.append([
            date,
            f'=HYPERLINK("{host}/campaigns/{r["uuid"]}/leads","{label}")',
            f"{r['pool']} - {r['auth']}",
            r["inboxes"], r["seeds"],
            f'=HYPERLINK("https://spamchecker.mailreach.co/tests/{r["public_id"]}","{r["public_id"]}")',
            r["tag"], f"{r['scanned']}/{r['seeds']}",
            r["gw"], r["gmail"], r["m365"], r["outlook"],
            r["work"], r["overall"],
            f"{r['score']} (B2B {r['btob_score']})",
            f"{r['verdict']} - {r['rationale']}",
        ])
    return rows


def format_requests(cfg, results, start_row):
    sid = cfg["sheet"]["sheet_id"]
    r0 = start_row - 1  # the API is 0-based

    def repeat(row_idx, c0, c1, fmt, fields):
        return {"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": row_idx, "endRowIndex": row_idx + 1,
                      "startColumnIndex": c0, "endColumnIndex": c1},
            "cell": {"userEnteredFormat": fmt}, "fields": fields}}

    reqs = [
        repeat(r0, 0, 16, {"textFormat": {"bold": True}}, "userEnteredFormat.textFormat.bold"),
        repeat(r0 + 2, 0, 16,
               {"backgroundColor": SLATE, "textFormat": {"bold": True, "foregroundColor": WHITE}},
               "userEnteredFormat(backgroundColor,textFormat)"),
    ]
    for i, r in enumerate(results):
        row = r0 + 3 + i
        reqs.append(repeat(row, 0, 15, {"backgroundColor": ZEBRA if i % 2 == 0 else WHITE},
                           "userEnteredFormat.backgroundColor"))
        reqs.append(repeat(row, 15, 16,
                           {"backgroundColor": OUTCOME.get(r["verdict"], ZEBRA),
                            "wrapStrategy": "WRAP"},
                           "userEnteredFormat(backgroundColor,wrapStrategy)"))
    return reqs


def main():
    cfg = load_config()
    sheet = cfg["sheet"]
    if not sheet.get("spreadsheet_id"):
        die("config.json sheet.spreadsheet_id is empty.")

    if "--peek" in sys.argv:
        peek(cfg)
        return

    path = os.path.join(ROOT, "results.json")
    if not os.path.exists(path):
        die("results.json not found. Run 7_results.py first.")
    with open(path) as fh:
        results = json.load(fh)

    rows = build_rows(cfg, results)
    start = sheet["start_row"]
    print(f"block -> {sheet['tab']}!A{start}  ({len(rows)} rows, {len(results)} pools)")
    for i, row in enumerate(rows):
        print(f"  {start + i:>4}  {str(row[:3])[:110]}")
    print("\nRead the previous block first (--peek) and confirm this mirrors it.")
    if not confirm_flag("--write", "write this block"):
        return

    rng = f"{sheet['tab']}!A{start}"
    sheets("PUT",
           f"/{sheet['spreadsheet_id']}/values/{rng.replace(' ', '%20').replace('!', '%21')}"
           "?valueInputOption=USER_ENTERED",
           {"values": rows})
    sheets("POST", f"/{sheet['spreadsheet_id']}:batchUpdate",
           {"requests": format_requests(cfg, results, start)})
    print(f"\nwrote {len(rows)} rows and formatting at row {start}.")
    print("Read the block back and diff it against the previous round before "
          "calling it done: header color, zebra parity, both hyperlinks, "
          "Score format, Verdict colors.")


if __name__ == "__main__":
    main()
