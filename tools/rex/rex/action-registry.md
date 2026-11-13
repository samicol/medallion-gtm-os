# Clay Action Registry

Every known Clay action with exact keys, input names, output keys, gotchas, and code examples.
For actions not listed here, use `clay.search_enrichments("keyword")` to discover them (Section 8).

Auth account IDs are workspace-specific. Read them from the `authAccounts` map in
`rex-config.json` (copy `rex-config.example.json`), for example
`cfg = clay_flow.load_config(); cfg["authAccounts"]["openai"]`. The names (`openai`, `rapidapi`,
...) are whatever you called each account there; list your accounts with
`clay.list_auth_accounts()`.

---

## 1. AI & Content

> **Build AI columns by cloning a working one.** If you have any AI column that
> already runs in your workspace, use `clay.clone_column(...)` and swap only
> the prompt (and condition). It keeps the model, auth account and output
> schema exactly as they work today. Hand-built configs are often accepted by
> Clay and then never run. See clay-api-reference.md > "Creating a Use AI
> Column".
>
> **Model names:** use the exact model id a working column in your workspace
> uses. A typo'd or retired model name can leave every cell queued forever
> with no error. The model names below are examples from when this was
> written and may have changed. For per-row work, pick the cheapest model that
> passes a one-record and small-sample test.

### Create Content (no web access)

Generates text/JSON from data already in the table. Cheap, fast, deterministic.

- **key:** `use-ai`
- **package:** `67ba01e9-1898-4e7d-afe7-7ebe24819a57`
- **inputs:**
  - `useCase`: `'"use-ai"'` (NOT "claygent")
  - `model`: `'"gemini-2.5-flash"'` or `'"grok-4-1-fast-reasoning"'` (for JSON)
  - `prompt`: formula string with column refs
  - `systemPrompt` (optional): `'"You are a..."'`. Keep under 1000 chars, no markdown
- **output:** text or JSON (use `?.key` to extract fields)
- **auth:** `cfg["authAccounts"]["gemini"]` or `cfg["authAccounts"]["grok"]`
- **gotchas:**
  - actionKey is `"use-ai"`, NOT `"ai"`. `"ai"` silently drops all inputs
  - For JSON output: use Grok + `answerSchemaType`. Gemini/GPT wrap JSON in code fences.
  - `answerSchemaType` needs `formulaMap` (not `formulaText`) + `_metadata` input with `"modelSource": "user"`
  - JSON schemas must be double-encoded: `json.dumps(json.dumps(schema))`

```python
clay.create_action_column(t_id, "Qualify Lead",
    action_key="use-ai",
    package_id="67ba01e9-1898-4e7d-afe7-7ebe24819a57",
    inputs={
        "useCase": '"use-ai"',
        "model": '"gemini-2.5-flash"',
        "prompt": '"Qualify this company:\\n" + {{@Enrich Company}}',
    },
    auth_account_id=cfg["authAccounts"]["gemini"],
    view_id=v_id)
```

### Claygent (web research)

AI agent that browses the internet to find answers. Costs more per row than Create Content (dollars on your own model key, Clay credits on a Clay-managed key; see "How AI columns are billed" in `clay-api-reference.md`) but can look up live data.

- **key:** `use-ai` (same as Create Content)
- **package:** `67ba01e9-1898-4e7d-afe7-7ebe24819a57`
- **inputs:**
  - `useCase`: `'"claygent"'` (this differentiates it from Create Content)
  - `model`: `'"gpt-5-nano"'` (cheapest) or `'"gpt-4.1"'` (complex research)
  - `prompt`: research instruction with column refs
- **output:** text research results
- **auth:** `cfg["authAccounts"]["openai"]`
- **gotchas:**
  - Same actionKey `"use-ai"` as Create Content. `useCase` differentiates
  - More expensive (agent loop + web search), use only when table data isn't enough
  - Best with OpenAI models (GPT), not Gemini

```python
clay.create_action_column(t_id, "Research Company",
    action_key="use-ai",
    package_id="67ba01e9-1898-4e7d-afe7-7ebe24819a57",
    inputs={
        "useCase": '"claygent"',
        "model": '"gpt-5-nano"',
        "prompt": '"Find the exact employee count for " + {{@Company LI URL}}',
    },
    auth_account_id=cfg["authAccounts"]["openai"],
    view_id=v_id)
```

---

## 2. Enrichment

### Enrich Company (MixRank)

Firmographics, funding, tech stack, employee count from LinkedIn company URL.

- **key:** `enrich-company-with-mixrank-v2`
- **package:** `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`
- **inputs:**
  - `company_identifier`: LinkedIn company URL (NOT company name, NOT domain)
- **output keys:** `?.name`, `?.url` (LI URL), `?.website`, `?.description`, `?.employee_count`, `?.industry`, `?.country`, `?.founded`, `?.org_id`
- **does NOT return:** `domain`, `city`, `funding_stage`, `short_description`
- **auth:** none needed (Clay-managed enrichment)
- **gotchas:**
  - Input name is `company_identifier`, NOT `url` or `domain`
  - Company names like "Stealth" or "Cuez" fail with `ERROR_INVALID_INPUT`
  - Best practice: extract LI company URL from Enrich Person → `experience[0].url` using `mappedResultPath`

```python
clay.create_action_column(t_id, "Enrich Company",
    action_key="enrich-company-with-mixrank-v2",
    package_id="e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
    inputs={"company_identifier": '{{@Company LI URL}}'},
    view_id=v_id)
```

### Enrich Person (MixRank)

Profile data, job title, experience history from LinkedIn profile URL.

- **key:** `enrich-person-with-mixrank-v2`
- **package:** `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`
- **inputs:**
  - `person_identifier`: LinkedIn profile URL (NOT `linkedin_url`, NOT `url`)
  - `email`: include as empty binding (required even if blank)
- **output keys (top-level):** `?.title`, `?.org`, `?.location_name`, `?.headline`, `?.url`, `?.num_followers`, `?.connections`
- **nested data (use `mappedResultPath`):**
  - `["experience", "0", "url"]`: current company LI URL
  - `["experience", "0", "org"]`: current company name
- **auth:** none needed (Clay-managed enrichment)
- **gotchas:**
  - Input name is `person_identifier`, NOT `linkedin_url`
  - MUST include empty `email` input (silently required)
  - Nested paths need `mappedResultPath` array or formula returns empty

