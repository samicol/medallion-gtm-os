# Practical Clay Column Playbook

Use this reference to decide which tables and columns a campaign needs. Adapt it to each
campaign instead of applying it as a fixed template. Start with the campaign decision, select the matching architecture, and add only
the columns required to move a row safely from source to delivery.

The central test is operator work. A trustworthy column removes research, comparison, or
decision work from the human. An untrusted or unexplained column adds supervision. A table
is clean when the operator can see why a row is present, what evidence was collected, which
decision was made, and what happens next without reconstructing the build history.

For the exact configuration of recurring Clay components, use `technical-recipes.md`. This
playbook decides what belongs in the table; the technical recipes define how the selected
component is wired and proven on real rows.

## Contents

- Choose the campaign architecture first
- The row lifecycle
- Companies table recipe
- Thin Find People staging recipe
- Shared People table recipe
- What the recurring Clay actions do
- Formula policy
- Clean default views
- Final column audit

## Choose the campaign architecture first

| Archetype | Use when | Production surface | Distinguishing evidence |
| --- | --- | --- | --- |
| Account-first | The ICP starts with a company segment | Companies + thin Find People source + shared People | Company identity, firmographics, website evidence, company verdict |
| Signal-first | A dated event creates the reason to contact | Signal Companies + thin Find People source + shared People | Event identity, date, source URL, relevance, company verdict |
| People-first | The approved source already contains named people | Thin People Source + shared People; Companies only if an account decision is still required | Person identity, current-role evidence, source provenance |
| Enrichment/export | The result is a clean dataset with no campaign | One canonical table plus an export view | Identity, required enrichments, validity status, no copy or delivery |

Use account-first by default for outbound. Signal-first is account-first with an event root.
People-first still needs company context when it matters: add one company lookup when
company fit or company evidence affects contact qualification or copy.

Do not treat experiments as a fifth architecture. When a table contains competing prompts, duplicated
message variants, timestamped triggers, or parallel provider chains, select the approved
production path and remove everything that does not support it.

## The row lifecycle

Every production row should move through these roles in order:

```text
source -> canonical identity -> deduplication -> cheap gate -> evidence
       -> qualification -> routing -> contact evidence -> contact gate
       -> contactability -> copy -> approved delivery
```

Not every campaign needs every role. The order still matters. Never research or write copy
before the cheapest available exclusion gate. Never deliver before identity, qualification,
employment, and the required contactability checks are proven.

For every proposed column, answer:

1. Which later decision or operator action consumes it?
2. Is it a root, evidence, decision, gate, route, handoff, or delivery field?
3. Can a formula do this deterministic job more reliably than AI?
4. Can the consumer bind the nested source or action output directly?
5. Which run condition prevents unnecessary spend?
6. What does blank, failed, or low-confidence mean for the row?
7. How will one real cell prove that it works?

If question 1 has no answer, omit the column.

## Companies table recipe

This is the normal account-first structure. Take the exact firmographics and gates from the
approved segment. The table pattern does not define them.

