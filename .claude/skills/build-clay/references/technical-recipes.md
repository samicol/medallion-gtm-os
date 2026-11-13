# Clay Technical Implementation Recipes

Use this reference once you know which columns a campaign needs and have to configure the
recurring Clay components exactly. These are implementation contracts. They do not set
campaign defaults. Replace the segment, persona, prompt content, output vocabulary,
models, accounts, and field IDs with approved live values. Preserve the component boundary,
dependency direction, run gate, output shape, and proof method.

## Contents

- Read a live component before reproducing it
- Example implementation readback: grouped evidence to shared People
- Detect and verify grouped columns
- Build grouped website evidence with a fallback
- Build company qualification
- Build Claygent people discovery
- Build a Find People source
- Route both sources into one People table
- Verify current employment
- Build contact qualification
- Prove the complete chain on real rows

## Read a live component before reproducing it

The best reference is a workbook you already trust: a Companies table, its paired People
table, and its Find People staging table, all built to this method. Clay URLs follow this
shape:

`https://app.clay.com/workspaces/<workspace_id>/workbooks/<workbook_id>/tables/<table_id>/views/<view_id>`

Use such tables as component references. Do not treat them as global templates. Read the live object before
copying anything (`clay.get_table(table_id)`, `clay.get_column(table_id, field_id)`). A
screenshot can prove visible grouping and cell behavior, but it cannot prove the complete
prompt, input bindings, output schema, model account, or backend group configuration.

For every reference action, capture this contract:

| Layer | Read back | Why it matters |
| --- | --- | --- |
| Field | ID, name, type, `groupId` | Proves identity and group membership |
| Action | action key, package, use case, model, account | Proves the backend matches the label |
| Inputs | every binding and nested path | Prevents a plausible prompt from receiving the wrong field |
| Output | native JSON Schema and mapped result paths | Defines what downstream actions may consume |
| Gate | conditional-run formula and button/auto-run mode | Defines eligibility and spend |
| Evidence | one eligible cell and one ineligible or fallback cell | Proves both the positive and negative path |

Do not hand-assemble a complex AI, routing, source, or waterfall payload from memory. Clone
the nearest verified live column with `clay.clone_column(source_table_id, source_field_id,
table_id, name, input_overrides=..., condition=...)`, then override only the named inputs.
Read the result back before running it. Cloning is especially important for AI actions:
the native output schema (`answerSchemaType`) has a fiddly encoding, and a cloned column
carries a working one. Treat internal Clay endpoints and payloads as operational evidence
rather than a stable public API contract; `clay-api-reference.md` and `action-registry.md` record what is
currently known.

The model for each AI action is your choice. For per-row work, pick a cheap, capable model
that handles the job; reserve stronger models for copy or hard judgment. Before
binding a model, verify that the exact model ID exists in your Clay workspace and that the
provider account you bind can run it. A typo or an unknown model name does not fail loudly:
the column can sit in the queue forever. Rename the action so its visible name matches the
model actually bound. Model names that appear below are examples. Do not use them as
defaults.

## Example implementation readback: grouped evidence to shared People

The following is an example of reading back a working build. It shows how the
components are configured in Clay; its campaign values, prompts, models, field names, IDs,
and gates are not defaults. Preserve the reusable contract described later in this
reference, including where the example is intentionally called out as narrower or weaker.

### Companies: visible group, evidence fallback, and native outputs

| Component | Observed configuration | Reusable lesson |
| --- | --- | --- |
| `Website Scrape` | One visible basic group containing `Company Website Evidence / Claygent / Run 1 / 4.1 Nano` and `Run 2 / 4.1 Nano` | Group related action columns as one operator-facing component; keep fallback logic on the actions |
| Run 1 | Claygent, GPT 4.1 Nano, strict JSON Schema; gate `!!{{Company}} && !!{{Domain}}` | Require canonical identity before research and return evidence as native structured data |
| Run 2 | Same prompt and schema; gate `{{Company Website Evidence / Claygent / Run 1 / 4.1 Nano}}?.confidence?.toLowerCase()=="low"` | Keep the output contract identical so the qualifier can consume either run |
| Company qualification | Use AI, GPT 5 Mini; supplied-row data only; strict JSON Schema; current gate `!!{{Company}}` | Separate evidence collection from fit judgment and bind both evidence objects directly |
| Visible outputs | `Qualification` and `Fit Score` expose the qualifier result as child fields with `Go to parent column` | Use native mapped child outputs for operator-facing values instead of formula extractors |