```python
col = clay.create_action_column(t_id, "Enrich Person",
    action_key="enrich-person-with-mixrank-v2",
    package_id="e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2",
    inputs={"person_identifier": '{{@Person LI URL}}', "email": ""},
    view_id=v_id)

# Extract nested company URL:
clay.create_formula_column(t_id, "Current Company URL",
    formula_text=f'{{{{{col["id"]}}}}}',
    mapped_result_path=["experience", "0", "url"], view_id=v_id)
```

---

## 3. Sources (Table Creation)

> **Find People and Find Companies are NOT configured the same way.** Earlier
> versions of these docs said they were, and following that returns HTTP 400.
> Use the client helpers below; they build the full request body. The side by
> side comparison is in clay-api-reference.md > "create-cpj-table".

### Find Companies (MixRank Source)

Creates a new table of companies matching filters (industry, size, country, type).

- **key:** `find-lists-of-companies-with-mixrank-source`
- **package:** `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`
- **endpoint:** `POST /sources/create-cpj-table` (NOT regular `POST /sources`)
- **client:** `clay.create_find_companies_source(workbook_id, table_name, inputs)`
- **returns:** `{"tableId", "viewId", "workbookId", "sourceId", "isNewTable"}`
- **source fields:** `.name`, `.linkedin_url` (NOT `.url`), `.domain`, `.country`, `.size`, `.description`, `.industry`, `.location`, `.type`
- **gotchas:**
  - `hasEvaluatedInputs` MUST be `True` (False = 400). The helper sets it.
  - `cpjConfig.typeSettings` must be the full source object, not just `{inputs}`; top level needs `workspaceId` (string) and `workbookName`. The helper sets these.
  - Regular `POST /sources` returns 404 "Invalid subscriptions"
  - Requires a Clay plan with source subscriptions
  - The search runs on creation. The table then holds only the source column: add formula extractors before using or exporting it.
  - `description_keywords` is a literal text match on the company description and narrows hard. For broad pools, start with `industries` + `country_names` + `sizes`.

```python
res = clay.create_find_companies_source(wb_id, "Companies - Insurance DE", inputs={
    "sizes": ["200", "500", "1000", "5000"],
    "types": ["Privately Held", "Public Company"],
    "industries": ["Insurance"],
    "country_names": ["Germany"],
    "company_identifier": [],
    "exclude_entities_configuration": [],
})
src = clay.get_source_field_id(res["tableId"])
clay.create_formula_column(res["tableId"], "Company Name", f"{{{{{src}}}}}?.name", view_id=res["viewId"])
clay.create_formula_column(res["tableId"], "Domain", f"{{{{{src}}}}}?.domain", view_id=res["viewId"])
clay.create_formula_column(res["tableId"], "Company LinkedIn", f"{{{{{src}}}}}?.linkedin_url", view_id=res["viewId"])
```

### Find People (MixRank Source)

Creates a new table of people matching filters (job title, geography), optionally limited to the companies in one of your tables.

- **key:** `find-lists-of-people-with-mixrank-source`
- **package:** `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`
- **endpoint:** `POST /sources/create-cpj-table`
- **client:** `clay.create_find_people_source(workbook_id, table_name, inputs)`
- **returns:** `{"tableId", "viewId", "workbookId", "sourceId", "isNewTable"}`
- **source fields:** `.first_name`, `.last_name`, `.name`, `.latest_experience_title`, `.location_name`, `.domain`, `.url` (LinkedIn profile URL, NOT `.linkedin_url`)
- **gotchas:**
  - `hasEvaluatedInputs` MUST be `False` (the opposite of Find Companies). The helper sets it.
  - **Company filtering needs all of these together**, or the search ignores your companies and returns people from anywhere who match the title keywords:
    - `company_table_id` + `company_table_view_id`: your Companies table and view (the table must have rows; empty = 400)
    - `company_table_field_id`: the **Domain column** on that table, NOT its source column
    - `company_identifier`: a **non-empty list of domain strings** read from that table
    - `start_from_method`: `"query"`
  - Setting `company_table_id` auto-creates a `lookup-company-in-other-table` column. Do not create it yourself (400 "field already exists"). Read company columns through it with `{{LOOKUP}}?.["Column Name"]`, not `?.record?.["Column Name"]` (returns null).
  - The source column id is generated for API-created tables. Use `clay.get_source_field_id()`, never a hard-coded id.
  - After creation, spot-check a few rows: do these people work at your companies?
  - **Domain scope vs LinkedIn scope.** This source filters people by company domain. Use it when each company has its own domain. When branches, franchisees, or local subsidiaries share the brand's domain, a domain filter pulls people from every branch in every country; scope people by company LinkedIn URL instead, with the DSL people search source (`run-search-dsl-export-to-s3` with `clay.filter_to_companies(...)`) described in [`skills/design-clay-table-json`](../../.claude/skills/design-clay-table-json/SKILL.md). That source takes its row limit inside the query. The same skill also covers `trigger-find-people-source`, an action on the Companies table that starts a people search for one company; its inputs are not documented here, so follow that skill.

```python
companies = clay.list_records(T_COMPANIES, V_COMPANIES, field_ids=[F_DOMAIN])
domains = [r["cells"][F_DOMAIN]["value"] for r in companies if r["cells"].get(F_DOMAIN, {}).get("value")]

res = clay.create_find_people_source(wb_id, "People - Find People", inputs={
    "job_title_keywords": ["Head of Finance", "CFO"],
    "job_title_mode": "smart",
    "start_from_method": "query",
    "company_table_id": T_COMPANIES,
    "company_table_view_id": V_COMPANIES,
    "company_table_field_id": F_DOMAIN,      # Domain column, not the source column
    "company_identifier": domains,           # must not be empty
})
t_people = res["tableId"]
src = clay.get_source_field_id(t_people)
lookup = next(f["id"] for f in clay.get_table(t_people)["table"]["fields"]
              if "lookup-company-in-other-table" in (f.get("typeSettings") or {}).get("actionKey", ""))

clay.create_formula_column(t_people, "Full Name", f"{{{{{src}}}}}?.name", view_id=res["viewId"])
clay.create_formula_column(t_people, "Job Title", f"{{{{{src}}}}}?.latest_experience_title", view_id=res["viewId"])
clay.create_formula_column(t_people, "LinkedIn Profile", f"{{{{{src}}}}}?.url", view_id=res["viewId"])
clay.create_formula_column(t_people, "Company Name", f'{{{{{lookup}}}}}?.["Company Name"]', view_id=res["viewId"])
```

