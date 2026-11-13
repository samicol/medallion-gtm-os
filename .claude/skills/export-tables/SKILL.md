---
name: export-tables
description: "Export one or more Clay tables to local CSV files. Use it when someone wants a Clay table's data on disk (for a backup, a hand-off or offline analysis), for one table or a short list of tables whose IDs they already know."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.

# Export Tables

This skill exports Clay tables to CSV and downloads them to a local
directory. It is a thin loop over the existing single-table export and does
not auto-discover "every table in a workspace", so pass the exact table IDs
you want exported.

## When to use this

- Someone hands you 2-10 specific table IDs and wants CSVs of all of them in
  one call instead of one at a time.
- You need the file on disk. The underlying Clay export API only returns a
  signed download URL; this method downloads the file from it.

## When NOT to use this

- "Export every table in my workspace": there is no auto-discovery here. Call
  `clay.list_tables()` yourself first, filter to the ones you actually want,
  then pass that list. Do not export an entire workspace without confirming
  which tables matter: most workspaces have staging and scratch tables mixed
  in with production ones.
- You need the full enrichment JSON from action columns. Native CSV export
  renders action columns as the literal string `"Response"`, so use
  `fetch_all_records_full()` for one table's raw JSON instead.

## How to run it

```python
from clay_client import ClayClient

clay = ClayClient()
results = clay.export_tables(
    ["t_abc123", "t_def456"],
    out_dir="./exports",
)
```

Each table gets `{out_dir}/{table_name}.csv` on disk (falls back to the raw
table ID as the filename if the name can't be read or isn't
filesystem-safe). `results` is `{table_id: "ok (N bytes) -> path"}` on
success or `{table_id: "error: ..."}` on failure. One failing table does not
abort the rest of the batch, so always check every value in `results`. The
call returning does not mean every table exported.

To export a filtered view of a specific table instead of the whole table,
pass `view_ids={table_id: view_id}`.

## Caveats

- This has no track record yet inside Rex. It is a simple loop over
  `export_csv()` plus a download step and has not been used heavily. Treat it
  as functional but unproven at scale, and watch the `results` dict for
  partial failures on large batches.
- Exporting many large tables sequentially can take a while, because
  `export_csv()` polls Clay's async export job per table before this method
  downloads it.
