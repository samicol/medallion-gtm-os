---
name: calculate-costs
description: "Report the real dollar spend and Clay-credit usage of a Clay table's AI and action columns, read from the cost data Clay stores on each cell. Use it when someone asks what a Clay table cost, which columns are most expensive, which rows are outliers, or whether a batch run is affordable before scaling it up."
---

> **Starter-kit notes.** From the Rex v2.1 skill of the same name (MIT, see `tools/rex/LICENSE`). Path mapping for this repo:
> - Rex lives at `tools/rex/`. "Repository root" in this skill means `tools/rex/`. Run Python from there with its venv:
>   `cd tools/rex && .venv/bin/python ...` (`from clay_client import ClayClient` works from that folder).
> - Rex docs referenced below: `tools/rex/clay-api-reference.md`, `tools/rex/action-registry.md`, `tools/rex/GETTING_STARTED.md`.
> - Clay workspace: never guess a workspace id; read it from the Clay URL (`app.clay.com/workspaces/<workspace_id>/...`).
> - Read-only. Use only workspaces you are authorised to read; per-workspace AI keys belong to that workspace.

# Calculate Costs

This skill reports what a Clay table actually cost. Clay stores cost data on
every action-column cell: the dollar spend charged to the AI provider, plus any
Clay credits consumed. Rex reads
`cell.externalContent.fullValue.totalCostToAIProvider` and
`cell.externalContent.upfrontCreditUsage`, the same fields Clay's own billing
is built from, and turns them into a report. The provider dollars and the
credit counts are what Clay recorded, so you can report them as actual spend.
Any dollar figure that includes converted credits is an estimate (see below).

## When to use this

- Someone asks "how much did this table cost to run" or "what's this campaign
  spending on AI."
- Before scaling a batch run from N rows to all rows. Check the per-row cost
  on the sample first.
- A table feels expensive and you need to find which column is responsible.
- You need to flag rows that ran but produced no usable cost data
  (`uncosted` cells) before reporting a total. An uncosted cell means the cost
  data is missing. Do not count it as $0.

For a whole workspace over a month (credits by table and integration, AI
provider dollars by table, column and model), use `workspace-cost-audit`.

## How to run it

```python
from clay_client import ClayClient

clay = ClayClient()
summary = clay.print_cost_report(table_id)
```

This prints a terminal report (total spend, credits, cost by column, top-N
most expensive rows) and returns the same data as a dict:

```python
summary["totals"]["total_cost_usd"]       # provider $ plus credits at $0.014 (estimate)
summary["totals"]["total_credits"]        # Clay credits, in Clay's own unit
summary["totals"]["net_cost_usd"]         # after subtracting refunded cells
summary["totals"]["uncosted_cells"]       # ran, but no cost data AND no known
                                           # actionKey price; investigate before
                                           # trusting the total
summary["by_column"]                      # list, sorted by spend descending
summary["top_rows"]                       # 50 most expensive rows, with
                                           # per-cell breakdown
```

For lower-level control (a specific view, a subset of action columns, or the
raw per-cell data before aggregation), use `get_cell_costs(table_id, view_id,
field_ids)` directly and pass the result to `clay_costs.aggregate()` yourself.
Both live in `clay_client.py` / `clay_costs.py`.

## Reading the output

- **Provider dollars and Clay credits**: two different units. Provider
  dollars are what an AI column billed your own model provider key. Clay
  credits are what Clay-managed actions used: non-AI enrichment, and AI columns
  that run on a Clay-managed key (see "How AI columns are billed" in
  `clay-api-reference.md`). Judge each unit on its own.
- **`total_credits` and `total_cost_usd`**: every total (overall, per column,
  per row) carries both, side by side. `total_credits` is Clay's own unit.
  `total_cost_usd` is provider dollars plus those credits converted at the
  fixed rate `clay_costs.CLAY_CREDIT_USD` ($0.014 per credit). The conversion
  is an estimate, because your real price per credit depends on your Clay plan.
  Provider dollars alone are `total_cost_usd - total_credits * 0.014`. Quote
  credits in Clay's unit next to the dollar figure, and do not present the
  blended figure as the amount billed.
- **`share_pct` per column**: cost share of a column, out of total gross
  spend. Useful for "which column should I optimize first."
- **`p50_cost` / `p95_cost`**: provider-dollar cost percentiles across successful cells for
  that column. A wide gap between p50 and p95 means a few outlier rows are
  driving the average up. Inspect them individually via `top_rows`.

## Caveats: do not skip these

- Some entries in `clay_costs.PROVIDER_COSTS` are marked `source: "guess"`.
  These have not been screenshot-verified against Clay's UI. Before quoting a
  per-provider $/hit number to a client, check the entry's `source` field via
  `clay_costs.entry_for_action_key(action_key)`. If it says `"guess"`, verify
  in Clay's UI first.
- `uncosted_cells > 0` means real spend is being undercounted. Those cells
  were not free. Investigate before reporting a total as final. Usually an
  `actionKey` is not in `PROVIDER_COSTS` yet (add it), or Clay has no cost data
  for the cell.
- This only reports cost for cells that have already run. It does not
  estimate cost for un-run cells or predict a batch's price before running it.
