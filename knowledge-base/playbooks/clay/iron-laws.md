# Clay Iron Laws

The non-negotiable rules we follow every time we work in Clay. These are the difference between a senior GTM engineer and a junior one, between a clean workflow and a clunky one.

Every rule is equally important. They are ordered meta-first, micro-later.

---

## Workspace & Organization

**1. Keep your workspace organized.** Folders > Workbooks > Tables. No loose tables floating around.

**2. One workbook = one workflow.** Be organized. Don't mix unrelated workflows in the same workbook.

**3. Follow the same naming convention in every step.** Tables, columns, enrichments: consistent naming across the board.

**4. 1 table = 1 data source.** Multiple data sources = multiple tables + 1 consolidated table. Mixing sources in one table makes it clunky.

**5. Accounts ≠ contacts.** Have tables for both. Run the enrichments you can on accounts first, then look up from contacts. This saves credits.

## Building & Testing

**6. When working on a new table, make sure the table is off.** Do not turn it on until you're happy with the outputs. Build in draft mode.

**7. When building enrichments, run them in batches of 10 rows until you're happy with the output.** Then run on the rest of the table. Never run a new enrichment on the full table blind.

**8. When duplicating tables, make sure you are using the same data source.** If not, the table will look like a mess. If you want to run the same enrichments on a different source, use template blocks vs duplicating the whole table.

## Enrichment Efficiency

**9. BYOK first, credits second.** Always check which enrichments we can run with our own API keys before burning Clay credits.

**10. Leverage data cache.** When working on a table, think about how you can get info by looking up into tables you already have vs using enrichments. Don't re-enrich what you already know.

**11. 1 Claygent run = 1 task.** Do not ask Claygent for multiple outputs in one run. Split into separate columns.

**12. Conditional runs > filters.** Make sure your enrichments have conditional formulas. Do not use filters to control data flow. Filters are for data visualization, not to avoid/enable enrichment runs.

## Data Hygiene

**13. Always dedupe.** No exceptions.

**14. Always check for multiple people from the same account in your table.** Make sure you're not including all of them in campaigns. That's a spam risk.

**15. Use checkboxes as checkpoints** to keep your data structured and track row progress through the workflow.

**16. Leverage lookups and sending data to other tables** as much as you want. Move data between tables freely to keep each table clean and purpose-driven.

## Reusability

**17. Save part of your workflows as templates you can re-utilize in other workflows.** This saves a ton of time and errors.

**18. Save enrichments as templates when you can.** Claygents, HTTP API calls, Sequencer pushes: anything reusable should be templated.