### Search DSL Source (addition beyond upstream v2.1, reverse-engineered and verified live 2026-09-24)

The people/company search the Clay UI builds today. Use it instead of Find People (MixRank) when the
filter needs anything MixRank's inputs cannot express: **job-start recency, person or company
country, company size, industry exclusion**, or any mix of them in one query. Proven live on a
production workbook (a new-revenue-leaders workflow).

**Do not hand-build these through `POST /sources/create-cpj-table`.** A hand-built body with
`actionKey: run-search-dsl-export-to-s3` passes validation only with a `previewActionKey`, and every
guessed value fails at run time with `404 "Incorrect source configuration for source with id s_..."`
(it also leaves a broken table behind). Clay's UI uses a separate `search-dsl` API family instead:

| Step | Endpoint | Body | Returns |
|---|---|---|---|
| Preview (free, imports nothing) | `POST /workspaces/{ws}/search-dsl/query` | `{"query", "selectMode": "preview"}` | `{totalCount, rowCount, rows (≤250), previewCoverage, durationMs}` |
| Create table + source, run it | `POST /workspaces/{ws}/search-dsl/send-to-table` | `{"dslQuery", "tableName", "workbookId"}` (also accepts `destinationTableId`, `budgetId`) | `{tableId, viewId, workbookId, sourceId}` |
| Change query and re-run | `POST /workspaces/{ws}/search-dsl/sources/{sourceId}/update-and-run` | `{"dslQuery", "mode": "add" \| "replace"}` | `{sourceRunId}` |
| Run status | `GET /workspaces/{ws}/sources/{sourceId}/runs` | | `runs[]` with `status`, `numberOfRowsAdded` |

- **client:** `clay.search_dsl_preview(query)`, `clay.send_search_dsl_to_table(query, table_name, workbook_id)`,
  `clay.update_and_run_search_dsl_source(source_id, query, mode="add")`
- **source it stores:** `actionKey: run-search-dsl-export-to-s3`, `previewActionKey: null`,
  `hasEvaluatedInputs: true`, `idPath: clay_metadata.clay_profile_id`, `sourceRecordLimit: 50000`,
  `inputs: {dslQuery, entityType: "people", selectProjectionName: "table-legacy-filters-people", selectProjectionVersion: 1}`
- **auto-created columns (people):** First Name, Last Name, Full Name, Job Title
  (`.matched_experience.title`), Company (`.matched_experience.company.name`), City, State or
  Province, Country (`.structured_location.*`), LinkedIn Profile (`.social_urls.linkedin`)
- **full record payload** (read nested paths directly, e.g. `{{f_people_search}}.matched_experience.start_date`):

```json
{
  "clay_metadata": {"clay_profile_id": 798011650, "company_record_id": null, "company_table_id": null},
  "first_name": "Miles", "last_name": "Jennings", "name": "Miles Jennings",
  "matched_experience": {
    "title": "Head of Marketing & Growth", "start_date": "2026-08", "end_date": "",
    "company": {"clay_company_id": 16093741, "domain": "reveliolabs.com", "name": "Revelio Labs",
                "social_urls": {"linkedin": "https://www.linkedin.com/company/revelio-labs"}}
  },
  "social_urls": {"linkedin": "https://www.linkedin.com/in/miles-j-92029/"},
  "structured_location": {"city": "Farmington", "state_or_province": "Connecticut",
                          "country": "United States", "country_iso": "US", "region": "NAM"}
}
```

  `matched_experience` is the experience that satisfied the query, so `start_date` (YYYY-MM) gives
  tenure in role with a plain formula, and `company.domain` / `company.social_urls.linkedin` give the
  keys for a Companies table derived from People.

- **proven query syntax** (new-to-role people, US/Canada, company size + industry exclusion):

```text
select from people
where location_country in ("United States", "Canada")
  and experiences.count(is_current = true
    and job_title is_similar_to ("VP of Sales", "Head of Marketing", "Director of Growth")
    and start_date >= today() - interval 3 months
    and company.locations.count(country_name in ("United States", "Canada")) >= 1
    and company.company_size in ("11-50", "51-200", "201-500")
    and company.industry not_in ("Staffing and Recruiting", "Human Resources")) >= 1
limit 20000
```

- **gotchas:**
  - **The run starts the moment `send-to-table` returns**, even though the stored source says
    `disableTriggerOnCreate: true`. The query's `limit N` is the only row cap, so the helpers refuse a
    query without one. Preview first and set `N` from `totalCount`.
  - **The new table is created with `AUTO_RUN_ON: true`.** `send_search_dsl_to_table()` switches it off;
    do the same if you call the endpoint directly.
  - Preview is free and returns the true `totalCount` for the whole query plus up to 250 sample rows
    (`previewCoverage: "partial"` when the sample is capped). Use it to size a search before importing.
  - `runs[0].status` can still read `QUEUED` after the rows have landed. Count rows with
    `get_record_ids()` rather than trusting the run status alone.
  - Over the records API the source cell's `value` is only the preview text (the person's name). Read
    nested data through a formula on the source field, not from the cell.
  - `is_similar_to` is fuzzy: a title list for VP/Head/Director of Sales also returns "Growth Lead",
    "Senior Sales Manager" and staffing "bench sales" titles. Keep a deterministic title gate downstream.
  - Company size uses LinkedIn buckets (`"2-10"`, `"11-50"`, `"51-200"`, `"201-500"`, ...). A 10-250 band
    cannot be cut exactly in the query: include the bucket that crosses the edge and gate on the real
    employee count downstream.
  - `update-and-run` modes, both verified live 2026-09-24:
    - **`add` loads the next page.** It skips people the source already returned and appends up to `N`
      new ones. Running the same `limit 25` query twice gave 50 different people, not a no-op.
    - **`replace` deletes every existing row and re-imports** from the new query (50 old rows gone,
      500 new rows in). Anything built on those rows is lost with them, so use it before adding columns
      that hold written values, never after.
  - **Search imports cost 0 Clay credits.** Balance 6,200 before and after a 500-row import. The plan's
    `findPeopleSearchLimit` / `peopleTableRowLimit` (50,000 on Growth) cap how many rows one search can
    return; read them from `GET /workspaces/{ws}` → `featureFlags`. Credit balance:
    `GET /workspaces/{ws}/credit-balance` → `{"balance"}`.
  - Also in the same API family, found but not yet exercised: `POST /workspaces/{ws}/audiences/v2/dsl.diagnose`
    (compile a query without running it), `.../audiences/v2/dsl.fields` (fields a query can reference),
    `.../search-dsl/summarize` (plain-English summary of a query).
  - How this was found: the route contracts ship in Clay's web bundle (`app.clay.com/assets/store-*.js`,
    search for `search-dsl`). Re-check there if an endpoint starts returning `NoMatchingURL`.
  - **`clay.filter_to_companies(@table(...))` adds a `trigger-find-people-source` ACTION column to the
    referenced companies table** (seen 2026-09-25). Never run it (it starts a people search per company);
    tell the table's owner it appeared. Warned in the `send_search_dsl_to_table()` docstring.