| Order | Column or component | Role | Add when | Contract and run gate |
| ---: | --- | --- | --- | --- |
| 1 | Real company source | Source | Always | Native Clay source field; preserve source ID and configuration |
| 2 | `Company Name` | Identity | Always | Canonical visible name; prefer native mapped output |
| 3 | `Company Domain` | Identity | Always | Normalized domain; primary account join key |
| 4 | `Company LinkedIn URL` | Identity | When available or used by research | One canonical URL; no competing copies |
| 5 | `Company Source Record ID` | Lineage | When the source exposes one | Stable trace back to origin |
| 6 | `Company Dedup Key` | Gate | When source uniqueness is not proven | Deterministic normalized domain, with an approved fallback |
| 7 | Required source firmographics | Evidence | Only if a gate or qualifier consumes them | Examples: location, employee count, industry; do not copy the whole source object into columns |
| 8 | Canonical firmographic enrichment | Evidence | When a required source value is absent or weak | One coherent structured action; fallback only on blank, failed, or low confidence |
| 9 | Canonical geography or size | Handoff | When multiple evidence sources must be reconciled | Deterministic preference logic; usable fallback beats weak primary |
| 10 | Deterministic segment gate | Gate | Whenever fit can be cheaply excluded | Geography, size, domain, source-age, or exclusion logic from the approved segment |
| 11 | `Company Website Evidence / Claygent` | Evidence | When official-site facts affect fit or copy | Runs only after cheap gates; returns neutral evidence, URLs, missing evidence, confidence |
| 12 | Evidence fallback | Evidence | Only if the first research action can be materially incomplete | Runs on blank, failed, or low confidence; never just because a second provider exists |
| 13 | `Company Fit Qualification / Use AI` | Decision | When fit is not fully deterministic | Consumes collected evidence; does not browse; structured verdict, reason, confidence |
| 14 | Visible `Company Qualification` | Operator output | When operators filter or scan it | Native mapped output if possible; no formula extractor solely for the next action |
| 15 | Company-level campaign evidence | Evidence | Only if qualification or copy consumes it | Research once here: buyer signal, job event, tooling, or value-prop evidence |
| 16 | Qualified Companies view | Routing | Normally | One approved filter used to scope both people sources |
| 17 | Find People trigger | Routing | When Clay Find People is a source | Exactly one active trigger bound to the qualified view or domains |
| 18 | `People Search / Claygent` | Evidence/source | When public-web coverage is required | Structured `contacts[]`; current-role proof; bounded count; qualified companies only |
| 19 | `Send table data` | Routing | After Claygent contacts are proven | List mode, `contacts[]` as `listData`, company context as parent `rowData` |
| 20 | Prospect count | Operator control | Only if an operator uses it to detect coverage gaps | Lookup plus deterministic count; not required for every campaign |

Keep source identity visible, but do not create a formula for every source property. A source
or action object may be bound directly downstream. Surface a scalar only when the operator
must scan, filter, deduplicate, or route by it.

### Signal-first additions

Place signal columns between source identity and company qualification:

| Column | Purpose | Requirement |
| --- | --- | --- |
| `Signal Type` | Names the campaign event | Controlled vocabulary defined by the campaign |
| `Signal Date` | Enforces recency | Deterministic age gate; retain source date |
| `Signal Source URL` | Makes the event auditable | Direct evidence URL; AI reasoning does not count |
| `Signal Evidence` | States what occurred | Factual extraction separated from outreach interpretation |
| `Signal Relevance` | Decides whether it matters | Deterministic where possible; AI only for semantic judgment |
| `Campaign Angle` | Optional handoff to copy | Add only if copy consumes it; do not generate several unused ideas |

A signal-first campaign should preserve this order: event identity, a cheap recency,
employee, or geography gate, event interpretation, then people search. Do not generate
campaign angles before proving the account and contact. Keep one evidence-backed angle only
when downstream copy consumes it.

## Thin Find People staging recipe

The staging table exists to discover and route people. Keep it thin so it does not turn into
a second People table.

| Order | Component | Requirement |
| ---: | --- | --- |
| 1 | Real Find People source | Bound directly to the qualified Companies view or domains; no total search limit on this MixRank source (see the scope note below) |
| 2 | Native person and company identity | Use source fields needed by the destination contract; avoid extractor formulas used only by routing |
| 3 | Literal provenance label | `Find People`, carried inside the route payload for operator readability |
| 4 | `Send table data` | Single-row mode; map person identity, company identity, location, source record ID, and provenance |

Do not enrich, qualify, find emails, or write copy here. Read one destination row and compare
every mapped field before routing the eligible population.

Scope note: `clay.create_find_people_source` (Find People, MixRank) filters people by company
domain. Use it when each qualified company has its own domain. When branches, franchisees, or
local subsidiaries share the brand's domain, a domain filter pulls people from every branch, so
scope by company LinkedIn URL with the DSL people search source in
[`design-clay-table-json`](../../design-clay-table-json/SKILL.md). That source takes its row
limit inside the query (`limit N`, plus a per-company cap such as `limit 3 by
clay_company_id`); the no-total-limit rule above is only for the MixRank source.

