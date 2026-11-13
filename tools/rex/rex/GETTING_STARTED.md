# Getting started with Rex

> **In this starter kit:** Rex lives in `tools/rex/` and its skills are already installed in the repository's `.claude/skills/`. Run Claude Code and the pipeline commands below from the **repository root**; run SDK snippets (`from clay_client import ClayClient`) from `tools/rex/`. Campaign folders go in `output/campaigns/<slug>/`, company context in `context/`. Where a command says `python3`, use `tools/rex/.venv/bin/python` if you installed the dependencies into the venv (section 2).

This guide takes you from a fresh clone to your first real campaign table in Clay, built by Claude Code and run on about ten rows for a dollar or two. It assumes you already know Clay: sources, AI columns, formulas, run conditions, views. It covers:

- What Rex gives you and what you have to bring.
- Installing Rex and connecting it to your Clay account.
- Configuring the campaign pipeline.
- A smoke test that spends nothing, or at most cents.
- Writing the campaign brief, running the first build, and saving the result.
- Plugging in your own skills, and fixing the usual problems.

> **IMPORTANT:** Rex is unofficial. It calls Clay's internal API with your browser session, is not affiliated with or supported by Clay, and can break when Clay changes that API.

---

## 1. What you get and what you bring

**Out of the box:**

- **The SDK** (`clay_client.py`): create tables and columns, run columns, read records, export and import table schemas. AI columns are safer to change here than by hand: `update_column()` merges your change into the live settings, and `clone_column()` copies a working AI column and swaps only the prompt.
- **Cost reports:** `clay.print_cost_report(table_id)` prints real spend per column and per row, in dollars and Clay credits, from the same cell data Clay bills from. Provider dollars are actual spend; the dollar value of Clay credits is an estimate at a fixed rate per credit. **ClayLens** (`claylens/`) shows the same numbers as a dashboard inside Clay. For a whole workspace over a month, `python3 clay_workspace_costs.py --workspace <workspace_id>` reports Clay credits by table, integration and day, and AI provider dollars by table, column and model (`workspace-cost-audit`).
- **Export:** `clay.export_tables([...], out_dir="./exports")` downloads several tables as CSV in one call.
- **Browser capture:** `clay_browser.py` records Clay's API traffic while you click, so you can find the inputs of an action Rex does not document yet.
- **Nine skills** in the repository's `.claude/skills/`: `build-clay`, `prompt-builder`, `campaign-contract`, `design-clay-table-json`, `import-clay-table`, `save-clay-schema`, `calculate-costs`, `workspace-cost-audit`, `export-tables`.

**You bring:**

- **A Clay account and its session cookie.** Rex needs no API key; it uses your logged-in session.
- **For the campaign pipeline, a `rex-config.json`:** your workspace id, the auth account id of the AI provider your columns run on, the model ids, and a budget cap.
- **The campaign inputs:** a one-sentence ICP, about 30 best-fit companies, 10 to 20 companies that look similar but are wrong (your controls), the persona, and the offer.
- **Your copy guidance.** Rex writes opening lines from what the table found about each company. The offer, what the copy may claim and the voice come from you.
- **Everything after the table.** Rex does not send, find or validate emails, sequence, or push to a CRM. It stops at a table you have read and approved.

---

## 2. Install and connect

1. **Clone the repo and install the dependencies.** You need Python 3.9 or newer (`clay_client.py` uses `list[dict]` annotations, which 3.8 rejects). Chromium is needed only for `clay_browser.py`.

   ```bash
   git clone <starter-kit-repo-url> gtm-starter-kit && cd gtm-starter-kit/tools/rex
   python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m playwright install chromium   # only for clay_browser.py
   ```

2. **Save your session cookie.** Follow `COOKIE_SETUP.md`: copy the `claysession` cookie from Chrome DevTools into `tools/rex/clay-session.json` next to `clay_client.py`. The file is gitignored. The pipeline scripts also accept the cookie in the `CLAY_SESSION` environment variable; the SDK on its own reads only the file.

3. **The skills are already installed.** They live in `.claude/skills/` at the repository root, so run Claude Code from there. The pipeline scripts inside them (`.claude/skills/import-clay-table/scripts/`, `.claude/skills/save-clay-schema/scripts/`) find `clay_flow.py`, `clay_client.py` and `rex-config.json` by walking up to the repository root and into `tools/rex/`, so keep that layout. Add your own skills as more folders in `.claude/skills/` (section 8).

