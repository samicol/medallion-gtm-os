---
name: import-clay-table
description: "Import one Clay table JSON (flow blueprint) into your Clay workspace with auto-run off, fill it with a small source run, prove every paid column on one row that should qualify and one that should be rejected, run the rest only if the spend projected from real per-cell cost fits the budget, and read the demo view back as the viewer will see it. Use it after design-clay-table-json, or when someone says 'import this table' or 'run the demo table'. It does not change the table design (to change it, fix the JSON and re-import), and it does not send, find emails or export to any sending tool."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.

# Import Clay Table

This skill takes a finished table JSON and makes it a populated Clay table that someone can open
and show. Your job ends when the demo view holds the rows the contract promised, every visible cell
is filled with something true, and you have read those cells yourself.

The result is the demo view, read row by row. A successful import, a green check or a full table
comes earlier and proves much less. Most false "done" claims come from stopping one step before
that read.

## Setup

- Auth: `tools/rex/clay-session.json` next to `clay_client.py` (see `COOKIE_SETUP.md`), or the `CLAY_SESSION`
  environment variable.
- Config: copy `tools/rex/rex-config.example.json` to `tools/rex/rex-config.json` (gitignored) and fill in:
  - `workspaceId`: the Clay workspace to build in. Required; the scripts never guess one.
  - `folderId`: optional folder to file new workbooks in.
  - `authAccounts`: name to auth account id, for every `${bindings.authAccounts.<name>}` the JSON
    uses. List your accounts with `ClayClient().list_auth_accounts()`.
  - `models`: name to model id, for every `${bindings.models.<name>}` the JSON uses.
  - `budgetUsd`: the spend cap for `run`.
  Every value can be overridden per command: `--workspace`, `--folder`,
  `--auth-account name=aa_...`, `--model name=...`, `--budget`, or `--config other.json`.

## Boundaries

- No sending, no email finding or validation, no export to a sending tool or CRM.
- Budget: the owner's number (`budgetUsd`). Before it starts, `run` projects the spend from the
  real per-cell cost of the rows already run and refuses to start when spend so far plus the
  projection exceeds the budget. It checks once, before the run, and does not stop a run partway,
  so a run whose rows cost more than the proven rows can finish above the budget.
- Each command writes only inside the workbook of the table you name, in the configured
  workspace, and refuses a workspace your Clay session cannot see or a table in another
  workspace. The client re-reads the table before every write and refuses one outside that
  workbook; do not work around it.
- Do not repair the table by hand in Clay. If a column is wrong, fix the JSON and re-import (or
  resume), and say what changed. A hand fix makes the saved schema lie. The exception is an
  explicit instruction from the owner; then do it and record it.

## Tools

```bash
S=.claude/skills/import-clay-table/scripts/clay_table.py
python3 -u $S import <flow.json> --receipt output/campaigns/<slug>/import-receipt.json
python3 -u $S source <table-id> --limit <n>
python3 -u $S one-row <table-id> --record <record-id> --expect qualify|reject
python3 -u $S run <table-id> [--budget 5] [--spend-tables <every table id of this build>]
python3 -u $S spend <table-id> [<table-id> ...]
python3 -u $S read <table-id> --view <demo view id> --limit 15
```

