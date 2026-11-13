# Changelog

## v2.1 (2026-09-24)

### New skill

- **`workspace-cost-audit`**: what a whole Clay workspace spent in one UTC month. Clay credits come from Clay's daily credit series and are broken down by table, workbook, integration and day. AI provider dollars come from the cost stored on each Use AI cell that ran on your own key, by table, column and model, with refunded cells left out. The two are reported as separate totals.

### New tool

- `clay_workspace_costs.py`: the command-line audit behind the skill. `--workspace` is required and must be visible to your session. `--month` defaults to the current UTC month. `--full-scan` reads every table instead of only the tables touched in the month. It writes `report.json` plus `tables.csv`, `integrations.csv`, `daily.csv`, `ai_columns.csv` and `ai_models.csv` to `reports/` (now in `.gitignore`).
- Read-only by construction: its HTTP session refuses every method except GET before anything reaches the network.
- Consistency gates that fail closed: a duplicate or missing day in the credit series, a duplicate table or integration id, a failed record read, an AI table without an unfiltered view, credit attribution below `--min-coverage` (default 0.75), or totals that do not add up across accounts, models, workbooks, tables and integrations stop the run with an error code and write no report. `--allow-missing-days` accepts days Clay left out of the series only when the independent workspace report proves they were zero.
- Reuses `clay_costs.extract_cost_fields()` for the fields it shares with `calculate-costs`, so one table's provider dollars match in both when all of its AI cells ran inside the audited month (`calculate-costs` covers all time).

### Tests

- `tests/test_workspace_costs_offline.py`: synthetic fixtures for the gates, the daily-series check, refunds, Clay-managed keys, strict pagination, the GET-only session, and a check that the CLI refuses to run without `--workspace`. Run with `python3 -m pytest -q tests`.

## v2.0 (2026-09-24)

### New skills

- **`build-clay`**: build or audit a complete outbound workbook. A Companies table decides which accounts belong in the campaign and why. People are found two ways (Clay's Find People search and a Claygent web-research column) and land in one shared People table, where enrichment, qualification and copy run once. Every new column is proven on one real record before it runs on the rest.
- **`prompt-builder`**: write per-row prompts for AI columns. Each prompt runs on every row, returns JSON that matches a schema, and is tested on the exact model that will run it.
- **`calculate-costs`**: actual spend per column and per row, in dollars and Clay credits, read from the same cell data Clay bills from.
- **`export-tables`**: export many tables to CSV in one call.
- Campaign pipeline: `campaign-contract`, `design-clay-table-json`, `import-clay-table`, `save-clay-schema` skills, `clay_flow.py` (the workbook-scoped Clay client the pipeline scripts use), `skills/import-clay-table/scripts/` (the importer and runner: held import, one-row proof, and a budget check that projects spend from real per-cell cost and refuses to start a run that would exceed it), `rex-config.example.json`, empty `registry/` template.

### Docs

- **`GETTING_STARTED.md`**: from a fresh clone to your first campaign table: setup, pipeline config, a smoke test that spends nothing or cents, a campaign brief template, the first build on about ten rows, your own schema registry, and where your own copy and GTM skills plug in.

### New tools

- **ClayLens** (`claylens/`): Chrome extension that shows the same cost analytics live in the browser.
- `clay_costs.py`: cost extraction and aggregation behind `print_cost_report()`.

### Safer client defaults (`clay_client.py`)

- `create_table()` now creates workbooks with **auto-run off**. Opt in with `auto_run=True`. With auto-run on, adding a paid column runs it on every row immediately.
- `update_column()` now **merges** partial `typeSettings` into the live column (read, then merge; `inputsBinding` merged by input name). Before, a partial update wiped the model, auth account and output schema of AI and enrichment columns without any error. Pass `replace=True` for the old full-replacement behaviour.
- Every HTTP call now has a **default 30 second timeout** (`ClayClient(timeout=...)` to change it). Before, `me()` and other calls could hang forever on an expired cookie.
- `create_column()` raises `ClayColumnConfigError` when Clay reports a `settingsError`, so you do not get a broken column back.

### New client helpers

- `get_column()`: read one column's full live config.
- `clone_column()`: copy a known-good column's config and change only the inputs you name. The recommended way to build AI columns.
- `create_find_companies_source()` and `create_find_people_source()`: build the full request body for each source, including the settings where they differ.
- `get_source_field_id()`: look up a source table's generated source column id.
- `create_route_row_column()`: "Send table data" (route-row) into another table, single-row or list mode.
- `create_field_group()` and `get_field_groups()`: column groups.
- `export_tables()`, `export_csv()`, `fetch_all_records_full()`, `get_cell_costs()`, `print_cost_report()`.

### Documentation fixes

- Find People and Find Companies need **different** settings (`hasEvaluatedInputs`, `idPath`, LinkedIn URL field). The old docs said they were the same, and following them returned HTTP 400. Both are now documented side by side, including the four inputs Find People needs to stay limited to your companies.
- A typo'd or unknown model name can leave an AI column queued forever with no error. Docs now say to copy the model id from a working column and to clone known-good AI columns instead of hand-building the output schema.
- `action-registry.md`: new entries for Send Table Data (route-row) and column groups.
- README examples corrected to match the actual client signatures.

### Tests

- `tests/test_client_offline.py`: offline tests (mocked HTTP, no Clay account) for auto-run off, updates that merge instead of wiping, `clone_column()`, and timeouts. Run with `python -m unittest discover -s tests`.
- `tests/test_export_schema_offline.py`: offline test (stubbed Clay client) that a saved schema contains no auth account id or other source workspace id unless you pass `--keep-origin`.