The example Run 1 schema requires `scrape_status`, `identity`,
`company_description_3_sentences`, `offering`,
`website_sections_overview_5_sentences`, `evidence_by_section`, `evidence_atoms`,
`missing_or_unclear`, `source_urls`, and `confidence`, with
`additionalProperties: false`. The qualifier schema requires `qualification`, `fit_score`,
`score_reason`, `segment_match`, `segment_match_reason`, `fit_reason`,
`positive_signals`, `disqualification_reasons`, `evidence_ids`, and `confidence`, also with
`additionalProperties: false`.

Two observed gates are narrower than the reusable contract. Run 2 covers explicit `low`
confidence but not a blank, errored, missing, or otherwise unresolved Run 1. The qualifier
runs when only Company is present instead of requiring identity plus admissible evidence.
Treat these as facts about that example table. Do not reproduce them.

### Find People: thin staging and single-row routing

The example staging table has only three production components: the real `Find People`
source, the auto-created `Company Table Data` lookup, and `Send Table Data`. The source is
company-scoped by real domain identifiers and uses campaign-specific title include and
exclude filters.

`Send Table Data` targets the shared People table in single-row mode. Its additional-data
contract includes:

```text
Source, Full Name, Job Title, Last Name, Role Gate, First Name,
Company Name, LinkedIn URL, Company Domain, Current Employer,
Source Record ID, Company Record ID, Role Evidence URL,
Current Role Start, Role Evidence Type, Current Role Verified
```

Its gate is:

```javascript
!!String({{Find People}}?.name||'').trim()
&& !!String({{Find People}}?.company_record_id||'').trim()
&& !!String({{Find People}}?.latest_experience_title||'').trim()
&& !!String({{Find People}}?.url||'').trim()
```

The action has `Update existing rows on re-run`, `Auto-extract new columns`, and `Include
column colors` enabled; `Auto-map existing columns` is disabled. The example route
requires a LinkedIn URL. That is a campaign-specific admission rule. Find People does not
require it in general. Once a production destination contract is stable, disable automatic
new-column extraction unless schema expansion is explicitly intended; otherwise a route can
make the shared table dirty by changing its physical surface during a re-run.

### Shared People: evidence, employment, and qualification

| Component | Observed configuration | Reusable lesson |
| --- | --- | --- |
| People source field | Three real source IDs converge into one native source column | Preserve native lineage even when several discovery paths share one destination |
| `Company Table Data` | One lookup appears immediately after the source | Bring company truth into People once instead of routing competing snapshots |
| `Still Employed? / Use AI / <model>` | Consumes LinkedIn Experiences, optional Enrich Person, Job Title, Company Name, and Full Name; strict schema with `response` (`YES`, `NO` or `REVIEW`) and `countryCode` | Decide current employment with one AI action, because string matching fails on rebrands, acquisitions, legal suffixes and translated names; expose the verdict as a mapped child |
| Employment gate | Exact formula shown below | Gate employment work on company fit plus the exact evidence identity required by the campaign |
| `Contact Qualification / Use AI / 5 Mini` | Uses supplied person, role, normalization, enrichment, and company lookup data; strict schema with `status`, `persona_description`, `score`, `first_name_for_copy`, and `company_name_for_copy` | Keep persona judgment separate from employment and return one coherent decision object |
| Contact gate | `{{Still Employed?}}?.response=="YES"` | Require the exact positive employment value; never gate on truthiness |
| Visible outputs | `Still Employed?`, `Status`, and `Fit Score` are mapped child fields linked to their parent actions | Map the few business values an operator scans; keep the structured parent for downstream bindings |

The example current-employment action runs on:

```javascript
String({{Company Table Data}}?.["Qualification"]||"").trim().toLowerCase()==="qualified"
&& !!String({{People Sources}}?.["LinkedIn URL"]||{{People Sources}}?.linkedinUrl||"").trim()
```