#### Search DSL: filterable keys, buckets, scopes and helpers (verified live 2026-09-29)

- **Country on companies (verified 2026-10-13):** `locations.count(country_name = "United States" and is_headquarters = true) >= 1` = US-HQ companies; drop `is_headquarters` for any-location. Top-level `country`/`country_iso` stay Unknown.
- **Filterable company keys (backlog #13).** On `select from companies` only `domain`, `company_size` and
  `industry` were accepted of the keys tried; `clay_company_id`, `id`, `linkedin_url`, `social_urls.linkedin`,
  `url`, `website`, `name`, `company_name`, `org_name`, `linkedin_company_id`, `size`, `country`, `country_name`
  all return 400 `Unknown field '<key>' for entity 'companies'`. Inside people `experiences.count(...)` only
  `company.domain` works (`company.linkedin_url`, `.clay_company_id`, `.id`, `.name` → `Unknown field ... in
  experience expression`). So a LinkedIn-scoped company list needs `clay.filter_to_companies(@table("t:v:f"))`
  (people queries only). `validate_dsl_query()` refuses these keys before the call.
  `POST /workspaces/{ws}/audiences/v2/dsl.fields` and `.../dsl.complete` answer for Clay's CRM *audiences* DSL
  (accounts/people/opportunities), NOT the search DSL, so they cannot be used as its field catalog.
- **company_size buckets (backlog #25):** exactly `"1"`, `"2-10"`, `"11-50"`, `"51-200"`, `"201-500"`,
  `"501-1,000"`, `"1,001-5,000"`, `"5,001-10,000"`, `"10,001+"` (`COMPANY_SIZE_BUCKETS`). Anything else
  (`"501-1000"`, `"10000+"`, `"0-1"`) is a 400 whose message suggests the nearest buckets.
- **Domain is a noisy key (backlog #16).** `domain = "stripe.com"` returns 34-38 company entities (the real
  Stripe plus "DanielTems", an Andorra "Stripe", "Stripe Press"...); `clay.com` returns 7 ("Clay University",
  "The Cla Oven"...), in no useful order. `lookup_companies_by_domain(domains, workbook_id, filters=)` imports
  all of them in one free search and `best_company_for_domain()` ranks name/LinkedIn-slug match, then size.
- **Company search record payload** (source field `f_companies_search`): `name`, `domain`, `size`, `type`,
  `industry`, `description`, `annual_revenue`, `social_urls.linkedin`, `clay_metadata.clay_company_id`,
  `primary_location{city,state_or_province,country,country_iso,region,postal_code,is_headquarters}`,
  `total_location_count`, `total_funding_amount_range_usd`. Preview rows are flatter: `id`, `name`, `size`,
  `industry`, `type`, `location`, `country`, `linkedin_url`.
- **People preview rows are flat (backlog #31):** `id` (clay_profile_id), `name`, `url` (LinkedIn),
  `location_name`, `latest_experience_company`, `latest_experience_title`, `matched_experiences:
  [[company, title, location, start_date, end_date, is_current], ...]`: no company domain. Name them with
  `parse_dsl_preview_row()`. Imported tables get no Company Domain / Start Date column:
  `send_search_dsl_to_table(..., extra_columns=["company_domain", "start_date"])` adds them
  (`{{f_people_search}}.matched_experience.company.domain` / `.start_date`).
- **Scope trade-off (backlog #32):** target companies (`filter_to_companies`) resolves each account to ONE
  Clay company entity, so brands with several entities on a domain can lose people (one client workflow: 19-28
  of 128 companies missed vs a literal domain list); a domain list pulls every entity on that domain,
  branches included. `compare_dsl_scopes(people_where, domains, "t:v:f")` previews both (free) and lists the
  companies only one scope found; decide per list. A **preview** with `filter_to_companies` does NOT add the
  #24 side column (only a real import does). Two `filter_to_companies` cannot be OR-ed (400); `@table()` is
  only valid inside `filter_to_companies`; `update-and-run` cannot change target companies.
- **Several sources, one table (backlog #33):** `add_search_dsl_source(table_id, query)` posts
  `send-to-table` with `destinationTableId` (+ the table's `workbookId`/name) → `isNewTable: false`. Set
  `set_table_dedupe(table_id, <LinkedIn Profile>)` first (`tableSettings.DEDUPE_FIELD_ID` +
  `DEDUPE_KEEP_STRATEGY`); live: a 6-person source on a 3-row deduped table gave 6 rows, 6 unique.
- **Source → table:** `GET /sources/{id}` has `tableId: null` for search sources; the table is
  `sourceSubscriptions[0].tableId` (`clay.source_table_id()`), which the `replace` guard (backlog #9) uses.

#### Jobs Search DSL (backlog #22, 2026-09-25): prefer Find Jobs

`select from jobs` exists but its filters differ from its payload: `company.domain`, `job_posted_date` and
`is_open` work; `clay_company_id`, `company_name`, `country` and `linkedin_company_id` are `Unknown field`;
`is_similar_to` needs async compile (preview returns 400). Use the Find Jobs source below (what the reference
hiring workflow uses), not the jobs Search DSL.

#### Folders, workbooks, cell statuses (verified live 2026-09-29)

- Folder: `POST /workspaces/{ws}/folders {"name", "parentFolderId"?}` → `f_...` (nested works). Contents:
  `POST /workspaces/{ws}/resources_v2/ {"parentResource": {"type": "FOLDER", "id": f}, "filters": {}, "isGlobalSearch": false}`.
- Workbook: `POST /workbooks {"name", "workspaceId", "parentFolderId"?, "settings": {"isAutoRun": false}}`;
  read `GET /workspaces/{ws}/workbooks/{id}` (not `/workbooks/{id}`, which is `NoMatchingURL`); description
  `PATCH /workspaces/{ws}/workbooks/{id} {"description"}`.
- A cell whose run condition is false reads `metadata.status: "ERROR_RUN_CONDITION_NOT_MET"` (the view
  filter operator is `RUN_CONDITION_NOT_MET`); errored cells carry `metadata.errorMessagePreview` (e.g. the
  list-clean `502 ... RateLimitError`). Treat every `ERROR_*` as final; retry only plain `ERROR`.
- Run conditions are stored on action columns; a `conditionalRunFormulaText` sent on a formula column is dropped.
  Waterfall formula columns can be created over the API: `{"type": "formula", "typeSettings": {"formulaType":
  "waterfall", "formulaWaterfall": [{"formula", "prompt"?}, ...], "dataTypeSettings": {"type": "text"}}}`.

### Find Jobs (MixRank Source) (addition beyond upstream v2.1, verified live 2026-09-25)

Creates a table of open job postings at the companies in one of your tables. This is what a reference
"Hiring in Function" workflow uses, not the jobs Search DSL.

- **key:** `find-lists-of-jobs-with-mixrank-source` (preview `find-lists-of-jobs-with-mixrank-source-preview`)
- **package:** `e251a70e-46d7-4f3a-b3ef-a211ad3d8bd2`
- **endpoint:** `POST /sources/create-cpj-table` with `cpjConfig.type: "jobs"`
- **client:** `clay.create_find_jobs_source(workbook_id, table_name, company_table_id, company_view_id, company_linkedin_field_id, company_record_ids, company_linkedin_urls, job_title_keywords, max_days_since_posted=30, limit_per_company=1, locations=["United States"], employment_type=["Full-time"], job_title_exclude_keywords=None)`
- **returns:** `{"tableId", "viewId", "workbookId", "sourceId", "isNewTable"}`
- **typeSettings:** `name "Find jobs"`, `idPath "job_id"`, `iconType "Briefcase"`, `recordsPath "jobs"`,
  `previewTextPath "title"`, `defaultPreviewText "Profile"`, `sourceRecordLimit 50000`,
  `hasEvaluatedInputs: true`, `disableTriggerOnCreate/Update: true`, `scheduleConfig.runSettings "once"`
- **inputs:** `startFrom "ClayTableOfCompanies"`, `company_table_id`, `company_table_view_id`,
  `company_table_field_id` (the Company LinkedIn COLUMN), `company_identifier` (LinkedIn URLs) +
  `company_record_id` (record ids, same order), `job_title_keywords`, `job_title_exclude_keywords`,
  `max_num_days_since_posted`, `min_num_days_since_posted: null`, `limit_per_company`, `limit 50000`,
  `locations`, `locations_exclude []`, `employment_type` (`"Full-time"`, `"Contract"`, ...), `seniority []`,
  `has_recruiter false`, `job_description_keywords []`, `exclude_job_identifiers []`, `name ""`
- **source fields** (`FIND_JOBS_FIELDS`): `.company_name`, `.title`, `.company_url` (company LinkedIn),
  `.domain`, `.posted_at`, `.seniority`, `.location`, `.url` (job posting URL)
- **gotchas:**
  - **Runs on create** and costs 0 Clay credits (2 companies x `limit_per_company` 1 = 2 rows in ~10s).
    The company list and `limit_per_company` are the only row caps.
  - Clay creates the table **auto-run ON and auto-named** after the source (e.g. "Full-time US Jobs,
    Account Exec, Software Engineer"). The helper renames it and turns auto-run off, then reads both back.
  - Unlike Find People, it does NOT add a lookup column to the companies table. Join back with
    `create_lookup_column(..., multiple=True)` on Company LinkedIn.

```python
src = clay.get_source_field_id(res["tableId"])
for col, key in FIND_JOBS_FIELDS.items():
    clay.create_formula_column(res["tableId"], col, f"{{{{{src}}}}}?.{key}", view_id=res["viewId"])
```

### Webhook Source

Receives JSON payloads via HTTP POST. Creates a source column with full payload.

- **type:** `"source"` column (not action column)
- **config:** `typeSettings: {"sourceType": "webhook", "sourceIds": []}`
- **gotchas:**
  - Individual fields are NOT auto-populated. You must create formula extractors
  - Extractors: `formulaText: "{{source_field_id}}?.json_key"` with `formulaType: "text"`
  - Common mistake: plain text columns show in UI but are empty (they're not formulas)

---

## 4. Lookups (Cross-Table)

### Lookup Row in Other Table

Find a single matching row in another Clay table.

- **key:** `lookup-row-in-other-table`
- **package:** `4299091f-3cd3-4d68-b198-0143575f471d`
- **inputs (ALL use `fields|` prefix):**
  - `tableId`: target table ID (string literal `'"t_xxx"'`)
  - `fields|targetColumn`: field ID in target table (`'"f_xxx"'`)
  - `fields|filterOperator`: `'"EQUAL"'`, `'"CONTAINS"'`, etc.
  - `fields|rowValue`: formula ref from current table (`'{{@Column Name}}'`)
  - `fields|limit` (optional): max results
- **client:** `clay.create_lookup_column(table_id, name, target_table_id, target_field_id, row_value_field_id, multiple=False, limit=None, view_id=None, operator="EQUAL")` returns the field id (addition beyond upstream v2.1; sets `referencedTableId` too)
- **output:** the API cell value is only `"✅ Record Found"` / `"❌ No Record Found"`. The data is in
  `externalContent.fullValue` as `{"record": {<target column NAME>: value}}` (read it with `read_ai_output()`).
  Extractor: `{{f}}?.record?.["Col"]` (`lookup_extract_formula(f, "Col")`). Text and formula columns both cross.
- **gotchas:**
  - Input names use the `fields|` prefix, NOT just `targetColumn`
  - Without `fields|` prefix, inputs are silently dropped
  - `fields|filterOperator` accepts only `EQUAL` or `CONTAIN`
  - Costs 0 Clay credits, but still runs only when triggered (auto-run off). Prove on 1 row first.
  - **The result is a snapshot.** Changing the target table does not update it, and a plain re-run keeps
    the old value. `run_column(..., force=True)` (`"forceRun": true`) refreshes it (verified 2026-09-25).

```python
clay.create_action_column(t_id, "Find in CRM",
    action_key="lookup-row-in-other-table",
    package_id="4299091f-3cd3-4d68-b198-0143575f471d",
    inputs={
        "tableId": '"t_target_table_id"',
        "fields|targetColumn": '"f_email_field"',
        "fields|filterOperator": '"EQUAL"',
        "fields|rowValue": '{{@Email}}',
    },
    view_id=v_id)
```

### Lookup Multiple Rows in Other Table

Same as Lookup Row but returns multiple matches.

- **key:** `lookup-multiple-rows-in-other-table`
- **package:** `4299091f-3cd3-4d68-b198-0143575f471d`
- **inputs:** Same as Lookup Row (all use `fields|` prefix), plus optional `fields|limit` (0-100)
- **client:** `clay.create_lookup_column(..., multiple=True, limit=10)`
- **output:** display string like "✅ 3 Records Returned"; data in `externalContent.fullValue` as
  `{"records": [{<column NAME>: value}, ...]}`. Extractor: `({{f}}?.records || []).filter(r => ...)` or
  `lookup_extract_formula(f, "Col", multiple=True)` → `({{f}}?.records || []).map(r => r?.["Col"])`

### Send Table Data (route-row)

Writes rows from this table into another table: one row per record, or one row per item of a list (list mode). This is how a Companies table feeds a shared People table, or how several people sources land in one table.

- **key:** `route-row`
- **package:** `b1ab3d5d-b0db-4b30-9251-3f32d8b103c1`
- **client:** `clay.create_route_row_column(table_id, name, target_table_id, row_data, condition=None, list_data=None, view_id=None)`
- **inputs:**
  - `tableId`: target table id as a string literal (`'"t_xxx"'`)
  - `rowData`: a **`formulaMap`** of `{target column name: formula}` (not `formulaText`)
  - list mode only: `type` = `'"list"'` and `listData` = a formula that returns a list
- **typeSettings:** also set `referencedTableId` to the target table id
- **gotchas:**
  - It is a write into another table. Give it an "Only run if" condition (for example, only qualified rows) and run it on one record first, then check the target table.
  - Running it twice on the same record sends the row twice. Guard re-runs, or dedupe in the target table.
  - Pass stable identifiers (domain, LinkedIn URL, source record id) in `rowData` so the target row can always be traced back.

```python
clay.create_route_row_column(
    T_COMPANIES, "Send to People",
    target_table_id=T_PEOPLE,
    row_data={
        "Company Name": "{{f_company_name}}",
        "Company Domain": "{{f_domain}}",
        "Qualification": "{{f_qualification}}",
    },
    condition='{{f_qualification}} == "QUALIFIED"',
    view_id=V_COMPANIES,
)

# List mode: one People row per item in a research column's "people" list.
# rowData holds the per-company columns copied onto every row sent.
clay.create_route_row_column(
    T_COMPANIES, "Send found people",
    target_table_id=T_PEOPLE,
    row_data={"Company Name": "{{f_company_name}}", "Company Domain": "{{f_domain}}",
              "Discovery Source": '"Claygent"'},
    list_data="{{f_research}}?.people",
    condition="!!({{f_research}}?.people?.length)",
)
```

In list mode, each list item is sent along with the `rowData` columns. After
the one-record test, open a new row in the target table and check where the
item's fields landed before you build columns that read them.

---

## 5. HTTP API

### HTTP API v2 (Generic)

Make any HTTP request to external APIs. Used for RapidAPI, HubSpot, Tavily, custom endpoints.

- **key:** `http-api-v2`
- **package:** `4299091f-3cd3-4d68-b198-0143575f471d`
- **inputs:**
  - `method`: `'"GET"'`, `'"POST"'`, `'"PATCH"'`
  - `url`: API endpoint (string literal or formula)
  - `queryString`: use `formulaMap` for key-value pairs (NOT `formulaText`)
  - `body`: use `formulaMap` for structured JSON (NOT `formulaText`)
  - `headers`: use `formulaMap` for each header (NOT `formulaText`)
  - `removeNull`, `followRedirects`, `shouldRetry` (optional booleans)
- **output:** display string "Status Code: 200". Use `?.key` extractors for response body
- **auth:** `cfg["authAccounts"]["rapidapi"]` (auto-injects API key headers)
- **gotchas:**
  - `queryString`, `headers`, `body` MUST use `formulaMap`. `formulaText` with JSON splits chars into rows
  - Auth account (RapidAPI) auto-injects `X-RapidAPI-Key` and `Host` headers
  - Use `Clay.secret("token_name")` in formulas for stored secrets

**Common HTTP patterns:**

RapidAPI (LinkedIn data):
```python
clay.create_action_column(t_id, "LinkedIn Profile",
    action_key="http-api-v2",
    package_id="4299091f-3cd3-4d68-b198-0143575f471d",
    inputs={
        "method": '"GET"',
        "url": '"https://fresh-linkedin-scraper-api.p.rapidapi.com/api/v1/profile"',
        # queryString needs formulaMap pattern: see clay-api.md for details
    },
    auth_account_id=cfg["authAccounts"]["rapidapi"],
    view_id=v_id)
```

HubSpot CRM (search/create/update):
```python
# Uses Clay.secret() for HubSpot token or hubspot auth account
clay.create_action_column(t_id, "HubSpot Search",
    action_key="http-api-v2",
    package_id="4299091f-3cd3-4d68-b198-0143575f471d",
    inputs={
        "method": '"POST"',
        "url": '"https://api.hubapi.com/crm/v3/objects/contacts/search"',
        # body + headers via formulaMap
    },
    auth_account_id=cfg["authAccounts"]["hubspot"],
    view_id=v_id)
```

---

## 6. Integrations

### Instantly: Add Lead to Campaign

Enroll a prospect into an Instantly email campaign.

- **key:** `instantly-v2-add-lead-to-campaign`
- **package:** `70cda03a-a576-4a6c-b3b3-55e241f828b5`
- **inputs:**
  - `email`: prospect email
  - `first_name`: first name
  - `last_name`: last name
  - `company_name`: company name
  - `campaign`: campaign UUID (get via `POST /actions/dynamicFields` with `parameterPath: "campaign"`)
- **auth:** `cfg["authAccounts"]["instantly"]`
- **gotchas:**
  - Campaign UUIDs are dynamic: retrieve via API or save in config
  - Requires email (fails without it)

```python
clay.create_action_column(t_id, "Add to Instantly",
    action_key="instantly-v2-add-lead-to-campaign",
    package_id="70cda03a-a576-4a6c-b3b3-55e241f828b5",
    inputs={
        "email": '{{@Email}}',
        "first_name": '{{@First Name}}',
        "last_name": '{{@Last Name}}',
        "company_name": '{{@Company}}',
        "campaign": '"campaign-uuid-here"',
    },
    auth_account_id=cfg["authAccounts"]["instantly"],
    view_id=v_id)
```

### Instantly: Find Leads

- **key:** `instantly-v2-find-leads`
- **package:** `70cda03a-a576-4a6c-b3b3-55e241f828b5`
- **status:** Available but input details not fully documented. Use `clay_browser.py` or HAR to discover inputs.

### Instantly: Update Lead

- **key:** `instantly-v2-update-lead`
- **package:** `70cda03a-a576-4a6c-b3b3-55e241f828b5`
- **status:** Available but input details not fully documented. Use `clay_browser.py` or HAR to discover inputs.

### HeyReach: Add Lead to Campaign

Enroll a prospect into a HeyReach LinkedIn outreach campaign.

- **key:** `heyreach-add-lead-to-campaign`
- **package:** (workspace-specific: find via `search_enrichments("heyreach")`)
- **inputs:**
  - `firstName`, `lastName`: prospect names
  - `profileUrl`: LinkedIn profile URL
  - `companyName`: company name
  - `position`: job title
  - Custom fields: `vmid`, `Campaign`, `HubSpot Company ID`, `HubSpot Contact ID`
- **auth:** HeyReach auth account from `rex-config.json` (`authAccounts`)
- **gotchas:**
  - Campaign ID is hardcoded per workflow (not dynamic like Instantly)
  - Custom fields map to HeyReach campaign field definitions

### Google Sheets: Add Row

Append a row to a Google Sheet for reporting/tracking.

- **key:** `google-sheets-add-row-v2`
- **package:** (workspace-specific: find via `search_enrichments("google sheets")`)
- **inputs:** spreadsheet ID, sheet name, column values (discover exact names via HAR)
- **status:** Used in production (influencer monitoring) but input details not fully documented in registry.

---

## 7. Social

### LinkedIn Posts

Fetch recent posts and shares from a LinkedIn profile.

- **key:** `social-posts-get-post-activity-posts-and-shares`
- **package:** `b210a16b-cdaf-4cbd-ad9b-42d762cd165f`
- **inputs:**
  - `socialUrl`: LinkedIn profile URL (NOT `linkedin_url`)
  - `num_posts`: number of posts as STRING (e.g. `'"10"'`, not `10`)
- **output:** JSON with post activity, engagement, shares
- **auth:** none needed (Clay-managed)
- **gotchas:**
  - Input name is `socialUrl`, NOT `linkedin_url` or `url`
  - `num_posts` is a STRING, not a number

```python
clay.create_action_column(t_id, "LinkedIn Posts",
    action_key="social-posts-get-post-activity-posts-and-shares",
    package_id="b210a16b-cdaf-4cbd-ad9b-42d762cd165f",
    inputs={
        "socialUrl": '{{@Person LI URL}}',
        "num_posts": '"10"',
    },
    view_id=v_id)
```

**Alternative: RapidAPI LinkedIn Posts (via HTTP API)**

Use `http-api-v2` with Fresh LinkedIn Scraper for LinkedIn posts.
- **endpoint:** `GET /api/v1/user/posts`
- **param:** `username` (NOT `url`): extract slug from LinkedIn URL
- **gotcha:** `/user/posts` does NOT accept a `url` param. It accepts only `urn` or `username`. Error: "Either urn or username must be provided"

```python
# Extract username from LinkedIn URL: "https://linkedin.com/in/johndoe/" → "johndoe"
username_formula = f'{li_ref}.split("/in/")[1]?.split("/")[0]'

clay.create_column(t_id, {
    "type": "action", "name": "LinkedIn Posts",
    "typeSettings": {
        "dataTypeSettings": {"type": "json"},
        "actionKey": "http-api-v2",
        "actionVersion": 1,
        "actionPackageId": "4299091f-3cd3-4d68-b198-0143575f471d",
        "authAccountId": cfg["authAccounts"]["rapidapi"],
        "conditionalRunFormulaText": f"!!{li_ref}",
        "inputsBinding": [
            {"name": "method", "formulaText": '"GET"'},
            {"name": "url", "formulaText": '"https://fresh-linkedin-scraper-api.p.rapidapi.com/api/v1/user/posts"'},
            {"name": "queryString", "formulaMap": {"username": username_formula}},
        ],
    }
}, view_id=v_id)
```

---

## 8. Discovery (Finding New Actions)

Not all actions are in this registry. Clay has hundreds of enrichment providers.

```python
# Search by keyword
results = clay.search_enrichments("find email")
for r in results:
    print(r["entity_id"])  # format: "{packageId}/{actionKey}"
    print(r["name"], r.get("description", ""))

# Documented actions not in sections above:

# LeadMagic Find Work Email (discovered 2026-03-30)
# - key: leadmagic-find-work-email
# - package: edb58209-a62d-42be-992a-e41b87eeacc2
# - inputs: linkedin_url, name (full name string), domain (company domain)
# - auth: <your-auth-account-id> (look up via clay.list_auth_accounts())
# - output: ?.email (work email address)
# - gotcha: ALL THREE inputs required; missing name/domain = column error

# - Many more available via search
```

When using a newly discovered action:
1. Get `action_key` and `package_id` from `entity_id` (split on `/`)
2. Input names are UNKNOWN: use `clay_browser.py` or ask user for HAR
3. Create a test column, inspect in Clay UI, iterate
4. Once working, add to this registry for future use

---

## Common Patterns

### Formula Extractors (access action results)
```python
# Top-level key
clay.create_formula_column(t_id, "Company Name",
    formula_text=f'{{{{{enrich_col_id}}}}}?.name', view_id=v_id)

# Nested key (requires mappedResultPath)
clay.create_formula_column(t_id, "Company LI URL",
    formula_text=f'{{{{{enrich_col_id}}}}}',
    mapped_result_path=["experience", "0", "url"], view_id=v_id)
```

### Conditional Execution (save credits)
```python
# Only run expensive AI if gate check passes
clay.create_action_column(t_id, "Deep Qualify",
    action_key="use-ai",
    package_id="67ba01e9-1898-4e7d-afe7-7ebe24819a57",
    inputs={...},
    condition='{{@Gate Check}} == "PASS"',
    auth_account_id=cfg["authAccounts"]["gemini"],
    view_id=v_id)
# Status when skipped: ERROR_RUN_CONDITION_NOT_MET (normal, 0 credits spent)
```

### Column Groups
Clay groups related columns (for example an enrichment and its output
columns) under one named header. Each group lives in the table's
`fieldGroupMap`, and each member field carries the same `groupId`.
```python
gid = clay.create_field_group(t_id, [enrich_id, output_id], "Company Enrichment",
                              output_field_ids=[output_id])
groups = clay.get_field_groups(t_id)          # {groupId: group}
members = [f["id"] for f in clay.get_table(t_id)["table"]["fields"] if f.get("groupId") == gid]
```
Verify after creating: every intended member points back to the same `groupId`.

**Colour** is not a group property (groups only take `name` + `fields`). It is a per-VIEW field setting:
`PATCH /tables/{t}/views/{v}/fields/{f} {"color": ...}`, enum `red|yellow|blue|green|violet|orange|pink|grey`
(read back in `view["fields"][f]["color"]`). Helpers: `clay.set_column_color(t_id, view_id, field_ids, color)`,
or `create_field_group(..., color="green", view_ids=[...])` (default: every view).

### Native Waterfalls (addition beyond upstream v2.1, verified live 2026-09-25)
**Rule:** a waterfall (work email, phone, ...) is Clay's NATIVE waterfall group, never provider
columns chained by hand. Reference build: a production `1. People` table's
"Work Email" group, saved as **`templates/waterfall-work-email.json`**.

Shape of the reference work-email waterfall:
- Steps in order: Prospeo (`prospeo-find-work-email-v2`, the CLIENT's own Prospeo account) → Icypeas
  (`icypeas-find-email-v2`) → LeadMagic (`leadmagic-find-work-email`) → Findymail
  (`findymail-find-work-email`) → Wiza (`wiza-find-work-email`, also gets LinkedIn + company name).
  Inputs: full name + company domain (Wiza: LinkedIn URL, full name, domain, company).
- One merged output column (`formulaType: "waterfall"`, `waterfallType: "person/workEmail"`).
- ONE run condition on the group (e.g. `Persona Status == "GTG" && Company Send-Ready? && domain && full name`);
  Clay appends "earlier steps found nothing" to each later step itself.
- `runAsButton: true`, validation `conservative`, catch-all excluded, unknown excluded.

API (reverse-engineered from the Clay web bundle: createWaterfallV2 / updateWaterfallV2 / deleteWaterfallV2):
| Call | Endpoint |
|---|---|
| create | `POST /workspaces/{ws}/tables/{t}/waterfall/v2` |
| update | `PATCH /workspaces/{ws}/tables/{t}/waterfall/v2/{groupId}` (full create body; `fieldId` on each step to keep, steps left out are DELETED with their column; `skipActionFieldRuns: true`). Verified live 2026-10-14; use `clay.update_waterfall()` |
| delete | `DELETE /workspaces/{ws}/tables/{t}/waterfall/v2/{groupId}` (deletes step + merged columns) |

Create body: `waterfallConfigs` [{name, type:"actionConfig", actionKey, actionPackageId, inputsBinding,
attributePath, authAccountId}] (a formula step is {name, type:"formulaConfig", formulaText}),
`waterfallFieldName`, `waterfallGroupName`, `runAsButton`, `attributeEnum` ("person/workEmail", ...),
`conditionalRunFormulaText`, `inputCombination`, `requiredInputsBinding`, `validationStrategy`
(conservative|balanced|aggressive|advanced), `includeCatchAll`, `includeUnknown`, `excludeRoleBased`,
`excludeDisposable`, `safeToSend`, `maxConsecutiveIdenticalNotFound`, `requireValidationSuccess`,
`createDataProviderField`, `activeViewId`.

```python
import json
tpl = json.load(open("templates/waterfall-work-email.json"))
# re-point the template's {{f_...}} refs to this table's columns (tpl["_field_names"] maps id -> column name)
s = json.dumps({k: v for k, v in tpl.items() if not k.startswith("_")})
for old_id, new_id in remap.items(): s = s.replace(old_id, new_id)
res = clay.create_waterfall(t_id, json.loads(s), view_id=v_id,
                            condition='{{f_persona}} == "GTG" && !!{{f_domain}} && !!{{f_name}}')
# res = {"groupId", "mergeFieldId", "stepFieldIds", "response"}; nothing runs (run-as-button, auto-run off)
tpl2 = clay.export_waterfall(t_id, res["groupId"])   # read any waterfall back as a template
clay.delete_waterfall(t_id, res["groupId"])          # no undelete
```
The template ships with every `authAccountId` set to `null`: set each step to a connection in your
own workspace first (own-key accounts first, then Clay-managed ones; `clay.list_auth_accounts()` lists them). Clay-managed steps spend Clay data credits when run.
Live check 2026-09-25: recreated the reference on a scratch table, read back identical (steps, accounts,
inputs, validation, inputCombination, requiredInputsBinding, runAsButton), deleted cleanly, 0 credits.

### Records (CRUD)
```python
# Create
records = clay.create_records(t_id, [{f_url: "https://linkedin.com/in/someone"}])
record_ids = [r["id"] for r in records]

# Read (2-step)
ids = clay.get(f"/views/{v_id}/records/ids")
records = clay.post("/bulk-fetch-records", {"recordIds": ids, "tableId": t_id})

# Run columns on records
clay.run_and_wait(t_id, [col_id], record_ids, timeout=120)

# Re-run cells that already have a result ("forceRun": true on PATCH /tables/{id}/run).
# Needed to refresh lookups; on a paid column it re-spends credits.
clay.run_column(t_id, [col_id], record_ids=record_ids, force=True)
```