4. **Check the connection with a read.** This changes nothing in Clay.

   ```python
   from clay_client import ClayClient
   clay = ClayClient()        # prints: [clay] logged in as <your email> | workspace <id>
   ws = clay.get("/my-workspaces")
   for w in (ws.get("results", ws) if isinstance(ws, dict) else ws):
       print(w["id"], w.get("name"))
   ```

   If you see your email and your workspaces, the cookie works.

> **IMPORTANT:** `ClayClient()` without arguments picks the first workspace your session can see. If you belong to more than one, always pass it: `ClayClient(workspace_id=<workspace_id>)`. The pipeline refuses to run without an explicit workspace for the same reason.

---

## 3. Configure the pipeline

The four pipeline skills read their settings from `rex-config.json`. Copy the example (the real file is gitignored) and fill in each value:

```bash
cp rex-config.example.json rex-config.json
```

```json
{
  "workspaceId": <workspace_id>,
  "folderId": "",
  "authAccounts": { "llm": "<auth_account_id>" },
  "models": { "default": "<model_id>" },
  "budgetUsd": 2
}
```

- **`workspaceId`** (a number, no quotes). Open any table in the workspace you want to build in and read it from the URL: `app.clay.com/workspaces/<workspace_id>/...`. The scripts check that your session can open it and stop if not.
- **`folderId`** (optional). A Clay folder id to file new workbooks in. Leave it empty to file them at the top level.
- **`authAccounts.llm`**. The id of the AI provider account your AI columns bill to. List your connected accounts and pick the one you use for AI columns:

  ```python
  clay = ClayClient(workspace_id=<workspace_id>)
  for a in clay.list_auth_accounts():
      print(a)
  ```

  If you already have a working AI column, the surest way is to read the account it uses (next step prints it).
- **`models.default`**. The exact model id your workspace offers. Do not type it from memory or from a list in the docs. Copy it from an AI column that already runs:

  ```python
  t = clay.get_table("<table_id>")
  for f in t.get("table", t).get("fields", []):
      ts = f.get("typeSettings") or {}
      model = next((b.get("formulaText") for b in ts.get("inputsBinding", []) if b.get("name") == "model"), None)
      if model:
          print(f["name"], f["id"], model, ts.get("authAccountId"))
  ```

  Why this matters: Clay accepts a column with a mistyped or retired model id, and its cells then stay queued forever with no error.
- **`budgetUsd`**. The spend cap for the `run` step. Start at 1 or 2 for a first build. Every value can also be overridden per command with `--workspace`, `--folder`, `--auth-account llm=<auth_account_id>`, `--model default=<model_id>`, `--budget` or `--config <path>`.

---

## 4. Smoke test (about ten minutes)

Do this once before your first campaign. Steps 1 to 4 spend nothing.

1. **Dry-run the example table offline.** `.claude/skills/design-clay-table-json/references/example.flow.json` is a small fictional campaign that was proven live. The dry run reads the file and your config and never calls Clay:

   ```bash
   python3 .claude/skills/import-clay-table/scripts/import_flow.py \
     --schema .claude/skills/design-clay-table-json/references/example.flow.json --dry-run
   ```

   Expect `"status": "DRY_RUN"` and `"autoRun": false`. If your config is filled in, the warnings about `${bindings.authAccounts.llm}` and `${bindings.models.default}` having no value are gone. The one left, a paid column without a run condition, is expected: it is the first qualification step.

2. **Read the cost of a table you already ran.** Pick any table with AI columns that have run. It is a read, and it shows you what the cost report looks like before you rely on it:

   ```python
   summary = clay.print_cost_report("<table_id>")
   ```

   If it reports uncosted cells, those cells ran without cost data. Treat that total as a floor until you know why.

3. **Create a test table.** New tables are created with auto-run off, so nothing runs when you add columns:

   ```python
   table = clay.create_table("Rex smoke test")
   print(table["id"], table["workbookId"])
   ```

4. **Import the example held.** This creates a real workbook with the example's source, columns and demo view, and runs nothing:

   ```bash
   S=.claude/skills/import-clay-table/scripts/clay_table.py
   python3 -u $S import .claude/skills/design-clay-table-json/references/example.flow.json \
     --receipt output/campaigns/example/import-receipt.json
   ```

   Expect `IMPORTED_HELD` and a Clay link per table. Open it and check auto-run is off and the table has zero rows.

5. **Optional: run the example on ten companies.** This rehearses section 6 on a campaign that is known to work, and it spends real money on the AI cells. Run `source` with `--limit 10`, `one-row`, then `run` with `--budget 1`, and check the result with `spend`. Delete the smoke-test workbooks in Clay when you are done.

