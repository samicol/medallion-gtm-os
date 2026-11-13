# Rex

> **Unofficial. Not affiliated with or supported by Clay. May break without notice.**

Rex lets [Claude Code](https://docs.anthropic.com/en/docs/claude-code), or any other AI coding agent, work inside Clay. It calls Clay's internal API with your own browser session, so you do not need an API key. The agent can build tables, add and run columns, read the results and tell you what the work cost in dollars.

Rex is named after a dog.

> **About this copy.** This folder is Rex v2.1 by Leszek Lammel (MIT, see [LICENSE](LICENSE)), plus the additions listed under
> [Additions beyond upstream v2.1](#additions-beyond-upstream-v21), bundled into this GTM starter kit. The Rex skills live in the
> starter kit's [`.claude/skills/`](../../.claude/skills/) folder, not in a `skills/` folder here. Rex is unofficial: it is not
> affiliated with or supported by Clay, and Clay can change its internal API at any time.

---

**New here? Start with [GETTING_STARTED.md](GETTING_STARTED.md).** It takes you from a fresh clone to your first campaign table on about ten rows, and explains what Rex gives you out of the box and what you bring yourself.

---

## What costs Clay actions and credits (read before spending)

**Canonical reference: [`knowledge-base/playbooks/clay/actions-data-credits.md`](../../knowledge-base/playbooks/clay/actions-data-credits.md).**
Check it before choosing how to build anything. Short version, verified live on a production workbook (2026-09-24):

| Free (no actions, no credits) | Costs 1 action per row (+ data credits unless your own key) |
|---|---|
| Search sources / imports (Find People, Search DSL `send-to-table`) | Any provider enrichment, including Prospeo inside Clay |
| Send table data (route-row), lookups: data transfers between Clay tables | AI columns (Use AI, Claygent) |
| Formulas, filters, manual/API data entry, Search DSL preview | HTTP API columns, CRM/warehouse syncs, sequencer sends |

**Billing plan changes the answer (LEARNINGS #35).** The table above is the NEW Clay plan. Legacy-plan workspaces
consume no actions at all (data credits only). `workspace_billing(ws)` / `clay.billing_model(table_id)` return
`legacy` / `actions` / `unknown` from `WORKSPACE_BILLING` in `clay_client.py` (ships empty: add your own workspace ids once you know their plan).
Legacy: run action-heavy work inside Clay. New plan: run it outside Clay and write back. Unknown: ask, then record it.

Provider calls made **outside** Clay (e.g. Prospeo API with the client's key) cost 0 Clay actions, but bill the provider
directly, and the values land without Clay lineage: record where they came from in the table.

## Additions beyond upstream v2.1

- **2026-10-29 (backlog #87): default work-email waterfall, validation by API.** `create_waterfall_from_template(table, template, inputs, condition, field_name=None)` fills `{{FULL_NAME}}` / `{{COMPANY_DOMAIN}}` / `{{COMPANY_NAME}}` / `{{LINKEDIN_URL}}` and creates the waterfall WITH step validation; `templates/waterfall-work-email.json` = an example standard (Prospeo → LeadMagic → Icypeas → Findymail → Wiza → FullEnrich; set each step's `authAccountId` to your own connection first) + top-level `validationActionConfig` (LeadMagic, `inputName: email`), the body key Clay's own app sends (found in its JS bundle; per-step keys are ignored). Read back, raises if a step lacks validation. `create_waterfall()` sends `validationActionConfig`; `update_waterfall(..., validation=None)` keeps the existing one ({} removes); `export_waterfall()` records it.
- **2026-10-29 (backlog #86): formula prompts.** `create_formula_column(..., prompt=[...])` REQUIRES the plain-English prompt (`formulaPrompt`, the box above the formula; parts list, `"[Column]"` / `"{{f_id}}"` become chips) and refuses one that misses a column the formula uses; `update_column()` refuses a new `formulaText` without `formulaPrompt` (list parts built for you; `require_prompt=False` / `replace=True` skip); `build_formula_prompt()`, `formula_prompt_gaps()`, `audit_formula_prompts(table)`. `create_ai_extraction_column()` and Search DSL extra columns write a prompt automatically. Scripts that call `create_formula_column` without `prompt=` now raise; add one or pass `prompt=False`.
- **`organize_table(table, layout)`** (2026-10-19, backlog #67): groups, colours and orders columns left to right in every view in one call, reads back. Default after every build step.
- **2026-10-16:** `set_view_order()` (views reorder via `afterViewId`; `order` PATCH is ignored, backlog #64); `_load_cookies()` sends `__Host-claysession` (backlog #63).
- **2026-10-14:** `create_http_auth_account(name, headers)`: store API keys in a Clay "HTTP API (Headers)" connection instead of a column's plaintext headers (backlog #66).
- **2026-10-14:** `update_waterfall(table, group, steps, allow_remove=False)` + `waterfall_steps_with_ids()`: edit a native waterfall in place via `PATCH .../waterfall/v2/{groupId}`, kept steps keep their columns (backlog #64).
- **2026-10-14:** `set_group_members()` (move fields into one existing group, read back) + `create_field_group()` refuses fields from 2+ groups (backlog #62).
- **2026-10-13:** `create_field_group()` refuses source columns before any write (Clay 400s on them; backlog #61). `us_hq_filter()` + `rename_source()` (backlog #58, #59).
- **2026-10-08:** `guess_column_data_type(name)` + `create_formula_column(data_type=None)` infers `url` / `email` from the column name so domain and link columns are clickable (backlog #54); `update_column()` lints a new `formulaText` (spread syntax etc.) before PATCHing, `lint=False` overrides (backlog #53).
- **Backlog batch 2026-09-29** (all offline-tested in `tests/test_local_additions_offline.py`, live-checked on scratch workbooks in two test workspaces):
  - Folders + workbooks: `create_folder(name, parent_folder_id=)`, `list_folder(folder_id)`, `get_workbook()`, `create_workbook(name, folder_id=)`, `create_table(..., folder_id=)`, `set_workbook_description()`. Backlog #26, #34, #37.
  - Search DSL: `validate_dsl_query()` runs on every DSL call (`COMPANY_SIZE_BUCKETS`, unfilterable company keys); `parse_dsl_preview_row()`; `send_search_dsl_to_table(extra_columns=[...])` (`DSL_EXTRA_COLUMNS`); `add_search_dsl_source(table_id, query)`; `set_table_dedupe(table_id, field_id)`; `source_table_id(source_id)`; `update_and_run_search_dsl_source(mode="replace")` refuses tables with text/action columns unless `allow_row_loss=True`; `compare_dsl_scopes()`; `lookup_companies_by_domain()` + `best_company_for_domain()`. Backlog #9, #13, #16, #25, #31, #32, #33.
  - Views: `set_view_filter()` checks each condition against that column's own `supportedFilterOperators` / `needsValue`. Backlog #10.
  - Formulas: `lint_clay_formula()`; `create_formula_column()` refuses `new Set` / spread / `\uXXXX` escapes (`lint=False` overrides), `create_column()` warns. Backlog #35, #56.
  - Audits: `formula_logic()`, `describe_columns()`, `label_drift()` / `audit_formula_labels()`, `audit_route_condition()` (node `vm`, empty context). Backlog #27, #28. `formula_logic()` also accepts older bare-string `formulaWaterfall` branches (#42).
  - Runs: `run_paced()` (batches, read-back, retries plain `ERROR` only, rate-limit count, `ERROR_*` statuses final). Backlog #36.
  - AI: `list_ai_models_in_use()`, `credit_balance()`, `clone_column()` warns on `clay-*` models when credits are low. Backlog AI-models row.
  - `create_view(copy_colors=True)` copies the Default view's column colours onto the new view; `copy_view_colors()` helper. Backlog #50.
  - `create_records()` lineage guard: refuses more than `API_ROW_WRITE_LIMIT` (2) rows per call unless `allow_bulk_api_rows=True` (only on the operator's explicit request or non-Clay data); build derived tables with `create_route_row_column()`. Backlog #48.
  - Find Jobs: `company_identifier_field_id` / `company_identifiers` aliases (LinkedIn OR domain column). Backlog #29.
- `WORKSPACE_BILLING` / `workspace_billing()` / `clay.billing_model()`: per-workspace Clay billing plan (legacy = no actions consumed, actions = new plan, unknown = ask); the login line prints it. Decides inside-Clay vs outside-and-write-back for action-heavy work. Backlog #35.
- `clay.create_waterfall()` / `export_waterfall()` / `delete_waterfall()`: native Clay waterfall groups (`/waterfall/v2`), reference template `templates/waterfall-work-email.json` (an example work-email waterfall: own-key provider first, then Clay-credit providers). Backlog #25, see action-registry "Native Waterfalls". `create_waterfall()` returns the group the call created (id diff before/after), never a same-named existing one, and raises otherwise (backlog #69).
- `clay.table_workspace(table_id)`: workspace-scoped table paths (view filter/sort, waterfall create/delete, generate_formula) now use the TABLE's own `workspaceId`, not the client default; a bare `ClayClient()` warns when you belong to several workspaces; `create_view()` deletes the view it just created if filter/sort/columns fail, so no half-configured view is left. Backlog #30.

This copy is Rex v2.1 (upstream `68fb058`) plus the additions above, kept through the upgrade by a 3-way merge on 2026-09-24. `tests/test_local_additions_offline.py` fails if a future merge drops any of them.

- **`clay_public.py`**: client for Clay's official Public API (Search). See the section below. Uses `CLAY_API_KEY` from the repo `.env`, not the session cookie.
- **Search DSL source helpers** (added 2026-09-24, verified live): `search_dsl_preview(query)` returns the free
  `totalCount` plus up to 250 sample rows; `send_search_dsl_to_table(query, table_name, workbook_id)` creates the
  table + source, runs it, and switches the table's auto-run off; `update_and_run_search_dsl_source(source_id, query)`
  changes the query and re-runs. Both write helpers refuse a query without `limit N`, because the run starts
  immediately. This is how to build people searches filtered on job-start recency, country, company size or
  industry. Full contract and payload paths: `action-registry.md` > Search DSL Source.
- **`ClayClient.update_records()`**: bulk PATCH `/tables/{id}/records`. Use it instead of `update_record()`, whose singular PATCH returns 200 but has been seen to silently no-op (confirmed 2026-08-24).
- **View helpers** (upstream Rex cannot create views; added 2026-09-24, verified live):

```python
from clay_client import ClayClient, view_filter

view = clay.create_view(table_id, "Qualified - ready to push",
    filter_items=[view_filter(f_qualified, "EQUAL", "yes"),     # EQUAL is case-sensitive
                  view_filter(f_email, "NOT_EMPTY")],
    combination_mode="AND",                                        # or "OR"
    sort_items=[{"fieldId": f_score, "direction": "DESC"}],
    visible_field_ids=[f_company, f_name, f_email, f_qualified])  # shown in this order, rest hidden
clay.view_count(table_id, view["id"])        # rows after the filter
clay.set_view_filter(table_id, view_id, [...])   # replace; [] clears it
clay.set_view_sort(table_id, view_id, [...])
clay.set_view_columns(table_id, view_id, [...])
clay.delete_view(table_id, view_id)          # rows untouched, no undelete
```

  API facts behind them: create = `POST /tables/{id}/views {"name"}` (a filter or sort in that body is ignored);
  filter = `PATCH /workspaces/{ws}/tables/{id}/views/{view}/filter {"items": [...], "combinationMode"}`, where each
  condition uses **`fieldId`** (not `field`); clearing needs an empty body (`{"items": []}` returns 404); sort =
  `PATCH .../sort {"items": [...]}`. **Clay answers 200 to an unknown operator and silently drops that condition**,
  so the view shows every row. `set_view_filter()` only accepts `VIEW_FILTER_OPERATORS` (from Clay's front-end
  enum) and raises `ClayViewFilterError` if Clay stored fewer conditions than were sent. `CONTAIN` is
  case-insensitive, `CONTAIN_ANY` takes a list, and run-status operators (`HAS_ERROR`, `HAS_NOT_RUN`,
  `RUN_CONDITION_NOT_MET`, ...) work on action columns.

- **AI column guards** (LEARNINGS.md backlog #1-#4, added 2026-09-24, verified live):

```python
# 1. Cloning a Claygent needs an explicit use case; the bound useCase is read back after create
clay.clone_column(src_tid, src_fid, tid, "Qualify / Use AI / 5 Mini", use_case="use-ai")

# 2. Extraction formulas that survive claygent (camelCase) vs use-ai (snake_case) key casing
clay.create_ai_extraction_column(tid, f_ai, "roleBucket", name="Role Bucket")
#    -> {{f_ai}}?.roleBucket ?? {{f_ai}}?.role_bucket      (ai_extract_formula() for the text)

# 3. Verify an AI column from its REAL output, not the "Response" placeholder cell
clay.read_ai_output(tid, record_id, f_ai)              # {"status", "output", "keys", "metadata"}
report = clay.verify_ai_column(tid, f_ai, record_ids[:3])
# report["problems"]: key_missing (+ casing suggestion), extraction_empty, no_output, action_not_success

# 4. Routed identity columns get real types (default column_types="auto": email->email, domain/url/linkedin->url)
clay.create_route_row_column(tid, "Send to People", people_tid, row_data)
clay.retype_route_columns(people_tid, {"Company Domain": "url"})
```

- **Table, column, lookup, jobs and view guards** (LEARNINGS.md backlog #12, #14, #17-#21, #23, #24; added
  2026-09-25, each verified live on a scratch workbook that was then deleted):

```python
# #14/#18 create_table() now PATCHes the name + AUTO_RUN_ON=false and reads both back
#         (ClayTableConfigError if they don't stick; Clay ignores both on create, even in a new workbook),
#         then deletes the blank "New Column" + blank row Clay adds (remove_placeholder=False keeps them)
t = clay.create_table("Companies | WF6 | 2026-09-25", workbook_id=wb_id)

# #12 create_column() defaults typeSettings.dataTypeSettings to {"type": "text"} for text/formula columns
clay.create_column(tid, {"type": "text", "name": "Company Name"})     # no more 400 "Missing data type settings."

# #21 Find Jobs (MixRank) source over a companies table; runs on create, renamed + auto-run off after
res = clay.create_find_jobs_source(wb_id, "Open Roles | Test", t_companies, v_companies, f_company_linkedin,
                                   record_ids, linkedin_urls, ["Account Executive"],
                                   max_days_since_posted=30, limit_per_company=1,
                                   locations=["United States"], employment_type=["Full-time"])
#     extract with FIND_JOBS_FIELDS: company_name, title, company_url, domain, posted_at, seniority, location, url
#     total_limit= (default 25,000 = plan cap per search, #29); a company DOMAIN column works as the identifier too

# #17 Lookup columns; output keyed by target column NAME
f_l = clay.create_lookup_column(tid, "Lookup: Jobs", t_jobs, f_jobs_company_li, f_company_li, multiple=True, limit=10)
lookup_extract_formula(f_l, "Job Title", multiple=True)  # ({{f_l}}?.records || []).map(r => r?.["Job Title"])
lookup_extract_formula(f_l1, "Job Title")                # {{f_l1}}?.record?.["Job Title"]

# #23 forceRun: refresh a lookup snapshot after the target table changed (a plain re-run keeps the old value)
clay.run_column(tid, [f_l], record_ids=ids, force=True)     # also run_and_wait(..., force=True)

# #20 Column colour is per VIEW; enum red|yellow|blue|green|violet|orange|pink|grey
clay.set_column_color(tid, view_id, [f_a, f_b], "blue")
clay.create_field_group(tid, [f_l, f_x], "Jobs", color="green", view_ids=[view_id])  # default: every view

# #19 set_view_columns()/create_view() refuse to hide action or source columns (ValueError, nothing written)
clay.set_view_columns(tid, view_id, [...], allow_hide_actions=True)   # explicit override only
```

  #24: `send_search_dsl_to_table()` docstring warns that `clay.filter_to_companies(@table(...))` adds a
  `trigger-find-people-source` action column to the referenced companies table; never run it.
  Deleting scratch objects: `DELETE /tables/{id}` and `DELETE /workbooks/{id}` both return 200 (no undelete).

**Gotchas found in real builds go in [`LEARNINGS.md`](LEARNINGS.md)**, which also holds the improvement backlog: every learning is promoted to a code fix, test, skill rule or doc here, and tracked until DONE. Read it before building.

## What's new in v2.1

**See what the whole workspace spent.** The new [`workspace-cost-audit`](../../.claude/skills/workspace-cost-audit/SKILL.md) skill runs `clay_workspace_costs.py`, a read-only monthly audit of one Clay workspace:

- **Clay credits** for the month, from Clay's daily credit series, broken down by table, workbook, integration and day.
- **AI provider dollars** (what AI columns billed your own OpenAI, Anthropic or Gemini key) by table, column and model, from the cost Clay stores on each AI cell. Refunded cells are left out.
- **Two separate totals.** Credits and provider dollars land on different bills, so the report never adds them.
- **Gates that fail closed.** A missing or duplicate day, a duplicate id, an incomplete read or a breakdown that explains too little of the total stop the run with an error code, and no report is written.

```bash
python3 clay_workspace_costs.py --workspace <workspace id> --month 2026-09
```

It writes `report.json` and CSVs to `reports/`, which git ignores. It only reads: its HTTP session refuses every method except GET. For one table in detail, keep using `calculate-costs` or ClayLens.

## What's new in v2

**Build a whole outbound workbook.** The new [`build-clay`](../../.claude/skills/build-clay/SKILL.md) skill teaches the agent to build or audit a complete outbound workbook with:

- **A Companies table** that shows which accounts belong in the campaign and why.
- **Two ways of finding people** at those companies: Clay's Find People search, plus a Claygent web-research column for the people the database misses.
- **One shared People table** where both sources land. All enrichment, qualification and copy happen there, once.
- **One-record proof before scale.** Every new column runs on one real record and gets checked before it touches the rest of the table.

**Prompts that work on every row.** The new [`prompt-builder`](../../.claude/skills/prompt-builder/SKILL.md) skill writes the prompts for AI columns. Each prompt runs on thousands of rows, returns JSON that matches a schema, and is tested on the exact model that will run it.

**Cost in dollars and in credits.** See what each column and each row cost, in dollars and in Clay credits, from the same data Clay bills from. Get it in code with `clay.print_cost_report()` ([`calculate-costs`](../../.claude/skills/calculate-costs/SKILL.md)), or live in the browser with the **ClayLens** Chrome extension ([`claylens/`](claylens/README.md)).

**Bulk export.** Export many tables to CSV in one call ([`export-tables`](../../.claude/skills/export-tables/SKILL.md)).

**Safer defaults.** v1 could get expensive or break columns without telling you. v2 fixes that:

- **New tables are created with auto-run off.** With auto-run on, adding a column runs it on every row straight away. On a big table that can use up a month of credits before you notice. You now opt in with `auto_run=True`.
- **`update_column()` no longer wipes AI column settings.** Clay replaces a column's whole config on update, so changing only the prompt used to delete the model, schema and account. Rex now reads the column first and merges your change in.
- **Every API call has a timeout**, so an expired cookie fails fast instead of hanging.
- **New helpers:** `clone_column()` (copy a working AI column and change only the prompt), `create_find_companies_source()` / `create_find_people_source()`, `create_route_row_column()` ("Send table data"), and column groups.
- **Docs fixed.** Find People and Find Companies need different settings. The old docs said they were the same, which gave a 400. The docs also now say that a mistyped model name can leave a column queued forever.

**From a campaign brief to a live table.** Four new skills take a campaign from idea to a table you can show:

- [`campaign-contract`](../../.claude/skills/campaign-contract/SKILL.md) writes the campaign down as one Markdown contract: one section per Clay object in build order, every prompt verbatim, the model, the run conditions and the expected funnel.
- [`design-clay-table-json`](../../.claude/skills/design-clay-table-json/SKILL.md) turns the contract into an importable table JSON. It applies the Clay rules that prevent the usual failures: run conditions on every paid column, the row limit inside the search query, a free preview of the search before you commit, and a demo view that shows every source and AI column next to its answer.
- [`import-clay-table`](../../.claude/skills/import-clay-table/SKILL.md) imports the table with nothing running and pulls a small source. It proves every paid column on one row that should qualify and one that should not. Before it runs the rest, it projects the spend from the real per-cell cost of the proven rows and refuses to start if the projection exceeds your budget. It checks once, before the run, and does not stop a run partway.
- [`save-clay-schema`](../../.claude/skills/save-clay-schema/SKILL.md) exports the table you approved, including your manual edits. It checks that the table re-imports cleanly and adds it to your own `registry/`, so the next build starts from something that worked.

The pipeline reads your workspace, folder, auth accounts, models and budget from `rex-config.json` (copy [`rex-config.example.json`](rex-config.example.json)). It never guesses a workspace and refuses one your Clay session cannot see. Each command writes only inside the workbook of the table you name, in the configured workspace.

Full list of changes: [CHANGELOG.md](CHANGELOG.md).

---

## Requirements

```
Python 3.9+
requests
playwright (for clay_browser.py only)
```

```bash
pip install -r requirements.txt
python -m playwright install chromium  # only if using clay_browser.py
```

---

## Quick Start

**1. Get your session cookie.** Follow [COOKIE_SETUP.md](COOKIE_SETUP.md).

**2. Create `clay-session.json`** in the same directory:
```json
{"claysession": "s%3Ayour-cookie-value-here"}
```

**3. Use the client:**
```python
from clay_client import ClayClient

clay = ClayClient()                      # uses the first workspace your session can see
# clay = ClayClient(workspace_id=12345)  # pass it if you belong to more than one
# [clay] logged in as you@company.com | workspace 12345

# List all tables
tables = clay.list_tables()
for t in tables:
    print(t["name"], t["id"])

# Get records
records = clay.list_records(table_id, view_id)
for r in records:
    print(r["cells"])
```

---

## Using the skills with Claude Code

In this starter kit the Rex skills are already installed in `.claude/skills/` at the repository root. Run Claude Code from the repository root (not from `tools/rex/`) so it loads them. The pipeline scripts inside the skills (`.claude/skills/import-clay-table/scripts/`, `.claude/skills/save-clay-schema/scripts/`) find `clay_client.py`, `clay_flow.py` and `rex-config.json` in `tools/rex/` by walking up to the repository root, so keep that layout. Then ask in plain words, for example "build the Clay workbook for this segment" or "what did this table cost?".

---

## What's in the box

Authentication uses your browser session cookie. You do not need an API key.

| File | What it is |
|------|-----------|
| `clay_client.py` | Python SDK for Clay's internal REST API. Create tables, add columns, run enrichments, export and import schemas, calculate real cost, bulk-export. |
| `clay_costs.py` | Per-cell cost and telemetry extraction and aggregation (provider-cost table, credit lookup). `print_cost_report()` runs on it. |
| `clay_workspace_costs.py` | Read-only monthly cost audit of a whole workspace: Clay credits by table, integration and day, AI provider dollars by table, column and model, with consistency gates. Run it from the command line; see `.claude/skills/workspace-cost-audit`. |
| `clay_flow.py` | Workbook-scoped Clay client used by the pipeline scripts: an explicit workspace, a write guard that refuses tables outside the approved workbook, and the source, view and import routes the importer needs. |
| `clay_browser.py` | Playwright daemon that captures `api.clay.com` traffic in real time. Use it to find the input parameter names of undocumented action types. |
| `action-registry.md` | Catalog of known Clay actions with exact keys, package IDs, inputs, outputs and gotchas |
| `clay-api-reference.md` | API reference: endpoints, column schemas, action types |
| `claylens/` | Companion Chrome extension. It runs the same cost math as `clay_costs.py` live in the browser, as a dashboard with charts for a Clay table. See [claylens/README.md](claylens/README.md). |
| `GETTING_STARTED.md` | Setup, configuration and your first campaign build |
| `../../.claude/skills/` | SKILL.md files (in the starter kit's root) that teach an AI agent how to use Rex: `build-clay`, `prompt-builder`, `campaign-contract`, `design-clay-table-json`, `import-clay-table`, `save-clay-schema`, `calculate-costs`, `workspace-cost-audit`, `export-tables` |
| `tests/` | Offline tests for the client's safety defaults, the schema exporter and the workspace cost audit (no Clay account needed) |
| `rex-config.example.json` | Template for `rex-config.json`: workspace, folder, auth accounts, models and budget for the pipeline scripts. |
| `registry/` | Your approved table schemas, saved by `save-clay-schema` and read by `design-clay-table-json`. Starts empty. |
| `COOKIE_SETUP.md` | Step-by-step guide to extract your session cookie from Chrome |
| `clay-session.json.example` | Template for the session file |
| `requirements.txt` | Python dependencies |

---

## clay_client.py: the SDK

### Table management
```python
table = clay.create_table("My New Table")          # auto-run OFF by default
table_id, workbook_id = table["id"], table["workbookId"]
clay.list_tables()
```

### Column creation
```python
# Text column
clay.create_column(table_id, {"type": "text", "name": "Company Name"})

# AI column, safest way: copy a working AI column and change only the prompt
clay.clone_column("t_known_good", "f_known_good_ai", table_id, "Qualify Company",
                  input_overrides={"prompt": '"Company: " + {{f_name_field_id}}'})

# AI column from scratch (Create Content / Use AI)
clay.create_action_column(table_id, "Qualify Company",
    action_key="use-ai",
    package_id="67ba01e9-1898-4e7d-afe7-7ebe24819a57",
    inputs={
        "useCase": '"use-ai"',
        "model":   '"gemini-2.5-flash"',   # use a model id that exists in YOUR workspace
        "prompt":  '"Company: " + {{f_name_field_id}}',
    },
    auth_account_id="YOUR_AUTH_ACCOUNT_ID")

# Change only the prompt; model, schema and account are kept
clay.update_column(table_id, col_id, {"typeSettings": {
    "inputsBinding": [{"name": "prompt", "formulaText": '"New prompt"'}]}})
```

### Run enrichments and wait
```python
clay.run_column(table_id, [col_id], record_ids=[...])
records = clay.run_and_wait(table_id, [col_id], record_ids=[one_record_id], timeout=120)
```

### Schema export/import
```python
# Export (field IDs → portable column name references)
schema = clay.export_schema(table_id)

# Import into another table (resolves dependencies automatically)
new_table = clay.create_table("Cloned Table")
clay.import_schema(new_table["id"], schema)
```

### Other operations
- `clay.create_records(table_id, [{"col_id": "value"}, ...])`: add records
- `clay.update_record(table_id, record_id, {"col_id": "value"})`: update a record
- `clay.delete_records(table_id, [record_ids])`: delete records
- `clay.set_condition(table_id, col_id, condition)`: add "Only run if" logic
- `clay.generate_formula(table_id, "natural language description")`: AI formula generation
- `clay.search_enrichments("keyword")`: discover available actions
- `clay.list_auth_accounts()`: list connected integrations
- `clay.get_column(table_id, col_id)`: read one column's full live config
- `clay.create_find_companies_source(...)` / `clay.create_find_people_source(...)`: Find Companies / Find People source tables
- `clay.create_route_row_column(...)`: "Send table data" into another table
- `clay.create_field_group(...)` / `clay.get_field_groups(...)`: column groups

### Cost calculation

Rex reads per-cell dollar spend and Clay credit usage from the same fields Clay's own billing uses, so the report shows what was actually spent. See [calculate-costs](../../.claude/skills/calculate-costs/SKILL.md).

```python
summary = clay.print_cost_report(table_id)
# prints: total spend, credits, cost by column, top-10 most expensive rows
# summary["totals"]["total_cost_usd"], summary["by_column"], summary["top_rows"]
```

For the live, in-browser version of the same cost math, see [claylens/](claylens/README.md).

For a whole workspace over a month, use the command-line audit instead. See [workspace-cost-audit](../../.claude/skills/workspace-cost-audit/SKILL.md).

```bash
python3 clay_workspace_costs.py --workspace <workspace id>              # current UTC month
python3 clay_workspace_costs.py --workspace <workspace id> --month 2026-08
```

### Bulk export

Export multiple tables to CSV and download them to disk in one call. See
[export-tables](../../.claude/skills/export-tables/SKILL.md).

```python
results = clay.export_tables(["t_abc123", "t_def456"], out_dir="./exports")
# {table_id: "ok (N bytes) -> path"} or {table_id: "error: ..."} per table
```

---

## clay_public.py: official Search API (addition beyond upstream v2.1)

Searches Clay's proprietary GTM database (~850m people, ~60m companies) via the official Public API. Three-step flow wrapped into one call: discover filter fields → create search → page through results (stateful server-side iterator, `has_more` flag, 500 records/page max).

```python
from clay_public import ClayPublicClient
clay = ClayPublicClient()  # reads CLAY_API_KEY from env or repo .env

# Discover valid filter names before building a search
fields = clay.search_fields("people")   # or "companies"

# Fetch records
people = clay.search("people", {
    "job_title_keywords": ["cfo", "vp finance"],
    "location_countries_include": ["United States"],
}, max_results=500)
```

CLI:

```bash
.venv/bin/python clay_public.py fields companies
.venv/bin/python clay_public.py search people '{"job_title_keywords": ["cfo"]}' --max 100 --csv cfos.csv
```

Notes:
- Handles 429s automatically (honors `Retry-After`, exponential backoff).
- `matched_experience` in results is contextual and may be `null`; use `latest_experience_*` fields for current role.
- This is the read/search layer only. Table writes stay on `clay_client.py` (internal API); the public key is not valid for internal v3 endpoints and vice versa.

## clay_browser.py: API discovery

A Playwright daemon that runs in the background, captures all `api.clay.com` requests and responses, and lets you query them. Use it when you need the input parameter names for an action type that is not in the registry yet.

### Usage

```bash
# Start the daemon
python clay_browser.py launch --headless

# Navigate to a Clay table
python clay_browser.py goto "https://app.clay.com/workbooks/..."

# Interact with the UI
python clay_browser.py click "Add enrichment" --role button
python clay_browser.py fill "LeadMagic" --placeholder "Search"
python clay_browser.py click "Find Work Email"

# See what API calls were made
python clay_browser.py requests --filter fields --last 5

# Other commands
python clay_browser.py snapshot          # accessibility tree of current page
python clay_browser.py screenshot out.png
python clay_browser.py eval "document.title"

# Stop the daemon
python clay_browser.py close
```

### How it works

- Forks a daemon process that listens on a UNIX socket (`/tmp/clay-browser/server.sock`).
- Injects your session cookie from `clay-session.json`.
- Attaches Playwright request and response listeners to capture all `api.clay.com` traffic.
- Writes captured requests as JSONL to `/tmp/clay-browser/requests.jsonl`.

### Commands

| Command | Description |
|---------|-------------|
| `launch [--headless]` | Start the browser daemon |
| `close` | Shut down the daemon |
| `goto <url>` | Navigate to a URL |
| `snapshot` | Accessibility tree snapshot of the page |
| `screenshot [path]` | Save a PNG screenshot |
| `click <text> [--role] [--nth]` | Click an element by text |
| `fill <text> [--placeholder]` | Type text into an input |
| `requests [--filter] [--last N]` | Show captured API calls |
| `eval <js>` | Execute JavaScript in page context |
| `click_selector <selector>` | Click by CSS selector |

---

## action-registry.md: action catalog

A reference of all known Clay actions with exact specifications. Each entry includes:

- **`key`:** the `actionKey` identifier
- **`package`:** the `actionPackageId` UUID
- **`inputs`:** exact field names, types, required or optional
- **`output`:** keys you can read with `?.field_name` formulas
- **`auth`:** which auth account type to use
- **`gotchas`:** common mistakes

Categories covered: AI & Content, Enrichment (MixRank), Sources (Find People/Companies), Lookups, HTTP API, Integrations (Instantly, HeyReach, Google Sheets), Social (LinkedIn Posts).

When you meet an action that is not in the registry, use `clay_browser.py` to discover its inputs.

---

## Authentication

Clay authenticates with a `claysession` cookie that is set when you log in through the browser. The Python client reads this cookie from `clay-session.json` and sends it with every API request, the same way the browser does.

See [COOKIE_SETUP.md](COOKIE_SETUP.md) for how to extract the cookie from Chrome DevTools.

---

## Gotchas

These took hours to figure out. `clay-api-reference.md` has the full list.

- **`GET /views/{id}/records` returns its rows under `"results"`.** There is no `"records"` key.
- **Pagination is broken.** The API always returns the same first N records, whatever the offset or cursor. Use the 2-step `ids → bulk-fetch` approach in `clay_client.py`.
- **`queryString` and `headers` in HTTP API columns must use `formulaMap`.** `formulaText` splits JSON character by character.
- **Formula columns must be created as text first**, then PATCHed with `formulaText` + `formulaType: "text"`.
- **`answerSchemaType` requires `formulaMap`.** With `formulaText` it fails without an error. `jsonSchema` must be double JSON-encoded. `_metadata` with `modelSource: '"user"'` (inner quotes) is required.
- **`dataTypeSettings`:** `{"type": "text"}` renders best in the Clay UI, but some workspaces return 400 for `text` when `answerSchemaType` is set. Cloning a working column avoids guessing.
- **A mistyped or unknown model name can leave a column queued forever**, with no error. Copy the model id from a working column and run one record first.
- **Partial `typeSettings` updates wipe the rest** when sent raw. `update_column()` merges for you; raw `clay.patch()` does not.
- **Find People and Find Companies are configured differently** (`hasEvaluatedInputs`, LinkedIn URL field name). Use the client helpers.
- **`actionKey` must be `"use-ai"`.** Using `"ai"` drops all `inputsBinding` without an error.
- **Prompt escaping:** no `{single_braces}` in prompt text (Clay parses them as field refs). No unescaped `"quotes"` inside formula strings (they empty the prompt without an error). Use `Clay.formatForAIPrompt({{field}})` for field injection.
- **Formula `.indexOf()` and `.includes()` are unreliable.** Use `/pattern/i.test(String({{f_id}}) || "")` instead.
- **Lookup columns use the `fields|` prefix** for filter inputs: `fields|targetColumn`, `fields|filterOperator`, `fields|rowValue`.
- **Webhook source tables need formula extractors.** Data columns are NOT populated automatically; PATCH them with `formulaText` + `formulaType`.
- **Formula columns cannot be JSON-typed** (400 `Data type "json" is not supported for basic fields`). Only action columns hold objects; keep formula outputs text and `JSON.parse({{f}} || "{}")` downstream. Clay formulas do support `??`.

---

## Disclaimer

This repo documents behavior observed in browser network requests (HAR files). It is not affiliated with Clay and may break if Clay changes its internal API. Use at your own risk.

---

## License

[MIT](LICENSE)
