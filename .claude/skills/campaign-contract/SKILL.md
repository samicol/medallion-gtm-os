---
name: campaign-contract
description: "Write contract.md, the Markdown build sheet for one Clay campaign, from an approved campaign decision (who is targeted, what the signal is, what the copy may claim, how many rows are needed). The contract has one section per Clay object in build order, with every prompt verbatim, the model, every run condition and the demo view. Use it when someone asks to write, fill or fix a campaign contract, or when a segment is approved and the next step is the Clay table. It does not write the table JSON (that is design-clay-table-json), it does not touch Clay, and it does not make the commercial decisions."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.

# Campaign Contract

This skill writes the build sheet for one campaign. An operator with Clay open, or an agent
writing the Clay table JSON, should be able to build from it without asking anyone a question, so
everything in it is something that gets created or typed in Clay. Write it once, as `contract.md`
in the campaign's folder (for example `output/campaigns/<slug>/contract.md`). `design-clay-table-json`
then turns it into the table.

You own the table's decisions: which source and filters, which columns in which order, what each
AI column judges and returns, which model, when each column runs, how a company verdict reaches
the people rows, and what the demo view shows. You do not own the commercial decisions: who the
campaign is for, what the offer is, what the copy may claim. Those arrive with your input.

## Input, and what counts as approved

- The campaign decision from whoever owns it: the target segment, exclusions, the signal the
  campaign relies on, what the copy may and may not claim, and the number of finished rows needed.
- Later explicit corrections from the same owner.

If a commercial decision is missing or contradictory (who qualifies, what is excluded, what the
copy may claim, how many rows are needed), name it and stop. That is the owner's decision. If a
fact is missing (a Clay filter value, a model account's display name, what a provider calls a
field), go and find it in the live Clay workspace with `clay_client.py` or `clay_browser.py`, or on
the web. A fact is never a reason to stop.

## Read before writing

1. `references/contract-standard.md` completely. It defines the contract's shape: one section per
   Clay object, `Field | Contract` tables, a prompt block only where there is a prompt.
2. The closest approved table in `tools/rex/registry/INDEX.md`, if the registry has one for this motion.
   Read its JSON to see how a working table of this kind carried judgment from column to column.
   Learn the construction; never copy its names, filters or prompt text.
3. `references/example-contract.md`, a fictional worked example of the finished shape.

## Design the table

Work out the funnel first, in numbers: how many companies or people the source should return, how
many survive each check, and how many finished rows the demo view needs. The source limit follows
from that. Then decide each object in build order and give it a section.

Decisions that past builds got wrong, so decide them explicitly:

- **Where the verdict lives and how it crosses.** In a two-table build a company's AI verdicts
  reach the people rows only through formula columns on the company table, read through a lookup.
  Give those formulas their own sections and a `Downstream` row.
- **Scoping.** The people search is scoped to the qualified companies, by company LinkedIn URL:
  either a find-people action on the company table, or a people source filtered to the company
  table's view. Say which, and cap people per company.
- **Run conditions.** Every paid column after the first check runs only on rows that passed it.
- **The signal is its own decision.** Give account fit, the targeting trigger and the buying
  signal three separate columns. A job post is a signal only when its content says so.
- **The copy route.** Qualified rows with an evidenced signal get signal-led copy; qualified rows
  without one get a declared fallback or stay out of the demo view, as the input says. Never
  invent timing, pain, budget, dissatisfaction or intent.
- **Model.** The model and model account for every AI column. Use what the input names; if it names
  none, pick one your workspace offers and state it in each AI section so the choice is visible.
  The contract is where the model is decided; later steps copy it.
- **The demo view.** Which rows it shows, which columns in which order, the target count, and how
  the view is cut to the target when more rows finish (a stated rule, a score, or a hand-set pick
  column). The view shows every source column and every AI column, each followed by the formula
  that shows its answer, in causal order.

## Prompts

A prompt that decides who qualifies or what the email says is load-bearing. Write it with care (or
with a prompt-building skill if you have one): its inputs, its output schema, and what it does when
an input is missing. Put each prompt verbatim in its section as a fenced `text` block followed by
its output schema as a fenced `json` block, inside `<details><summary>Prompt</summary> ...
</details>`, with the output fields also in the `Result` row. Never summarize a prompt: the
builder copies it into Clay as written.

## Write it without adding decisions

- Section 1 is `Campaign Overview` and carries only `Campaign in a nutshell` (short plain-language
  paragraphs, inside a `<details>` block) and `Starting Point` (one sentence naming the source).
  Every later section is one Clay object, numbered in build order.
- Give a section only to an object that exists in this build: a source, a column, or a view a
  later step consumes. Never write a section that says `Not applicable`.
- Never merge two columns into one section. An evidence retriever and a classifier are two
  sections.
- Derive each table's rows from the object, by the method in the standard. Include a row only
  when it carries a value, write `-` for a Clay field deliberately left unset, and omit a row whose
  question this object does not raise. Do not write an `Acceptance rule` row.
- The contract is neutral about demo and production: it contains the columns this build contains.
- Write each cell as a value. Do not add a sentence explaining it.
- Keep Clay identifiers out. Never show a workbook, table, source, field, view or account id
  (`wb_`, `t_`, `s_`, `f_`, `gv_`, `aa_`), an `actionKey`, a raw API parameter, or the data vendor
  behind a native Clay source. Name an existing object by its exact display name, and a model
  account by its Clay display name. A prompt that contains a Clay id is not ready: rewrite it to
  reference the column by name.
- Write nothing that is not a table row or prompt text. No campaign map, no limits list, no
  paragraph between sections explaining a choice.
- A contract is a build layout. Leave out test protocol and status: sample sizes, review batches
  and claims that anything already exists.
- The title line carries `DRAFT` and the date. Nothing else carries status.

## Check before handing off

Read the contract top to bottom as the person who will build it with Clay open. Every object has a
section, every section has what the builder needs, no section describes something that is not a
Clay object, and nothing requires a decision the input did not make.

Then hand off: the file path, the expected funnel in numbers, the paid columns, and any owner
decision you could not make. `design-clay-table-json` builds from it. When the build changes a
filter, a limit, a column or a prompt, the contract is updated to match the table that exists.

## Good and bad

Good: the input says account-first, US independent breweries, the copy may cite only what the
brewery says about itself. The contract has a company source with named Clay filter values and a
limit, a brewery check with a cheap model, a formula wrapper for its verdict with a `Downstream`
row, an opening-line column that runs only on qualified rows and whose prompt forbids invented
facts, and a demo view of the finished rows.

Bad: the same contract with one "Qualify company" column that judges fit and signal together, an
unscoped people search, an email prompt that reads an AI column directly across tables, and no demo
view section. It reads fine, and the table it produces is full of rows nobody can stand behind.
