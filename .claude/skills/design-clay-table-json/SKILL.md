---
name: design-clay-table-json
description: "Write the Clay table JSON (the portable flow blueprint) for one campaign from its campaign contract, using approved schemas in the local registry as working examples. Use it when a contract exists and the next step is 'build the table' or 'write the table JSON', or when a blueprint needs repair before import. It produces one flow JSON file that passes the importer's dry run. It does not import, run or spend in Clay (import-clay-table does that), and it does not decide the campaign (campaign-contract does that)."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.

# Design Clay Table JSON

You turn a campaign contract into the exact Clay workbook an operator would have clicked together:
sources, columns, prompts, run conditions and the demo view, written as one JSON file that
`import-clay-table` imports in one pass. After import, people make small manual edits in Clay, so
write the JSON as the first draft of a real table that someone will open and use.

You own the table's construction. You do not own the campaign's decisions. If the contract is
silent or contradictory on who is targeted, what the signal is, how many rows are needed, or what
the copy argues, stop and send it back to `campaign-contract`. A table built on an invented
decision looks finished and is wrong.

## Inputs

- The campaign's `contract.md`: one section per Clay object, in build order.
- The registry, `tools/rex/registry/INDEX.md`: approved schemas saved by `save-clay-schema`, what each is
  good for, and where its JSON lives. It starts empty.
- `references/example.flow.json`: a fictional worked example (a company search, an AI check, a
  formula wrapper, a gated AI column, a demo view). It imports and runs; it was proven live.
- `references/flow-blueprint.schema.json`: the file format.
- The Clay facts below, and `action-registry.md` / `clay-api-reference.md` in `tools/rex/` for
  action keys and inputs.

## Output

`output/campaigns/<slug>/table.flow.json` (or wherever the campaign lives), in the same format as every
registry schema (`$schema`, `schemaVersion`, `flow`, `requiredBindings`, `tables[]` with
`columns[]` and `views[]`), plus a clean dry run.

## Method

### 1. Read the contract as a build list

List every Clay object the contract names, in order: each source, each column, each view. That
list is the table. Copy counts literally: if the contract says about ten finished rows, the source
limits and filters must plausibly yield ten finished rows after every qualification step. Write
the expected funnel down (companies sourced, qualified, people found, people qualified) before you
write JSON, because the source limit follows from it.

### 2. Learn from the closest working table

Open `tools/rex/registry/INDEX.md` and choose one or two schemas with the same motion (people-first,
account-first, signal-first) and the most similar buyer. With an empty registry, use
`references/example.flow.json`. Read the whole JSON. Do not work from a summary. You are learning
Clay's shape and how a working table carried judgment from column to column, so do not clone it.

Before you drop, rename or simplify anything you learned from an example, ask what that column
feeds downstream. A formula that looks like junk is often the only thing carrying a company verdict
into the people table; removing it blocks every person row.

Never carry over an example's names, filters, domains or prompt text. Every string in your JSON
comes from this contract. Search your finished JSON for the example's industry words before you
hand it on.

### 3. Preview the source before writing it

Run the source query as a free search preview first, in the Find Companies / Find People preview
in Clay's UI. Read the first 20 names. If fewer than a third are the
right kind of company or person, fix the query and leave the prompts alone. Industry filters are coarse:
a food-and-beverage industry filter alone returns coffee roasters, agencies and trade bodies next
to breweries; a `description contains (...)` keyword filter fixes most of it.

### 4. Write the JSON

Work table by table in `flow.buildOrder`. For each column the contract section gives you the name,
type, inputs, output fields, run condition and consumer. The Clay facts below are how those become
JSON. Use placeholders, never live ids:

- `${workbook.id}`, `${tables.<t>.id}`, `${tables.<t>.fields.<slug>.id}`,
  `${tables.<t>.views.<view>.id}`, `${tables.<t>.sources.<slug>.id}` for objects the import creates.
- `${bindings.authAccounts.<name>}` for every `authAccountId`.
- `${bindings.models.<name>}` or a literal for every `model`. The model is whatever the contract
  names; no script, config or example overrides it.

### 5. Dry-run and fix

```bash
python3 .claude/skills/import-clay-table/scripts/import_flow.py --schema output/campaigns/<slug>/table.flow.json --dry-run
```

The dry run checks auto-run is off everywhere, every `{{@Column}}` reference exists, search sources
carry a `limit`, sources cannot trigger themselves, prompts have no unescaped quote, the default
view is declared, and it warns about paid columns without a run condition and bindings with no
value yet. Fix every error at its cause. A dry run only proves the importer can read the file. It
does not prove the prompts work or the source returns the right rows; that proof is the one-row
test in `import-clay-table`.

### 6. Hand off

Report the file path, the expected funnel, the columns that cost money per row, and anything in the
contract you could not express in Clay. Then `import-clay-table` takes over.

## Clay facts that decide whether the table works

Each of these cost a real build a day or more.

**Only formula columns cross tables.** A people row reads company data through a
`lookup-company-in-other-table` action. That lookup carries the company row's formula columns. It
never carries an AI action column's output. So every AI answer the people side needs gets its own
formula on the company table, for example `Brewery Qualified?` = `{{@Qualify Brewery}}?.isBrewery`
with `mappedResultPath: ["isBrewery"]`. The people side reads the lookup, and the email prompt
receives the lookup as one block: `Clay.formatForAIPrompt({{@Company Context}})`.

