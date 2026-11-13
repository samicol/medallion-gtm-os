# Clay table registry

Approved Clay tables, saved as portable table JSON exported from the live table after approval.
`design-clay-table-json` reads this list to find the closest working example for a new campaign.
`save-clay-schema` adds a row here when the owner approves a table.

Every file listed here is in the format `import-clay-table` imports, contains no rows, and passed a
dry-run re-import when it was saved. Read a schema to learn how a working table is built. Never copy
its names, filters or prompt text into a new campaign.

Until the first entry exists, start from
[`example.flow.json`](../../../.claude/skills/design-clay-table-json/references/example.flow.json)
(a fictional worked example in the `design-clay-table-json` skill).

## How to use it

1. Build and approve a table (`/campaign-contract` -> `/design-clay-table-json` -> `/import-clay-table`).
2. Run `/save-clay-schema`: it exports the live table to `schemas/<slug>.json` (no rows, auth accounts
   replaced by named bindings), dry-runs a re-import, and adds one row to the table below.
3. The next `/design-clay-table-json` run reads this file and starts from the closest schema of the same
   motion (`people-first`, `account-first` or `signal-first`).

The kit ships this registry empty on purpose. Schemas can contain your table names, filters and prompts:
keep them in your own private copy of the repo.

## Approved schemas

| Schema | Motion | Built for | What it shows | Approved |
|---|---|---|---|---|

## Seen but not approved

Tables worth remembering as warnings, with the reason they were not approved.

| Table | Why not approved |
|---|---|
