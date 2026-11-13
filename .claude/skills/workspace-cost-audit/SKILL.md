---
name: workspace-cost-audit
description: "Report what a whole Clay workspace spent in one month: Clay credits by table, workbook, integration and day, and AI provider dollars by table, column and model. Read-only, with consistency gates that stop the run instead of reporting a number they cannot prove. Use it when someone asks what their Clay workspace spent this month, which tables or integrations used the credits, or what the AI columns cost on their own model keys."
---

> **Starter-kit notes.** From the Rex v2.1 skill of the same name (MIT, see `tools/rex/LICENSE`). Path mapping for this repo:
> - Rex lives at `tools/rex/`. "Repository root" in this skill means `tools/rex/`. Run Python from there with its venv:
>   `cd tools/rex && .venv/bin/python ...` (`from clay_client import ClayClient` works from that folder).
> - Rex docs referenced below: `tools/rex/clay-api-reference.md`, `tools/rex/action-registry.md`, `tools/rex/GETTING_STARTED.md`.
> - Clay workspace: never guess a workspace id; read it from the Clay URL (`app.clay.com/workspaces/<workspace_id>/...`).
> - Run as `cd tools/rex && .venv/bin/python clay_workspace_costs.py --workspace <workspace_id>`. Reports land in `tools/rex/reports/` (gitignored; they contain table names and spend, keep them out of commits).

# Workspace Cost Audit

This skill answers "what did my Clay workspace spend this month, by table and
by integration?" It reads Clay's own credit reports and the cost Clay stores on
AI cells, checks that the numbers agree with each other, and writes a JSON
report plus CSVs you can open in a spreadsheet.

It reports two billing axes and never adds them together:

- **Clay credits.** What Clay charged the workspace. The total comes from
  the daily spend series in Clay's credit reporting. The workspace, table and
  integration reports then say where those credits went.
- **AI provider dollars.** What AI columns billed your own model provider key
  (OpenAI, Anthropic, Gemini and so on) through Clay. They come from the
  `totalCostToAIProvider` value Clay stores on every Use AI cell that ran.
  Your provider bills these, so they never show up in credits.

Keep them apart when you report. They land on different bills, and the dollar
value of a credit depends on your Clay plan.

## When to use this, and when to use something else

- **This skill:** one workspace, one month, every table. "What did we spend in
  August?", "which workbook used most of the credits?", "what did the AI
  columns cost on our OpenAI key this month?"
- **`calculate-costs`:** one table, every cell, with per-row and per-column
  detail and percentiles. Use it once this audit has shown you which table to
  look at.
- **ClayLens** (`claylens/`): the same per-table numbers live in the browser,
  while you work in the table.

## How to run it

From the root of your Rex clone:

```bash
python3 clay_workspace_costs.py --workspace <workspace id>
```

The workspace id is the number in your Clay URL
(`app.clay.com/workspaces/<id>/...`). It is required and never guessed, and
the script refuses a workspace your session cannot open, so a session that
belongs to several workspaces cannot audit the wrong one by accident.

Options:

| Option | What it does |
|---|---|
| `--month YYYY-MM` | UTC month to audit. Default: the current UTC month, up to now. |
| `--full-scan` | Read every table, not only the ones touched this month. Much slower (see below). |
| `--include-table t_...` | Add a table to the normal scope. Repeatable. |
| `--allow-missing-days` | Accept days with no entry in Clay's daily series, only when the independent workspace report proves they were zero. |
| `--min-coverage 0.75` | Share of credits the workspace, table and integration reports must each explain. |
| `--tolerance 0.000001` | Allowed difference in the consistency checks. |
| `--workers 20` | Parallel record reads. |
| `--output-dir PATH` | Where to write the report. Default: `reports/workspace-costs-<workspace>-<month>/`, which git ignores. |

Auth is the same `clay-session.json` as the rest of Rex (see
`COOKIE_SETUP.md`). If `CLAY_SESSION` is set in the environment, it wins.

The script only reads. Its HTTP session refuses every method except GET
before anything reaches the network, so it cannot run a column, edit a table
or change a setting.

### What it reads

1. Clay's three credit reports for the month: the daily spend series, the
   workspace report (folder, workbook, table) and the integration report.
2. The tables in scope. By default that is every table updated since the
   month started, plus every table with credits in the month, plus any
   `--include-table`. With `--full-scan` it is every table.
3. In each table with a Use AI column, every row, through a view with no
   filter and no row limit, so filtered views cannot hide rows.

## Reading the output

The terminal prints a summary. The files are:

| File | What is in it |
|---|---|
| `report.json` | Everything below plus the gates, scope, thresholds and limitations |
| `tables.csv` | Credits and provider dollars per table, with AI cell counts |
| `integrations.csv` | Credits and action executions per integration |
| `daily.csv` | Credits per UTC day; `bucket_present` is false for a day Clay did not report |
| `ai_columns.csv` | Provider dollars per AI column, with its table, model, account and billing |
| `ai_models.csv` | Provider dollars per provider and model |

The fields that matter:

- **`credits`**: the month's Clay credits from the daily series. This is the
  authoritative credit total.
- **`provider_usd`**: provider dollars from AI cells that ran on your own key
  in the month, after refunds.
- **`Other / non-table or unattributed`** in `tables.csv` or
  `integrations.csv`: credits the daily series has but no current table or
  integration explains. Usually deleted tables or work outside tables. The
  gates require the named rows to explain at least `--min-coverage` of the
  total.
- **`ai_cells_missing_cost`**: AI cells on your own key that ran but have no
  stored provider cost. Their spend is real and not in `provider_usd`, so
  treat `provider_usd` as a floor while this is above zero.
- **`ai_cells_credit_billed`**: AI cells that ran on a Clay-managed key. Clay
  billed them in credits, so they have no provider dollars, and their cost is
  already in `credits`.
- **`ai_cell_credits_subset`**: credits recorded on the AI cells themselves.
  A cross-check only. The credit total comes from the credit reports.
- **`action_execution_credits`**: Clay's separate action-execution count,
  reported alongside credits. It is not added to them.

## The gates

The report is written only when every gate passes. A failed gate prints
`"status": "FAIL"` with an error code and writes nothing, because a partial
total that looks final is worse than no total. The main codes:

| Code | Meaning | What to do |
|---|---|---|
| `CREDIT_TIME_SERIES_INCOMPLETE` | Days are missing from Clay's daily series | On a quiet workspace Clay leaves out days with no activity. Rerun with `--allow-missing-days`. It still fails if the series and the workspace report disagree, because then a missing day may have had spend. |
| `CREDIT_REPORT_EXCEEDS_SERIES` | The breakdown reports more credits than the daily series, often because a day with spend is missing from the series | Rerun later. Do not report the month until it passes. |
| `CREDIT_TIME_SERIES_DUPLICATE_BUCKET` | Clay returned the same day twice | Rerun. Do not report the month. |
| `CREDIT_WORKSPACE_REPORT_COVERAGE_TOO_LOW` / `CREDIT_TABLE_ATTRIBUTION_TOO_LOW` / `CREDIT_INTEGRATION_ATTRIBUTION_TOO_LOW` | The reports explain less than `--min-coverage` of the credits | Usually credits spent on tables that were deleted since. The error shows the daily-series total (`series=`); you can quote that and say the breakdown is incomplete. Lower `--min-coverage` only if you accept a partial breakdown. |
| `DUPLICATE_CREDIT_TABLE_ID` / `DUPLICATE_CREDIT_INTEGRATION_ID` | An id appears twice in a report | Rerun; a duplicate would inflate coverage. |
| `FAILED_RECORD_FETCHES` | Some rows could not be read | Rerun. |
| `AI_TABLES_WITHOUT_UNFILTERED_VIEW` | An AI table has only filtered views | Add a view with no filter and no row limit to that table in Clay, then rerun. |
| `INCOMPLETE_RECORD_INVENTORY` / `*_DRIFT` | Row or table counts changed during the read | Something is running in the workspace. Rerun when it has finished. |
| `MODEL_RECONCILIATION_FAILED` | Totals by account, model, workbook, table or integration do not add up to the headline | Look at the failed rows in the error. Do not report the month. |
| `WORKSPACE_NOT_VISIBLE` | Your session cannot open that workspace | Check the id, or log in to Clay with an account that belongs to it. |

## Caveats

- **Fast mode can miss a table.** The default scope relies on a table's
  `updatedAt` and on the credit report. A table with AI columns on your own
  key, no Clay credits in the month and a stale `updatedAt` is not read. Run
  `--full-scan` from time to time, or add known tables with `--include-table`.
- **`--full-scan` is slow on a big workspace.** It reads every row of every
  table with an AI column, one record at a time, and reads table, schema and
  row inventories twice to prove nothing moved. On a workspace with hundreds
  of AI tables that can take hours.
- **Only the latest result per cell is stored.** If a cell was re-run, only
  the last run's cost is readable. Earlier runs cost money that no longer
  appears on any cell. The same goes for deleted tables and columns: their
  credits stay in the credit reports, their provider dollars are gone.
- **The gates only compare Clay's numbers with each other.** Before you
  quote them, check `credits` against the usage page in Clay and
  `provider_usd` against your provider's billing page.
- **Clay's internal API is unofficial.** The credit-reporting endpoints are
  undocumented. If Clay changes them, the audit fails with an error code
  instead of guessing.