Source labels are an audit surface too. If a People table's source labels name a different
campaign, event, or list than the table itself, the rows prove that several sources
converge, but the mismatch is not clean lineage by itself. Treat it as an audit finding
until the owner confirms that cross-campaign reuse is intentional; otherwise separate or
rename the destination so an operator can trust what population it contains.

## Detect and verify grouped columns

A full table-object read (`clay.get_table(table_id)`) identifies groups, and
`clay.get_field_groups(table_id)` returns them directly. The group definitions live in
`table.fieldGroupMap`; each member field carries the same `groupId`.

```text
table.fieldGroupMap[<group-id>]
  -> name
  -> type
  -> fields[]
  -> settings
  -> groupDetails          # present for richer groups such as waterfalls

table.fields[*].groupId    # joins an individual field to the group
```

Verify the group as a two-sided join. Checking that a group name exists is not enough:

1. Find the group by ID in `fieldGroupMap` and confirm its name and type.
2. Resolve every declared member ID to a real field.
3. Confirm every intended member field points back to that same `groupId`.
4. Reject missing, unexpected, or duplicated members.
5. For a waterfall, also confirm `groupDetails.sequenceSteps`, the output or merge field,
   provider order, validation settings, and the group-level run condition.
6. Open the view and confirm the group renders in the intended place. Group membership does
   not by itself prove the operator-visible ordering or collapsed state.

Create a basic visual group with Rex:

```python
group_id = clay.create_field_group(table_id, [run_1_id, run_2_id], "Website Scrape")
```

Under the hood this uses the internal table group surface: it first posts the member field
IDs and then sets the returned group metadata:

```text
POST /tables/<table-id>/fields/group
{
  "fieldIds": ["<run-1-field-id>", "<run-2-field-id>"]
}

POST /tables/<table-id>/fields/group/<group-id>
{
  "name": "Website Scrape",
  "type": "basic",
  "fields": [
    {"id": "<run-1-field-id>"},
    {"id": "<run-2-field-id>"}
  ]
}
```

If Clay stops accepting this minimal shape, read a working basic group from a live table and
match it rather than guessing. The load-bearing fallback logic remains on the action fields. A group
organizes one conceptual component for the operator; it does not make Run 2 conditional on
Run 1.

## Build grouped website evidence with a fallback

A well-built Companies table displays `Website Scrape` as one component made of multiple
action columns. The intended reusable shape is:

```text
cheap company eligibility gate
  -> Company Website Evidence / Claygent / Run 1 / <model>
  -> Company Website Evidence / Claygent / Run 2 / <model>
  -> Company Fit Qualification / Use AI / <model>
```

Configure Run 1 as neutral research:

- use case: `claygent`;
- inputs: canonical company name, normalized domain, and company LinkedIn URL when useful;
- browsing scope: official company sources first, with a bounded page or search budget;
- job: return identity and offering evidence, evidence atoms, source URLs, missing or unclear
  evidence, and confidence;
- output: native structured JSON, so no later action has to parse prose;
- run condition: canonical identity exists and every cheaper deterministic company gate has
  passed;
- no fit verdict and no outreach copy.

Configure Run 2 as a real fallback. It must never be a duplicate run:

- same evidence contract as Run 1 so the qualifier can consume either result;
- a different research route only when it increases coverage;
- run only when the row remains eligible and Run 1 is missing, errored, explicitly
  unresolved, or below the approved confidence threshold;
- do not trigger it merely because Run 1 returned a valid negative fact.

Express the gate from explicit output state whenever possible:

```text
eligible_company
&& (
  !run_1
  || run_1.status === "UNRESOLVED"
  || run_1.confidence === "LOW"
)
```

Avoid `Run 1 || Run 2` as the canonical merger when Run 1 can contain a non-null but weak
result. Downstream logic should either receive both objects and choose according to explicit
status, or use deterministic merge logic that prefers a usable fallback over a weak first
result.

Group both action fields under `Website Scrape` only after their individual contracts are
correct. Then prove three real cases:

1. eligible row, usable Run 1: Run 1 succeeds and Run 2 says `Run condition not met`;
2. eligible row, failed or unresolved Run 1: Run 2 executes;
3. ineligible row: neither action executes.

## Build company qualification

Company qualification is a separate `Use AI` action. It applies approved segment logic to
evidence already collected; it does not browse again.

Technical contract:

| Setting | Required configuration |
| --- | --- |
| Name | `Company Fit Qualification / Use AI / <model>` |
| Use case | `use-ai`, not Claygent |
| Inputs | canonical firmographics, deterministic gates, Run 1 object, Run 2 object |
| Prompt | decision criteria plus explicit instruction to use only supplied row data |
| Optional evidence | rendered null-safely so a missing fallback cannot break the prompt |
| Output | native JSON Schema with the approved verdict and evidence-backed reason |
| Run condition | required identity exists and at least one admissible evidence object exists |
| Mapping | visible business outputs only when operators filter, scan, route, or hand them off |

When interpolating optional structured actions into an AI prompt, use a null-safe binding,
for example the Clay equivalent of:

```text
format_for_ai(run_1 || "")
format_for_ai(run_2 || "")
```

The business schema may vary, but the technical separation should remain:

```json
{
  "verdict": "<approved enum>",
  "reason": "<evidence-backed explanation>",
  "confidence": "<approved enum, only when consumed>"
}
```

Configure this as the action's native output schema. A JSON example inside the prompt is not
enough. A strict object schema should declare every downstream property, require the fields
that every successful result must contain, and reject undeclared properties:

```json
{
  "type": "object",
  "properties": {
    "verdict": {"type": "string", "enum": ["<approved values>"]},
    "reason": {"type": "string"}
  },
  "required": ["verdict", "reason"],
  "additionalProperties": false
}
```

If a property can be absent, make that nullability explicit in the schema and make
every consumer null-safe. Do not let the prompt promise a field the action schema drops.

Do not invent a score, taxonomy, confidence field, or review status because another campaign
used one. When a visible `Qualification` field is required, map it from the action's native
structured result or create one deterministic business mapping. Do not create a ladder of
formula extractors for every AI property.

Treat prompt, bindings, output schema, and run condition as one atomic configuration. A
prompt edit that refers to a new property is incomplete until the schema and every consumer
are updated. Prove the result by reading the complete cell value. A successful column-update
response does not prove the output.

## Build Claygent people discovery

Place the people-search Claygent on qualified Companies. It is one of two discovery paths.
The final People table is separate.

Technical contract:

- use case: `claygent`;
- input: canonical company identity plus the approved geography, persona families, title
  exclusions, current-employment rule, and evidence-source policy;
- output: a native `contacts[]` array;
- every contact must be independently routable;
- return an empty array when no person is proven;
- run condition: the company verdict equals the approved positive verdict and canonical
  company identity exists.

Minimum reusable contact item:

```json
{
  "fullName": "string",
  "jobTitle": "string",
  "companyName": "string",
  "companyDomain": "string",
  "linkedInUrl": "string or null",
  "currentRoleEvidenceUrl": "string",
  "currentRoleEvidence": "string"
}
```

Set the action output to a native object schema whose `contacts` property is an array and
whose `items` schema requires the fields needed by the route. `contacts` itself should be
required and may be an empty array. This gives `Send table data` one stable `contacts[]` path
instead of asking it to parse prose or accept several possible result shapes.

Add campaign-specific fields only when the People table has a named consumer for them. Do
not require LinkedIn when official or other approved public evidence can prove the current
role. Do not route a contact that fails the Claygent's own geography, persona, or current-role
contract.

## Build a Find People source

Create Find People only after Company qualification has finished. Its company lookup
captures the current Companies data, so creating it against unfinished qualification can
produce an incomplete or polluted source.

Create it with `clay.create_find_people_source(workbook_id, table_name, inputs)`, which
returns the new `tableId`, `viewId`, `workbookId`, and `sourceId`. Under the hood it uses
the source-creation endpoint and action contract:

```text
POST /sources/create-cpj-table
actionKey: find-lists-of-people-with-mixrank-source
actionPackageId: e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2
cpjConfig.type: people
hasEvaluatedInputs: false
disableTriggerOnCreate: true
disableTriggerOnUpdate: true
```

The three company-scope inputs must agree:

```json
{
  "company_table_id": "<qualified-companies-table-id>",
  "company_table_view_id": "<qualified-companies-view-id>",
  "company_table_field_id": "<domain-column-id>",
  "company_identifier": ["company-one.com", "company-two.com"]
}
```

`company_table_field_id` must point to the Companies domain column, not its source field.
`company_identifier` must contain the actual normalized domains from the qualified view.