## Shared People table recipe

Both Find People and Claygent discovery converge here. This is the only downstream person
enrichment, qualification, copy, and delivery surface.

| Order | Column or component | Role | Add when | Contract and run gate |
| ---: | --- | --- | --- | --- |
| 1 | Real routed source | Source | Always | Preserve source field and source IDs; text provenance alone is insufficient |
| 2 | `Prospecting Source` | Lineage | Always with multiple paths | Operator-readable `Find People`, `Claygent`, or corroborated sources |
| 3 | `First Name`, `Last Name`, `Full Name` | Identity | As required downstream | Canonical values reconciled from actual route payloads |
| 4 | `Job Title` | Identity/evidence | Always | Current sourced title; never an inferred persona label |
| 5 | `Personal LinkedIn URL` | Identity | When available | Primary person key; rows without it can still qualify |
| 6 | `Company Name`, `Company Domain` | Identity | Always | Canonical company join data |
| 7 | `Person Source Record ID` | Lineage | When available | Trace to the discovery source |
| 8 | `Person Dedup Key` | Gate | Always when sources converge | LinkedIn URL first; approved name + domain fallback |
| 9 | Current-role evidence | Evidence | Always | LinkedIn experiences or carried official/public evidence URL |
| 10 | Person enrichment fallback | Evidence | Only when required identity or employment evidence is missing | Runs after dedup and only on the missing-evidence condition |
| 11 | `Still Employed?` | Gate | Always for role-based outreach | One `Use AI` action judging current employment from the current-role evidence against the target company, returning `YES`, `NO` or `REVIEW`; downstream gates require exactly `YES`. Never a formula, because name and domain matching fails on rebrands, acquisitions, legal suffixes and translated names |
| 12 | `Company Table Data` | Handoff | When company fit/evidence affects the person | Exactly one lookup keyed by canonical domain, or by company LinkedIn URL when branches share a domain |
| 13 | `Contact Qualification / Use AI` | Decision | When persona relevance is semantic | Consumes person evidence, employment gate, company verdict; returns structured verdict and reason |
| 14 | Visible `Contact Qualification` | Operator output | When operators filter or approve | This is the copy gate; do not add a duplicate `Copy Eligible` decision |
| 15 | Email provider actions | Contactability | Only when email is an approved channel | Sequential waterfall after qualification and employment; each provider runs only if no usable email exists |
| 16 | Email validation | Contactability | When campaign policy requires it | Validate only a candidate email; preserve clear valid/invalid/risky status |
| 17 | `Work Email` | Operator output | For email campaigns | One merged canonical address |
| 18 | `Email Status` | Gate/output | For email campaigns | One canonical validity state consumed by delivery |
| 19 | Required copy bundle | Handoff | Only for approved campaign channels | One action per coherent channel bundle, gated by qualification and required evidence |
| 20 | Variant or round robin | Routing | Only for a named experiment or sender policy | Deterministic assignment, persisted once |
| 21 | Delivery action | Delivery | Only when the build includes approved activation | Last stage; requires all campaign gates and explicit destination |

Copy should consume the best company evidence through the one company lookup and the best
person evidence already collected. It must not research the account again. Generate only the
messages the live sequence needs. Final copy is an output; drafting analysis, critique labels,
and alternative paragraphs belong in the prompt-development process. Keep them out of
production columns.

## What the recurring Clay actions do

