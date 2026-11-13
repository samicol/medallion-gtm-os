---
name: build-clay
description: "Build, audit, repair, or materially extend a production Clay outbound workbook: a Companies table, two people-sourcing paths (Find People and Claygent), and one shared People table. Use for requests such as /build-clay, 'build the workbook for this segment', 'audit this Clay table', 'is this table clean', or 'set up Companies and People in Clay'. It shows how to turn approved segment and persona logic into a gated pipeline for enrichment, qualification, prospecting, routing, and copy, how to keep real source lineage, how to bind nested source and action data directly, and how to prove each action on one real record before running it at scale."
---

> **Starter-kit notes.** Based on the `build-clay` skill that ships with Rex v2.1 (MIT, see `tools/rex/LICENSE`), plus the
> additions documented in `tools/rex/README.md` > "Additions beyond upstream v2.1". Path mapping for this repo:
> - Rex lives at `tools/rex/`. "Repository root" in this skill means `tools/rex/`. Run Python from there with its venv:
>   `cd tools/rex && .venv/bin/python ...` (`from clay_client import ClayClient` works from that folder).
> - Rex docs referenced below: `tools/rex/clay-api-reference.md`, `tools/rex/action-registry.md`, `tools/rex/GETTING_STARTED.md`.
> - Clay workspace: never guess a workspace id; read it from the Clay URL (`app.clay.com/workspaces/<workspace_id>/...`) and pass `workspace_id=` explicitly.
> - Sibling skills this one links to (`prompt-builder`, `design-clay-table-json`, `save-clay-schema`, `import-clay-table`) live next to it in `.claude/skills/`. `registry/` means `tools/rex/registry/`.
> - Company context (ICP, positioning, messaging) lives in `context/`; the campaign's workflow spec and build notes live in `output/campaigns/<workflow-slug>/`.
> - **Clay playbooks:** [`expert.md`](../../../knowledge-base/playbooks/clay/expert.md) (deep Clay reference), [`formulas.md`](../../../knowledge-base/playbooks/clay/formulas.md) (formula patterns) and [`iron-laws.md`](../../../knowledge-base/playbooks/clay/iron-laws.md) (non-negotiable build rules) in `knowledge-base/playbooks/clay/`.
> - **Learnings loop (mandatory):** read `tools/rex/LEARNINGS.md` (backlog + recent entries) before starting; log every new Clay/Rex gotcha there the moment it's found; follow its improvement rule (promote to Rex code/test/skill/docs, track in the backlog). Report OPEN backlog rows at the end of the build.
> - **Cost reference (read before any spend decision):** `knowledge-base/playbooks/clay/actions-data-credits.md` (summary table in
>   `tools/rex/README.md` > "What costs Clay actions and credits"). Search imports, Send table data, lookups and formulas
>   are free; provider enrichments and AI columns cost 1 action per row. Never assert a cost from memory.
> - **Starter-kit overrides (win over this skill where they conflict).** "The operator" below means the human running the build:
>   1. **No Use AI / Claygent at scale inside Clay** by default. Prove the column on 1-2 real rows in Clay, then replicate the prompt as a local LLM call and write results back with `ClayClient.update_records()` (bulk PATCH). Never use `update_record()` (singular PATCH has been seen to silently no-op). Scale runs inside Clay need the operator's explicit OK with a USD estimate.
>   2. **Clay deletes are permanent (no API undelete).** The cleanup steps below (remove losing actions, junk formulas, duplicate tables) require listing exactly what will be deleted and getting the operator's confirmation first. Once leads are in your sequencer, "remove" means detach them there, not delete Clay rows.
>   3. Use `export_schema()` (not `get_schema()`, which hides formulas) to read a table before any write.
>   3b. This Rex CAN create views (upstream can't): use `clay.create_view(...)` / `set_view_filter(...)` with `view_filter()` items (see `tools/rex/README.md` "Additions beyond upstream v2.1") for the qualified-Companies view and operator views instead of repurposing preset views.
>   3c. **AI columns (Rex guards, LEARNINGS #1-#3):** when cloning an AI column always pass `use_case=` (`"use-ai"` for anything that only works on row data; `"claygent"` only for live web research); Rex refuses a Claygent clone without it. Build every extraction formula with `clay.create_ai_extraction_column()` / `ai_extract_formula()` (casing-tolerant), never a hand-typed `?.camelKey`. Prove each AI column with `clay.verify_ai_column(tid, f_ai, [2-3 record ids])` and require `ok: True` before scaling; never judge it by the action cell's `"Response"` value.
>   3d. **Lineage stays visible (LEARNINGS #19):** action columns (lookups, enrichments, Send table data) and source columns (incl. "Rows from: <table>" on a Send-table-data target) stay VISIBLE in the clean/default view; only formula/plain helpers may be hidden. `set_view_columns()` / `create_view(visible_field_ids=...)` refuse to hide them; `allow_hide_actions=True` only with the operator's OK. Give each table a description and colour its column groups (`create_field_group(..., color=)`, per-view).
>   3f. **Every formula carries its plain-English prompt (LEARNINGS #86):** `create_formula_column(..., prompt=["True if ", "[Verdict]", " is \"GTG\""])` and `update_column(..., {'typeSettings': {'formulaText': ..., 'formulaPrompt': [...]}})`; Rex refuses a formula without one, or one that doesn't name every column the formula uses. In audit mode run `clay.audit_formula_prompts(table)` and fix every `stale` row.
>   3e. **Waterfalls are native (LEARNINGS #25):** any enrichment waterfall (work email, phone, ...) is ONE Clay native waterfall group with one merged column and one group-level run condition, built with `clay.create_waterfall_from_template(table, 'templates/waterfall-work-email.json', inputs={'FULL_NAME':..., 'COMPANY_DOMAIN':..., 'COMPANY_NAME':..., 'LINKEDIN_URL':...}, condition=...)` (the saved example: Prospeo → LeadMagic → Icypeas → Findymail → Wiza → FullEnrich, LeadMagic validation per step; LeadMagic step validation is created by the same call via the template's `validationActionConfig`, read back, and kept by `update_waterfall()`). Set the template's `authAccountId`s to your own connections first (`clay.list_auth_accounts()`). A sensible default: your own-key providers first, then Clay-credit providers; 4 steps by default, a 5th only if asked. **Validation: one validator on the waterfall, a second verifier on the results.** Conservative, no catch-all, run as button. Never chain provider columns by hand. Never run it without the operator's go-ahead.
>   4. **Type routed identity columns, never leave them as Clay's default text.** `Send table data`
>      auto-extracts every routed column as `formula` / `dataTypeSettings.type: "text"`. Before any
>      enrichment, retype identity columns to match the proven build: company domain -> `url`,
>      personal LinkedIn -> `url` (name it `LinkedIn Profile`), resolved email -> `email`. Text-typed
>      identity columns are accepted at creation and then fail or mis-handle downstream at
>      `Enrich Person`, LinkedIn scrapers and some email finders, and they lose UI click-through and
>      format validation, so a malformed row only surfaces when an action errors. In a proven
>      people table, `Company Domain` and `LinkedIn Profile` are typed `url` and the resolved email
>      `email`. Retyping is reversible and preserves the formula:
>      `clay.update_column(tid, fid, {"typeSettings": {"dataTypeSettings": {"type": "url"}}})`.
>      A bare hostname is NOT coerced to `https://` by the url type (verified 2026-09-24), so
>      domain matching is unaffected.
>   4b. **Where action-heavy work runs depends on the workspace's billing plan (LEARNINGS #35).**
>      Check `clay.billing_model(table_id)` before proposing a build. **`legacy`** (the old plan)
>      consumes NO Clay actions, so run action-heavy columns (HTTP API to your own endpoints, own-key enrichments,
>      provider enrichments) INSIDE Clay for lineage. Lookups, Send table data, search imports and formulas are free on
>      BOTH plans (0 actions), so never cost them or move them out of Clay. **`actions`** (new plan, 1 action per row per run): for anything that burns
>      actions at scale, propose running it OUTSIDE Clay and writing results back to a column with `update_records()`.
>      **`unknown`**: ask the operator which plan the workspace is on, then add it to `WORKSPACE_BILLING` in `clay_client.py`.
>      Data credits still apply on both plans (Clay-key providers, Clay-billed AI), and override #1 (no Use AI/Claygent at
>      scale) still stands regardless of plan.
>   4c. **Derived tables keep lineage (LEARNINGS #15):** a table derived from another (Companies-from-People,
>      People-from-Companies) is built with a Send table data column (`create_route_row_column`) plus a destination dedupe
>      key, never by writing rows with `create_records()`: API-written rows show nobody how the table was built. **Rex enforces this in code** (backlog #48): `create_records()` refuses more than 2 rows per call unless `allow_bulk_api_rows=True`, and you pass that flag **only when the operator expressly asks** for an API import in this conversation, or for data with no Clay origin. A 2-row test of a new table is allowed. Prove the
>      route on 1 row first. Writing rows is fine only for an external source that has no Clay origin (e.g. a sequencer/CSV
>      pull), and the table description then names the file it came from.
>   4c2. **Domain and link columns are clickable (LEARNINGS #54):** every column holding a domain,
>      website, LinkedIn or other URL gets data type `url` (email columns `email`), whether it is a formula, text input or
>      routed column. `create_formula_column()` now infers it from the name (`guess_column_data_type`); for text columns pass
>      `dataTypeSettings: {type: "url"}`. After a build, sweep every table for link-named columns still typed `text`.
>   4d. **One satellite table per question, one source per scope (LEARNINGS #33):** when several searches answer the same
>      question, add them to ONE table with `clay.add_search_dsl_source(table_id, query)`, and call
>      `clay.set_table_dedupe(table_id, <LinkedIn Profile field>)` BEFORE the second source (sources never dedupe each other).
>      People tables that need company keys: `send_search_dsl_to_table(..., extra_columns=["company_domain", "start_date"])`.
>      `update_and_run_search_dsl_source(mode="replace")` is refused on a table holding text/action columns (LEARNINGS #9).
>   4e. **Folders + workbook guide (LEARNINGS #26, #34, #37):** put each workflow's workbook in its folder
>      (`clay.create_folder(name)` then `clay.create_table(name, folder_id=...)`), and write the workbook guide with
>      `clay.set_workbook_description(workbook_id, text)`: that is where Clay shows it (a table description is not).
>   4f. **Search DSL scoping (LEARNINGS #13, #16, #25, #32):** Rex validates every query (`validate_dsl_query`): company_size
>      must be one of `COMPANY_SIZE_BUCKETS` (`"501-1,000"`, not `"501-1000"`), and only `domain` / `company.domain`
>      filter a company (no LinkedIn / id / name key). Scoping by a company list: run `clay.compare_dsl_scopes(where, domains,
>      "t:v:f")` first and choose the domain list or target-companies scope from its diff. Resolving many domains to Clay
>      companies: `clay.lookup_companies_by_domain(domains, <scratch workbook>)` (one free import) and use its `best` pick,
>      never the first match (one domain maps to dozens of entities).
>   4g. **Audit mode adds three readers:** `clay.describe_columns(tid)` (shows waterfall formula branches, which have no
>      `formulaText`), `clay.audit_formula_labels(tid)` (English condition label vs the condition that runs) and
>      `clay.audit_route_condition(tid, route_field)` (re-evaluates a Send table data rule over every row: routed but now
>      ineligible / eligible but never routed). A clean audit reports all three.
>   4h. **Rate-limited or flaky action columns run paced (LEARNINGS #36):** `clay.run_paced(tid, field, record_ids)` runs in
>      batches, reads every cell back, retries only plain `ERROR` cells with backoff and reports rate-limited counts. New formulas: Rex refuses
>      `new Set` / spread syntax (Clay returns EMPTY silently, LEARNINGS #35); still prove each on one known-positive row.
>   5. Log each proven column/run in `work-log/` (timestamped) as it completes, and keep the campaign's build notes in `output/campaigns/<workflow-slug>/`.
>   6. Segment/persona approval comes from the approved workflow spec in `output/campaigns/<workflow-slug>/` (see `/build-workflow-spec`). References in this skill to a specific agency or sample campaign are illustrative; ignore them.

# Build Clay

Use this skill to build one production workbook that an operator can understand, run, and
debug without knowing how it was created. Build the smallest complete production surface.
The Companies table decides which accounts belong in the campaign and why. Two independent
sourcing paths find current, relevant people at those accounts. One shared People table is
the only place where downstream enrichment, qualification, and copy happen. A table full of
data, or a schema that Clay accepts, does not meet that bar on its own.

The job mixes procedure, judgment, and Clay tooling. Follow the dependency order, but plan
from the campaign decision backward. For each stage, work out what decision the next stage
must make, which evidence makes that decision safe, and the cheapest reliable way to get
that evidence.

The same method works in two modes. In build mode you create or extend the workbook. In
audit mode you read an existing workbook and report, with evidence, where it departs from
this method: missing source lineage, junk formulas, prompts without a native schema, gates
in the wrong order, duplicated decisions, and unreconciled runs.

## Read the package

Read these files completely for every production build, repair, or audit:

- `references/build-session-goal.md`: execution behavior, the campaign manifest,
  anti-satisficing rules, and the definition of done;
- `references/column-playbook.md`: what belongs in each table;
- `references/technical-recipes.md`: how the recurring Clay components are wired and proven.

Also read Rex's `clay-api-reference.md` and `action-registry.md` at the repository root.
They hold the internal API shapes, action keys, package IDs, and known gotchas. Treat the
three references and the two Rex docs as one required package. Never claim
that a file was read unless you actually opened it in this session.

At the start of a building session, fill the placeholders in
`references/build-session-goal.md` and keep that manifest current as the session's working
memory. If a planning task becomes a building task, explicitly change the mode to `BUILD`,
restate the authorized mutations and spend, and then follow the building completion
contract.

## The table is the campaign made visible

A good workbook reads as the campaign's logic laid out in columns. An operator scanning a
row from left to right should see why this account is in or out, what evidence supported
that decision, why this person was chosen, and what happens next. Column order follows
causal order: source, identity, evidence, decision, permitted action.

This is the model of trust behind every rule below. Each trustworthy column removes
research, comparison, or judgment work from a human. Each column the operator cannot
explain adds supervision instead. When a table forces someone to re-research or re-decide
rows by hand, or to reconstruct the build history before trusting a value, it is not
finished, however complete it looks.

## Establish the build before touching Clay

Start from an approved client and segment definition: target company type, geography, size,
qualification and disqualification logic, persona titles including local-language variants,
title exclusions, and the intended campaign destination. The approved segment definition is
the authorization to build. Do not invent missing segment or persona logic in order to
produce a complete-looking table.

Local-language title variants must come from the approved brief or explicit title research.
Never translate or expand titles from memory. Likewise, do not invent a scoring scale,
status vocabulary, or threshold that the approved segment does not define.

Know where the workbook belongs and which model accounts belong to the client. Every AI
provider used in the build needs an account owned by the same client or explicitly approved
for that scope. Never borrow another client's account.

First decide whether an operation needs a model. Deterministic selection, binding,
deduplication, suppression and routing use no model. For live reconstruction, record the
model and account actually bound without rewriting history. For a new or repaired AI action,
choose the model per operation from the task, required output, quality, cost, speed, tool
capability, client account and available evidence. A proven model may default only for a
materially similar operation, never globally. If no comparison proves the choice, record it
as a hypothesis and run the smallest later canary before scale. Verify live account support
before spend and name the action after the model actually bound.

All Clay work goes through Rex's Python client:

```python
from clay_client import ClayClient

clay = ClayClient()
clay.me()  # proves the session cookie is valid before anything else
```

Before you build a complex action, look for a known-good live column that already does the
same job, in this workbook or another one you trust. When one exists, copy it with
`clay.clone_column(...)` and override only the named inputs (for example the prompt) and
the run condition. Do not rebuild an action payload from memory. A hand-assembled AI
payload is the most common way to create a column that looks right and never runs.

When the build needs a new or adapted AI prompt, author it with the sibling `prompt-builder`
skill ([`prompt-builder`](../prompt-builder/SKILL.md)) rather than drafting directly inside Clay. It
covers both a new prompt from a spec and the repair of an existing prompt. If you keep a
library of approved prompts, search it first: reuse an approved prompt when it fits, adapt
the nearest one when it is close, and write a new one only when nothing suitable exists.
The library tells you where a prompt came from; `prompt-builder` covers how to write it.

Before a write, prove the session, workspace, destination, and model accounts with live
reads (`clay.me()`, `clay.list_auth_accounts()`, `clay.get_table(table_id)`). Before a paid
run, check the model-provider billing state and any non-AI Clay-credit balance separately.
A missing mandated table is a blocker. Do not silently recreate it.

## Design the workbook as a dependency chain

Treat the table as a directed graph. Source fields and operator inputs are roots. Each
enrichment should produce one coherent unit of evidence for a later decision. Cheap,
deterministic gates should stop rows before expensive research. Qualification should consume
the evidence already collected. It should not browse again or infer what an upstream action
should have established.

Avoid the one-column shortcut in which a single large prompt receives a company
name and domain, researches everything, decides fit, and writes copy. It is difficult to
debug, impossible to gate economically, and hides whether the failure came from identity,
evidence, qualification, or copy. A good pipeline makes those boundaries visible without
turning every minor field into a separate action.

Build the smallest complete production surface. Add a column only when a later production
decision or operator action needs it. Do not carry a column over just because a previous
table had it.
Do not add diagnostic scores, statuses, helper actions, or extra views unless a named
downstream decision or operator workflow uses them. Keep sourcing tables as thin staging
surfaces. They discover and route people; the shared People table owns everything after
discovery.

### Prove source lineage before judging cleanliness

A People table can be full of rows and still have no source. Every person row must descend from
a real Clay source field: a Find People source or a routing source created by `Send table
data`. A plain text `Source` or `Prospecting Source` label does not prove lineage. Neither do
plain text identity fields on records inserted directly into the table.

Before counting columns or reviewing copy, inspect the live schema and rows:

1. Find every field whose type is `source` (`clay.get_source_field_id(table_id)` returns
   the main one; read the full table object to find all of them).
2. Read its source IDs and the configuration behind each source.
3. Confirm that Find People and Claygent routing sources target the intended shared People
   table.
4. Reconcile the live row distribution by source.
5. Trace one real destination row from every source back to its origin.

When two discovery paths converge, they may feed the same shared People source field through
two source IDs. Preserve an operator-readable source label inside the routed payload, but
do not mistake that label for the source itself. If a People table has no source field, call
the architecture unsourced and reject it as a reusable production pattern even when the
rows look plausible.

### Bind nested outputs directly

Source, lookup, webhook, and action cells are structured objects. Downstream prompts and
actions should reference the required nested property directly from that object. They may
also receive the entire structured object when that is the safer contract. Do not create a
formula column merely to copy or extract one nested property for another prompt or action.

Examples of junk wiring include a `Prompt Content` formula that only copies a webhook key,
one formula per webhook key, and formula copies of AI verdict fields used only by the next
action. Replace them with direct nested bindings from the source or action object.

Use native action output mapping or a mapped result path when an operator needs a
scalar value as a visible business output. Use formulas only when the formula performs real
deterministic logic: deduplication, a gate, ranking, suppression, normalization, or merging
multiple provider results. A formula that disappears without changing business logic after
the downstream binding points at the original nested value is a junk formula.

Two kinds of single-field formula are required. First, a formula that carries an
AI answer to another table: only formula columns cross a Clay lookup, so a People row can read a
company verdict only through a formula on the Companies table. Second, a formula that shows an
AI answer in the demo view, next to the AI column that produced it (see
[`design-clay-table-json`](../design-clay-table-json/SKILL.md)). The junk rule is for formulas
that copy a field nobody downstream needs: no other table reads it, no view shows it, and a
consumer in the same table could bind the nested value directly.

Do not classify formulas from their names or total count. Read each formula body, its inputs,
and every downstream consumer. Classify it as business logic, convenience extraction,
duplicate logic, or dead logic. Compare normalized formula bodies to catch exact duplicates,
then inspect their consumers before deciding which one can go. Employment logic deserves
this check explicitly: two differently named columns that implement the same current-role
test are one duplicated gate. They do not give you two independent controls. Any formula
still deciding current employment is stale by definition, because that decision belongs to
an action.
Report the evidence for every formula proposed for removal; never infer that all formulas
in a table are junk.

Cleanliness has two layers. The default view must be readable for the operator, and the
physical dependency graph must also be lean. Hiding convenience formulas does not make the
underlying table clean.

### Give every AI prompt a native JSON Schema

Every Claygent or Use AI action that contains a prompt must have a native JSON Schema
configured in the action's `answerSchemaType`. This is true even when the prompt returns one
short value or one message. A prompt instruction such as `return JSON`, generic JSON mode,
or Clay's loose field map is not a schema. See `clay-api-reference.md` for the exact
`answerSchemaType` encoding; it is easy to get wrong by hand, which is one more reason to
clone a known-good column.

Design the smallest schema that fully describes the promised output. Name only fields the
action actually owns, constrain closed vocabularies with enums, require every field needed
downstream, and set `additionalProperties: false` unless an approved contract needs
extensibility. Every field needs a named approved operator use or downstream consumer;
a technically valid schema does not justify a duplicate status, unused score, diagnostic
label, or invented vocabulary. Bind downstream conditions and prompts to the exact retained
schema paths. If the approved decision, prompt, schema, and downstream references disagree,
the action is not production ready. Repair that contract atomically: change the prompt
promise, native JSON Schema, and every affected downstream path together. A schema-only
repair that leaves the prompt promising removed fields is still broken.

For a single-field current-employment decision (`Still Employed?`), a good contract is an
object with required `response`, enum `YES | NO | REVIEW`, and no additional properties. A plausible-looking bad
version asks the model to return `{"response":"YES"}` but configures only a free-text
`response` field or JSON mode. The bad version can emit a typo, a new label, or malformed
shape while still looking structured in the cell; downstream truthiness checks can then run
on `NO` or `REVIEW`.

When auditing an existing workbook, enumerate every prompt-bearing AI action and read its
live `answerSchemaType`. Missing JSON Schema, invalid JSON Schema, prompt-schema mismatch,
or a downstream path absent from the schema is a production defect. Repair the contract
before another paid run. A schema repair does not retroactively validate old cells: inspect
existing outputs separately and decide explicitly whether to preserve, clear, or rerun them.

## Build and prove one column at a time

Create columns in dependency order. `clay.create_table(...)` leaves auto-run off by default;
keep it off until the whole chain is proven. For each action column:

1. Create or clone the action with its production run condition already attached
   (`clay.clone_column(..., condition=...)`, or `clay.set_condition(...)` right after
   creation).
2. Read the created column back with `clay.get_column(table_id, field_id)`. Confirm the
   action, mode, model, account, prompt, native JSON Schema, run condition, and every input
   binding.
3. Run it on one real eligible record with
   `clay.run_and_wait(table_id, [field_id], [record_id])`.
4. Open the actual cell and read the value, full value, confidence, and status. HTTP success,
   preview records, and a plausible prompt do not prove the action worked.
5. If the cell is wrong, repair the source prompt, binding, schema, condition, or reference
   with `clay.update_column(...)` and repeat on the same record.
6. Only after the cell is right, run the explicit eligible record IDs and reconcile run
   status against the eligible population.

The campaign pipeline's `import-clay-table` applies the stricter version of the same rule: it
proves every paid column on one row that should qualify and one that should be rejected before
running the rest.

```python
field = clay.clone_column(
    source_table_id="t_xxx",          # a known-good table
    source_field_id="f_xxx",          # a known-good AI column in it
    table_id=companies_table_id,
    name="Company Fit Qualification / Use AI / <Model>",
    input_overrides={"prompt": prompt_text},
    condition=gate_formula,
)
field_id = field["id"]

print(clay.get_column(companies_table_id, field_id))   # read back before running

[rec] = clay.run_and_wait(companies_table_id, [field_id], [one_record_id])
cell = rec["cells"][field_id]
print(cell.get("metadata", {}).get("status"), cell.get("value"))
```

`AWAITING_CALLBACK` is in flight. A processed-versus-eligible gap is a finding. Do not
delete rows to make a broken column look successful.

## Name the operator surface

Use these names:

- Workbook: `<Client> | <Segment> | <YYYY-MM-DD>`
- Companies table: `Companies | <Segment> | <YYYY-MM-DD>`
- Find People staging table: `People Source | Find People | <Segment> | <YYYY-MM-DD>`
- People table: `People | <Segment> | <YYYY-MM-DD>`

Name AI actions so the operator can see what the action does and how it runs:

`<Application> / <Claygent | Use AI> / [Run N] / <Model>`

Use `Run N` only when the same application has a real sequence or fallback. Do not call a
single action `Run 1` when no second run exists.

Good action names (the model names are illustrative; use the model actually bound):

- `Company Location & Employees / Claygent / Run 1 / <Model>`
- `Company Website Evidence / Claygent / Run 2 / <Model>`
- `Company Fit Qualification / Use AI / <Model>`
- `Contact Qualification / Use AI / <Model>`
- `Email 1 / Use AI / <Model>`
- `LinkedIn Messages 1-2 / Use AI / <Model>`

Name business outputs plainly: `Company Employee Count`, `Company Country`,
`Qualification`, `First Name`, `Job Title`, `Still Employed?`. Add an output such as
`Fit Score` only when the approved downstream logic actually uses it. Keep prompt versions,
experiment labels, timestamps, agent notes, and batch names in your prompt library or build
log. Keep them out of production column names.

## Worked example: company qualification

If you have a known-good Companies table that follows this pattern, read it as a component
reference. Do not clone it as a whole:

`https://app.clay.com/workspaces/<workspace_id>/workbooks/<workbook_id>/tables/<table_id>/views/<view_id>`

The useful architecture is:

```text
Find Companies
  -> source and action outputs referenced directly where possible
  -> LinkedIn location and employee count
  -> fallback research when the first result is missing, failed, or low-confidence
  -> canonical location and employee count
  -> country and region normalization
  -> deterministic segment-size gate
  -> official website evidence
  -> fallback website research when needed
  -> company fit qualification
  -> clean verdict outputs
  -> Find People staging source for the qualified company view
  -> Claygent people discovery on the same qualified companies
  -> both sources route into the shared People table
```

With Rex, the Companies table usually starts from
`clay.create_find_companies_source(workbook_id, table_name, inputs)`, which returns the new
`tableId`, `viewId`, `workbookId`, and `sourceId`.

Build the component like this:

- `Company Location & Employees / Claygent / Run 1 / <Model>` receives the company
  LinkedIn URL and returns structured `employeeCount` and `location`.
- `Company Location & Employees / Claygent / Run 2 / <Model>` receives the same URL and
  runs only when Run 1 is missing, failed, or low-confidence. When Run 2 returns a usable
  value, the canonical `Company Location` and `Company Employee Count` prefer it over the
  weak Run 1 result.
- `Company Country & Region / Use AI / <Model>` receives the canonical `Company Location`,
  instead of the weaker raw source location, and returns the full country and region.
- `Employee Count Qualification` is deterministic segment logic. Take its band from the
  approved segment. This example does not set one.
- `Company Website Evidence / Claygent / Run 1 / <Model>` receives company name, domain,
  and LinkedIn URL after the cheap gate passes. It collects neutral evidence from the
  official site: identity, offering, concise evidence atoms, source URLs, missing evidence,
  and confidence. It does not decide fit or write outreach.
- `Company Website Evidence / Claygent / Run 2 / <Model>` repeats that job only when the
  first result is missing, failed, or low-confidence. Put Run 1 and Run 2 in one visible
  column group (`clay.create_field_group(table_id, [run_1_id, run_2_id], "Website Scrape")`)
  so the operator sees one component.
- `Company Fit Qualification / Use AI / <Model>` consumes source firmographics, canonical
  geography and employee count, the deterministic gate, and website evidence. It does not
  browse. It returns the approved qualification verdict, evidence-backed reasons, and
  confidence. Include a fit score, positive-signal list, or separate disqualification
  taxonomy only when an approved downstream decision uses that field.
- Keep the structured qualification object when it is the safest handoff to People.
  Downstream prompts and routes should reference its nested verdict and reasons directly.
  Surface a scalar result natively only when an operator workflow needs to scan,
  filter, or route by it. Do not create formula extractors merely because the action
  returned structured data. The exceptions are the formulas that carry the verdict into People
  through the lookup, or show it in the demo view; those are required.

The important judgment is the separation of evidence from verdict. Website research should
describe what the official source supports. Qualification should decide whether that
evidence meets the approved segment. Combining both jobs makes the verdict harder to audit
and encourages the research action to find evidence that confirms its own conclusion.

### Good versus bad company qualification

A good build uses the enriched canonical location as the geography input, prefers a usable
fallback over a weak first run, and lets a cheap employee gate stop expensive website
research. The final qualifier receives named evidence fields and has one job: apply the
approved fit logic.

A plausible-looking bad build binds country normalization to the raw source `Location` even
though `Company Location` was just researched; runs a fallback but combines outputs as
`Run 1 || Run 2`, which silently keeps the weak first result; triggers Run 2 only when a
confidence string equals `low`, leaving blank and failed results uncovered; and leaves
several timestamped copies of the People trigger in the production table. Every action can
return HTTP 200 while the pipeline remains wrong. This is why prompt and input matching,
cell readback, and final cleanup are part of the build itself.

## Worked example: dual-source people prospecting

Suppose the approved campaign targets finance leaders at mid-market logistics companies.
Qualified Companies feed two independent discovery paths, and both converge on one People
table:

```text
Qualified Companies
  -> Source 1: Find People staging table
  -> Source 2: People Search / Claygent on the company row
  -> Send table data from both sources
  -> one shared People table
  -> canonical person and company identity
  -> deduplication and source provenance
  -> LinkedIn Experiences / Claygent
  -> Enrich Person only as fallback
  -> Still Employed?
  -> one Company Table Data lookup
  -> Contact Qualification
  -> campaign-required copy
  -> campaign-required validation or delivery actions
```

The second path is a people-search Claygent followed by `Send table data`. The Claygent
returns a structured `contacts[]` array. `Send table data` uses action key `route-row`,
method `list`, the contacts array as `listData`, company fields as parent `rowData`, and the
run condition `contacts.length > 0`. Clay creates one destination row per contact and keeps
the company data under the parent object. In Rex this is
`clay.create_route_row_column(table_id, name, target_table_id, row_data, condition=...,
list_data=...)`.

If you reuse a people-search Claygent from an earlier campaign, treat it as a component
reference. Do not copy the prompt word for word. Its title bank, exact-match rules, contact cap,
and output fields were written for that campaign's persona. A prompt tuned for finance
leaders will quietly miss or misjudge people when pasted into a campaign aimed at, say,
operations leaders.

Build the shared People table first as the destination for both routes. It is not itself the
Find People source table. The real routing source field is the root. Keep identity,
company, evidence, and provenance in the routed source payload and bind its nested
properties directly downstream. Surface a separate business field only when an operator
must scan or filter it, or when real deterministic logic such as deduplication or a gate
requires it. Do not reproduce every routed property as a convenience formula.

### Source 1: Find People

Create a thin Find People staging table scoped directly to the qualified Companies view or
domains with `clay.create_find_people_source(workbook_id, table_name, inputs)`. Do not use
a proxy scope table and do not set a total search limit on this source: the company filter
bounds it, and a total cap cuts people off at arbitrary companies. After creation, prove that
the company filter is active; an empty company-filter identifier means the source can return
unrelated people and nothing downstream should be built.

Choose the scope method by how the qualified companies' domains behave:

- **Each company has its own domain:** use the Find People (MixRank) source above. The helper
  filters people by company domain.
- **Branches, franchisees, or local subsidiaries share the brand's domain:** a domain filter
  pulls people from every branch in every country. Scope people by company LinkedIn URL
  instead, with the DSL people search source described in
  [`design-clay-table-json`](../design-clay-table-json/SKILL.md) ("Scope the people search to
  the qualified companies, by LinkedIn page"). That source type works differently: its row
  limit belongs inside the query (`limit N`, with a per-company cap such as
  `limit 3 by clay_company_id`), because a DSL search without one imports every match.

Use the approved person geography and broad approved title families. A campaign targeting
people located in Germany should set person location to Germany in Find People; a company
being German is not evidence that the person is located there. Broad terms such as
`finance`, `controller`, `director`, `head`, and their approved local-language variants may
be a better recall layer than a brittle exact-title list, but only when the approved persona
definition supports them.

Add one `Send table data` action to the staging table. Route each eligible person row to the
shared People table in single-row mode: call `clay.create_route_row_column(...)` with the
People table as `target_table_id`, map the canonical fields through `row_data`, and leave
`list_data` unset. Map the person identity, company identity, location, source record ID,
and a literal source label such as `Find People`. Require a usable identity. It does not
have to be a LinkedIn URL. Prefer personal LinkedIn when it exists; otherwise accept the
approved fallback of full name plus company domain and current-role evidence. Read one
created destination row and compare every mapped field before running the remaining
eligible records.

### Source 2: Claygent

Run one people-search Claygent on each qualified company. A reusable prompt architecture
has public-web research, explicit current-employment verification, a bounded contact count,
seniority ordering, no fabrication, structured JSON, and an empty result when no person is
proven. Fit the title, geography, and evidence rules to the approved campaign instead of
inheriting another campaign's criteria.

The output contract should make each contact independently usable in the shared People
table. At minimum it needs the person's name, current title, company identity, and an
official or otherwise approved evidence URL proving the current role. Return a personal
LinkedIn URL when found, but do not require it unless the approved campaign explicitly does.
This matters in manufacturing and other segments where reliable leaders may be visible only
on official company pages, association pages, or industry-directory pages. Do not make the
prompt return a contact that does not satisfy its own current-employment and geography
rules.

Follow the Claygent with one `Send table data` action:

- `target_table_id`: the shared People table;
- `type`: `list`;
- `list_data`: the Claygent `contacts[]` output;
- `row_data`: the canonical company identity and a literal source label such as `Claygent`;
- run condition: the contacts array exists and has at least one item.

Read the destination source payload before binding downstream actions. In a typical list
route, contact fields are on the routed item and company fields are under `parent`. Bind
the actual nested payload returned by the new route rather than assuming every Clay table
serializes it identically. Do not flatten it with formula extractors.

### Converge in one People table

Make the two routes satisfy one shared destination contract and preserve the real routing
source lineage. Preserve an operator-readable source label so an operator can tell whether
a row came from Find People, Claygent, or both, but keep the source field and source IDs as
the proof. Deduplicate before any paid downstream enrichment. Use personal LinkedIn URL as
the primary identity key when present; otherwise use normalized full name plus company
domain and current-role evidence or source record ID.
When both sources found the same person, keep the better verified value from either source
and preserve the second source as corroboration. Do not assume `Send table data` upsert has
deduplicated records across two different source columns; prove the destination row count
and inspect collisions.

Verify employment before qualification. When a LinkedIn URL exists, `LinkedIn Experiences /
Claygent / <Model>` may research that profile and `Enrich Person` may act as a fallback.
When no LinkedIn URL exists, verify the current role against the approved official or public
evidence carried by the discovery route. Lack of LinkedIn must not exclude an otherwise
verified contact. Decide `Still Employed?` with an AI action. Never use a formula for it.
The action matches the
sourced title and company against the best available current-role evidence and returns one
enum. That match only looks deterministic: legal suffixes, rebrands, acquisitions,
localized and translated names, promotions, and concurrent roles all defeat string
comparison, and a formula answers confidently while being wrong. Keep it one dedicated
action rather than a chain of duplicate copies, and keep it out of the contact
qualification prompt, which consumes `Still Employed?` as an input and gates on it. Do not
assume the first experience is current.

Use one `Company Table Data` lookup in the shared People table, keyed by canonical company
domain, to bring the company verdict and any campaign evidence into People. When branches or
franchisees share the brand's domain, key the lookup by company LinkedIn URL instead, the same
identifier you scoped the people search by, so each person joins to their own branch. Do not rely on
two routed snapshots of company evidence as competing sources of truth. Contact
qualification decides whether this person is a relevant current prospect using person
evidence, current employment, and the company verdict. It is the copy gate; do not add a
second `Copy Eligibility` column.

### Good versus bad dual-source routing

A good build uses Find People for structured recall and Claygent for public-web coverage,
routes both into one shared People table through real Clay source lineage, verifies one
routed row from each source, binds nested route and action data directly, deduplicates
before paid enrichment, and runs all later qualification and copy once on the canonical
person. LinkedIn is useful evidence, but a contact can qualify without it.

A plausible-looking bad build leaves Find People and Claygent contacts in separate finished
tables, enriches and writes copy twice, or pastes an earlier campaign's people-search prompt
into a campaign with a different persona. Another bad variant sends `contacts[]` without
`type: list`, causing the company row rather than each contact to be routed, assumes
route-row upsert removed cross-source duplicates without reading the destination, inserts
people as plain rows with a text `Source` label, requires LinkedIn in a segment that does
not require it, or adds one formula extractor for every nested action field. These builds
look populated but create unauditable provenance, split logic, duplicate spend, and a
bloated dependency graph.

Create only the copy the campaign needs. Use button-triggered actions on the approved
strongest model, with run conditions requiring a qualified contact and current employment.
Copy actions return only the final message field or structured bundle of final campaign
messages. They do not return analysis, review labels, or drafting notes. Missing evidence
blocks the action; it does not produce a `NEEDS_REVIEW` message.

If the campaign requires account signals, research them once on qualified Companies and
carry the evidence into People through the existing company lookup. Do not build one
research column per signal family.

## Price the run in the correct unit

This section assumes the client's own model API key is connected in Clay, which is how this
skill builds: Claygent and Use AI columns then bill the model provider in dollars and use 0
Clay credits. On a Clay-managed key the same columns use Clay credits instead; see "How AI
columns are billed" in `clay-api-reference.md`, and price them as credits.

On your own key, never estimate an AI batch by multiplying action columns by rows and
calling the result Clay credits. Clay's AI action metadata, including `actionExecution`
pricing fields, is not a Clay-credit quote for the model run.

Estimate AI spend in USD from the configured model, eligible rows, expected prompt and
output size, and the client-owned provider account. Prefer live provider billing or usage
telemetry. After the one-record proof, the sibling `calculate-costs` skill reads the real
per-cell spend Clay recorded, which is the best basis for extrapolating a batch. When exact
usage is unavailable, use a configured per-run dollar ceiling or calculate a labeled range
from live model pricing and explicit token assumptions. If neither basis has been read, say
the USD estimate is not yet available and read it before asking for approval. Never invent
a per-run dollar figure and never copy an illustrative price from a worked example. Do not
convert uncertainty into Clay credits.

Some non-AI enrichment providers do consume Clay credits. Price those actions separately
from AI:

- `Claygent` and `Use AI` on your own provider key: estimated provider cost in USD; Clay
  credits `0`. On a Clay-managed key: Clay credits from the live action price.
- Non-AI enrichment such as person, email, phone, or company-data providers: Clay-credit
  estimate from the live action pricing, plus any separate provider charge when applicable.
- A mixed run: show two lines, one for USD model spend and one for Clay credits, and judge
  each on its own. Rex's cost report (`calculate-costs`) also gives a `total_cost_usd` that
  converts credits at a fixed $0.014 per credit; treat that total as an estimate, and do not
  quote it in place of the two lines.

Before a paid batch, show the user the estimate in the correct units and the relevant live
balance or billing state, then wait for explicit approval.

Good when billing telemetry has not yet been read: `40 AI runs: USD estimate pending live
provider pricing/usage readback; 0 Clay credits. Enrich Person fallback: at most 5 Clay
credits from the live 0.5-credit action price. I will show the USD estimate before asking
for approval.`

Bad: `20 AI runs cost 20 Clay credits.` The arithmetic looks tidy, but it is wrong: on your
own provider key, AI runs are billed in USD by the model provider and use no Clay credits.

## Match every AI action before spending

An AI action is correctly authored only when its visible name and its backend agree. Confirm
that:

- `Claygent` versus `Use AI` matches `useCase`.
- The displayed model matches the bound model ID and the approved provider account.
- The bound model ID exists in this workspace. An unknown or misspelled model name can leave
  the column queued forever instead of failing loudly.
- The prompt is stored directly in the action column.
- Every prompt reference resolves to the intended current column, especially when both raw
  and enriched versions of a field exist.
- `answerSchemaType` contains a valid JSON Schema for every prompt-bearing AI action,
  including single-field decisions and copy.
- The schema contains the exact fields and closed vocabularies that downstream prompts,
  formulas, and actions reference directly.
- The run condition names the real upstream gate and covers the intended blank, failed, and
  confidence fallback cases.
- Editing a live prompt preserves the existing binding splices and other working action
  settings unless the change explicitly requires otherwise. `clay.update_column(...)` merges
  `typeSettings` and input bindings by default; pass `replace=True` only when you mean to
  overwrite the whole configuration.

Read the prompt and bindings in the Clay UI as well as through the API. If the operator view
and API readback disagree, stop and resolve the contradiction before scale.

## Finish as an operator and clear out the experiments

Once a prompt version wins, trace its downstream dependencies, repoint them, verify the
production path, and remove the losing action plus obsolete helpers. Audit every formula:
if it only copies or extracts one property from a source, lookup, webhook, or action cell,
rebind the consumer directly and remove it, unless it carries an AI answer across a lookup or
shows it in the demo view (see "Bind nested outputs directly"). If two formulas have the same normalized body,
trace both consumers, preserve the one canonical business gate, repoint its consumers, and
remove the duplicate. Never leave `V2`, `V3`, `test`, timestamps, personal notes, duplicate
trigger actions, or dead provider waterfalls on the production surface. Keep required
runtime helpers only when the production graph still depends on them, and hide them after
re-verifying those dependencies.

Order the default operator view along the workflow. By default, retain that view plus the
qualified Companies view needed to scope People. Add another view only when a named operator
workflow requires it. Verify in a browser that source fields and action outputs render as
intended, prompts are present where claimed, column groups sit where intended, and the
visible order tells the pipeline story. Remove duplicate tables created by interrupted
source attempts.

Before reporting completion:

- reconcile every bulk run against the eligible population;
- confirm native JSON Schema coverage for every prompt-bearing Claygent and Use AI action;
- report AI/model spend in dollars and non-AI Clay-credit spend separately;
- leave one clean Companies table, one thin Find People staging table, and one shared People
  table at the agreed destination; keep Claygent people discovery on the Companies table;
- record the exact source filters, actions, models, prompts, accounts, run conditions, and
  table links in a short build log;
- save the approved workbook with the [`save-clay-schema`](../save-clay-schema/SKILL.md) skill,
  which exports it into `registry/` so the recipe can be reproduced and audited.

Stop rather than improvise when segment or persona logic is missing, the workspace is wrong,
the session is expired, a mandated object is gone, a client model account is missing,
provider balance is exhausted, the People company scope is inactive, the live source does
not match the approved population, or the UI contradicts the backend configuration.