This source filters people by company domain. Use it when each qualified company has its own
domain. When branches, franchisees, or local subsidiaries share the brand's domain, a domain
filter pulls people from every branch in every country; scope people by company LinkedIn URL
instead, with the DSL people search source (`run-search-dsl-export-to-s3` with
`clay.filter_to_companies(...)` on the LinkedIn URL column) described in
[`design-clay-table-json`](../../design-clay-table-json/SKILL.md).
After creation, read the source immediately and assert:

```text
include_company_filter_identifier_count > 0
```

If the count is zero, stop. The source is not safely company-scoped. Do not build downstream
actions around it. Source membership state can outlive row deletion; if a source has already
admitted the wrong population, rebuild the staging table and source rather than assuming row
deletion repaired its internal scope.

Additional requirements:

- this MixRank Find People source has no arbitrary total-search cap; the company filter bounds
  it. A DSL people search is the opposite case: its limit goes inside the query (`limit N`,
  plus a per-company cap such as `limit 3 by clay_company_id`), or it imports every match;
- job-title, seniority, and person-geography filters come from the approved persona brief;
- discover the generated `type: source` field ID after creation with
  `clay.get_source_field_id(table_id)`; never assume a fixed ID;
- use the company lookup Clay creates automatically; do not create a duplicate lookup;
- access lookup values as `{{LOOKUP}}?.["Column Name"]`, not through `.record`;
- keep the staging table thin: source, auto-created lookup, the minimum route bindings, and
  one `Send table data` action.

## Route both sources into one People table

Build the shared People table before either route. Both sources must satisfy one canonical
destination contract and preserve their real Clay source lineage.

### Claygent list route

Create the `route-row` / `Send table data` action with
`clay.create_route_row_column(table_id, name, target_table_id, row_data, condition=...,
list_data=...)` (or clone a verified one) and configure:

```text
actionKey: route-row
destination tableId: <shared-people-table-id>
method/type: list
listData: <people-search-action>.contacts[]
rowData:
  companyName: canonical company name
  companyDomain: canonical company domain
  companyRecordId: source company record ID
  prospectingSource: "Claygent"
run condition: contacts exists && contacts.length > 0
```

List mode creates one destination record per contact. In the destination source payload,
the contact item and parent company data may occupy different nested paths. Read one actual
routed record before binding downstream actions; do not assume the path from another table.

### Find People single-row route

Use the same action family, but configure single-row mode by leaving `list_data` unset:

```text
actionKey: route-row
destination tableId: <same-shared-people-table-id>
no type: list
no listData
rowData:
  fullName: source person name
  jobTitle: latest experience title
  linkedInUrl: source profile URL when present
  companyName: company lookup name
  companyDomain: source or lookup domain
  personSourceRecordId: source record ID
  prospectingSource: "Find People"
run condition: approved usable identity exists
```

A usable identity may be a personal LinkedIn URL or an approved combination such as
normalized full name plus company domain and current-role evidence. The rule belongs to the
campaign contract; it must not silently become `LinkedIn required`.

After each route is created:

1. read the action back (`clay.get_column(...)`) and confirm destination, mode, bindings,
   and condition;
2. run one source record (`clay.run_and_wait(table_id, [route_field_id], [record_id])`);
3. locate the new destination record through the real source field;
4. compare every nested routed property with the origin;
5. record the source ID and source label;
6. only then run the remaining eligible records.

Deduplicate in the shared People table before paid enrichment. Prefer normalized LinkedIn
URL; use the approved name-plus-domain fallback when LinkedIn is absent. Do not assume two
different route sources upsert against one another automatically.

## Verify current employment

Current employment begins as an evidence problem and ends as one exact positive business
gate. Keep evidence collection, employment adjudication, and persona qualification separate.

When a personal LinkedIn URL exists, configure `LinkedIn Experiences / Claygent / <model>`:

- input: the personal LinkedIn URL and no unverified manual identity overrides;
- output: native `experiences[]`;
- every experience includes `title`, `company`, optional dates and location, and required
  `isCurrent: boolean`;
- `isCurrent` comes only from an explicit current-role marker in the source;
- a missing end date alone must not be treated as current.