| Action family | Architectural job | Use it when | Common misuse |
| --- | --- | --- | --- |
| `use-ai` | Semantic evidence extraction, qualification, or copy | The job cannot be expressed reliably as deterministic logic | One giant action researches, decides, and writes; or many AI columns normalize simple strings |
| `trigger-find-people-source` | Opens the structured people-discovery branch | Qualified companies are the approved search scope | Multiple timestamped triggers or an inactive company filter |
| `route-row` / `Send table data` | Moves canonical rows or explodes `contacts[]` into People | A source path hands off to the shared table | Treating a text source label as lineage; wrong single/list mode |
| `lookup-company-in-other-table` | Brings canonical company context into People | Person qualification or copy needs the company verdict/evidence | Multiple competing company snapshots or lookups |
| `lookup-row-in-other-table` | Joins one specific external decision or payload | A stable key and named downstream consumer exist | Generic lookups whose outputs are never consumed |
| `lookup-multiple-rows-in-other-table` | Measures or retrieves one-to-many coverage | Prospect count or a named operator workflow needs it | Adding counts merely because a reference table has them |
| Company/person enrichment | Fills missing identity or evidence | A required source value is absent or unreliable | Running by default before dedup or duplicating already sufficient source data |
| Email finders | Finds a candidate work email | A qualified, current contact enters an email campaign | Broad simultaneous waterfalls on every sourced row |
| Email validators | Determines whether a candidate is usable | A candidate email exists and delivery policy requires validation | Validating every provider output separately when the waterfall contract can stop earlier |
| `http-api-v2` | Calls a targeted missing data source | The API supplies a named field used downstream | Opaque catch-all enrichment with no operator-visible contract |
| Round robin | Persists deterministic experiment or sender assignment | A real campaign split exists | Random columns without a named experiment or owner |
| EmailBison, Instantly, HeyReach actions | Activates an approved campaign | Every upstream gate and destination is proven | Delivery columns added during exploration or allowed to auto-run early |

`Use AI` is an implementation family that can fill several architectural roles. Name every
AI action by its actual application: evidence, qualification, or copy. Its prompt and schema should have
one coherent job.

## Formula policy

Formulas are appropriate for deterministic work:

- canonical preference and fallback selection;
- normalization used by a real join, dedup key, or gate;
- exact segment, recency, or suppression gates, and gates that consume an AI verdict such as
  `Still Employed?` equal to `YES` (the employment decision itself is an AI action, never a
  formula);
- merging sequential provider results into one canonical output;
- stable variant assignment;
- operator counts or statuses used by a named workflow.

Formulas are not appropriate merely to expose every nested key from a source or action,
rename the same value several times, copy an AI verdict into the next prompt, or preserve a
discarded experiment. Keep the deterministic wiring a consumer needs, and remove wiring that
is duplicated or unconsumed.

Exemption: a single-field formula that carries an AI answer across tables is required, because
only formula columns cross a Clay lookup; without it the People side cannot read the company
verdict. So is a formula that shows an AI answer in the demo view next to its AI column (see
[`design-clay-table-json`](../../design-clay-table-json/SKILL.md)). The junk rule is for formulas
that copy a field nobody downstream needs.

## Clean default views

Physical dependency order and operator-visible order are related but not identical. Keep
runtime helpers only when the graph needs them, then hide them from the default view.

The Companies default view should normally show:

```text
Company Name | Domain | LinkedIn | source-critical firmographics
| decisive evidence | Company Qualification | qualification reason
| people coverage or next action
```

The People default view should normally show:

```text
Full Name | Job Title | Company | LinkedIn | Prospecting Source
| current-role evidence/status | Contact Qualification | qualification reason
| Work Email | Email Status | final campaign copy | delivery status
```

Do not expose provider-by-provider cells, prompt versions, fallback internals, raw lookup
objects, duplicated verdict extracts, or timestamps in the default operator view. Show each
AI answer through one formula; hide or remove any second copy of the same answer. Do not hide
broken or duplicated architecture as a substitute for removing it.

## Final column audit

Before declaring a table clean, trace every column forward:

- If nothing consumes it and no operator workflow uses it, remove it.
- If it copies a nested value only for another action, bind the consumer directly.
- If two columns make the same decision, keep one canonical gate.
- If an expensive action can run before a cheaper exclusion, repair its condition.
- If multiple provider actions can run at once, make the waterfall sequential.
- If copy exists before company and contact decisions, move it after the gates.
- If a delivery action can run without a canonical identity and destination, block it.
- If the default view does not tell the row's story from left to right, reorder it.
- If an operator must manually re-research or re-decide every row, the table is not finished.
