# ClayLens

ClayLens is Rex's companion Chrome extension. It adds a cost-analytics dashboard to `app.clay.com` tables and uses your live Clay session, so there is no auth to set up. It runs the same cost math as `clay_client.py`'s `get_cell_costs()` / `print_cost_report()`, live in the browser and with charts in place of a terminal report.

> **Unaffiliated with Clay. Install it with Load Unpacked. It is not on the Chrome Web Store.**

## What it does

Click the toolbar icon while you are on a Clay table. An analytics overlay opens with:

- **4 KPI cards:** total spend, credits used, rows analyzed, cost per success (with refunded and uncosted callouts)
- **Doughnut:** cost share by column (top 8 plus Other)
- **Bar:** cost distribution across columns
- **Columns table** you can sort and filter: name, model, runs, success%, errors, cost, $/run, p50, p95, share
- **Top 50 most expensive rows**, with a cell-level drill-down on click
- **CSV export** of the columns table

This folder contains the analytics dashboard only. The internal tool it was ported from also had schema-clone, template and verify modules. They are left out because they were not wired into the UI and depended on private pipeline conventions that do not belong in a public repo.

## Install (Load Unpacked)

1. Open `chrome://extensions`.
2. Enable **Developer mode** (top right).
3. Click **Load unpacked** and pick this folder (`rex/claylens/`).
4. Pin the extension to your toolbar (puzzle icon, then pin).
5. Open any Clay table (`https://app.clay.com/workspaces/.../tables/t_xxx`).
6. Click the ClayLens icon. The analytics dashboard opens.

After you install it, refresh any Clay tabs that were already open, once, so the content script attaches. Chrome does not inject content scripts into tabs that were open before the install.

## How costs are computed

ClayLens reads the actual cost data from each cell's payload. The one estimate is the dollar value of Clay credits, which uses a fixed rate.

- **LLM cost (`total_cost_usd`)**: from `cell.externalContent.fullValue.totalCostToAIProvider` (Claygent uses `costDetails.totalCostToAIProvider`).
- **Clay credits**: prefers `cell.externalContent.upfrontCreditUsage.totalCost` (Clay's own figure) over the lookup table in `lib/provider-costs.js`. Find People and Find Companies are set to 0 credits.
- **Effective $ per cell** = LLM cost + (credits × $0.014). The credit conversion uses a fixed rate, so this dollar figure is an estimate. The dashboard also shows credits on their own, in Clay's unit, next to the dollars; judge the two separately.
- **Refunded cells** are subtracted from `net_cost_usd` and shown separately in the totals card.
- **Uncosted cells** (the cell ran, but there is no cost data and no known actionKey) are flagged in the totals card. They are never counted as zero without a flag.

> **IMPORTANT:** Some entries in `lib/provider-costs.js` are marked `source: "guess"`. Check the per-action $ in Clay's UI before you rely on those numbers for anything client-facing.

## Architecture

```
manifest.json         MV3
content.js             Detects table context (workspaceId/tableId/viewId) from URL
background.js          Service worker: message router + bulk-fetch driver + IndexedDB cache
analytics.html/js       Dashboard UI
styles.css              Dark theme matching Clay
vendor/chart.umd.min.js Chart.js v4.4.0

lib/
├── clay-api.js           Single source of truth for api.clay.com/v3 traffic
├── cost-extractor.js     Per-cell cost field extraction (same semantics as ../../clay_costs.py)
├── model-prices.js       LLM model price catalog
├── provider-costs.js     Clay actionKey → credit cost
├── column-classifier.js  Heuristic classifier for AI columns (copy/research/classification)
└── aggregator.js         Pure aggregation: totals, byColumn, byRow, top-50
```

## Data flow

```
analytics.js  ──{action: 'analyze'}──►  background.js
                                            │
                                            ├─ getTable(tableId)               → field configs
                                            ├─ getRecordIds(tableId, viewId)   → record IDs
                                            ├─ fetchRecordsParallel (per-record GET, 20 workers)
                                            │      │
                                            │      └─ for each cell: extractCostFields()
                                            │
                                            ├─ aggregate(allCells, columnMeta) → totals + byColumn + byRow
                                            ├─ cacheExtraction (IndexedDB, keyed by workspaceId:tableId, 1h TTL)
                                            │
                                            └─ broadcast 'analyzeProgress' after each batch
                                            └─ respond {ok: true, extraction}  (byRow stripped from the wire payload; it stays in IndexedDB)
                                                          │
                                                          ▼
                                                   analytics.js renders
```

## Performance

- Analyze on a 200-row table: ~2s.
- Analyze on a 5,000-row table: ~15s (5 AI columns, 20-worker per-record fetch).
- IndexedDB cache: a reload that hits the cache returns instantly. Entries are marked stale after 30min and expire after 1h.
- A `chrome.alarms` heartbeat keeps the service worker alive during long analyzes on very large tables. Without it, MV3 workers terminate after ~30s idle, which would drop a big run without any error.
- If you click again or refocus the tab while an analyze is running, ClayLens joins the run in progress and does not start a second parallel fetch.

## Troubleshooting

**"Open a Clay table to begin".** The extension only activates on `https://app.clay.com/*` URLs with a `tables/t_xxx` segment.

**"Session expired".** Your Clay session cookie is gone. Refresh `app.clay.com` and try again. ClayLens uses your logged-in session and has no separate auth.

**Costs look wrong.** Check the `uncosted_cells` count in the totals card. If it is high, those are cells (often action columns) whose `actionKey` is not in `lib/provider-costs.js`. Add the entry there with `source: "guess"` after verifying in Clay's UI.

**429 rate-limit errors.** The background worker uses exponential backoff (250ms / 500ms / 1s, 3 retries). If you still hit limits on a huge table, lower `FETCH_WORKERS` in `background.js` (default 20).

## Known limitations

- ClayLens does not estimate costs for cells that have not run (token prediction). It only reports actual spend.
- Some Clay credit costs in `lib/provider-costs.js` are best guesses (marked `source: "guess"`). Check the per-call $ in the Clay UI before you rely on them for client-facing numbers.
- `pickViewId` matches "All rows" by exact string. If your view has a different name, it falls back to the first view, which may hold fewer records than the full table.
- There is no cross-table portfolio dashboard, no cost chart over time, and no recommendation of cheaper models.

## License

[MIT](../LICENSE), the same as the rest of Rex.