**Take the company domain from the company row.** In a two-table build the person source's
`matched_experience.company.domain` is often blank. The company row already has the right domain.
Read it through the lookup.

**Scope the people search to the qualified companies, by LinkedIn page.** Either a
`trigger-find-people-source` action on the company table (with `companyIdentifier` = the company
LinkedIn URL and a run condition on the company verdict), or a people source whose `dslQuery` uses
`clay.filter_to_companies(@table("${tables.companies.id}:${tables.companies.views.default_view.id}:${tables.companies.fields.linkedin_url.id}"))`,
which reads the company table's default view, so filter that view to the companies whose people
you want. Match on the company LinkedIn URL. `build-clay`'s Find People (MixRank) helper,
`clay.create_find_people_source`, filters by company domain instead; that works when each company
has its own domain, but franchisees and local branches share the brand's domain, and a domain match
pulls people from every branch in every country. A LinkedIn URL match is right in both cases, so
this pipeline uses it. Cap people per company in the query with `limit 3 by clay_company_id`. An unscoped people search returns
random people worldwide and the table still looks full.

**AI columns.** `actionKey: use-ai`, `authAccountId: ${bindings.authAccounts.<name>}`,
`inputsBinding` with `useCase` (`"claygent"` when it must browse the web, `"use-ai"` when it only
reasons over its inputs), `model`, `prompt`, `answerSchemaType` (a `formulaMap` whose `jsonSchema`
is the JSON Schema as a string literal), and `_metadata` with `modelSource`. Pick the model per
column from the contract: a cheap model is enough for a yes/no check on a description; research and
copy may need a stronger one. The one-row proof shows whether the choice holds.

**Prompt strings are Clay formulas.** The prompt is a formula string literal, so every double quote
inside the text must be escaped, and inputs are joined with `+ Clay.formatForAIPrompt({{@Column}}) +`.
A raw double quote breaks Clay's parser and costs a rerun; building the formula with a JSON
encoder (`json.dumps(text)`) avoids it. Tell the model to write company names the way a person says
them, with no legal suffixes or symbols, and to greet the person by the first name as written in
their full name.

**Run conditions** go in `typeSettings.conditionalRunFormulaText`, for example
`{{@Brewery Qualified?}} == "yes"`. Every paid column after the first qualification step needs one,
otherwise you pay for research on rejected rows.

**Sources.** Company and people searches are `run-search-dsl-export-to-s3` sources with a
`dslQuery`. The row limit must be in the query (`limit 10` at the end); Clay refuses a page size
on these sources, and a trigger without a limit imports every match. This rule is for these DSL
search sources. The Find People (MixRank) source that `build-clay` creates with
`create_find_people_source` is a different source type: set no total limit on it, because its
company filter bounds it. Set
`disableTriggerOnCreate` and `disableTriggerOnUpdate` to `true`. Use only filter values Clay
accepts: the size field is `company_size` with values such as `"11-50"`, `"51-200"`,
`"201-500"`; industries are LinkedIn's names as Clay spells them, for example
`"Food and Beverage Manufacturing"` (with `and`, not `&`). An
invalid value passes the dry run and returns nothing, or the wrong rows, live. Jobs searches are
their own source type; if the contract's signal is a job post, source jobs, do not substitute an
industry search.

**Auto-run stays off.** `flow.workbook.create.settings.isAutoRun: false` and every table's
`tableSettings.AUTO_RUN_ON: false`, even when an example shows `true`. An auto-run workbook can
run tens of thousands of paid rows before anyone looks.

**The demo view is the product.** The importer cannot create new views; it renames and configures
the table's default view and reuses Clay's preset views. So the demo view is the view with
`logicalId: "default_view"`, named for example `Demo`, marked `isAcceptedDemoView: true`. Filter
it to the finished, qualified rows. On a company table the default view is also what a scoped
people search reads, so filter it to the companies whose people you want.

Show the work as well as the answers. The viewer has to see how each row was found and judged, so
the demo view shows every source column and every AI column (clicking one opens its prompt), each
AI column immediately followed by the formula that shows its answer, in causal order: source, then
the lookup to the company row, then company fields, fit and signal, then the person and their
check, then the email column and the email. The order of keys in the view's `fields` map is the
order on screen. Hide only system timestamps, raw JSON copies of a result already shown, and pure
filter helpers. Use plain names (`Brewery Qualified?` rather than `Verdict`). Treat an empty cell
in the demo view as a defect.

**Names are what the operator sees.** Column names are also the keys that `{{@Name}}` references
use, so choose the final display name before other columns reference it.

## What good looks like

`references/example.flow.json` is the minimal good shape, for a fictional seller of brewhouse
scheduling software targeting US independent breweries: a company search with a keyword filter
and `limit 10`, formula columns for name, domain, LinkedIn URL and description, a cheap-model
brewery check with a JSON answer, a formula wrapper for the verdict and one for the reason, an
opening-line column that runs only when the verdict is `yes`, a formula for the line, and a `Demo`
default view filtered to `yes` that shows all ten columns in causal order. When it ran live on ten
companies, four qualified and the demo view had no empty cell.

A full demo adds a second table: a people search scoped to the qualified breweries by LinkedIn URL
(`limit 3 by clay_company_id`), a lookup back to the company row, a person check, and an email that
receives the company row as one lookup block.

A plausible bad JSON passes the dry run and has the same columns, but its people source is not
scoped, its email reads the AI column directly across the lookup, or an example's prompt text is
still inside with the industry word replaced. All three have happened.