Use a person-enrichment action only as fallback when primary evidence is absent or weak. For
contacts without LinkedIn, consume the official or approved current-role evidence routed by
the discovery path.

Decide current employment with one `Still Employed? / Use AI / <model>` action, never with a
formula. A domain or name match looks deterministic, but legal suffixes (`GmbH`, `Inc.`,
`Ltd`), rebrands, acquisitions, parent and subsidiary names, translated or localized
company names, promotions, and concurrent roles all defeat string comparison, and a formula
answers confidently when it is wrong.

The action judges whether the person currently works at the target company. It compares the
person's current role and company evidence (LinkedIn experiences, the person-enrichment
fallback, or the official evidence carried by the discovery route) with the target company's
name, domain, and LinkedIn URL. It must:

- consume supplied evidence only and never browse;
- run only after company fit and the action-specific evidence identity are present;
- treat a role as current only on an explicit current marker, never on a missing end date
  alone;
- count the target company as matched across rebrands, acquisitions, legal suffixes, and
  translated names when the evidence supports that it is the same company, and say which
  evidence supports it;
- return a native strict schema with required `response`, enum `YES | NO | REVIEW`, and no
  additional properties; use `REVIEW` when the evidence conflicts or is too thin to decide;
- expose one mapped `Still Employed?` child for filtering and downstream gates;
- return any extra property such as language or country only when a named consumer uses it;
- leave persona fit to the later Contact Qualification action.

The verified current title, current-employment verdict, and evidence identity must come from
the same matched experience. A manually sourced title may help locate evidence, but it cannot
authorize persona fit when the verified current title differs. Do not use truthiness as the
gate: `!!{{Still Employed?}}` also admits `NO` and `REVIEW`. Require the exact positive value `YES`.

## Build contact qualification

Contact qualification is a `Use AI` action after company fit and employment are proven. It
does not browse and it does not decide whether the company belongs in the campaign again.

Technical contract:

| Setting | Required configuration |
| --- | --- |
| Name | `Contact Qualification / Use AI / <model>` |
| Use case | `use-ai` |
| Inputs | canonical person identity, verified current title, current-role evidence, company verdict, approved persona logic |
| Prompt | apply persona, function, seniority, exclusion, and authority rules to supplied data only |
| Output | native JSON Schema with approved contact verdict and evidence-backed reason |
| Run condition | company positive verdict, exact positive current-employment verdict, verified current title present |
| Consumer | copy gate, ranking or cap logic, and operator-visible final status |

When the company evidence is needed, bring it through one Company Table Data lookup keyed by
canonical domain. Do not trust two routed snapshots as competing sources of truth.

The action must bind the verified current title. The title supplied by the discovery source
is not enough on its own. After a repair, clear or reset stale successful outputs on rows that no
longer meet the condition. Otherwise an ineligible row can retain a plausible old verdict.

Do not add a second `Copy Eligibility` AI action. Contact qualification plus exact current
employment is the copy gate unless the campaign defines a separate deterministic control.

## Prove the complete chain on real rows

A technically complete build needs an execution proof as well as a schema proof. Use the
smallest real control set that covers every branch:

| Control row | Expected behavior |
| --- | --- |
| Company passes cheap gates; Run 1 strong | Run 1 runs, Run 2 does not, company qualifier runs |
| Company passes; Run 1 unresolved | Run 2 runs, qualifier consumes both safely |
| Company fails cheap gate | no website research or qualifier spend |
| Claygent returns contacts | list route creates one People row per contact |
| Find People returns a usable person | single-row route creates one People row |
| Same person from both sources | deterministic dedupe identifies the collision |
| Explicit current company match | `Still Employed?` returns the exact positive value `YES` |
| Former or unresolved role | contact qualifier does not run and no stale result remains |

For each control, preserve:

- origin record ID and destination record ID;
- field IDs, source IDs, group IDs, and view IDs;
- action name, model, account, prompt, schema, bindings, and run condition readback;
- cell status and complete value;
- row counts before and after routing;
- eligible, attempted, succeeded, skipped, errored, and awaiting-callback counts.

Finish with a browser read of the operator view. Confirm that `Website Scrape` is visibly one
component, the action order tells the dependency story, fallback cells show `Run condition
not met` on the normal path, business verdicts are easy to scan, and implementation helpers
do not make the table look like its build history.