`import` calls `scripts/import_flow.py`, which can also be run directly for a dry run
(`--dry-run`) or to resume a failed import from its receipt (`--resume-workbook`,
`--resume-table-ids-json`, `--resume-view-ids-json`; the receipt's `resumeState` has the values).

## Method

### 1. Import held

Run `import`. Auto-run stays off; the importer creates the workbook, tables, sources, columns and
views, runs nothing, then reads everything back and compares it with the JSON: every column's
settings, every source, the demo view's filter, visibility and column order, and zero rows. The
status is `IMPORTED_HELD` or `FAILED_PARTIAL_IMPORT` with the error. On a failure, fix the cause
and resume with the ids from the receipt rather than creating a second workbook. Record the
workbook, table and view ids in the campaign folder.

### 2. Fill the first table with a small, deliberate source run

Run `source` on the first table in build order with a limit that serves the expected funnel. The
limit lives in the JSON's search query; `source` refuses a search without one. Then read the first
names that arrived. If they are the wrong kind of company or person, stop here. A wrong source is
the cheapest thing to fix now and the most expensive thing to discover after the AI columns ran.

Clay keeps one empty scaffold row on a new table. The helper skips it everywhere, so no paid column
runs on a row with no input.

### 3. Prove every paid column on one row, both ways

Pick a row that should qualify (do not just take the first row) and run `one-row --expect qualify`.
It runs each action column on that record in dependency order and prints status, cost and value,
then every formula. Read every value as the viewer would:

- Does the research cite a real source about this exact company?
- Does the verdict follow from that evidence?
- Do the formula wrappers show the verdict (they are what the next table reads)?
- Is the copy about this company's actual situation, in the voice the contract asks for?

A 200 status, `SUCCESS` or a non-empty cell proves nothing on its own: a signal cell can be full and
the copy confident while the research found nothing.

Then run one row that should be rejected (`--expect reject`) and check it is rejected for the right
reason, and that the gated columns show `ERROR_RUN_CONDITION_NOT_MET` rather than a cost. Now you
know the gate works both ways.

If a value is wrong, find the column that caused it and fix the JSON. Re-import (a new workbook;
rename the old one `SUPERSEDED r<n> / ...` and ask the owner to delete it; you do not delete it) or,
for one broken column, resume with `--repair-columns-json`, which rebuilds that column and its
dependants in place. Then run `one-row` again.

On two-table builds, repeat on the second table after its source ran: the person row must show the
company's verdict through the lookup. If it is blank, the company side is missing a formula
wrapper; see `design-clay-table-json`.

### 4. Run the rest inside the budget

`run` reads the real cost Clay recorded on every action cell: AI provider dollars and Clay credits.
For the budget check it adds them into one dollar estimate by converting credits at the fixed rate
in `clay_costs.py` ($0.014 per credit), averages that over the rows that cost something, projects
it over the pending rows, and refuses to start when spent plus projected exceeds the budget. The
converted credit figure is an estimate; `spend` prints dollars and credits separately so you can
judge each. Once the run starts it goes to the end. It refuses to project
before any row has a recorded cost, so the one-row proofs come first. Pass every table of the build
to `--spend-tables` so the budget check covers the whole build. Run the first table fully before
triggering the second table's source, because the people search reads the company verdicts.

`spend` counts the latest run of each cell. Re-running a cell replaces its cost record, so repeated
one-row proofs cost slightly more than `spend` shows.

### 5. Read the demo view

`read <table> --view <demo view id>` prints the view's visible columns in on-screen order, row by
row, and counts empty cells. Check the row count against the contract, the column order (every
source and AI column visible, each followed by its answer, in causal order), and
`EMPTY_CELLS_IN_SAMPLE` (should be 0). For each row ask whether you would be comfortable if the
prospect read it aloud. If the count is short, say why in numbers (sourced, qualified, people
found, people qualified) and propose the smallest change: a wider source, a second page, or a looser
filter the contract allows. Do not quietly lower the target. If far more rows finish than the
contract needs, the contract should say how the view is cut; size the source from the funnel next
time.

### 6. Bring the contract up to date

Whatever changed during the build (a filter value, a keyword, a limit, an added column, a
tightened prompt) goes back into `contract.md`, so it describes the table that exists, prompts
verbatim.

### 7. Hand back

Give the owner: the Clay link to the demo view, the row count against the target, total spend, the
one best row to talk through and why, and anything you could not make true. Write the same into the
campaign folder as `run.md`. When the table is approved, `save-clay-schema` exports it into the
registry.