---

## 5. Write your campaign brief

The pipeline starts from decisions only you can make. `campaign-contract` will stop and ask rather than invent them, so write them down first. Keep one folder per campaign in `output/campaigns/<slug>/`, and put this in `brief.md`:

```markdown
# <campaign name>

ICP: <one sentence describing the business you want in the list, not your product>
Best-fit examples: <about 30 real companies that clearly match, each with its website>
Controls: <10 to 20 look-alikes that must be rejected: brokers, agencies, vendors to the industry>
Persona: <titles who own the problem, titles to exclude, people per company>
Signal: <the event that makes now a good time, if there is one; "none" is a valid answer>
Offer: <what you sell, and the proof you can stand behind>
Copy may claim: <facts the copy may use> / may not claim: <what it must never say>
Voice: <a few rules and two or three opening lines you have actually sent>
Rows needed: <how many finished rows the demo view should show; 10 for a first build>
```

**Why the controls matter.** A search that returns your best-fit companies can still be full of look-alikes. You use the best-fit list to check the source misses nothing and the controls to check the qualification column rejects what it should.

Then ask Claude Code to write the contract from the brief (for example "write the campaign contract for `output/campaigns/<slug>/brief.md`"). `campaign-contract` writes `output/campaigns/<slug>/contract.md`: one section per Clay object in build order, every prompt verbatim with its output schema, the model, every run condition, and the demo view. Read it as if you were going to build it by hand in Clay. Anything you would have to guess means the brief is missing a decision.

---

## 6. First build

Run the first build on about ten finished rows with a cap of $1 to $2. The point is to prove the method on a few rows you can read in full.

1. **Design the table JSON.** Ask Claude to run `design-clay-table-json` on the contract. It writes `output/campaigns/<slug>/table.flow.json`, starting from the closest approved schema in `tools/rex/registry/INDEX.md` (or the example while the registry is empty). Before writing the source it should preview the search for free in Clay and read the first 20 names. Check that your best-fit companies show up, then dry-run the file as in section 4.

2. **Import held.** Nothing runs; the importer creates the workbook and compares it with the JSON:

   ```bash
   python3 -u $S import output/campaigns/<slug>/table.flow.json --receipt output/campaigns/<slug>/import-receipt.json
   ```

3. **Pull a small source.** The row limit lives in the search query inside the JSON (`limit 10`), and `source` refuses a search without one:

   ```bash
   python3 -u $S source <table_id> --limit 10
   ```

   Open the table and read the names that arrived. If they are the wrong kind of company, stop and fix the source in the JSON. It is the cheapest fix now and the most expensive one after the AI columns ran.

4. **Prove every paid column on two rows.** Pick one row that should qualify and one that should be rejected. Do not just take the first row. Claude can read the record ids with `clay.list_records()`.

   ```bash
   python3 -u $S one-row <table_id> --record <record_id> --expect qualify
   python3 -u $S one-row <table_id> --record <record_id> --expect reject
   ```

   Read every printed value. The research should cite a real source about that company, the verdict should follow from it, and the rejected row should show `ERROR_RUN_CONDITION_NOT_MET` on the gated columns instead of a cost.

> **IMPORTANT:** A `SUCCESS` status or a full cell proves nothing on its own. A broken prompt and a good one look the same in the status bar. Only reading the answers tells them apart.

5. **Run the rest under the cap.** `run` projects the cost of the pending rows from the real per-row cost of your one-row proofs, and refuses to start if spent plus projected would exceed the budget. It checks once, before the run, and does not stop a run partway:

   ```bash
   python3 -u $S run <table_id> --budget 2 --spend-tables <table_id> [<second_table_id>]
   python3 -u $S spend <table_id>
   ```

   On a two-table build, run the company table fully before pulling the people source, because the people search reads the company verdicts.

6. **Read the demo view yourself.**

   ```bash
   python3 -u $S read <table_id> --view <demo_view_id> --limit 15
   ```

   Check the row count against the contract and `EMPTY_CELLS_IN_SAMPLE` (it should be 0). Then read each row as if the prospect were reading it over your shoulder. If a value is wrong, fix the JSON and re-import (or rebuild one column with `import_flow.py --resume-workbook ... --repair-columns-json ...`), then run `one-row` again. Do not patch the table by hand in Clay, or the saved schema will not match what actually ran.

---

## 7. Build your own registry

Every table you approve becomes the starting point for the next one. `tools/rex/registry/` ships empty.

