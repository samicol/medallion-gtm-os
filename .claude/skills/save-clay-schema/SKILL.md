---
name: save-clay-schema
description: "Save an approved Clay table into the local table registry. It exports the live workbook (including manual edits made in Clay) as portable table JSON, proves it re-imports with a dry run, and adds one row to registry/INDEX.md. Use it when the owner approves a demo or campaign table ('approved', 'save this table to the registry'), or to backfill a table they name as approved. It only reads from Clay and does not approve anything itself."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.

# Save Clay Schema

This skill saves an approved table into the registry, so the next campaign can start from a table
that worked. `design-clay-table-json` reads the registry before writing any new table. An entry is
only useful if it is exactly what worked, so save the live table. Never save the JSON that was
imported: people fix things by hand in Clay after import, and those fixes are often why the table
was approved.

## When to run

Only after a person approved this table, in their own words ("approved", "ship it", "good, save
it"). A green check, a reviewer's pass or your own opinion does not count as approval. If you are unsure,
ask one question and wait.

## Steps

1. **Find the live workbook and its tables.** From the campaign's `run.md` or import receipt, or
   from Clay. Note each table's logical role in build order (`companies`, `people`, `jobs`) and
   its demo view id.

2. **Export.** Read-only; the export contains no rows.

   ```bash
   python3 .claude/skills/save-clay-schema/scripts/export_table_schema.py \
     --slug <campaign-in-words> --name "<campaign in plain words>" \
     --pattern <people-first|account-first|signal-first> --workbook <wb_id> \
     --table companies:<t_id>:<demo view id> --table people:<t_id>:<demo view id> \
     --out tools/rex/registry/schemas/<slug>.json
   ```

   Live ids become placeholders. Auth accounts become `${bindings.authAccounts.<name>}`, named
   after `rex-config.json`'s `authAccounts` when the id matches and `auth_1`, `auth_2`, ... when it
   does not. By default the source
   workspace, workbook, table, view and account ids are stripped, so a saved schema is safe to
   share. Pass `--keep-origin` to keep them under `origin`/`originId` for private use; never commit
   a schema saved that way to a public repo.
   Models stay as the table actually used them.

3. **Prove it re-imports.** The script dry-runs the export through the importer and prints
   `reimportDryRun` with any errors and warnings; a non-zero exit means the export does not
   re-import. Then open the file and check what a dry run cannot: the model on every AI column is
   the one the table used, the demo view is the `default_view` with `isAcceptedDemoView: true` and
   its columns in on-screen order, and no other campaign's name appears in any prompt.

4. **Add one row to `tools/rex/registry/INDEX.md`** under Approved schemas: a readable name linking the
   file, the motion and table count, what the campaign sold, what the table shows (sources, the
   judgment columns, how the copy is built), and who approved it and when. Write "what it shows"
   for the next agent choosing an example: name the patterns someone could learn from.

5. **Record it with the campaign.** In the campaign's `run.md`, add the approval (who, when, in
   which words) and the path of the saved schema.

6. **Commit only these files** (`tools/rex/registry/schemas/<slug>.json`, `tools/rex/registry/INDEX.md`, `run.md`)
   if the registry lives in a repository.

## Re-saving

If the table changes after approval and the change is also approved, export again to the same
path. The file is overwritten; do not add a second row for the same table.