1. **Save only what you approved.** Once you have read the demo view and are happy with it, ask Claude to run `save-clay-schema`. It exports the live workbook, including any edits made in Clay after import, and contains no rows:

   ```bash
   python3 .claude/skills/save-clay-schema/scripts/export_table_schema.py \
     --slug <slug> --name "<campaign in plain words>" \
     --pattern account-first --workbook <workbook_id> \
     --table companies:<table_id>:<demo_view_id> \
     --out tools/rex/registry/schemas/<slug>.json
   ```

   `--pattern` is `people-first`, `account-first` or `signal-first`. The script dry-runs the export through the importer before writing it, and the skill adds one row to `tools/rex/registry/INDEX.md`.

2. **Keep ids out unless the registry is private.** By default, workspace, workbook, table, view and account ids are replaced with placeholders. `--keep-origin` keeps them; use it only in a registry nobody else can read.

> **IMPORTANT:** Stripping ids does not strip the campaign. A saved schema still holds your prompts, filters and offer. Never commit client schemas to a public fork of Rex or of this starter kit. Keep your registry in a private repo.

The next `design-clay-table-json` run reads `tools/rex/registry/INDEX.md` and starts from the closest saved schema of the same motion. It learns the construction from it and takes no names, filters or prompt text.

---

## 8. Bring your own skills

Rex decides how the table is built. What the campaign says is yours, and that is where your own skills fit.

- **Copywriting and voice.** Keep your offer and voice in `context/messaging/` and the campaign folder (the `Offer`, `Copy may claim` and `Voice` lines of the brief, or a separate `voice.md` you hand over with it). `campaign-contract` turns them into the opening-line prompt, verbatim in the contract. If you have your own copywriting skill, use it to write that prompt's rules and examples, then give the result to `prompt-builder`.
- **ICP, persona and positioning work.** Anything that produces the brief in section 5 plugs in before `campaign-contract`. The contract skill needs only the decisions.
- **Where to put them.** Add your skills as normal folders in `.claude/skills/` next to the Rex skills, or in `~/.claude/skills/` to use them in every project. Claude Code loads them all.
- **Any AI column prompt goes through `prompt-builder`.** Whatever wrote the rules, `prompt-builder` turns them into a per-row prompt with real input bindings and a JSON output schema, and tests it on the exact model that will run it.

For a full production workbook (Companies, Find People plus a Claygent people search, one shared People table) or an audit of an existing one, use `build-clay` instead of the four-step pipeline.

---

## 9. Troubleshooting

- **401 errors, or `ClayClient()` fails at start.** The cookie expired; it lasts a few weeks. Repeat steps 2 to 4 of `COOKIE_SETUP.md`. Every call has a 30-second timeout, so an expired cookie fails fast instead of hanging.
- **`Workspace <id> is not visible to this Clay session`.** The `workspaceId` is wrong, or the cookie belongs to a different Clay login.
- **HTTP 400 when creating a Find People or Find Companies source.** The two need different settings (`hasEvaluatedInputs` among them). Use `create_find_companies_source()` and `create_find_people_source()`, never one body for both.
- **AI cells stay queued forever.** Almost always an unknown or mistyped model id. Copy the id from a working column (section 3), or build the column with `clone_column()` from one that runs, then test one row.
- **Spend you did not expect.** Check auto-run first. `create_table()` and the importer leave it off, but a workbook created in Clay's UI or with `auto_run=True` runs every paid column on every row as soon as the column is added. Find where the money went with `print_cost_report()` or ClayLens. If you do not know which table it was, run `python3 clay_workspace_costs.py --workspace <workspace_id>` first: it lists the month's credits and AI provider dollars by table.
- **An update wiped a column's model, schema or account.** Clay replaces a column's whole config on update. `update_column()` reads the live column and merges your change in; a raw `clay.patch()` or `update_column(..., replace=True)` does not. Rebuild the broken column with `clone_column()` from a working one.
- **`REFUSED: search source ... has no limit in its query`.** Add `limit <n>` to the source's search query in the JSON and re-import. Without it, a trigger imports every match.
- **`STOP: no row has a recorded cost yet`.** Run `one-row` first. `run` only projects from real cost.
- **`STOP: projected spend exceeds the budget`.** Lower the row count with `--records`, or agree a higher `--budget`.
- **An action Rex does not know.** Start `python clay_browser.py launch` (a visible browser; use `python clay_browser.py --headless launch` to hide it), do the action in Clay, and read its inputs with `python clay_browser.py requests --filter fields --last 5`.
