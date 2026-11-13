# Rex / Clay learnings

Hard-won behaviours of Clay's internal API and AI columns, found while building real client
tables with Rex. Not part of the upstream Rex package. Client and workspace names are
anonymized: "Client A", "Client B" and so on are stable pseudonyms for different client workspaces,
"own workspace" is the builder's in-house workspace, and every id is a placeholder (`t_xxxxxxxx`,
`<workspace_id>`). "The operator" is the human who reviewed and approved the build. Newest first.
Each entry: what happened, what is actually true, what to do next time.

## 2026-11-05 · `create_table(name, folder_id=...)` names the NEW workbook after the table, not the workflow.

**What happened.** Client B FinTech lookalike import: `create_table("Accounts - Prospeo Lookalike (FinTech, under 50)", folder_id=...)` made workbook `wb_xxxxxxxx` with the same name as the table, because `create_table` passes `name` to `create_workbook`. **What is true.** Renaming afterwards works: `PATCH /workspaces/{ws}/workbooks/{id}` with `{"name": ...}`, read back via `get_workbook`. **Next time.** Create the workbook first (`create_workbook(<workflow name>, folder_id)`) and pass its id to `create_table`. **Rex follow-up:** backlog #90 (`workbook_name=` arg + `rename_workbook()` with read-back).

## 2026-11-03 · A new multi-row lookup into a freshly imported 32k-row table returns 0 records, even when the key matches; the same setup on an 8k table worked.

**What happened.** Client A Finance TAM. `Decision Makers (lookup)` on `1. Companies` (t_xxxxxxxx) → `3. Decision Makers` (t_xxxxxxxx, 32,666 rows from 5 Search DSL sources), EQUAL on a formula `LinkedIn Key` on both sides. Every test row came back `SUCCESS_NO_DATA` ("0 Records Found"), including SentryWest, which has 9 people in the target with the identical key. `force=True` re-runs over ~5 minutes did not help. The config is byte-identical to `Tech People (lookup)` into the 8,100-row `2. Tech People`, which works. **What is true.** Cause unknown (target size, an index built lazily on a new formula column, or the source run still settling). The cells read back fine over the API. **Next time.** Prove a new lookup on one row known to have a match before trusting counts; if it returns 0, compute the join locally from both tables and write the result as plain values (source tables allow cell writes). **Rex follow-up:** backlog #89.

## 2026-10-30 · Company DSL has `employee_count` and `description contains`; people DSL accepts `company_name`; partial previews are floors.

**What happened.** Client A real-economy niche sizing (free previews only). I needed 20-50 vs 51-100 and per-company staff counts, and company preview rows have no domain.

**What is true.** (1) `select from companies` accepts `employee_count >= N` (also `<=`, `<`, `=`), which is NOT the `company_size` bucket: a bucket 2-10 or 201-500 row can sit at EC 20-50, and about 664k of 2.25M US-HQ 11-50 rows have no EC. EC cannot be read back. Clay people profiles returned per company ran about half of EC. (2) `description contains "x"` works with OR groups, phrases and `not description contains`; `products_and_services is_similar_to (...)` works but its count looks unreliable (15,721, identical to an unrelated Legal Services cut). `founded_year`/`year_founded` also accepted. (3) Inside people `experiences.count(...)`, `company_name = "X"` IS accepted; add `company.industry`, `company.company_size` and the US-HQ clause as namesake guards. This contradicts action-registry "only company.domain works". (4) `previewCoverage: partial` can return far under 250 rows while more exist, so returned rows are a floor; only `complete` rows are exhaustive. Home health EC 20-100: 1,721 rows vs 2,779 totalCount; dental, all slices complete: 997 vs 996. (5) `industry` has 457 exact values; both old and new LinkedIn labels exist (Veterinary + Veterinary Services), and Property Management, Hospice, Dental, Management Consulting and Marketing and Advertising do not exist.

**Next time.** For size cuts use `company_size in ("11-50","51-200") and employee_count` between bounds. For per-company counts without domains, preview by `company_name` with the guards. For a real count, partition EC into slices and sum rows only where coverage is complete.

**Rex follow-up.** Backlog #88.

## 2026-10-29 · In-Clay BounceBan (http-api-v2) returns SUCCESS with no verdict while BounceBan is still "verifying"; the status formula goes blank.

**What happened.** Client A tech-headcount experiment, BounceBan Verify columns on `2. People` t_xxxxxxxx and `4. New DMs` t_xxxxxxxx. 40 of ~1,150 calls (3.5%) came back HTTP 200 `{"id": ..., "msg": "The email verification process is not yet complete ... poll ..."}`: cell status SUCCESS, cell value "Status Code: 200", `?.result` empty, so `Deliverable Email` stayed blank and the rows silently dropped out of the gates.

**What is true.** BounceBan single-verify is asynchronous for slow mail servers. A force re-run of just those cells about a minute later returned a verdict for all 40 (39 deliverable, 1 undeliverable).

**Next time.** After every BounceBan column run, count rows with SUCCESS but no result and force re-run only those (or poll `/v1/check?id=`) before running gates. Read the real output with `read_ai_output(table, record, field)`; the bulk value is only "Status Code: 200".

**Rex follow-up.** Backlog #84.

## 2026-10-29 · Waterfall step validation (e.g. LeadMagic) is not settable through the waterfall v2 API; `update_waterfall()` doesn't carry it.

**What happened.** Client A AI WF1. The team's standard (2026-10-19) wants LeadMagic validation on the email waterfall. Each `sequenceSteps[]` entry has a `validation` slot (null on this table); older Client A tables (Aug/Sep New AI Leadership) show `{"fieldId", "actionKey": "findymail-validate-email", "actionPackageId", "authAccountId", "inputsBinding": [{"name": "email", ...}]}`. On a scratch table, sending `validation` / `validationConfig` / `validationActionConfig` / `validationConfigs` / `validationAction` per step, and `validation*` at top level, on both POST and PATCH `/waterfall/v2` was accepted and ignored (read-back null). Reordering via `update_waterfall()` worked: Clay rebuilt every step's run-if and the merge order and kept all column ids. **What is true.** The catalog key is `leadmagic-validate-email` (package edb58209-a62d-42be-992a-e41b87eeacc2, inputs email, onlySafe). **Next time.** Set step validation in the Clay UI, then read `sequenceSteps[].validation` back to learn the payload. **Rex follow-up:** backlog #87. **Update 2026-10-29:** The operator set it in the UI; read-back per step = `{"fieldId": <own 'Validate <Provider>' action column>, "actionKey": "leadmagic-validate-email", "actionPackageId": "edb58209-a62d-42be-992a-e41b87eeacc2", "authAccountId", "inputsBinding": [{"name": "email", "formulaText": "({{step}} && {{step}}?.email)"}]}`; Clay rewrites every later step's run-if to "nothing found OR earlier validation not valid/valid_catch_all" and the merge to the first validated email. **Resolved same day:** the create/update body takes a top-level `validationActionConfig` (see backlog #87); per-step `validation` is ignored.

## 2026-10-29 · Formula prompts (`formulaPrompt`) go stale when the formula is changed by API; the operator wants them kept in sync.

**What happened.** Client A AI WF1. The operator opened `Eligibility Status` and the plain-English box still read "if Exec Role Match and MASTER Firmographic Fit and MASTER Campaign Eligibility…" after the formula had gained the `QA Exclude` override. An audit of the workbook found 19 formula columns whose prompt no longer named every column the formula uses, and 7 batch-created formulas with no prompt at all. **What is true.** The box is `typeSettings.formulaPrompt`, a JS string expression: quoted text joined with `+` to `{{f_id}}` refs (rendered as chips). `update_column` merging `{'formulaPrompt': ...}` sets it without touching `formulaText` or re-running cells. Clay never regenerates it from the formula. **Next time.** Write the prompt in the same step as every formula create/edit. **Rex follow-up:** backlog #86.

## 2026-10-29 · `ClayClient()` with no workspace_id picked workspace <workspace_id>, not Client A.

**What happened.** Client A AI WF1 Phase 4. A script built `ClayClient()` without `workspace_id`; the login line printed `workspace <workspace_id> (billing: unknown)`. Table-scoped calls (update_column, update_records, get_records) still worked because they use table ids. **What is true.** `_default_workspace()` no longer resolves to Client A; any workspace-scoped call (sources, actions/task previews, search DSL, billing) would have hit the wrong workspace. **Next time.** Always pass `workspace_id=<workspace_id>` for Client A. **Rex follow-up:** warn loudly when the default workspace has billing 'unknown', or require `workspace_id` for workspace-scoped helpers (backlog #85).

## 2026-10-29 · Prospeo/LinkedIn employee counts let big firms through a 50-500 gate; a duplicated Find People source filters by a stale company bitmap.

**What happened.** Client A AI WF1 batch Oct 28. (1) The People preview for the 241 "eligible" companies returned Oracle, Block, NBCUniversal and Huntington Bank executives. Their size had come from Prospeo / LinkedIn enrich (selectminds.com = old Oracle recruiting domain; Block 288; Huntington 113; NBCUniversal 193). A free Search DSL check per domain (`select from companies where domain = "x"`, take the largest `size` bucket) put 15 of 240 at 1,001+ and 19 at 501-1,000. (2) The duplicated `V2 Classical Search` (find-lists-of-people) still held the Sept batch's `include_company_filter_bitmap` + `source_clay_company_id_to_record_ids` (448 companies). A preview with `company_identifier` = the new domains and those two keys (plus `include_company_filter_identifier_count`) removed returned only the new companies, with `company_record_id` attribution, 0 credits. (3) Search DSL preview 429s above ~6 parallel calls.

**What is true.** A company's employee count from Prospeo / LinkedIn enrich can describe a sub-page or an alias domain, not the parent. Clay's company index `size` (LinkedIn self-declared bucket) is a free second opinion keyed by domain. People-search company scoping lives in the bitmap, not only in `company_identifier`.

**Next time.** Cross-check every size-qualified company against the Search DSL company index before the people search; DQ anything at 1,001+. When repointing a duplicated Find People source, drop the bitmap keys, set `company_identifier`, and preview to confirm every sample person is at a target domain. Keep DSL previews at 4-6 parallel.

**Rex follow-up.** Backlog #84.

## 2026-10-29 · AI column errors when its JSON schema lists a field the prompt never asks for; a function called with a blank input "succeeds" with defaults.

**What happened.** Client A AI WF1 batch Oct 28, Accounts `t_xxxxxxxx`. (1) `Cleaned Job Title` (use-ai) failed on 134 of 413 rows with `ERROR_BAD_REQUEST` "The AI response is missing these output fields: category": the output schema had a `category` field the prompt never mentions, so the model sometimes left it out. Removing it from `answerSchemaType.fields` fixed all 134. (2) `Competitor Check` (execute-subroutine → W#12 function `t_xxxxxxxx`) returned SUCCESS + `Competitor Status: DQ` with an empty Reason in under a second: its `Company Name` input (Final Company Name) was blank because `Normalize Company Name` had not run, the function's AI column stopped on `ERROR_BLANK_TOKEN`, and its status formula defaulted to DQ. Send data back ran anyway.

**What is true.** Clay enforces every schema field on the response, required or not. A function returns whatever its formulas hold when its AI step cannot run; SUCCESS on the calling column says nothing about the AI step.

**Next time.** Every schema field must be named in the prompt's OUTPUT line. Before running a function column, check its inputs are filled on the test rows and that the 2-row test returns a non-empty reason; put `!!input` in the caller's run-if.

**Rex follow-up.** Backlog #83.

## 2026-10-29 · A run-if can make a dependency cycle; Clay answers 400 "Dag is cyclical" and Rex only shows a bare 400.

**What happened.** Client A AI WF1 batch Oct 28, Accounts `t_xxxxxxxx`. Gating `Cleaned Job Title` behind Company US + Min Employee Count + Previous Batch Status was refused: `400 {"type":"BadRequest","message":"Dag is cyclical","details":{"inputFieldIdsWithErrors":[...]}}`. The loop: Master Company Domain (waterfall) -> Normalize a Domain -> Official Domain, whose run-if read Is Ai Role -> Cleaned Job Title. `update_column()` raised `requests.HTTPError: 400` without the body, so the reason was only visible with a raw PATCH.

**What is true.** Run-if formulas are dependency edges like inputs. Clay checks the whole column graph on every PATCH and refuses any change that closes a loop, naming the input fields involved.

**Next time.** When gating a column behind a downstream check, trace the gate fields' inputs AND run-ifs back to the column first. Here the fix was dropping Is Ai Role from Official Domain's run-if (it only runs on the 51 rows with no domain).

**Rex follow-up.** Backlog #82.

## 2026-10-29 · `run_and_wait()` returns while AI cells still say "Running..." (status AWAITING_CALLBACK).

**What happened.** Client A AI WF1 batch Oct 28, 2-row test of `Cleaned Job Title` (use-ai) and `check is AI Role from Post` (claygent) on Accounts `t_xxxxxxxx`. `run_and_wait()` returned on its first poll with both cells at `metadata.status = AWAITING_CALLBACK`, value `"Running..."`. Its done-check only waits while the value is empty, so the placeholder text counted as done. A manual poll showed SUCCESS ~30-90 s later.

**What is true.** While an AI/Claygent cell is in flight Clay writes the placeholder value `"Running..."` with status `AWAITING_CALLBACK`. A non-empty value is not a finished cell. Finished cells read `SUCCESS` (value `"Response"`; the real output is in the full value), `ERROR_*`, or `ERROR_RUN_CONDITION_NOT_MET` for skipped rows.

**Next time.** Poll on status, never on value: keep waiting while status is QUEUED / RUNNING / PENDING / AWAITING_CALLBACK / empty.

**Rex follow-up.** Backlog #81.

## 2026-10-28 · Find Jobs has a free count preview over the API; `jobCount` counts posts (capped at 10,000), not companies; title excludes are substring matches.

**What happened.** Client A AI WF1 batch Oct 28 (Accounts `t_xxxxxxxx`, source `s_xxxxxxxx`). The Clay web bundle's Find Jobs preview is `POST /workspaces/{ws}/actions/task` `{"actionTaskParams": {"actionKey": "<previewActionKey>", "actionPackageId": "<pkg>", "inputs": {...source inputs, "isPreviewRun": true, "isCountTotal": true, "limit": 50}}, "runType": "action-preview"}`. It returns a task id string; poll `GET /workspaces/{ws}/actions/tasks/{id}` until `status` is `COMPLETE`. Result: `output.data.jobs` (50 sample rows) + `output.data.jobCount`, `upfrontCreditUsage.totalCost` 0. The full 32-title search returned `jobCount` 10000 exactly; single titles returned real numbers (AI Engineer 9,081, Data Scientist 3,866). `limit` 100/250/1000 returned 0 rows (50 is the max that works). The excludes "Software Engineer" / "Solutions Architect" zeroed the keywords "AI Software Engineer" / "AI/ML Solutions Architect" (0 vs 2,098 without excludes). The same bundle has `POST /workspaces/{ws}/sources/sendTrigger/{sourceId}` (empty body), summary "Manually trigger a source run".

**What is true.** The preview is free. `jobCount` is posts matching the keywords, capped at 10,000, and ignores `limit_per_company`, so it overstates the import (Sept batch: same settings imported 4,140 rows, one per company). Title keywords and excludes are word/substring matches, so an exclude can silently kill an include keyword.

**Next time.** Preview each keyword separately for real numbers, keep `limit` at 50, and preview with and without the excludes to see which include keywords they cancel. Estimate the import from the last batch's row count, not `jobCount`.

**Rex follow-up.** Backlog #80: `find_jobs_preview(source_id, overrides)` helper (+ per-keyword mode, exclude-conflict warning). `sendTrigger` closes #63: tested live 2026-10-28, `POST /workspaces/<workspace_id>/sources/sendTrigger/s_xxxxxxxx` `{}` → 200 `{}`, 4,157 rows within 15 s (`state.numSourceRecords`), table auto-run stayed off, no other column ran. Helper `run_source(source_id)` still to add.

## 2026-10-27 · People Search DSL `job_title is_similar_to (...)` is semantic and over-matches badly.

**What happened.** Client B B6 persona search (`3. People - Persona Search`, t_xxxxxxxx), scoped with `clay.filter_to_companies(@table(...))` to 27,777 HealthTech accounts. `job_title is_similar_to ("Chief of Staff", ...)` previewed 7,981 people; the 250-row sample was mostly "Strategic Advisor" (80) and COO titles, with 2 actual Chiefs of Staff, and the top companies were LinkedIn, Morgan Stanley, Google (mis-domained accounts, #77). Finance previewed 20,412, Ops 26,771 (over the 25k cap).

**What is true.** `is_similar_to` is a semantic match, not a phrase match. `job_title contains "chief of staff"` (case-insensitive, OR-ed phrases) returned 691, almost all real CoS titles. Adding `company.company_size in ("1","2-10","11-50","51-200","201-500")` inside the same `experiences.count(...)` stops big-firm floods at the source. Watch `contains "coo"` (matches "Coordinator"): use `contains "coo "` + `job_title = "COO"`.

**Next time.** For persona title searches use OR-ed `contains` phrases plus a company-size condition inside `experiences.count`, and check the preview sample's top titles + top companies before importing.

**Rex follow-up.** Backlog #79.

---

## 2026-10-27 · A bare `/` inside a regex rule breaks the whole Clay formula (INVALID_FORMULA_PARSING_FAILED, every cell blank).

**What happened.** Client A zero-tech DM table `t_xxxxxxxx`: title rules are compiled into one chained-ternary formula of `/regex/.test(...)` literals. One rule used `(&|and|,|/)`; the unescaped `/` closed the regex literal, Clay saved the column with `settingsError: INVALID_FORMULA_PARSING_FAILED` and every cell came back null, so `Is Decision Maker?` read No on all 5,345 rows and the filtered views emptied.

**What is true.** `create_formula_column()` does not raise on a parse failure; the error only shows in the field's `settingsError`. Python `re` accepts the same pattern, so local tests pass.

**Next time.** Escape `/` as `\/` in any rule that becomes a JS regex literal; after creating a formula, read `settingsError` back and check one cell is non-null before building dependents.

**Rex follow-up.** Backlog #80.

---

## 2026-10-27 · Search DSL preview `totalCount` is an estimate; `views[0]` is not the default view.

**What happened.** Client A tech-headcount experiment. (1) Per-company people previews: `totalCount` said 0 tech people at one small health-tech domain while the preview returned 3 rows with `previewCoverage: complete` (and 23 vs 31 for all staff). (2) After adding columns to `1. Companies` (`t_xxxxxxxx`), `get_table()['views'][0]` became 'Errored rows' (0 rows), so a script wrote headcount to 0 of 5,120 rows.

**What is true.** Under 250 results, count the returned rows when coverage is complete; `totalCount` is only good for sizing big searches. View order in `get_table()` is not stable.

**Next time.** Use `len(rows)` when `previewCoverage == 'complete'`. Always pick a view by name ('All rows' / 'Default view'), never by index. Previews sustain ~100/min at 4 threads; 8+ threads get 429s.

**Rex follow-up.** Backlog #79.

---

## 2026-10-27 · Table dedupe on LinkedIn is an exact string match: a trailing slash makes two rows.

**What happened.** Client A tech-headcount experiment `2. People` (`t_xxxxxxxx`), dedupe on `LinkedIn Profile`, filled by three Send table data routes (Oct people, original-list founders, original-list tech DMs). 7,705 rows landed, but only 7,646 unique profiles after normalising: 59 pairs differ only by `/in/name/` vs `/in/name` (47 founder ↔ tech-DM pairs from two tables of the same list, 12 across lists).

**What is true.** `DEDUPE_FIELD_ID` compares the raw value. Clay Find People returns URLs with a trailing slash; Prospeo and some imports don't. Same goes for `www.` and http/https.

**Next time.** When several sources feed one deduped table, route a normalised key (lowercase, no scheme, no `www.`, no trailing slash) as its own column and dedupe on that, not on the display URL. Check unique normalised keys vs row count after every multi-source fill.

**Rex follow-up.** Backlog #78.

---

## 2026-10-26 · Size-filtered company lists hide big firms; `filter_to_companies` on their domain pulls the whole firm.

**What happened.** Client B FinTech under-50 pool (accounts `t_xxxxxxxx`, view `gv_xxxxxxxx`, 12,948 companies sized 0-10 / 10-50 by Clay + Prospeo). People search with `clay.filter_to_companies(@table(...Domain))` returned 27,293 people, and **12,996 of them sat at 66 domains**: fidelity.com 5,706, apple.com 1,757, nasdaq.com 449, coinbase.com 347, workday.com 512 and so on. A small entity (or a stale company record) carrying the big firm's domain was sized under 50; the people search matched every employee of the real firm on that domain.

**What is true.** A company's size bucket comes from one company record, but people search by domain matches everyone whose current company resolves to that domain. One mis-sized record can flood a people table, and the title gate alone lets the big firm's founders/GMs/MDs through.

**Next time.** After any people pull on a size-filtered account list, count people per domain. More than ~15 decision-maker-titled people at an "under 50" domain means it's mis-sized: flag it on the accounts table (here `DM People Found (Clay)` + `Headcount Mismatch?`, >15 → out) and review the 10-15 band by eye.

**Rex follow-up.** Backlog #77.

---

## 2026-10-22 · A rejected action column is still created: Rex raises, but the column stays in the table.

**What happened.** Copying Client C WF2's Bison import columns into a CSV-import table (Find People `t_xxxxxxxx`) with `campaign_id` left empty on purpose. `POST /tables/{id}/fields` answered with a field that has `settingsError: MISSING_INPUT "Required input campaign_id is not set"`. `create_column()` raised `ClayColumnConfigError`, and the script stopped, but the column (`f_xxxxxxxx`) was already in the table.

**What is true.** Clay saves an action column even when its settings are invalid; it just can't run. A raise from `create_column()` does not mean "nothing was written". An empty required input is a safe "not ready" state (the column cannot fire), useful when campaign IDs aren't known yet.

**Next time.** After a `ClayColumnConfigError`, read the table back before retrying or you create duplicates. To park a push column, leave the required input empty and expect the error.

**Rex follow-up.** Backlog #76.

---

## 2026-10-22 · A lookup-row column's "Record Found" text is a display preview; formulas see `{record: {...}}` or null.

**What happened.** Client A health-tech 1-50 people table t_xxxxxxxx: `Blocklist Status` tested the lookup with `?.foundRecord`, then (copying the NAL Send GTG formula) with `/Record Found/.test(String(lookup))`. Both returned GTG for jane.doe@example.com although `Blocklist Lookup (Email Domain)` showed "✅ Record Found". The record endpoint's `externalContent.fullValue` is `{"record": {"domain": "example.com", ...}}` on a hit and null on a miss; the "✅ Record Found" / "❌ No Record Found" string is only the cell preview that `get_records()` returns.

**What is true.** In formulas, a `lookup-row-in-other-table` column is an object: test `!!{{lookup}}?.record`. String-matching the preview never fires (String(obj) is "[object Object]"). The NAL search table's Send GTG (t_xxxxxxxx) uses the string test, so its blocklist DQ likely never fires.

**Next time.** Use `?.record` for lookup hits, and prove every gate formula on one known-positive row before trusting it (here: a domain already on LGTM_FF_Blocklist_Accounts).

**Rex follow-up.** Backlog #76.

---

## 2026-10-21 · Find People (create-cpj-table) rejects a limit above 25,000 with a bare 400.

**What happened.** Client A health-tech 1-50 people table t_xxxxxxxx: the third source (founders/CEOs on 17,905 accounts) was posted with `inputs.limit` / `sourceRecordLimit` 50,000 and `/sources/create-cpj-table` returned HTTP 400 with no message surfaced by `post()`. The same payload at 25,000 created the source (s_xxxxxxxx).

**What is true.** Find People has the same 25,000-per-search plan cap as Find Jobs (#29), but the error text is not shown, so it looks like a payload-shape bug. A big account list needs splitting into views of < 25,000 expected results.

**Next time.** Keep every Find People limit ≤ 25,000; for larger scopes, split the linked view (e.g. by size band) into several sources on the same table.

**Rex follow-up.** Backlog #75.

---

## 2026-10-28 · Search DSL `annual_revenue` IS a company filter; values are bucket strings like "75M-200M".

**What happened.** Client A Sales Rep Network planning: I tested `annual_revenue = "50M-100M"`, `in ("$50M-$100M")` and `>= 50000000`, printed only the HTTP status (400) and concluded revenue is not filterable. The operator showed the Clay UI's Annual revenue filter. Printing the response body gave Clay's own hint: `Invalid value ... Use one of: "75M-200M"`.

**What is true.** `select from companies where annual_revenue in (...)` works with exactly: `"1M-5M"`, `"5M-10M"`, `"10M-25M"`, `"25M-75M"`, `"75M-200M"`, `"200M-500M"`, `"500M-1B"`, `"1B-10B"`, `"10B-100B"`, `"100B-1T"` (no `$`, plain hyphen; the UI shows `$75M–$200M` and `$100B+`). There is no $50M boundary: `25M-75M` straddles it.

**Next time.** Always print the 400 response body from a DSL preview: Clay names the valid values. Never conclude a filter is unsupported from the status code alone.

**Rex follow-up.** Backlog #75: `ANNUAL_REVENUE_BUCKETS` in `validate_dsl_query()` (refuse other values with the list) + `search_dsl_preview()` raising with the response body.

---

## 2026-10-20 · Lookup-multiple-rows caps numberOfResults at 100; LinkedIn URL alone can't find "the same person".

**What happened.** Client A NAL Oct (search table t_xxxxxxxx → AI Builders t_xxxxxxxx): `lookup-multiple-rows-in-other-table` returned `numberOfResults: 100` for OpenAI (137 rows in the target), Scale (136) and Mercor, so the copy said "100 AI and ML engineers". Separately, 5 leads appeared in their own company's AI Builders list under a different LinkedIn URL (vanity slug vs id slug, e.g. /in/kananrahimov vs /in/kanan-rahimov-0471351a), so the slug-based self-exclusion missed them and the copy named the lead as "the one engineer" and counted them.

**What is true.** The lookup's count and records stop at 100. One person can have two LinkedIn URLs across Clay sources.

**Next time.** For counts that can exceed 100, compute from the target table (or a DSL count) and write an override; exclude "self" by LinkedIn slug OR normalized full name.

**Rex follow-up.** Backlog #73.

---

## 2026-10-20 · A table's views list is in no fixed order: views[0] is not the Default view.

**What happened.** Client A Oct 2026 Fractional AI and fCTO tables: scripts used `t["views"][0]` as "the default view". On these tables views[0] was "All rows", "Support view" or "Non enrichment columns". A GTG filter landed on fCTO's "Non enrichment columns" and on FAI's "All rows", and a scaled paid run picked up every row (339 / 324) instead of the GTG view. No credits were wasted only because every paid column was also gated on Source Status GTG.

**What is true.** `table["firstViewId"]` is the Default view. The `views` list order is arbitrary and differs per table.

**Next time.** Use `default_view_id(table)`. Gate every paid column on its own eligibility condition, never rely on a view to limit spend; build run lists from the eligibility VALUE, not a view.

**Rex follow-up.** Backlog #71: `default_view_id()` added and used in `import_schema()` / the other views[0] fallback; 2 offline tests (182/182).

---

## 2026-10-19 · create_waterfall() returned an EXISTING waterfall that had the same group name.

**What happened.** Client A fCTO October table (`t_xxxxxxxx`): a new 5-step work-email waterfall was created on a table that already had a 10-step native waterfall group named "Work Email". `create_waterfall()` picked the result group by name, so it returned the OLD group (`gr_xxxxxxxx`) and its merge column. BounceBan, Deliverable, Blocklist, Send GTG and the route were then wired to the old Work Email. Caught only because the returned merge id matched the old column; repointed before any run.

**What is true.** The waterfall/v2 POST response returns the table's whole `fieldGroupMap`, all groups included. The template's `waterfallGroupName` wins over `field_name`, so two groups can share a name.

**Next time.** Diff group ids before and after the POST; never pick by name. After any build, grep every downstream column for the merge id you expect.

**Rex follow-up.** Backlog #69: fixed in code (before/after diff, raises unless exactly one new waterfall group) + 2 offline tests.

---

## 2026-10-19 · Duplicating a workbook copies sources WITH their dedupe bitmap and auto-run ON.

**What happened.** Client A October iterations: `POST /workbooks/{id}/duplicate` `{name, parentFolderId, workspaceId}` copied NAL, Fractional AI and fCTO workbooks. Tables came over with 0 rows, field ids preserved, new table ids. Re-running the copied people-search sources returned fewer people than the free preview (NAL 917 vs ~1,000) because each copied source kept the original's `previous_entities_bitmap`, so it skipped everyone the original source had already returned. Table auto-run settings were copied too (6 tables had to be switched off). A route-row in the copy points at the COPIED target table (checked on fCTO), but lookups/sources tied to record ids of the original (NAL Open Roles / AI Builders) still point at the old records.

**What is true.** The bitmap carry-over is a free dedupe against the prior batch (useful for monthly iterations), but preview counts overstate what will import. Headline is filterable in Search DSL but is not returned on the record. A Bison Find Lead cell that is null means "not run", not "not found".

**Next time.** After duplicating: switch auto-run off on every table before anything else, expect imports below preview, re-check every lookup/source that references record ids.

**Rex follow-up.** Backlog #70: `duplicate_workbook(wb, name, folder)` that duplicates, turns auto-run off on every copied table, reads it back, and lists sources that carry a bitmap.

---

## 2026-10-19 · Column order lives in view.fields[id].order; organise every table by default.

**What happened.** The operator found the Client B B5 tables with no groups, colours or logical order: Rex only organised tables when asked. While adding `organize_table()`, the read-back of column order silently passed because these tables expose no `fieldOrder` list on their views.

**What is true.** Each view stores order as `view["fields"][field_id]["order"]`, a lexicographic sort key. `PATCH /tables/{t}/views/{v}/fields/{f}` with `{"afterFieldId": prev}` moves one column in one view; chaining it over the layout sets the full order. Groups are table-level, colours are per view.

**Next time.** Call `organize_table()` after every build step (source → company → location → lookups → exclusion → fit → people → email → send), and put each new column next to its siblings when it is created.

**Rex follow-up.** Backlog #67.

---

## 2026-10-19 · Send table data says SUCCESS for rows that never reach the target table.

**What happened.** Client B WF10 B5 (`wb_xxxxxxxx`): two route-row columns sent 31,982 rows (25,669 + 6,313) into `3. Accounts - Consolidated` (`t_xxxxxxxx`) in one burst. Every source cell read SUCCESS (`numberOfRowsSent: 1`), but the target stopped at 4,903 rows, then 6,992 after the table dedupe on Domain was switched off, with 0 duplicate or blank domains. A forced re-send of 500 missing rows landed 478 within 2.5 min.

**What is true.** A route-row cell's SUCCESS only means Clay accepted the send, not that the row was written. Large bursts (tens of thousands) lose most rows silently. A table dedupe on a column the source fills by formula may also drop rows that arrive before the formula computes (suspected, not proven).

**Next time.** After any Send table data run, compare the target row count with the number of source rows that passed the condition. Re-send only the missing keys with `forceRun`, in batches of about 1,000, waiting for the count to settle between batches. Leave target dedupe off when the sources are already unique.

**Rex follow-up.** Backlog candidate: `route_and_verify(table, route_field, target, key_field, batch=1000)` that sends in batches, diffs keys against the target, re-sends the missing ones, and reports the final gap.

---

## 2026-10-14 · A waterfall whose condition needs a company domain silently skips people from sources without one.

**What happened.** Client C LATAM WF2 consolidated: 30 of 496 GTG people never started the email waterfall (run condition requires Company Domain; Apollo/Clay/Prospeo rows sometimes carry only a company LinkedIn). Re-running did nothing: the cells sit at "run condition not met", which looks like "not run yet" in counts.

**What is true.** The company row usually has the domain from firmographics (Clay company search `Domain` / Prospeo `company.domain`). A `Resolved Domain` formula on Companies + an `Email Domain` formula on People (`own domain || lookup.Resolved Domain`), with the waterfall's inputs + condition re-pointed, recovered 22 of 30 (13 emails). Lookup cells are cached: re-run the lookup (force) after adding a column to the looked-up table.

**Next time.** Build People-level `Email Domain` with the company fallback before creating the waterfall, and audit "condition not met" counts after every waterfall run.

**Rex follow-up.** Backlog candidate: waterfall audit helper that counts rows stuck on ERROR_RUN_CONDITION_NOT_MET and names the missing input.

---

## 2026-10-14 · Apollo LinkedIn URLs are percent-encoded, so slug dedupe misses accented names.

**What happened.** Client C LATAM WF2 consolidated (`t_xxxxxxxx`) deduped on a `LinkedIn Slug` formula. Apollo exports `linkedin.com/in/ra%c3%bal-enrique-chumba` while Clay search returns `linkedin.com/in/raúl-enrique-chumba/`: same person, two slugs. 9 Apollo rows duplicated Clay/Prospeo people with accented names; 2 more were different slugs entirely (vanity vs numbered, #39).

**What is true.** Slugs must be normalised before compare: `decodeURIComponent`, lowercase, strip the trailing slash, and ideally strip accents. A name + company check still catches the vanity-slug cases.

**Next time.** Normalise slugs on import (decode the Apollo URL before writing it) and keep the name + company audit after any multi-source consolidation.

**Rex follow-up.** Folded into backlog #39 (`find_duplicate_people()` must decode + de-accent slugs).

---

## 2026-10-14 · A native waterfall can be edited in place: PATCH the group path, keep each step's fieldId.

**What happened.** Client C LATAM WF1 (`t_xxxxxxxx`, group `gr_xxxxxxxx`): the operator asked to add 6 email providers to a waterfall that already had test results. Rex only had create/delete. action-registry.md listed the update call as `PATCH .../waterfall/v2` (no group id); that returns 400 `NoMatchingURL`. Also: Prospeo's LinkedIn finder (`prospeo-find-work-email`, v1) now errors `Prospeo error: DEPRECATED`; and with `includeCatchAll: false`, Hunter's result flagged `status: accept_all` still landed in the merged Work Email.

**What is true.** `PATCH /workspaces/{ws}/tables/{t}/waterfall/v2/{groupId}` with the full create body works. Steps sent with their `fieldId` keep their column, values and position; steps without one are created; steps left out are deleted with their column. The merged column keeps its id. `skipActionFieldRuns: true` means nothing runs. Verified on scratch `t_xxxxxxxx` (add, reorder) and live on the Client C table (8 → 14 → 13 steps, 5 rows of results kept).

**Next time.** `clay.update_waterfall(t, gid, steps)` with `waterfall_steps_with_ids()` for the steps to keep. Don't use Prospeo v1 for LinkedIn lookups. Don't trust the waterfall's catch-all setting alone: run an external verifier before sending.

**Rex follow-up.** Backlog #64 (DONE), #65 (OPEN).

---

## 2026-10-14 · A Find Jobs source can be re-configured over the API but not re-run.

**What happened.** Iterating Client C WF1 for LATAM in a duplicated workbook (`wb_xxxxxxxx`), the copied jobs source `s_xxxxxxxx` needed new locations and keywords. `PATCH /sources/{id}` with the edited `typeSettings` saved and read back. Every guessed run endpoint returned 404 and `GET /workspaces/{ws}/sources/{id}/runs` stayed `[]`.

**What is true.** Duplicating a workbook copies sources with 0 rows and no run. The API path for re-running a cpj source is unknown (the Search DSL `update-and-run` endpoint does not apply to Find Jobs).

**Next time.** PATCH the inputs, read them back, then ask the user to click run on the source in the Clay UI. Don't spend time guessing endpoints.

**Rex follow-up.** Backlog #63.

---

## 2026-10-14 · Column groups cannot be merged in one call.

**What happened.** Regrouping Accounts - Consolidated, `create_field_group()` on Size columns + Headcount Bucket + the Prospeo lookup (already in two groups) got a 400: "Cannot merge multiple groups into one".

**What is true.** A new group can only take ungrouped fields or fields from one group. Updating an existing group's member list (`POST .../fields/group/{gid}`) does move fields across groups.

**Next time.** Pick the group to keep and call `set_group_members()`; `create_field_group()` now refuses multi-group input up front.

**Rex follow-up.** Backlog #62.

## 2026-10-13 · Source columns cannot be put in a column group.

**What happened.** Organising the Client B 51-500 people tables, `create_field_group()` with the people-search source column plus "Company Table Data" got a 400.

**What is true.** Clay answers "is a source column and cannot be grouped". Action and formula columns group fine. Colour on a source column still works (`set_column_color`).

**Next time.** Group everything except the source column; colour the source column the same as its group.

**Rex follow-up.** Backlog #61: `create_field_group()` now refuses source columns before any write (offline test added).

## 2026-10-13 · A route-row ("Send table data") condition blocks its own updates: a row that stops qualifying keeps its stale copy in the target.

**What happened.** On the Client A health-tech 50-200 send table, QA found john@example.edu. I set the source row's `Send Ready?` to "No" and force-ran the route column on it; the target row kept `Send Ready? = Yes`, because the route's run condition (`Send Ready? == "Yes"`) was no longer met, so nothing was sent.

**What is true.** Route-row only writes when its condition passes. A forced re-run can update a row that still qualifies (the 4 renamed companies refreshed fine) but cannot downgrade one that no longer does. Deleting the target row is the only way to remove it, and deletes need the operator's OK.

**Next time.** Give every send table a manual `QA Exclude` text column from the start and make the push columns and views require it empty; or route on a condition that is always true for the batch and carry the gate as a column.

**Rex follow-up.** Backlog #57.

## The improvement rule (standing, added 2026-09-24)

A learning that only lives in this file relies on someone remembering to read it. The goal is
that Rex itself stops the mistake from happening again. So:

0. **Know the cost model.** What spends actions vs data credits vs nothing:
   `knowledge-base/playbooks/clay/actions-data-credits.md` (summary in `README.md`). Check it, don't guess.
1. **Read before building.** Before any Clay build, repair or audit with Rex, read this file's
   backlog below and every entry newer than your last session.
2. **Log it the moment it's found.** Any new Clay/Rex gotcha (silent no-op, wrong default,
   misleading readback, casing, payload shape) gets an entry here immediately, newest first, in
   the format: what happened / what is actually true / next time. End it with a
   `**Rex follow-up:**` line naming the fix type and a backlog row.
3. **Promote every learning to the strongest fix that fits**, in this order:
   - **Code**: make Rex prevent or catch it (a safer default, validation, a read-back check,
     a helper that does it right). Best, because it works even when nobody reads docs.
   - **Test**: an offline test in `tests/test_local_additions_offline.py` so an upstream merge
     can't silently undo the fix.
   - **Skill**: a rule in `.claude/skills/build-clay/SKILL.md` (starter-kit overrides) for judgment
     calls code can't enforce.
   - **Docs**: `README.md` "Additions beyond upstream v2.1" / Gotchas, or `action-registry.md`, for API facts.
   A learning can need several of these. "Docs only" is acceptable only when code genuinely
   can't help, and the backlog row must say why.
4. **Track it in the backlog below** until it's promoted. Update the row's status and link the
   commit/file when done. Never delete entries or rows; they are the audit trail.
5. **Verify before closing.** A code fix is DONE only after it is proven: offline test passing
   plus, where it touches live behavior, one live check on a scratch table (never a client
   table). Log the promotion in `work-log/`.
6. **Carry forward on upgrade.** Every code fix here is an addition beyond upstream v2.1: list it in
   `README.md` "Additions beyond upstream v2.1" so the next upstream 3-way merge keeps it.
7. **Worth sharing upstream?** If a fix would help every Rex user (not workspace-specific), note
   it in the row. The maintainer decides whether to send it upstream.

## Improvement backlog

| # | Learning (date) | Proposed Rex fix | Type | Status |
|---|---|---|---|---|
| 90 | `create_table(name, folder_id=...)` gives the new workbook the TABLE name (Client B FinTech lookalike, 2026-11-05) | `create_table(..., workbook_name=None)` passes the workbook name separately; `rename_workbook(id, name)` PATCH + read-back; offline test | Code + test | OPEN |
| 89 | Multi-row lookup into a new 32k-row target returns 0 records although keys match; identical config on an 8k target works (Client A Finance TAM, 2026-11-03) | `verify_lookup(table, lookup_field, record_id, expected_min)` read-back check after create; `join_locally()` fallback that writes counts as values | Code + test | OPEN |
| 88 | Company DSL `employee_count` (not the bucket, not read back) and `description contains` are filterable; people DSL accepts `company_name` inside `experiences.count` (action-registry says only company.domain); `previewCoverage: partial` rows are a floor (Client A niche sizing, 2026-10-30) | Correct action-registry 'Filterable company keys'; `_DSL_BAD_COMPANY_KEYS` still blocks `company.name` correctly but docs must add `company_name`; helper `dsl_slice_count(where, ec_slices)` summing rows and flagging partial slices; `INDUSTRY` value list + validation in `validate_dsl_query()` | Code + test + docs | OPEN |
| 87 | Waterfall step validation not settable via waterfall v2 API (5 payload shapes ignored); `update_waterfall()` doesn't send `validation`, so a reorder could drop UI-set validation (Client A AI WF1, 2026-10-29) | Capture the UI's request once (browser-use CLI on a scratch table) to learn the shape; then `create_waterfall`/`update_waterfall` carry per-step `validation`, refuse a reorder that would drop an existing one, and the template gets LeadMagic validation on every step | Code + test + template | DONE 2026-10-29: body key is a TOP-LEVEL `validationActionConfig` {actionKey, actionPackageId, inputName: "email", authAccountId} (from Clay's app JS schema `createWaterfallV2`/`updateWaterfallV2`), one provider for all steps; Clay adds `Validate <step>` columns + rewrites run-ifs/merge. Rex: create/update/export carry it, `create_waterfall_from_template()` verifies it; 5 offline tests (196/196); live on scratch t_xxxxxxxx: created 6 validated steps in one call, reorder kept validation; README, `/build-clay` 3e |
| 86 | `formulaPrompt` (plain-English box) is not kept in sync with `formulaText`; Rex formula helpers never set it (Client A AI WF1, 2026-10-29) | `create_formula_column(..., prompt=[...])` + `update_formula(..., prompt=...)` that build the prompt from text/column parts, warn when a formula is written without one; `audit_formula_prompts(table)` listing refs missing from the prompt; `/build-clay` audit mode flags stale prompts | Code + test + skill | DONE 2026-10-29: `build_formula_prompt` / `formula_prompt_gaps` / `audit_formula_prompts`, prompt required in `create_formula_column` + `update_column`; 9 offline tests (`FormulaPrompts`, 191/191 pass); live on scratch table `t_xxxxxxxx` (refuse without prompt on create + update, prompt written + read back, audit clean); `/build-clay` override 3f; README Local additions |
| 85 | `ClayClient()` without workspace_id defaulted to workspace <workspace_id> instead of Client A (Client A AI WF1, 2026-10-29) | Warn when the default workspace's billing is unknown; workspace-scoped helpers require an explicit workspace_id | Code + test | OPEN |
| 84 | In-Clay BounceBan http-api-v2 cell = SUCCESS with no verdict while BounceBan is "verifying" (~3.5% of calls); rows drop out of the gates silently (Client A tech-headcount, 2026-10-29) | Rex helper `rerun_pending_verifications(table, action_field, result_field)`: find SUCCESS cells with an empty result, force re-run after 60s, report; status formula template that shows "verifying" instead of blank | code + test | OPEN |
| 83 | use-ai schema field missing from the prompt → ERROR_BAD_REQUEST on a share of rows; execute-subroutine with a blank input returns SUCCESS + default outputs (Client A AI WF1, 2026-10-29) | Lint in create/update of use-ai columns: every `answerSchemaType` field name must appear in the prompt; `run_function_test()` that checks inputs are non-blank and outputs non-empty on the test rows | Code + test | OPEN |
| 82 | Clay refuses a run-if/input change that closes a column loop: 400 "Dag is cyclical" + `inputFieldIdsWithErrors`; Rex `patch()` raises a bare HTTPError and hides the body (Client A AI WF1, 2026-10-29) | `patch()`/`post()` raise an error carrying Clay's message + details; `update_column()` names the fields in a cycle error | Code + test | OPEN |
| 81 | `run_and_wait()` treats an in-flight AI cell (status AWAITING_CALLBACK, value "Running...") as done because its value is non-empty (Client A AI WF1, 2026-10-29) | Decide done by status only: wait on QUEUED/RUNNING/PENDING/AWAITING_CALLBACK/empty; offline test with a fake AWAITING_CALLBACK cell | Code + test | OPEN |
| 80 | Find Jobs free preview = `POST /workspaces/{ws}/actions/task` (`runType: action-preview`, `isPreviewRun`, `isCountTotal`, limit ≤ 50) + poll `/actions/tasks/{id}`; `jobCount` = posts capped at 10,000, ignores limit_per_company; excludes are substring matches that can cancel include keywords (Client A AI WF1, 2026-10-28) | `find_jobs_preview(source_id, overrides, per_keyword=False)` helper returning count, sample, unique companies, credits; warn when an exclude is a substring of an include | Code + test + docs | OPEN |
| 79 | People Search DSL `job_title is_similar_to` is semantic: "Chief of Staff" previewed 7,981 (mostly Strategic Advisor / COO, big firms) vs 691 with `contains` + company-size inside `experiences.count` (Client B B6, 2026-10-27) | `validate_dsl_query()` warning on `job_title is_similar_to` in people queries; helper `title_phrase_clause(phrases)` building OR-ed `contains` (+ guards like `coo `); `preview_sample_report()` printing top titles + companies from a preview | Code + test + docs | OPEN |
| 80 | `create_formula_column()` returns OK when Clay can't parse the formula: `settingsError: INVALID_FORMULA_PARSING_FAILED`, all cells null (unescaped `/` in a regex literal, Client A zero-tech DMs 2026-10-27) | Raise ClayColumnConfigError when the created field carries a settingsError; lint regex literals for unescaped `/` before posting | Code + test | OPEN |
| 77 | Size-filtered account lists contain mis-sized big firms (fidelity.com etc.); a domain-scoped people search then pulls the whole firm: 12,996 of 27,293 people at 66 domains (Client B FinTech under 50, 2026-10-26) | `people_per_domain_report(people_table, accounts_table, max_per_domain=15)` helper writing a count + mismatch flag to the accounts table; build-clay rule: run it after every people pull on a size-filtered list | Code + test | OPEN (done by hand in a one-off script, `headcount_mismatch.py`) |
| 78 | Table dedupe on a LinkedIn URL column is exact-string: `/in/x/` vs `/in/x` (and www / http) land as two rows; 59 of 7,705 in the Client A tech-headcount People table from 3 routes (2026-10-27) | `create_route_row_column()` helper option to add a normalised `LinkedIn Key` (and `Domain Key`) to rowData + `set_table_dedupe()` on it; `find_duplicate_people()` (#39) to normalise slugs | Code + test | OPEN |
| 79 | Search DSL preview `totalCount` is an estimate (0 vs 3 real rows; 23 vs 31) and `get_table()['views'][0]` changes order after column adds (wrote to 0 of 5,120 rows) (Client A tech-headcount, 2026-10-27) | `dsl_preview_count(query)` helper returning len(rows) when coverage complete, else totalCount + flag; `view_id_by_name(table, name)` helper and use it in Rex scripts/docs instead of views[0] | Code + test | OPEN |
| 76 | `create_column()` raises on a `settingsError`, but Clay has already saved the column (MISSING_INPUT on an empty Bison `campaign_id`); a retry makes a duplicate (2026-10-22) | Include the created field id in `ClayColumnConfigError` as an attribute, and add `allow_settings_error=True` to return the field instead of raising (for intentionally parked columns) | Code + test | OPEN |
| 76 | `lookup-row-in-other-table` value in formulas = `{record:{...}}` / null; "Record Found" is only the preview `get_records()` shows, so `/Record Found/.test(String(x))` never fires (Client A 1-50 + NAL Send GTG, 2026-10-22) | `lookup_hit_formula(field_id)` helper returning `!!{{f}}?.record`; `get_records(full=True)` option reading externalContent.fullValue for action cells; build-clay rule: prove each gate on a known-positive row | Code + test | OPEN |
| 75 | Find People `/sources/create-cpj-table` with `limit`/`sourceRecordLimit` > 25,000 → bare HTTP 400 (Client A health-tech 1-50, 2026-10-21; 25,000 works) | `create_find_people_source()` helper (from a proven build_sources payload) validating limit 1..25,000 + surfacing the 400 body in `post()` errors | Code + test | OPEN |
| 75 | DSL `annual_revenue` filter values are `"1M-5M"` … `"25M-75M"`, `"75M-200M"` … `"100B-1T"` (no `$`); I wrongly concluded "not filterable" from a bare 400 (Client A Sales Rep Network, 2026-10-28) | `ANNUAL_REVENUE_BUCKETS` validation in `validate_dsl_query()`; `search_dsl_preview()` surfaces the 400 body (Clay lists valid values); action-registry note | Code + test + docs | OPEN |
| 74 | Workbook tab (table) order is `settings.tablePresentationSettings` {tableId: index} on `PATCH /workspaces/{ws}/workbooks/{wb}`; read back as `orderedWorkbookTables`. A duplicated workbook keeps the source order and deleted tables leave stale entries (Client A NAL Oct, 2026-10-20: push table sat first) | `set_table_order(workbook, [table ids])` with read-back; `organize_table()` docs: column order is not tab order; build-clay rule: number tables 1..n and order tabs to match | Code + test | OPEN (done by hand on wb_xxxxxxxx) |
| 73 | `lookup-multiple-rows-in-other-table` caps numberOfResults/records at 100 (OpenAI 137 → 100 in copy); same person appears under two LinkedIn URLs across sources, so slug-only self-exclusion fails (Client A NAL Oct, 2026-10-20) | Warn in Rex when a lookup returns exactly 100; helper `count_by_key(table, key_field)` for true counts; build-clay rule: self-exclude by slug OR normalized name | Code + docs | OPEN |
| 72 | `run_paced()` forced 40-row batches: Clay left most cells in each batch untouched (status stayed blank), so every batch waited out its 420 s timeout (~40 rows / 14 min on Client A Oct runs, 2026-10-20). One plain (non-forced) `run_column` call per 100 rows finished 204 cells in <1 min | `run_paced()`: plain run first, force only for ERROR retries; re-trigger cells still blank after 2 min; don't wait on AWAITING_CALLBACK async steps (Wiza) inside a waterfall run | Code + test | OPEN (workaround in a one-off client run script) |
| 71 | `views[0]` is not the Default view (list order arbitrary; `firstViewId` is). Scripts put a GTG filter and a paid run on the wrong view (Client A Oct 2026, 2026-10-20); spend saved only by column-level gates | `default_view_id(table)`; `import_schema()` + view fallback use it; build-clay rule: gate paid columns on eligibility, never on a view | Code + test | PARTIAL 2026-10-20: helper + 2 offline tests (182/182); live check on scratch pending |
| 70 | Duplicating a workbook (`POST /workbooks/{id}/duplicate`) copies tables empty with field ids kept, copies sources WITH the original's `previous_entities_bitmap` (imports < preview: free dedupe vs prior batch) and copies auto-run ON (2026-10-19, Client A Oct iterations) | `duplicate_workbook()`: duplicate, auto-run off on every table + read-back, report bitmap-carrying sources and record-id-bound lookups | Code + test | OPEN |
| 69 | `create_waterfall()` picked the result group by name and returned an EXISTING same-named waterfall; downstream columns got wired to the old merge column (Client A fCTO Oct, 2026-10-19) | Diff fieldGroupMap ids before/after the POST, raise unless exactly one new waterfall group | Code + test | PARTIAL 2026-10-19: code + 2 offline tests (180/180); live check on a scratch table pending |
| 68 | Send table data marks a source cell SUCCESS (`numberOfRowsSent: 1`) for rows that never land: a 31,982-row burst into Client B B5 consolidated stopped at 4,903 then 6,992 rows; forced re-sends of 500 landed 478 (2026-10-19) | `route_and_verify()`: send in batches, diff keys against the target, re-send missing, report the gap; build-clay rule: always compare target count to routed count | Code + skill | OPEN |
| 67 | Operator (2026-10-19): Rex must group, colour and order columns logically left to right BY DEFAULT on every table it builds, and place each NEW column in its logical spot (not appended at the far right), so anyone opening the table can follow it. Column order is per view in `view.fields[fid].order` (lexicographic key, no `fieldOrder` list on these tables); `PATCH views/{v}/fields/{f} {afterFieldId}` moves one column | `organize_table(table, layout)` (DONE: groups + colours + per-view order + read-back); NEXT: an `after=` / `group=` option on every create_* column helper that moves the new column next to its siblings and into the group in all views, + build-clay rule "organise after every build step" | Code + test + skill | PARTIAL 2026-10-19: `organize_table()` live on scratch `t_xxxxxxxx` (order + groups + colour read back) and used on Client B B5 tables 1/1b/3/4; offline test + create-time placement still OPEN |
| 66 | http-api-v2 columns carried BounceBan keys in plaintext in their `headers` input (visible to anyone in the workspace; the own API key sat in the Client C US WF1 column). Clay's "HTTP API (Headers)" connection type (`http-api`, authenticationType custom) stores headers server-side: `POST /workspaces/{ws}/app-accounts {name, appAccountTypeId:"http-api", auth:{headers:{...}}, defaultAccess, roles}`; the column then sets `authAccountId` and leaves `headers` empty. `/app-accounts/jwt/{type}` returns nothing for this type (2026-10-14) | `create_http_auth_account(name, headers)` (refuses duplicate names); build-clay rule: never put keys in an HTTP column's headers | Code + test + skill | PARTIAL 2026-10-14: helper + offline test; live: `bounceban-own` aa_xxxxxxxx created and used by a column (3/3 calls 200). Still OPEN: build-clay rule, and rotating the exposed BounceBan key |
| 64 | No way to add/reorder/remove steps on an existing native waterfall; registry listed the update path without the group id (400 NoMatchingURL). `PATCH /workspaces/{ws}/tables/{t}/waterfall/v2/{groupId}` with the full body + `fieldId` per kept step works; omitted steps are deleted with their columns (2026-10-14, Client C LATAM WF1) | `update_waterfall(table, group, steps, allow_remove=False)` + `waterfall_steps_with_ids()`; registry path corrected | Code + test + docs | DONE 2026-10-14: 2 offline tests (176/176); live on scratch `t_xxxxxxxx` (removal refused, add + reorder, ids kept) |
| 65 | `prospeo-find-work-email` (v1, the only Prospeo finder with a LinkedIn input) errors `DEPRECATED`; a waterfall with `includeCatchAll: false` still merged Hunter's `accept_all` result (2026-10-14) | `create_waterfall()`/`update_waterfall()` warn on known-deprecated action keys; audit helper that lists merged emails whose provider status is catch-all/accept_all | Code + docs | OPEN |
| 63 | A Find Jobs (cpj, `find-lists-of-jobs-with-mixrank-source`) source's search CAN be changed over the API (`PATCH /sources/{id}` with the full `typeSettings`, inputs read back exactly) but there is no known API to re-run it: `POST /sources/{id}/run`, `/refresh` and the `/workspaces/{ws}/sources/{id}/...` variants all 404 `NoMatchingURL`; runs list stays empty (Client C WF1 LATAM copy, 2026-10-14) | Find the UI's re-run call in the web bundle; until then: PATCH the inputs, then the user clicks run on the source in the UI | Code + docs | OPEN | 2026-10-28: bundle names `POST /workspaces/{ws}/sources/sendTrigger/{sourceId}` (empty body) "Manually trigger a source run"; LIVE-VERIFIED same day: 200, 4,157 rows in <15 s, no other columns ran. Remaining: `run_source()` helper + offline test + docs
| 64 | View order: PATCH `{"order": ...}` on a view returns 200 but is ignored; PATCH `{"afterViewId": <view>}` moves it (Client B table 8 cleanup, 2026-10-16). Clay system views (All rows, Errored rows, Support view, Non enrichment columns, Fully enriched rows) cannot be deleted (403) | `set_view_order(table_id, [view_ids])` chains afterViewId | Code + test | Code + offline test DONE 2026-10-16; used live on table 8 |
| 1 | `useCase` claygent vs use-ai; `clone_column()` silently carries the source's use case (2026-09-24) | `clone_column(use_case=)`: cloning a Claygent without an explicit `use_case` is refused before any write; bound `useCase` read back after create (`ClayColumnConfigError` on mismatch); warns when the column name contradicts the bound mode | Code + test + skill | DONE 2026-09-24: 6 offline tests; live: refused on the real July Claygent column, nothing written. Positive clone path verified offline only (a live clone would bind another client's AI account). Worth sharing upstream |
| 2 | claygent vs use-ai return different key casing (`roleBucket` vs `role_bucket`) (2026-09-24) | `ai_extract_formula()` / `ai_key_variants()` / `create_ai_extraction_column()` emit `?.roleBucket ?? ?.role_bucket`; acronyms and non-identifier keys left as-is | Code + test + skill | DONE 2026-09-24: 4 offline tests; live: Clay supports `??` (scratch table) and a camelCase-only formula reproduces the empty-SUCCESS bug. Worth sharing upstream |
| 3 | AI action cells read back as `"Response"` over the API even on success (2026-09-24) | `read_ai_output()` reads the real output (single-record `externalContent.fullValue`); `verify_ai_column()` checks every extraction formula against the real output keys: `key_missing` (casing variant given as `suggestion`), `extraction_empty`, `no_output`, `action_not_success` | Code + test + docs | DONE 2026-09-24: 5 offline tests; live read-only on both Client C tables: ok, and the WF1 table's output shows both key casings. Worth sharing upstream |
| 4 | Send table data auto-extracts routed identity columns as text (2026-09-24) | `create_route_row_column(column_types="auto")` (default) retypes email→email, domain/website/url/linkedin→url right after creation (Clay creates the target columns immediately); `retype_route_columns()` for explicit types; reads back | Code + test | DONE 2026-09-24: 5 offline tests; live on scratch: url/url/email/text, formulas kept, routed values land. Skill rule also DONE (build-clay override #4) |
| 5 | Unknown view-filter operator returns 200 and is silently dropped (2026-09-24) | `set_view_filter()` validates operators + reads back, raises `ClayViewFilterError` | Code + test + docs | DONE (`clay_client.py` view helpers, 6 offline tests, README Local additions) |
| 6 | Singular `PATCH /records/{id}` returns 200 but no-ops (2026-08-24) | `update_records()` bulk PATCH; `update_record()` docstring warns | Code + test | DONE |
| 7 | Hand-built Search DSL source via `create-cpj-table` → 404 "Incorrect source configuration"; MixRank Find People can't filter on start date / country / size / industry (2026-09-24) | `search_dsl_preview()`, `send_search_dsl_to_table()`, `update_and_run_search_dsl_source()` on Clay's `search-dsl` endpoints | Code + test + docs | DONE (`clay_client.py`, 4 offline tests, action-registry.md > Search DSL Source, README). Worth sharing upstream |
| 8 | `send-to-table` creates the table with auto-run ON and starts the run immediately; `limit N` is the only row cap (2026-09-24) | Helper switches auto-run off after create; write helpers refuse a query without `limit N` | Code + test | DONE |
| 12 | `create_column({"type":"text","name":...})` returns 400 "Missing data type settings." though the docstring shows that exact example (2026-09-24) | `create_column()` defaults `typeSettings.dataTypeSettings` to `{"type": <column type>}` for basic columns when omitted; fix the docstring | Code + test | DONE 2026-09-25: 2 offline tests (text/formula default; explicit type kept; action untouched; caller dict not mutated); live: `{"type":"text","name":...}` created on scratch with `dataTypeSettings: text` |
| 40 | Clay tables cap at 100 fields: `create_column` returns 400 "cannot create new field due to table size limit" (Client A NTL retargeting hit it mid-build, 2026-09-30) | `create_column()` checks the table's field count first and raises a clear error listing unreferenced columns (refs=0) as cleanup candidates; batch helpers count needed columns up front | Code + test | OPEN |
| 41 | `create_field_group()` with a field that is already in another group returns THAT group's id and merges the new fields into it (no new group); renaming it afterwards then strands the newcomers ungrouped (2026-09-30) | `create_field_group()` checks every field's `groupId` first and refuses (or `move=True` removes them from the old group) before creating; read back that the returned id is new | Code + test | OPEN |
| 43 | `create_column({"type":"email","name":...})` returns 400; it needs `typeSettings.dataTypeSettings.type` set explicitly. Rex only defaults that for text/formula (#12), so email/url/number columns fail without it (2026-10-01) | Extend the #12 default to every basic type (email, url, number, date, checkbox) | Code + test | OPEN |
| 44 | Formulas cannot tell "action not run" from "ran, no data" (Find Lead `SUCCESS_NO_DATA`, lookup no record): both read as empty, so a "blank = clean" formula passes un-run rows; and gpt-4o-mini Claygent competitor verdicts were wrong both ways (1 false yes, 1 missed consultancy in 298) (2026-10-01) | Helper `assert_column_ran(table, field, record_ids)` that reads cell statuses and fails if any row is un-run before a gate formula is trusted; build-clay rule: every AI competitor column gets an override column + a cross-check of its "no" calls | Code + test + skill | OPEN |
| 36 | in-house list-clean HTTP column: a 1,121-row run got 74 cells `502 upstream check failed: RateLimitError`; forced retries (batches of 15, then single rows) kept failing for 10+ min (2026-09-29) | A paced runner that runs in paced batches, reads back statuses and retries only ERROR cells with backoff; report the rate-limited count. Also flag to the endpoint owner | Code + test | DONE 2026-09-29: `run_paced()` (the list-clean deploy script that wrapped it is client-specific and not included), 3 offline tests; live on Client A scratch route column: 2 US rows routed, BR reported `not_run` (ERROR_RUN_CONDITION_NOT_MET), resume skipped SUCCESS. Real list-clean endpoint not re-hit (74 Client A cells still ERROR, needs the operator's OK to retry); flag to the endpoint owner still open |
| 35 | Legacy Clay plans consume no actions; only the new plan does. Client A is legacy (2026-09-29) | `WORKSPACE_BILLING` + `workspace_billing()` + `clay.billing_model()`; login line prints the plan; build-clay override 4b: legacy = run action-heavy work inside Clay, actions plan = run outside + `update_records()`, unknown = ask and record | Code + test + skill + docs | DONE 2026-09-29: 3 offline tests (112/112 pass); no live check needed (no Clay call, pure lookup). Other workspaces (Client C, Client F, Client D, <workspace_id>) still unknown: record each once the operator confirms |
| 25 | Search DSL `company_size` buckets need comma thousands separators; `"501-1000"` → 400 (2026-09-29) | Validate `company_size` against the bucket list client-side and raise with Clay's allowed set before the call | Code + test | DONE 2026-09-29: `COMPANY_SIZE_BUCKETS` (9, probed live) + `validate_dsl_query()` on every DSL call, 3 offline tests; live: "501-1000" refused before the call |
| 13 | Companies Search DSL: `id`, `clay_company_id`, `linkedin_url` are not filterable (400 "Unknown field" / 0 rows); `domain` is, but brands share domains; `clay.filter_to_companies()` only works in people queries (2026-09-24) | Find the filterable company key via `audiences/v2/dsl.fields`; document it in action-registry.md | Docs | DONE 2026-09-29: probed live, only `domain`/`company.domain` filter a company (13 keys rejected; audiences `dsl.fields` is the wrong catalog); action-registry.md + `validate_dsl_query()` refuses the rest (offline test) |
| 14 | `create_table(name, workbook_id=<existing>)` returns a table with `AUTO_RUN_ON: true` (only the new-workbook path sets auto-run off) (2026-09-24) | `create_table()` PATCHes `tableSettings.AUTO_RUN_ON=false` after creating in an existing workbook and reads it back | Code + test | DONE 2026-09-25: offline tests (CreateTableSettles); live: BOTH paths (new workbook too) came back `AUTO_RUN_ON: true`; now PATCHed off and read back. Also removes the blank "New Column" + blank row (`remove_placeholder=True`) |
| 15 | Built a Companies table by writing rows through the API (`create_records`): fast and free, but it has no source lineage, so nobody can see how it was built; the operator caught it (2026-09-24) | build-clay override: derived tables (Companies-from-People) are built with a Send table data column + destination dedupe key, never API-written rows; prove the route's cost on 1 row first | Skill | DONE 2026-09-29: build-clay override 4c. Skill only because a derived table can legitimately be written from a non-Clay source (e.g. a Bison CSV); the rule names that exception |
| 16 | Companies Search DSL `preview` caps at 250 rows per call, so per-call lookup of 5k companies ≈ 3h; one `send-to-table` import of `domain in (...)` + size/country filters took ~2 min (31k rows, free) (2026-09-24) | Helper `lookup_companies_by_domain(domains, filters)` that imports to a scratch table and matches by company id; docs | Code + docs | DONE 2026-09-29: `lookup_companies_by_domain()` + `best_company_for_domain()`, 2 offline tests; live: stripe.com/clay.com resolved in one free import, `best` = real Stripe (5,001-10,000) and Clay; found domain maps to 34/7 entities (documented) |
| 9 | `update-and-run` `replace` deletes every existing row; `add` appends the next page, not a no-op (2026-09-24) | Refuse `replace` on a table that has non-source columns unless `allow_row_loss=True` | Code + test | DONE 2026-09-29: `update_and_run_search_dsl_source(mode="replace")` refuses tables with text/action columns unless `allow_row_loss=True` (source → table via `sourceSubscriptions`), 3 offline tests; live: refused on scratch, rows kept |
| 10 | Every field exposes `supportedFilterOperators` with `needsValue` (2026-09-24) | `set_view_filter()` validates each condition against its column's own operator list, not just the global enum | Code + test | DONE 2026-09-29: `_check_filter_against_fields()` in `set_view_filter()`, 3 offline tests; live: GREATER_THAN on a text formula refused, CONTAIN on it allowed (it is supported) |
| 11 | JSON-typed formula columns return 400 "not supported for basic fields" (2026-09-24) | Docs only, because it's a Clay rule, not a Rex bug: keep formula outputs basic-typed, `JSON.parse` downstream | Docs | DONE 2026-09-24: README Gotchas |
| 17 | Lookup cells read back as `"✅ Record Found"`; the data sits in `externalContent.fullValue` as `{record: {...}}` (single) / `{records: [...]}` (multiple), keyed by column NAME, and plain text columns cross too, not only formulas. Tables take a `description` via `PATCH /tables/{id}` (2026-09-24) | `create_lookup_column(single|multiple)` helper that proves on 1 row and returns the extractor formula (`?.record?.["Col"]` / `?.records.filter(...)`); `set_table_description()` | Code + test + docs | DONE 2026-09-25: `create_lookup_column()` + `lookup_extract_formula()`, 4 offline tests; live on scratch: single + multiple lookups, `?.record?.["Job Title"]` and `?.records` extractors resolved on both rows. `set_table_description()` not added (a plain `PATCH /tables/{id}` does it) |
| 18 | `create_table(name, workbook_id=<existing>)` can leave the table named "Custom Table": the name didn't stick and nobody noticed until the operator looked at the workbook (2026-09-24) | `create_table()` reads the table back and PATCHes `name` if it differs; raise if still wrong | Code + test | DONE 2026-09-25: offline test (name that never sticks raises `ClayTableConfigError` after one retry); live: every new table is named "Custom Table" / "Custom Table (2)" on create, fixed by the PATCH + read-back |
| 19 | House rule: action columns (lookups, enrichments, Send table data) AND source columns (incl. "Rows from: <table>" on a Send-table-data target) must stay VISIBLE in the clean/default view; only formula/plain helpers can be hidden (2026-09-24) | build-clay override rule + `set_view_columns()` refuses to hide an action or source column | Skill + code | DONE 2026-09-25: code (`set_view_columns()` / `create_view()` raise ValueError before any write, `allow_hide_actions=True` override), 3 offline tests, build-clay override 3d; live: refused on scratch with the 2 lookup columns listed, view unchanged |
| 20 | Column colour is a per-VIEW field setting, not a group property: `PATCH /tables/{t}/views/{v}/fields/{f} {"color": ...}`, enum `red|yellow|blue|green|violet|orange|pink|grey` (from the app bundle; field groups only take `name` + `fields`). Verified live 2026-09-24 | `set_column_color(table, view, field_ids, color)` validating the enum; option on `create_field_group(color=, view_ids=)` | Code + test + docs | DONE 2026-09-25: `set_column_color()` + `create_field_group(color=, view_ids=)`, 3 offline tests; live: violet + green read back in `view.fields[f].color` |
| 21 | Clay **Find Jobs** source can be created over the API: `POST /sources/create-cpj-table` with `cpjConfig.type: "jobs"`, actionKey `find-lists-of-jobs-with-mixrank-source`, idPath `job_id`, recordsPath `jobs`, `hasEvaluatedInputs: true`, inputs incl. `company_table_id/view_id/field_id` (Company LinkedIn), `company_identifier` + `company_record_id` lists, `job_title_keywords`, `max_num_days_since_posted`, `limit_per_company`. Runs on create (0 credits); table comes back auto-run ON and auto-named (2026-09-25) | `create_find_jobs_source()` helper (turns auto-run off, renames, returns ids) + offline test | Code + test + docs | DONE 2026-09-25: `create_find_jobs_source()` + `FIND_JOBS_FIELDS`, 3 offline tests, action-registry.md > Find Jobs; live: 2-company scratch table, limit_per_company 1 → 2 jobs in ~10s, renamed + auto-run off, all 8 extractors filled |
| 22 | Jobs Search DSL (`select from jobs`) exists but filters differ from its payload: `company.domain`, `job_posted_date`, `is_open` work; `clay_company_id`, `company_name`, `country`, `linkedin_company_id` are 'Unknown field'; `is_similar_to` needs compileAsync (preview 400). The operator: Find Jobs is the function WF6 uses, not this (2026-09-25) | Document in action-registry; prefer Find Jobs source | Docs | DONE 2026-09-29: action-registry.md > Jobs Search DSL (prefer Find Jobs). Docs only: nothing to enforce, Rex has no jobs-DSL helper |
| 23 | `forceRun: true` on `PATCH /tables/{id}/run` DOES refresh a lookup-multiple snapshot after the target table's formula changed (a plain re-run does not) (2026-09-25). **Same trap, second symptom (Client D WF1 2026-09-25):** a column ADDED to the target table after the lookup ran is absent from the cached payload, so `{{lookup}}?.record?.["New Col"]` reads EMPTY on every row (not stale - undefined), with no settingsError and a healthy `✅ Record Found` cell. `get_records` shows the cell's `externalContent.fullValue.record` as `{}`, so you cannot confirm it from a read-back; diagnose it by the fact that sibling extractions of OLDER target columns still resolve. Fix is the same `force=True` re-run of the lookup column. | `run_column(force=True)` param | Code + test | DONE 2026-09-25: `run_column(force=)` / `run_and_wait(force=)`, 3 offline tests; live: after changing the jobs title formula a plain re-run kept the old lookup value, `force=True` refreshed it |
| 24 | `send-to-table` with `clay.filter_to_companies(@table(...))` adds a `trigger-find-people-source` action column to the referenced companies table (2026-09-25) | Warn in `send_search_dsl_to_table()` docstring; never run it | Docs | DONE 2026-09-25: docstring warning + offline test + action-registry.md; docs only because Clay adds the column server-side and Rex can't stop it (the helper could delete it afterwards, but it may belong to a live table) |
| 25 | House rule: a waterfall is Clay's NATIVE waterfall group (`fieldGroupMap` entry `type: "waterfall"`, `settings.attribute` e.g. `person/workEmail`, `groupDetails.sequenceSteps` + `mergeField`, merged column `formulaType: "waterfall"`), not chained action columns. Reference: Client D WF6B People `gr_xxxxxxxx` (2026-09-25) | `create_waterfall(table, attribute, steps, required_inputs, condition, validation)` helper that reproduces that shape; build-clay override rule | Code + test + skill | DONE 2026-09-25: `create_waterfall()` / `export_waterfall()` / `delete_waterfall()` on `/waterfall/v2`; template `templates/waterfall-work-email.json`; 4 offline tests; live: recreated the reference on a scratch table, identical read-back, deleted, 0 credits |
| 26 | Workbook description (the one Clay shows under Workbook settings → Description) is `PATCH /workspaces/{ws}/workbooks/{id} {"description": ...}`; table-level `description` (PATCH /tables/{id}) stores fine but the operator couldn't find it in the UI (2026-09-25) | `set_workbook_description()` helper; build-clay: write the workbook guide there | Code + test + skill | DONE 2026-09-29: `set_workbook_description()` (reads back via `GET /workspaces/{ws}/workbooks/{id}`) + build-clay override 4e, 1 offline test; live on scratch |
| 27 | Formula-waterfall columns (`formulaType: "waterfall"`, logic in `typeSettings.formulaWaterfall[]`, NOT `formulaText`) are invisible to any reader that only looks at `formulaText`; conditions carry a separate plain-English `conditionalRunFormulaPrompt` that can silently disagree with `conditionalRunFormulaText` (2026-09-25) | `export_schema()` / audit dump: render `formulaWaterfall` branches; audit helper flags label-vs-formula drift (keywords in the prompt label absent from the formula) | Code + test | DONE 2026-09-29: `formula_logic()`, `describe_columns()`, `label_drift()`, `audit_formula_labels()`, 3 offline tests; live: waterfall column created over API and rendered, Canada-label vs US-formula flagged on a scratch route column |
| 28 | A table's current Send-table-data condition is not proof of what it routed: Client E W#3 has 451 rows its own route rule now blocks (rule edited after the run) (2026-09-25) | Audit helper: re-evaluate the live condition over routed source rows and report routed-but-ineligible / eligible-but-unrouted | Code + skill | DONE 2026-09-29: `audit_route_condition()` (node `vm`, empty context, per-row timeout) + build-clay 4g, 2 offline tests incl. no-fs-access; live: after editing the rule US→CA it reported 2 routed-but-ineligible (US) + 1 eligible-but-unrouted (CA) |
| 29 | Find Jobs create returns 400 "Your current plan provides up to 25,000 per search." when `inputs.limit` / `sourceRecordLimit` exceed the plan cap; `create_find_jobs_source()` hard-coded 50,000 (Client A's workspace, 2026-09-28). Also: `company_table_field_id` / `company_identifier` can be a company DOMAIN column (live: stripe.com by domain and by LinkedIn URL both returned the same 5 jobs) | `total_limit` param (default 25,000, validated 1..25,000) on `create_find_jobs_source()` | Code + test | DONE 2026-09-28: code + offline test (62/62); live: 3 small test sources in Client A wb_xxxxxxxx (2 Stripe controls + Chartbeat, 5/5/0 jobs). Rename DONE 2026-09-29: `company_identifier_field_id` / `company_identifiers` aliases + docstring (old names still work), 2 offline tests; same payload as the live-verified path |
| 30 | `ClayClient()` with no `workspace_id` picks `/my-workspaces[0]`, which silently changed to <workspace_id> on 2026-09-29 (Client C tables live in <workspace_id>). Table-scoped endpoints still worked, but workspace-scoped ones (`/workspaces/{ws}/tables/{t}/views/{v}/filter`) returned a bare 404, so `create_view()` created the view and then failed on the filter, leaving a half-configured view (2026-09-29) | Derive the workspace from the table (`get_table()` → `workspaceId`) for table-scoped helpers, or raise a clear 'table belongs to workspace X, client is on Y' error on 404; `create_view()` should apply the filter before reporting success or roll back | Code + test | DONE 2026-09-29: `table_workspace()` + `_ws_table_path()` used by set_view_filter/sort, create/delete_waterfall, generate_formula; multi-workspace warning in `_default_workspace()`; `create_view()` rollback; 5 offline tests (109/109); live: bare `ClayClient()` (defaulted to <workspace_id>) filtered a view on scratch table `t_xxxxxxxx` in <workspace_id>, filter stored, 2/3 rows |
| 34 | Workbooks land in a folder by passing `parentFolderId` in the `POST /workbooks` body (read back on the workbook). Folder contents list via `POST /workspaces/{ws}/resources_v2/ {"parentResource": {"type": "FOLDER", "id": f}}`; a top-level `parentFolderId` key in that body is ignored and returns the ROOT listing, which looks like 'not placed' (2026-09-29) | `create_table(folder_id=)` for new workbooks + `list_folder(folder_id)` helper using the parentResource shape | Code + test | DONE 2026-09-29: folder half covered by #37 helpers (`list_folder` uses parentResource), offline tested, live on scratch |
| 39 | Consolidating people from two sources (Clay Search DSL + Prospeo) deduped only on LinkedIn slug let 15 of 1,487 people through twice: the same person carries different slugs across sources (vanity vs numbered, renamed profiles, e.g. `ariel-lacina333` vs `ariel-lacina-b74787192`); caught only by an exact-email check after the email waterfall (Client C WF2, 2026-09-29) | build-clay rule + helper: dedupe consolidated People on LinkedIn slug AND work email (and name + company domain before emails exist); `find_duplicate_people()` audit helper that reports all three keys | Skill + code | OPEN |
| 35 | Clay formulas silently return EMPTY (no error, status blank) when they use `[...new Set(arr)]`; Plant City read blank on all 469 rows though 237 had one plant. `arr.filter((v,i,a)=>a.indexOf(v)===i)` works (2026-09-29) | `create_formula_column()` lints for spread syntax / `new Set` and suggests the indexOf dedupe; prove any new formula on 1 known-positive row before trusting a count | Code + test | DONE 2026-09-29: `lint_clay_formula()`; `create_formula_column()` refuses (lint=False overrides), `create_column()` warns, 4 offline tests; live: refused on scratch before any write |
| 31 | Search DSL people **preview** rows are a flat shape (`name`, `latest_experience_*`, `location_name`, `matched_experiences: [[company, title, location, start, end, is_current], ...]`), NOT the table payload (`matched_experience.company.domain`, `structured_location.city`); parsing preview with table paths reads all None. Imported tables get no Company Domain column by default. `company.domain in (...)` inside `experiences.count(...)` scopes to a company list WITHOUT `filter_to_companies` (so no #24 side column) (2026-09-29) | `parse_dsl_preview_row()` helper returning named fields; `send_search_dsl_to_table(extra_columns=["company_domain", "start_date"])` adding the formula columns; docs in action-registry | Code + test + docs | DONE 2026-09-29: `parse_dsl_preview_row()` + `send_search_dsl_to_table(extra_columns=)` (`DSL_EXTRA_COLUMNS`), 4 offline tests; live: Company Domain + Start Date filled (clay.com, 2025-11) |
| 32 | Search DSL Target companies (`clay.filter_to_companies(@table(...))`) resolves each account to one Clay company entity, so brands with several entities on one domain lose people: on Client C WF1 (128 cos) domain-target missed 19 and LinkedIn-target 28 vs a literal `company.domain in (...)` list, flipping 2 companies (Aurubis, Precast) from "has a reliability team" to "none". Also: two `filter_to_companies` cannot be OR-ed (400); `@table()` is only valid inside `filter_to_companies` (not in `company.domain in`); `update-and-run` cannot change target companies (400 "Create a new search to use different target companies") (2026-09-29) | Docs in action-registry (coverage trade-off, when to prefer a literal domain list); helper `compare_dsl_scopes()` that previews both scopes and diffs sample companies before import | Docs + code | DONE 2026-09-29: `compare_dsl_scopes()` + action-registry scope trade-off, 1 offline test; live: both scopes 73 for stripe/clay (no loss on single-entity brands); preview does not add the #24 column |
| 33 | A table can hold several sources: `POST /workspaces/{ws}/search-dsl/send-to-table` with `destinationTableId` adds a Search DSL source to an EXISTING table (`isNewTable: False`, rows land in the same `f_people_search` column so existing formulas cover them). Sources do NOT dedupe against each other (655+657 = 1,312 rows); `PATCH /tables/{id} {"tableSettings":{"DEDUPE_FIELD_ID":<LinkedIn Profile>,"DEDUPE_KEEP_STRATEGY":"keep_oldest"}}` collapsed them retroactively to 676 unique within seconds. The operator caught that I had built separate tables per search instead (2026-09-29) | `add_search_dsl_source(table_id, query)` helper + `set_table_dedupe(table_id, field_id, keep="keep_oldest")`; build-clay rule: one satellite table per question, one source per scope, dedupe on person LinkedIn | Code + test + skill | DONE 2026-09-29: `add_search_dsl_source()` + `set_table_dedupe()` + build-clay 4d, 5 offline tests; live: 6-person source on a 3-row deduped table → 6 rows, 6 unique LinkedIn |
| 34 | The use-ai model list is dynamic (`/actions` → use-ai `model` input has `dynamicOptions: true`, `options: []`), so there is no catalog to read; the reliable list is the models already bound on live columns (scan `inputsBinding.model` per `useCase`). Clay-native models (`clay-argon`, `clay-helium`, `clay-neon`) bill **Clay credits**, not the workspace model key: with ~0.1 credits all 4 clay-argon cells returned `ERROR_OUT_OF_CREDITS` (2026-09-29) | `list_ai_models_in_use()` helper (scan + counts by useCase); `clone_column()` warns when the target model is a `clay-*` model and the workspace credit balance is low | Code + test + docs | DONE 2026-09-29: `list_ai_models_in_use()` + `credit_balance()` + clone warning for `clay-*` models under 100 credits, 2 offline tests; live scan of <workspace_id> (top: claygent gpt-4o-mini 88), balance 0.1 |
| 37 | Rex has no folder-create helper. `POST /workspaces/{ws}/folders {"name": ...}` creates a top-level folder (returns `f_...` id, `parentFolderId: null`); `POST /workbooks` with `parentFolderId` places the workbook in it (read back via resources_v2 parentResource listing). Verified live on Client B (2026-09-29) | `create_folder(name, parent_folder_id=None)` helper + `create_table(folder_id=)` (pairs with #34 folder row) | Code + test | DONE 2026-09-29: `create_folder()` (nested too), `list_folder()`, `create_workbook(folder_id=)`, `create_table(folder_id=)`, 5 offline tests; live on <workspace_id> scratch |
| 38 | Cells whose run condition is false read `metadata.status: "ERROR_RUN_CONDITION_NOT_MET"` (not `RUN_CONDITION_NOT_MET`); other `ERROR_<REASON>` statuses exist (`ERROR_OUT_OF_CREDITS`) (2026-09-29) | `_run_finished()`: every `ERROR_*` is final; `run_paced()` retries only plain `ERROR` and reports the rest under `not_run` | Code + test + docs | DONE 2026-09-29: 1 offline test; live on Client A scratch: BR row reported `not_run`, 0 unfinished |
| 39 | Rex has no table-delete helper; `DELETE /tables/{id}` works (200 with the table body, then GET → 404). Also: Send table data into a new table ran at ~90-250 rows/min (15.6k rows ≈ 1-3 h) while an API export/import of the same rows took ~4 min (2026-10-05, Client B WF10 B3) | `delete_table(table_id, expect_name=)` helper that refuses unless the name matches + reads back 404; build-clay note: for one-off moves of >~3k rows, show the operator the speed trade-off (Send table data lineage vs import) before choosing | Code + test + skill | OPEN |
| 40 | Provider prices live in `GET /actions?workspaceId=<ws>` (plain `/actions` → 400): each action has `pricing.credits` plus `pricing.prePricingChange2026.credits` and `pricing.postPricingChange2026.credits` (`basic` data credits + `actionExecution` actions). Work-email finders on the new plan: Icypeas 0.2, LeadMagic 0.3, Findymail 0.5, Wiza 0.5 (+1 action each); legacy 0.5 / 1 / 2 / 2 (2026-10-05, Client B ws). | `action_pricing(keys, plan=)` helper reading the right price set via `workspace_billing()`; `create_waterfall(order="cheapest")` option; fix `list_actions()` to pass workspaceId | Code + test | OPEN |
| 41 | Standalone Find Jobs (no company list) = `startFrom: "CsvOfCompanies"` + empty company inputs; jobs Search DSL cannot send to a table ("Jobs queries cannot be sent to a table yet"); no company-size filter on the source (2026-10-06, own workspace) | Standalone mode in `create_find_jobs_source()` (company_table_id optional), auto-run off, offline test | Code + test + docs | OPEN | 2026-10-08 live: a raw `create-cpj-table` jobs post with the standalone inputs (`startFrom: CsvOfCompanies`, empty company lists, `company_table_*: null`) WORKS over the API (Hiring BDRs, 3,586 posts); helper code still to add. Also: a "Rows from" source column cannot be put in a field group (400).

| 42 | Older UI-built formula waterfalls store `typeSettings.formulaWaterfall` as bare formula STRINGS (e.g. Client D WF1 June `Master Company Domain`: `["{{f_x}}", "{{f_y}}?.normalizedUrl"]`), not `{formula, prompt}` objects; `formula_logic()` / `describe_columns()` crashed with `AttributeError: str has no .get` (2026-09-30) | Accept both shapes in `formula_logic()` | Code + test | DONE 2026-09-30: string branches normalised to `{formula}`; offline test; live: `describe_columns()` ran clean on the June WF1 workbook (read-only) |
| 45 | The **department ("job function") filter exists only on the classic Find People (MixRank) source** (`inputs.job_functions`, values e.g. `"Engineering"`, `"Information Technology and Computer Science"`; seniority = `job_title_seniority_levels_v2` with `c-suite`/`vp`/`director`/`head`...). The Search DSL has no such field (Clay's own filter-to-DSL map says `job_functions: {unsupported: "no_dsl_field"}`; DSL only has `seniority` inside `experiences.count`). A classic source CAN be added to an existing classic table via `cpjConfig.destinationTableId` + `destinationTableSetupMode: "source_only"` (rows land in the same source column, deduped by profile), but NOT to a table with a Search DSL source (400 "Filters mode sources cannot be added to a table that has an advanced search source"). Classic and DSL return different LinkedIn slugs for the same person (same as #39) (2026-10-02) | `create_find_people_source(destination_table_id=, job_functions=, seniority_levels=)` with enum validation (`JOB_FUNCTIONS`, `SENIORITY_LEVELS_V2`); `validate_dsl_query()` refuses department-like keys with a hint to use the classic source; docs in action-registry | Code + test + docs | OPEN |
| 46 | Clay's formula engine is modern V8-level JS: `\p{L}`/`\p{Script=Latin}` with the `u` flag, lookbehind `(?<=...)`, `.normalize()`, arrow callbacks inside `.map/.filter/.replace`, and `[x].map(v => ...)[0]` as a let-binding (no IIFE) all work (proved on Client B Master People, 8.6 KB first-name cleaner = Node output on 6,218/6,218 rows). A formula PATCH followed by `run_column(force=True)` DOES recompute every cell. Blank text in an `override || formula` column falls through to the formula, so an intentional blank needs a sentinel (`(blank)`) (2026-10-05) | `clean_formula_test(js, rows)` helper: substitute `{{f_id}}` with row values, run in Node, diff vs Clay read-back; docs: formula-capabilities note + override-column pattern (never write into a formula cell) | Code + test + docs | OPEN |
| 46 | **Send table data (route-row) into a table that already has same-named text columns does NOT fill them**: rows land in a new `Rows from: <first source table>` source column with the rowData as keys; the text columns stay empty. Two route-row columns from two tables into one target **share that one source column** (`typeSettings.sourceIds` lists both). Target columns must be formulas `{{source}}?.["Key"]`. Force re-run updates the linked row in place (2026-10-06) | `create_route_row_column(..., target_formula_columns=True)` that creates `{{source}}?.["key"]` formula columns on the target for every rowData key (once per target, reused by a 2nd route); doc in action-registry | Code + test + docs | OPEN |
| 47 | **Column order over the API**: `PATCH /tables/{t}/views/{v}/fields/{f}` with `{"afterFieldId": ...}` moves one column (works per view, any position); `PATCH /tables/{t}/views/{v}/reorder-fields` `{fieldIds, afterFieldId}` only moves fields that are already adjacent (400 "Fields are not adjacent in the view", 500 on bad input). Field groups do not set order (2026-10-06) | `set_column_order(table, view_ids, field_ids)` chaining afterFieldId moves, with read-back of `fields[f].order` | Code + test | OPEN |
| 48 | `create_records()` used to build a derived Companies table (4,248 rows, no lineage) a second time despite #15's skill rule; the operator asked that it not repeat unless they expressly say so (2026-10-06) | Code guard: `create_records()` refuses > `API_ROW_WRITE_LIMIT` (2) rows unless `allow_bulk_api_rows=True`; build-clay 4c says the flag is only for the operator's explicit request or non-Clay data | Code + test + skill | DONE 2026-10-06: guard + 3 offline tests (162/162 pass); no live check needed (refuses before any API call) |
| 49 | Bulk domain → company import: giant domains (google.com 28.6k entities) break the 25,000-per-search cap; Size comes back as a select (`optionIds`), which silently broke a size tie-break on 70 domains (2026-10-06) | `lookup_companies_by_domain()`: giant-domain pre-scan + exclusion, chunking with preview-sized limits ≤ 25,000, name-first matching from a domain→name map, select decoding | Code + test | OPEN |
| 50 | New views start with no column colours (colour is per view), so views made after `create_field_group(color=)` looked uncoloured (2026-10-06) | `create_view(copy_colors=True)` copies the Default view's colours; `copy_view_colors(table, target, source=None)` helper | Code + test | DONE 2026-10-06: 2 offline tests (164/164); live: scratch view on own table 2 came out with all 18 colours, then deleted |
| 51 | Claygent answered from the prompt's description without browsing (`stepsTaken: []`) on 2 of 4 test rows (2026-10-07) | `verify_ai_column()` flags `no_browsing` for claygent cells with empty `stepsTaken`; build-clay prompt rule "REQUIRED: open the domain" for web checks | Code + test + skill | OPEN |
| 52 | Classic Find People linked to a companies view ignores the `company_record_id` / `company_identifier` subset you pass: the server rewrites both to EVERY record in the linked view (3-domain test → scoped to all 255), and each source auto-adds an "Update People Search (Find people Table)" action column to the companies table. Smart title mode adds noise (Director, Head of CS, SDR) (2026-10-07) | `create_find_people_source()`: warn/validate that the subset == the view's records (test on a small VIEW, not a small list); document the auto trigger columns; `destination_table_id=` param (see #45); recommend a title-classifier formula after smart mode | Code + test + docs | OPEN |
| 53 | Clay formulas reject JS spread (`[...a, ...b]`): the column gets `settingsError: INVALID_FORMULA_PARSING_FAILED` and every cell keeps its OLD value silently, so downstream routers looked fine but were stale. Also: classic Find People with `company_table_field_id` = Company LinkedIn returns the same entities as the domain scope (+1 AE on 254 companies), while the Search DSL `filter_to_companies` found 22 more AEs (2026-10-07) | `update_column()` / `create_formula_column()`: read back `settingsError` and raise; offline check that refuses `...` in formulaText; docs: LinkedIn-scoped recovery = DSL, not classic | Code + test + docs | PARTIAL 2026-10-08: `update_column()` now lints formulaText (offline test); settingsError read-back + docs still OPEN |
| 54 | Domain / LinkedIn / URL columns were created as `text` (formula default), so the operator could not click them; 12 columns across the Hiring AEs tables (2026-10-08) | `guess_column_data_type()`; `create_formula_column(data_type=None)` infers url/email from the name; build-clay override 4c2 + post-build sweep | Code + test + skill | Code + 4 offline tests DONE (168/168); live: 12 columns retyped to url on our own workspace, read back OK; scratch-table check of the auto-infer path still to do |
| 55 | A company whose Clay entity is the generic **"Stealth Startup"** LinkedIn page poisons every LinkedIn-scoped people search: harmonic.ai pulled 2,854 "founders" of unrelated stealth companies (and its 1-50 size came from the same entity) (2026-10-08) | Pre-flight in people-source helpers: warn when a scoped company's LinkedIn slug is a known generic page (stealth-startup, self-employed, confidential) or a single company returns > N rows; a stock `Experience Company` / employer-match formula for people tables | Code + test + docs | OPEN |
| 57 | Route-row condition blocks its own downgrade: a source row that stops meeting the route condition cannot be updated in the target by a forced re-run (Client A health-tech 50-200 send table, 2026-10-13) | `create_route_row_column()` docstring + build-clay rule: add a `QA Exclude` column on every send table and gate push columns/views on it; optional `create_send_table()` helper that does it | Code + docs | OPEN |
| 56 | Clay's formula parser rejects `\uXXXX` escapes in string literals (valid JS, Node accepts it): the column gets `settingsError: INVALID_FORMULA_PARSING_FAILED` at a misleading `pos` and keeps old/empty values. Was only in memory (`feedback_clay_formula_unicode_escapes.md`, 2026-09-11), not here; hit again on the /campaign-qa demo E1L2 (2026-10-08) | `lint_clay_formula()` flags `\uXXXX` / `\u{...}`, so `create_formula_column()` / `update_column()` refuse before any write | Code + test | DONE 2026-10-08: 1 offline test (169/169); live: `create_formula_column` with `\u2014` refused on demo table `t_xxxxxxxx` (own workspace, not a client), field count unchanged. Worth sharing upstream |
| 58 | Company Search DSL CAN filter by country: `locations.count(country_name = "United States" and is_headquarters = true) >= 1` (US-HQ only; sample all US) vs `locations.count(country_name = "United States") >= 1` (any US location, pulls foreign HQs). `country`, `country_iso`, `primary_location.country` are Unknown fields; inside `locations` `country_iso` is Unknown. Raw POSTs must send `selectMode: "preview"` or the query runs in full and times out (2026-10-13, Client B 51-500 TAM) | Add `us_hq_filter()`/`country_filter(names, hq_only=True)` helper + accept it in `validate_dsl_query()`; correct action-registry 'Filterable company keys' (country IS filterable via locations.count) | Code + test + docs | OPEN |
| 47 | Search DSL sources created via `send_search_dsl_to_table()` / `add_search_dsl_source()` are named after the TABLE, so several sources on one table are indistinguishable; the operator: always name Find Company sources properly. `PATCH /sources/{id} {"name"}` renames (read back via `GET /sources/{id}`); source column renamed via `PATCH /tables/{t}/fields/f_companies_search` (Client B FinTech TAM, 2026-10-13) | `source_name=` param on both helpers (required when adding a 2nd source), renamed + read back before returning | Code + test | OPEN |
| 59 | Every Search DSL source added with `add_search_dsl_source()` / `send_search_dsl_to_table()` is named after the TABLE, so a 4-slice accounts table showed 4 identical sources 'Accounts - Clay (Company Search)' (Client B 51-500 TAM, 2026-10-13; the operator caught it). `PATCH /sources/{id}` with `name` + full `typeSettings` (name changed) renames it, query untouched | `rename_source()` added (reads back); next: `source_name=` param on both helpers so every slice is named at creation | Code + test | OPEN |
| 60 | Table dedupe `DEDUPE_KEEP_STRATEGY: keep_oldest` did NOT keep the first-routed copy when a second Send table data source sent the same key later: Client B FinTech consolidated, Prospeo routed first (2,306 rows), Clay routed after; 837 overlapping domains ended up as the Clay row, the Prospeo row (with exact employee count) gone (2026-10-13). Send table data also ran ~2,500 rows/min here (34k in ~13 min), far faster than the 90-250/min seen on 10-05 | Don't rely on route order + keep_oldest to choose which source wins; route once and enrich from the preferred source with a free lookup by key, or merge outside Clay. Docs + build-clay rule | Docs + skill | OPEN |
| 61 | `create_field_group()` with a SOURCE column (e.g. a people-search source) → Clay 400 "is a source column and cannot be grouped", after nothing else written; a retry with the source removed works (Client B 51-500 people tables, 2026-10-13). Colour the source column with `set_column_color()` instead. Also: grouping a field that is already in a group moves it, and naming the new group renames it (the stray probe group was absorbed, no orphan) | `create_field_group()` refuses source columns before any write, naming them | Code + test | Code + offline test DONE 2026-10-13 (130/130); live check on scratch table pending |
| 62 | `create_field_group()` with fields that already sit in 2+ groups → Clay 400 "Cannot merge multiple groups into one" (Client B Consolidated regroup, 2026-10-14). `POST /tables/{t}/fields/group/{gid}` with `{name, fields}` on ONE existing group moves the other fields into it (old groups keep a stale empty shell). | Guard in `create_field_group()` (refuse before write) + new `set_group_members()` (update members, read back). 2026-10-16: some ungrouped fields silently refuse to JOIN an existing group (200 OK, not applied; read-back caught it) while a fresh group for them works: use a new numbered sub-group (6a/6b) | Code + test | Code + offline test DONE 2026-10-14 (132/132); used live on Client B Consolidated |
| 63 | Clay renamed the session cookie to host-only `__Host-claysession` (2026-10-15); sending only `claysession` gets 401 "You must be logged in" even with a fresh value, and the row may not appear under app.clay.com in DevTools → Cookies | `_load_cookies()` sends the value under both names (`__Host-claysession` on api.clay.com + legacy `claysession`); COOKIE_SETUP.md updated (copy from Network → Request Headers) | Code + docs | DONE 2026-10-15 (live login OK, 135/135 offline) |
| 62 | View filter on a SELECT (colour-coded label) column: only `{"type":"SELECT_EQUAL","fieldId":f,"value":{"optionIds":[id]}}` works. A plain id, a list, the option text, EQUAL/CONTAIN, CONTAIN_ANY are all accepted and SILENTLY ignored (view shows every row). `optionIds` with several ids only matches the FIRST; use one SELECT_EQUAL per option + combinationMode OR (Client B FinTech consolidated, 2026-10-14) | `view_filter()` builds the optionIds shape for select fields (look up option id by text) and refuses multi-id; `set_view_filter()` read-back compares view_count with an expected count when given | Code + test | OPEN |
---

## 2026-10-08 · `\uXXXX` escapes break Clay formulas (Node says the JS is fine).

**What happened.** Building the /campaign-qa demo People table (`t_xxxxxxxx`), the E1L2 formula carried the planted em dash as `\u2014`. Clay stored the column with `settingsError: INVALID_FORMULA_PARSING_FAILED` at pos 675; `node --check` on the same JS passed. Swapping the apostrophes to `\u0027` (first guess) kept the error; putting the literal `-` and `'` in fixed it.

**What is actually true.** Clay's formula parser does not accept `\uXXXX` escapes inside string literals, and the reported `pos` points somewhere else (Clay rewrites `{{f_}}` refs before parsing). This was already in memory from 2026-09-11 but never made it into Rex.

**Next time.** Write literal UTF-8 characters into formula text (`json.dumps(..., ensure_ascii=False)` if building it in Python). Always read `settingsError` after creating a formula.

**Rex follow-up:** Code + test, backlog #56 (DONE): `lint_clay_formula()` now refuses `\uXXXX`.

## 2026-10-08 · "Stealth Startup" LinkedIn entities poison LinkedIn-scoped people searches.

**What happened.** Hiring BDRs contacts: a classic Find People source scoped by company LinkedIn added 2,865 rows; 2,854 hung off harmonic.ai. Its Clay company entity is the generic "Stealth Startup" LinkedIn page, so every stealth-mode founder on LinkedIn matched. The lookup to table 2 (limit 100) then returned stealth founders and never reached Harmonic's real staff; the pick was "Founder - Stealth Startup". Harmonic's 1-50 size came from the same wrong entity.

**What is true.** The source record carries `latest_experience_company` / `matched_experience.company_name`; comparing it to the company name / domain root catches the bad rows (2,083 say "Stealth" outright, ~770 list random employers). A lookup's 100-record limit means one polluted company can hide its real people.

**Next time.** Before a LinkedIn-scoped people search, check the companies' LinkedIn slugs for generic pages and any company whose preview count is out of line with its size. Add an employer-match column to every people table and rank mismatches last.

**Rex follow-up.** Backlog #55.

## 2026-10-07 · A formula that fails to parse keeps its old values; spread syntax is unsupported.

**What happened.** Combining two lookup arrays in table 2 with `[...a, ...b]` "worked": no API error, and every row kept a sensible AE count. Two hours later a check showed companies with LinkedIn-found AEs still at 0. The column had `settingsError: INVALID_FORMULA_PARSING_FAILED`, and Clay had left every cell at its previous value.

**What is true.** Clay's formula parser rejects JS spread. A parse failure is silent: the PATCH succeeds and cells stay stale. `.concat()` works. Name-dedupe across tables needs the same name columns in both (table 4 lacked Last Name, so the union double-counted to 861).

**Next time.** Read back `settingsError` after every formula create/update. Dedupe across engines on first + last name built the same way on both sides.

**Rex follow-up.** Backlog #53.

## 2026-10-07 · Find People scopes to the whole linked VIEW, not the list you pass.

**What happened.** Own-workspace Hiring AEs team check: I created a classic Find People source linked to table 2's 255-row view, passing only 3 domains as a test. It returned 100 AEs (the limit) across 65 companies. Reading the source back, Clay had replaced `company_record_id` and `company_identifier` with all 255 records of the view.

**What is true.**
- The scope of a linked classic Find People source is the linked view. The id/domain lists you send get overwritten server-side, so a small list is not a small test.
- Each source adds an "Update People Search (Find people Table) - <timestamp>" action column to the companies table (one per source, so 3 here).
- A second source with `cpjConfig.destinationTableId` + `destinationTableSetupMode: source_only` added the remaining rows (100 → 453) with dedupe, 0 credits.
- Smart title mode matched a few non-AEs (Director, Head of Customer Success, SDR, BD Manager); a title-classifier formula on the people table is needed before counting.
- Domain scope misses people whose profile points at another domain: 14 of 255 companies had no DM by domain. Re-pointing a classic source's `company_table_field_id` at the **Company LinkedIn column** (linked to a view of just those companies) works and recovered DMs at 6 of the 14 (0 credits). The same person can carry a stale title in classic data (Board Member) and the current one in the DSL (Cofounder & CEO): check the DSL preview before excluding a company's founder.

**Next time.** To test, point the source at a small filtered VIEW (or keep `limit` small). Count people only through a classifier formula. Expect and group the auto trigger columns.

**Rex follow-up.** Backlog #52.

## 2026-10-07 · Claygent model bake-off (competitor + B2B check): gpt-4.1-mini beat gpt-5-mini and gpt-4o-mini.

**What happened.** Same prompt + 13-field schema, 3 cloned columns, 10 deliberately hard companies on own table 2
(sales recruiters, a GTM tool vendor, an AI outbound service, an outsourced-sales firm, a digital agency, a gov marketplace,
home infusion care, an exam-prep company, a schools/consumer health company). Ground truth checked on the live sites.

**What is true.**
- gpt-4.1-mini: 10/10 verdicts right, browsed on every row (1-6 steps), ~$0.0089/row.
- gpt-5-mini: 8/10. Skipped browsing on 2 rows even with "REQUIRED: open the domain" (Zgraph called a growth agency
  competitor without visiting; it is a web-design/marketing studio = not a competitor) and called a live site
  (shopgarage.com) "no site" at low confidence. ~$0.0069/row.
- gpt-4o-mini: cheapest (~$0.0016/row) but kept a B2C patient-care company (home infusion) as b2b, failed one row with
  no output, and mis-flagged two non-software companies as GTM tool vendors.

**Next time.** For live-web classification on our OpenAI key, default to gpt-4.1-mini; prove any cheaper model on a
10-row hard set first. Read `stepsTaken` per row: a row with 0 steps is unverified.

**Rex follow-up.** Docs + skill: model guidance in build-clay; `no_browsing` flag already tracked in #51.

## 2026-10-07 · A Claygent skips browsing when the input already carries a description.

**What happened.** Hiring AEs competitor/B2B Claygent (own table 2, gpt-5-mini on `own-openai-1`): 2 of 4 test rows
(RevPilots, GaggleAMP) came back SUCCESS with `stepsTaken: []`, i.e. the agent answered from the Clay description I passed
in and never opened the site (one even said so in `reasoning`). Verdicts were right, but only by luck of a current description.

**What is true.** A Claygent decides for itself whether to browse. Rich context in the prompt makes it skip research.
`stepsTaken` in the cell's fullValue (read via `read_ai_output()`) is the only proof it browsed.

**Next time.** For live-web checks say "REQUIRED: open the domain before you answer; the description is only a hint", and
check `len(stepsTaken) > 0` on every test row. After the fix all 3 re-runs browsed (1 step each), ~$0.006-0.010/row.

**Rex follow-up.** Code: `verify_ai_column()` should flag Claygent rows with empty `stepsTaken` (`no_browsing`). Backlog #51.

## 2026-10-06 · Views created after a column group have no colours.

**What happened.** Hiring AEs table 2: `create_field_group(..., color=)` coloured every view that existed at that moment.
Three views added afterwards ("Qualified", "Qualified + Founding / First AE", "Review") showed all 18 grouped columns
uncoloured. The operator: "I don't think they are color labeled in Clay."

**What is true.** Colour is a per-view field setting (#20). A new view starts with no colours and does not inherit them.

**Next time.** Group + colour after the views exist, or let `create_view()` copy them (now the default).

**Rex follow-up.** Code + test, backlog #50 (DONE).

## 2026-10-06 · Domain → company enrichment for 4,248 domains: giant domains, the 25k cap, and Size as a dropdown.

**What happened.** Hiring AEs table 3 (our own workspace, `t_xxxxxxxx`): `select from companies where domain in (...)`
for 1,500-domain chunks. One chunk counted 42,098 entities and `send-to-table` failed 400 **"Limit exceeds your plan row
limit of 25,000 per search."** (my `limit` was 30,000). Cause: a few domains hold thousands of entities. Then I read the
picked records' Size and it came back as `{"optionIds": [...]}`, so my "prefer the larger bucket" tie-break ranked every
record equal and 70 of 227 tied domains were picked arbitrarily.

**What is true.**
- Giant domains (2026-10-06): google.com 28,586, linkedin.com 5,468, odoo.com 1,479, webflow.io 1,225, amazon.com 925,
  baidu.com 788, canva.com 506. Normal domains average ~2 entities (59 random domains → 126). A `company_size` filter does
  NOT remove them (google.com still ~20k small entities).
- Finding them is cheap: preview counts per 50-domain group, then bisect only groups ≥500 (85 + ~30 free previews).
- Exact name match against the job post's company name resolves 4,196 of 4,222 domains; domain-root / LinkedIn slug adds 6.
- The imported Size column is a SELECT: map `optionIds` to labels via the field's `typeSettings` options before ranking.

**Next time.** Pre-scan for giant domains, exclude them, set each chunk's `limit` from its preview count (≤ 25,000), match on
company name first, and decode select options before comparing sizes.

**Rex follow-up.** Code + test: `lookup_companies_by_domain()` should pre-scan + skip giant domains, chunk under the 25k
cap, accept a `{domain: company name}` map to match on name, and decode select values. Backlog #49.

## 2026-10-06 · Built a derived Companies table with API-written rows again; guard moved into code.

**What happened.** Hiring AEs (our own workspace): I collapsed 16,126 AE job posts into a Companies table by
writing 4,248 rows with `create_records()`. The operator: "we are using the send table data column so that we are able
to connect things back." Same mistake as #15, which only had a skill rule, so it repeated. The API table
(`t_xxxxxxxx`) was deleted with the operator's OK and is being rebuilt with Send table data from a
one-post-per-company verdict column on the jobs table.

**What is true.** A skill rule is not enough: the call has to fail. Derived tables are built with
`create_route_row_column()` (+ verdict column or destination dedupe); API rows only on the operator's explicit request.

**Next time.** `create_records()` now raises above 2 rows unless `allow_bulk_api_rows=True`. Do not set the flag
on your own judgment, not even for speed.

**Rex follow-up.** Code + test + skill, backlog #48 (DONE).

## 2026-10-06 · Find Jobs can search ALL jobs (no company list): `startFrom: "CsvOfCompanies"` with an empty company list.

**What happened:** building our own Hiring AEs workflow signal-first. Every Find Jobs action schema lists
`company_identifier` as required, and Rex's `create_find_jobs_source()` only builds `startFrom:
"ClayTableOfCompanies"`. The jobs Search DSL (`select from jobs`) previews globally (title `contains` works,
`job_posted_date >= "YYYY-MM-DD"` works, `company.company_size in (...)` works; `country`, `region`,
`locality`, `location_country` are `Unknown field`; `location contains "United States"` misses "New York, NY"
style rows) but `send-to-table` returns 400 **"Jobs queries cannot be sent to a table yet."**
The operator then created the source in the UI (Sources > Find jobs) and Rex read it back: table
`t_xxxxxxxx`, source `s_xxxxxxxx`, ws <workspace_id>.

**What is actually true:** the UI's standalone Find jobs is the SAME action (`find-lists-of-jobs-with-mixrank-source`,
`create-cpj-table` jobs config) with `inputs.startFrom: "CsvOfCompanies"`, `company_identifier: []`,
`company_record_id: []`, `company_table_id: ""`, `company_table_view_id/field_id: null`, plus
`job_title_keywords`, `locations ["United States"]`, `employment_type`, `max_num_days_since_posted 30`,
`limit 25000`. It searches every job (16k+ US "Account Executive" rows in 30 days and still loading), 0 credits.
There is **no company-size filter** in this source, so size has to be gated downstream. The table comes back
`AUTO_RUN_ON: true`. Rows keep arriving for minutes after creation (12,550 → 16,126 between two reads).

**Next time:** for a signal-first jobs pull, build the source with `startFrom: "CsvOfCompanies"` and an empty
company list; don't use the jobs Search DSL for tables. Count rows only after the source finishes.

**Rex follow-up:** Code + test: `create_find_jobs_source(..., company_table_id=None)` → standalone mode
(`startFrom "CsvOfCompanies"`, empty company inputs), keep `total_limit` ≤ 25,000, turn auto-run off. Backlog #41.

## 2026-10-05 · Long cleaning formulas in Clay: what the engine supports, and how to override safely.
**What happened.** Built Clean First Name / Clean Company Name on Client B WF10 B3 Master People `t_xxxxxxxx` as single JS expressions (8.6 KB / 3.3 KB), tested in Node on all 6,218 rows first. A 2-row probe proved `\p{L}`+`u`, lookbehind, `.normalize()` and `[x].map(v=>...)[0]` binding. Later a wrapper edit added one `)` too many: Clay stored the formula with `settingsError: INVALID_FORMULA_PARSING_FAILED` and kept serving the old cell values (no visible break).
**What is true.** Modern JS works in formulas (not IIFE, not spread/new Set per #35). PATCH formulaText + `run_column(force=True)` recomputes. `override || clean` columns: empty override falls through, so use a sentinel for a deliberate blank.
**Next time.** Write long formulas as files, `new Function('return '+expr)` syntax-check + run on every row in Node, PATCH, read `settingsError`, force-run, diff Clay vs Node on all rows. Overrides go in a separate text column, never into the formula cell.
**Rex follow-up.** Backlog #46.

## 2026-09-29 · Whole backlog promoted into Rex; five new gotchas found while doing it.

**What happened.** The operator asked to fix every OPEN backlog row. All 18 (+ the #29 rename) are now code, test, skill
or docs, 158 offline tests pass (was 112), each code fix live-checked on SCRATCH workbooks: `SCRATCH rex backlog
2026-09-29` + folder `SCRATCH rex folder 2026-09-29` in our own workspace (searches only, 0 credits) and
`SCRATCH rex route source/target` in Client A (legacy plan, 0 actions; route-row only, no external calls).

**What is actually true (new).**
- A cell whose run condition is false reads `metadata.status: "ERROR_RUN_CONDITION_NOT_MET"`, not the view-filter
  name `RUN_CONDITION_NOT_MET`. `run_paced()` first counted those rows as "unfinished"; fixed: every `ERROR_*`
  status is final, only plain `ERROR` is retried (so `ERROR_OUT_OF_CREDITS` is never re-spent blindly).
- Clay's `domain` index is noisy: `domain = "stripe.com"` gives 34-38 company entities, `clay.com` 7, in no useful
  order (first rows were "DanielTems" and "Clay University"). Any domain → company lookup must rank, never take row 1.
- `audiences/v2/dsl.fields` / `dsl.complete` describe Clay's CRM *audiences* DSL, not the search DSL, so the
  search DSL has no field catalog endpoint; keys and buckets were settled by free previews (400 messages name the
  bad field and suggest buckets).
- A run condition sent on a FORMULA column is dropped silently (conditions live on action columns). Waterfall
  formula columns CAN be created over the API with `formulaType: "waterfall"` + `formulaWaterfall[]`.
- A **preview** using `clay.filter_to_companies(@table(...))` does not add the #24 `trigger-find-people-source` side
  column; only a real import does.

**Next time.** Use the helpers listed in README "Additions beyond upstream v2.1 > Backlog batch 2026-09-29". The 74 Client A
list-clean cells (`t_xxxxxxxx`, 502 RateLimitError) are still ERROR: retry them with
`clay.run_paced(table, field, record_ids)` once the operator OKs it, and tell the endpoint owner if they persist.

**Rex follow-up:** backlog #38 (ERROR_* statuses), DONE.

---

## 2026-09-29 · Creating a folder + workbook in it over the API.

**What happened.** Needed a "Workflow #7" folder with a new workbook and table in a client's workspace.
Rex had `list_folders()` but nothing to create one.

**What is true.** `POST /workspaces/{ws}/folders {"name": "..."}` works on the first try and returns the folder.
`POST /workbooks {"name", "workspaceId", "parentFolderId", "settings": {"isAutoRun": false}}` lands the workbook
in that folder; `create_table(name, workbook_id=)` then names the table, turns auto-run off and removes the
placeholder, as expected. Rows written with `create_records()` in batches of 100 (518 rows, 25 text columns + one
email column) read back complete.

**Next time.** Use the two calls above until the helper exists. **Rex follow-up:** code + test, backlog #37.

---

## 2026-10-06 · Send table data into a pre-built table; column order over the API.

**What happened.** Client A health-tech TAM send table: I first loaded 1,346 rows by API (the operator: with ~1,300 rows use Send table data). Rebuilt with two route-row columns (founders + tech DMs) into the table I had pre-built with text columns: the rows arrived but every text column stayed empty.

**What is true.** Route-row writes the rowData into one source column (`Rows from: <first sending table>`); a second route into the same table reuses it (`sourceIds` has both). Same-named target columns are not mapped. Make each target column a formula on the source field (`{{f_src}}?.["Email"]`, data type email/url as needed). `forceRun` re-sends update the linked row in place. Column order: per-field `afterFieldId` PATCH on each view; `reorder-fields` only for adjacent fields.

**Next time.** Default to Send table data for any consolidation under a few thousand rows. Create the target table empty, add the route(s), test 2 rows, then add formula columns on the source field and group them. Put the cross-table decisions (dedupe, cap) in a text verdict column on each source table and use it as the route's run condition.

**Rex follow-up.** Backlog #46, #47.

## 2026-10-02 · Department filter = classic Find People only; adding a second Find People source to one table.

**What happened.** Client A health-tech TAM: the operator asked for tech decision makers by Clay's technology department filter, linked to the companies table (Target companies), all searches in one table. I had first run a Search DSL title search with a pasted domain list; ~20 guessed department keys all returned 400.

**What is true.**
- The DSL has no department field. Clay's web bundle maps legacy filters to DSL and marks `job_functions` as `unsupported: no_dsl_field`. `seniority in ("C-suite", "VP", "Director", "Head")` does work inside `experiences.count(...)`.
- The classic source takes `job_functions` (27 values: `Engineering`, `Information Technology and Computer Science`, `Science and Research`, ...) and `job_title_seniority_levels_v2` (`founder, owner, board-member, partner, c-suite, vp, director, head, manager, senior, mid-level, entry, intern, unknown`) with `job_title_seniority_match_mode: exact|floor`.
- `POST /sources/create-cpj-table` accepts `cpjConfig.destinationTableId` (+ `destinationTableSetupMode: source_only | add_basic_fields`): a second classic Find People source lands in the SAME source column of an existing classic table (`isNewTable: false`), deduped on profile (280 + 246 new = 526). It runs on create; `inputs.limit` is the cap. Adding it to a DSL-source table fails with 400.
- The new table is auto-named after the filters and has auto-run ON; the auto-created `Company Table Data` lookup does not run until triggered (`run_column`, free).
- Classic vs DSL results for the same 257 companies: 94 slug mismatches, but only 9 real misses once matched on name + company domain.

**Next time.** Department or seniority ask → classic Find People linked to a companies view, not the DSL. Put every search for one persona in one classic table from the start. Match people across engines on slug OR name + domain.

**Rex follow-up.** Backlog #45.

## 2026-10-01 · "Not found" and "not run" look identical to a formula; cheap Claygent verdicts need a second check.

**What happened.** On a client's people table, `Bison: Find Lead` returned `SUCCESS_NO_DATA` for people not in
Bison, and my suppression formula (`!{{find}} ? "" : ...`) left them blank. Changing blank to "GTG (not in Bison)"
makes an un-run row look clean too. Separately, a gpt-4o-mini Claygent competitor check over 298 companies
(~$0.001 each) flagged one product company and missed a custom-software consultancy.

**What is true.** A formula only sees the cell value; run status is visible through the API only
(`metadata.status`). Cheap web-research models summarise the homepage and under-read "we build for clients".

**Next time.** After running a lookup/Find Lead that a gate depends on, read statuses via the API and confirm every
row ran. Give every AI verdict column an override column, and cross-check its "no" calls against an independent
description before trusting the count.

**Rex follow-up:** #44.

---

## 2026-10-01 · Basic non-text columns need explicit dataTypeSettings.

**What happened.** Importing the Client B CSV into a new Client A table, `create_column` with `{"type": "email", "name": "Email"}`
returned 400 after 8 text columns were created, leaving a half-built table. Passing
`typeSettings: {"dataTypeSettings": {"type": "email"}}` worked (same for url and number).

**What is true.** Clay wants dataTypeSettings on every basic column type; Rex fills it in only for text/formula.

**Next time.** Pass dataTypeSettings for every basic type; when a multi-column create fails part-way, resume on the same table.

**Rex follow-up:** #43.

---

## 2026-09-30 · Grouping a field that already belongs to a group merges instead of creating.

**What happened.** On the Client A NTL table, `create_field_group([Find Lead, 6 extracts, Suppression], ...)` returned
`gr_xxxxxxxx`, the existing "Push to Bison" group that Find Lead already sat in. Clay merged the new
fields into it. Renaming that group to push-only (3 fields) then left Find Lead + extracts ungrouped.

**What is true.** `POST /tables/{t}/fields/group {fieldIds}` reuses a member's current group. A field can only
belong to one group.

**Next time.** Take fields out of their old group first (rewrite the old group's field list), then create the new
group, and check the returned id isn't an existing one.

**Rex follow-up:** #41.

---

## 2026-09-30 · Clay tables stop at 100 columns.

**What happened.** Adding 6 extract columns for the Bison Find Lead output on the Client A NTL retargeting table
(`t_xxxxxxxx`), the 3rd create returned 400 "Table ... cannot create new field due to table size
limit" (userFriendly: "This table has reached its column limit"). The table had exactly 100 fields
(incl. Created At / Updated At), 2 of the 6 landed.

**What is true.** Clay caps a table at 100 fields. Snapshot tables imported with many metadata columns
(this one came with ~50) hit it fast once enrichment, cleaning, copy and push columns are layered on.

**Next time.** Before a multi-column build, count fields and budget columns; combine small extracts into one
formula where the value is only read by people; propose deleting unreferenced snapshot columns (with the operator's OK).

**Rex follow-up:** #40.

---

## 2026-09-29 · List-clean endpoint rate-limits bulk runs from Clay.

**What happened.** Ran the saved in-house list-clean HTTP column on 1,121 NTL retargeting rows (batches of 200).
1,047 succeeded; 74 errored with `502 {"detail":"upstream check failed: RateLimitError"}`. Retrying in batches of
15 with 20s gaps, and later single rows, still errored.

**What is true.** The limit is on the endpoint's upstream provider, not Clay. It can last longer than a
session-length retry loop. Rows without a clean value must be gated out (Send Eligible? checks the final vars).

**Also found (same run):** the endpoint returns `pass` while cutting some titles to a bare level: "SVP, Head of
Engineering" -> "SVP", "Co Founder & CTO" -> "Co Founder", "VP, AI Platform & Principal Architect" -> "VP" (22 of
1,121). A `pass` verdict is not proof the title kept its function.

**Next time.** Run in smaller paced batches from the start, read back statuses, retry only ERROR cells later.
Always put a raw fallback in the final variable formula (override || clean || raw) so a failed cell never blanks a
row. QA clean titles for bare levels (`^(S?VP|Director|Head|Manager|Lead|Co-?Founder)$`) and restore from raw.

**Rex follow-up:** #36 (also: deploy script should emit the final-variable formulas with the raw fallback and a bare-level QA check).

---

## 2026-09-29 · Clay actions only exist on the new plan; legacy workspaces (Client A) consume none.

**What happened.** Before cleaning names/titles and re-running a lookup on the Client A New Tech Leaders table, I
costed it at ~1,400 Clay actions (and wrongly counted the lookup re-run as actions) and suggested scoping the run down. The operator: Client A is a legacy Clay
account, so it doesn't consume actions at all.

**What is true.** Actions are a new-plan meter. Legacy-plan workspaces pay data credits only, so HTTP API
columns on our own endpoints and own-key enrichments cost nothing extra there. On new-plan workspaces those
cost 1 action per row per run. Lookups are free on BOTH plans (0 actions, 0 credits), as are Send table
data, search imports and formulas: never cost them.

**Next time.** Check `clay.billing_model(table_id)` before proposing where work runs. Legacy: run it inside
Clay (keeps lineage). New plan: for action-heavy work, propose running it outside Clay and writing back to a
column. Unknown: ask, then add the workspace to `WORKSPACE_BILLING`.

**Rex follow-up:** #35 (DONE: code + test + build-clay override 4b + README).

---

## 2026-09-29 · Target companies (filter_to_companies) under-matches multi-entity brands vs a domain list.

**What happened.** The operator asked to scope the Client C WF1 reliability satellite with Target companies
(reusable: re-run from the Accounts table) and to use the Prospeo company LinkedIn for coverage.
Built three versions over the same accounts: literal `company.domain in (<128>)` = 636 people;
Target companies by LinkedIn (`t_xxxxxxxx`) missed 28 of them; Target companies by domain
(`t_xxxxxxxx`) missed 19; the union of both still missed 15. LinkedIn found 0 people the
domain list missed. Misses cluster at Amrize, ASR Group, Aurubis, Kaiser, Bonnell, Precast.

**What is true.** Target companies matches a resolved company entity; the literal domain predicate
matches each experience's domain, so it catches every entity sharing that domain. `OR` of two
`filter_to_companies` = 400; `@table()` only works inside `filter_to_companies`; a source's target
companies can't be changed via update-and-run. Each Target-companies search adds an
"Update People Search" (`trigger-find-people-source`) column to the referenced table: that is the
re-run button, not junk (hide it, don't run it unintentionally).

**Next time.** Preview both scopes and diff before importing when completeness drives copy routing.

**Rex follow-up:** #32.

---

## 2026-09-29 · DSL preview rows are a different shape from the imported payload; scope by domain list.

**What happened.** Client C WF1 reliability satellite: the preview returned totalCount 613 but every
sample field read `None`, because I parsed preview rows with the table payload paths
(`matched_experience.company.domain`). Preview rows are flat: `matched_experiences` is a list of
`[company, title, location, start, end, is_current]` arrays. The imported table
(`t_xxxxxxxx`) also had no company domain column, which the People lookup needs.

**What is true.** Scoping with `company.domain in ("a.com", ...)` inside `experiences.count(...)`
works for 128 domains in one query (all 96 matched domains were in the list) and avoids the
`filter_to_companies` side effect (#24). Add `{{f_people_search}}.matched_experience.company.domain`
and `.start_date` as formula columns after import.

**Next time.** Read `matched_experiences[i]` by index in previews; add the domain formula right after
import.

**Rex follow-up:** #31.

---

## 2026-09-29 · Default workspace drifted; view filter 404 left a half-built view.

**What happened.** Creating a filtered view on Client C WF2 `t_xxxxxxxx` with a bare
`ClayClient()`: the client logged in to workspace **<workspace_id>** (first entry of `/my-workspaces`), not
<workspace_id>. Record reads/writes and view creation worked (table-scoped paths), but `set_view_filter` hit
`/workspaces/<workspace_id>/...` and got a plain 404. The view `gv_xxxxxxxx` existed unfiltered.

**What is true.** The default workspace is whatever Clay lists first, and that can change when a new
workspace is added. A 404 on a workspace-scoped path usually means wrong workspace, not a missing view.

**Next time.** Always pass `workspace_id=` explicitly (own workspace = <workspace_id>, Client A = <workspace_id>).
Check the `[clay] logged in ... workspace N` line before writing.

**Rex follow-up:** #30.

## 2026-09-28 · Find Jobs source rejected above the plan's 25,000-per-search cap.

**What happened.** Building a "hiring devs" signal on the Client A New Tech Leaders retargeting table,
`create_find_jobs_source()` got 400 "Your current plan provides up to 25,000 per search." The helper
sent `limit` and `sourceRecordLimit` = 50,000 (copied from a UI-built table on a larger plan).

**What is true.** The per-search cap is plan-dependent; this workspace allows 25,000. Nothing is created
when the create call fails.

**Next time.** Pass `total_limit` (default 25,000). Keep test runs small with `limit_per_company`. A company DOMAIN column works as the identifier (verified vs LinkedIn URL on stripe.com), so no Company LinkedIn column is needed.

**Rex follow-up:** #29.

## 2026-09-25 · Formula waterfalls hide their logic; condition labels and route rules drift from what actually ran.

**What happened.** Audit of Client E W#3 (workspace <workspace_id>, `t_xxxxxxxx`). A dump that only read
`formulaText` showed the 11 copy columns (E1L1...E1PS) and `Final Email` as empty formulas. The People TAM
work-email waterfall's plain-English run condition said "skip Otro" while the formula did not, and the
route into W#3 now excludes 451 rows it already sent.

**What is actually true.**
- Clay's conditional "formula waterfall" columns store `formulaType: "waterfall"` and an ordered
  `formulaWaterfall: [{formula, prompt?}]` list (first non-empty branch wins). There is no `formulaText`.
- Every condition can carry `conditionalRunFormulaPrompt` (the AI-generated English label the UI shows) next
  to `conditionalRunFormulaText` (what runs). They are not kept in sync.
- A route-row's condition is its CURRENT rule; the destination table shows what past runs sent. Re-evaluate
  the live rule over routed rows before trusting either.

**Next time.** When auditing, read `formulaWaterfall` branches, compare condition label vs formula, and
reconcile routed rows against the live route rule.

**Rex follow-up:** backlog #27, #28 (Code), OPEN.

---

## 2026-09-25 · New tables ignore their name and auto-run setting; Find Jobs, lookups and colours promoted into Rex.

**What happened.** Promoting backlog #12, #14, #17-#21, #23, #24 into Rex, live-checked on a scratch
workbook in <workspace_id> (`SCRATCH rex test ...`, deleted afterwards).

**What is actually true.**

- `create_table()` in a NEW workbook is no better than in an existing one: both returned a table named
  `Custom Table` / `Custom Table (2)` with `tableSettings.AUTO_RUN_ON: true` (the workbook's
  `isAutoRun: false` does not reach the table), plus a blank text column `New Column` and one blank row.
  The workbook itself does take its name. `PATCH /tables/{id} {"name", "tableSettings": {"AUTO_RUN_ON": false}}`
  fixes both, merges into the other tableSettings keys and returns the whole table.
- Find Jobs over a 2-row companies table with `limit_per_company: 1` returned 2 jobs in ~10s, auto-named
  after the search ("Full-time US Jobs, Account Exec, Software Engineer"). Unlike Find People it adds NO
  lookup column to the companies table.
- Lookup-multiple cells read `"✅ 1 Record Returned"`; single `"✅ Record Found"`. Both keyed by column name,
  system columns (`Created At`, `Updated At`) included.
- `DELETE /tables/{id}` and `DELETE /workbooks/{id}` both return 200; the workbook GET then 404s.

**Next time.** Use `create_table()` (it now fixes name + auto-run and removes the placeholder),
`create_find_jobs_source()`, `create_lookup_column()` + `lookup_extract_formula()`, `run_column(force=True)`
for stale lookups, `set_column_color()`. Scratch tests: one scratch workbook, delete it at the end.

**Rex follow-up:** #12, #14, #17-#21, #23, #24 DONE 2026-09-25 (see backlog).

---

## 2026-09-24 · Lookup payload shape; text columns cross lookups; table descriptions over the API.

**What happened.** Rebuilt the WF6B `2. Companies` table with native lineage (People → Send table
data → Companies, deduped on Clay Company ID → Lookup row into the firmographics import → formula
extractors). Over the API a lookup cell's `value` is only `"✅ Record Found"` / `"❌ No Record Found"`
(status `SUCCESS_NO_DATA`), same trap as AI cells.

**What is true.** Single-row lookup: `externalContent.fullValue = {"record": {<column name>: value}}`,
so the extractor is `{{lookup}}?.record?.["Industry"]` (no `mappedResultPath` needed). Multiple-row
lookup: `{"records": [...]}`, so rollups are `({{lookup}}?.records || []).filter(r => r?.["Persona
Status"] == "GTG").length`. Plain **text** columns (written via `update_records`) cross the lookup
too, not only formula columns. `fields|limit` accepts `'50'`. Route-row + table dedupe
(`DEDUPE_FIELD_ID`, `keep_oldest`) collapsed 6,001 people into exactly 5,560 companies. Tables take a
`description` via `PATCH /tables/{id} {"description": ...}` and it reads back. Every step: 0 credits.

**Next time.** Read lookup output from the single-record endpoint (`read_ai_output()` works for it);
prove the extractor on 1 row; give each table a description + a clean Default view and a
"How it was built (all columns)" view so newcomers see lineage without clutter.

**Rex follow-up.** Backlog #17.

## 2026-09-24 · Formula columns can't be JSON-typed; Clay formulas support `??`; every field lists its filter operators.

**What happened.** Live-testing the key-casing fix (backlog #2) on the scratch table, I tried to
fake an AI output object with a formula column typed `json`. Both the text-then-PATCH path and a
direct `type: "formula"` create returned **400 `Data type "json" is not supported for basic
fields`**. The successful create response for a text formula column also carried a
`supportedFilterOperators` list (`[{"operator": "EQUAL", "needsValue": true}, ...]`).

**What is actually true.**

- Only action columns hold structured objects. A formula column must be a basic type (`text`,
  `url`, `email`, ...). To pass an object through a formula, keep it `text` and
  `JSON.parse({{f}} || "{}")` it where it's used.
- Clay formulas support `??`. Verified: `JSON.parse(x)?.roleBucket ?? JSON.parse(x)?.role_bucket`
  returned the snake_case value, while the camelCase-only formula read back empty with status
  SUCCESS (the exact backlog #2 failure).
- Each field's definition lists the view-filter operators it accepts, with `needsValue`.

**Next time.** Don't fake AI output with a JSON formula column; use text plus `JSON.parse`. For
view filters, the per-field operator list is a stricter check than the global enum.

**Rex follow-up:** #10 Code + test (per-field operator validation), OPEN. #11 Docs, DONE (README Gotchas).

---

## 2026-09-24 · People searches with recency / country / size filters: use the Search DSL endpoints

**What happened.** Building Client D WF6B (new revenue leaders, last 90 days), plain Find People
(MixRank) returned 9,944 global titleholders: it has no inputs for job-start date, country, company
size or industry. WF6's working source turned out to be a Search DSL source. Hand-building that
source through `POST /sources/create-cpj-table` failed twice with `404 "Incorrect source
configuration"` and left broken tables behind, because no `previewActionKey` value works for it.
Clay's UI uses a separate `search-dsl` API (found in its web bundle, `store-*.js`). Separately, a
same-query `add` re-run that I first logged as "0 new rows" had simply not finished: it added 25 new
people.

**What is actually true.**

- Preview, free: `POST /workspaces/{ws}/search-dsl/query {"query", "selectMode":"preview"}` gives the
  true `totalCount` and up to 250 rows. Create: `.../search-dsl/send-to-table`. Change + re-run:
  `.../search-dsl/sources/{id}/update-and-run {"dslQuery","mode"}`.
- `send-to-table` runs immediately and creates the table with auto-run ON.
- `add` = next page of people not yet returned. `replace` = delete all rows, re-import.
- Search imports cost 0 credits (6,200 before and after 500 rows).
- The record payload carries `matched_experience.start_date` and `matched_experience.company.domain`,
  so tenure and a Companies-from-People key are free formulas.
- Run status can read `QUEUED` after rows landed, and a finished-looking check can be early: poll
  `/sources/{id}/runs` until `SUCCESS` before counting.

**Next time.** Preview first, size `limit N` from `totalCount`, create with
`send_search_dsl_to_table()`, and settle the query (use `replace`) before adding any column that
holds written values.

**Rex follow-up:** backlog #7 and #8 DONE; #9 OPEN (guard `replace`).

---

## 2026-09-24 · Use `useCase: "use-ai"` for classification. Reserve `"claygent"` for real web research.

**What happened.** Building the Client C WF1 contact qualifier, I cloned the proven column from
the July people table (`t_xxxxxxxx` / `f_xxxxxxxx`) and carried its settings
across unchanged. That column was configured `actionKey: use-ai` with `useCase: "claygent"`. The operator
caught it mid-run and corrected it: the prompt is a pure title classifier with no browsing step, so
it should never have been a Claygent.

**What is actually true.**

- `claygent` is a **browsing agent**. It is for fetching and extracting from the live web.
- `use-ai` is a **plain model call** over data already on the row. It is for classifying,
  normalizing, extracting, routing, rewriting, scoring, and any other transformation of supplied
  content.
- **A prompt that references only row fields and issues no research instruction must be
  `use-ai`.** Choosing `claygent` for that work is wrong on principle even when it appears to
  behave: you are handing a task to an agent that is licensed to go browse, and nothing in the
  prompt stops it.
- Cost is **not** the tell. Measured on 750 real rows of this exact prompt under `claygent`:
  $0.00130/row, p50 $0.00132, p95 $0.00175, 0 Clay credits. Essentially identical to the `use-ai`
  proof. Because the prompt never asked it to browse, Claygent did not browse, so the bill looked
  normal while the configuration was still wrong. **Do not use cost to decide whether the use case
  is right.**
- Clay's own cost report labels this column `use_case: classification` regardless, so that field
  does not tell you what is configured either. Read `inputsBinding` → `useCase` directly.

**Next time.**

1. `clone_column()` carries the source column's `useCase`. Cloning a good column does not make the
   use case right for the new job. **Always read `useCase` back and override it explicitly.**
2. Decide from the prompt: does it require information not already on the row? If no → `use-ai`.
3. Name the column after what is actually bound (`/ Use AI / <model>`). The skill's rule that the
   visible name must match the backend exists for exactly this, and a cloned name inherits the
   source's label silently.
4. If you discover the mismatch mid-run, rows already processed do not automatically need
   re-running. Judge by whether the outputs are sound, not by provenance tidiness.

**Rex follow-up:** Code + test + skill. Backlog #1 (DONE 2026-09-24).

---

## 2026-09-29 · Search DSL `company_size` buckets need comma thousands separators.

**What happened.** A people DSL preview with `company.company_size in ("51-200", "201-500", "501-1000")`
returned 400 Bad Request. Same query with the first two buckets alone worked.

**What is actually true.** Clay's bucket labels carry comma separators above 999. `"501-1000"` is
invalid; `"501-1,000"` is valid. Clay's error body names the allowed values, which is the fastest way
to find them:

```
{"type":"BadRequest","message":"Invalid value \"501-1000\" for field 'company_size'.
 Use one of: \"501-1,000\", \"5,001-10,000\"."}
```

**Next time.** Read the 400 body rather than guessing the bucket vocabulary; Clay enumerates the
valid set in the message. The sub-1,000 buckets (`11-50`, `51-200`, `201-500`) have no comma, so a
query can look correct and only break when the range crosses 1,000.

**Rex follow-up:** validate `company_size` values client-side against the known bucket list and raise
before the call, surfacing Clay's allowed set. Backlog row 25.

---

## 2026-09-24 · `claygent` and `use-ai` return DIFFERENT KEY CASING from the same prompt and schema.

**What happened.** After switching the qualifier's `useCase` from `claygent` to `use-ai` mid-run,
the `Persona Role Bucket` extraction formula (`?.roleBucket`) resolved on exactly the 452 rows run
before the switch and on none of the 2,432 run after. Every other extraction formula was fine.

**What is actually true.** Same prompt, same `answerSchemaType`, different output key casing:

```
claygent rows :  roleBucket   corporateHq     (camelCase)
use-ai rows   :  role_bucket  corporate_hq    (snake_case)
```

Single-word keys (`relevant`, `tier`, `seniority`, `confidence`, `reason`) are identical in both,
which is why the breakage looked selective and random rather than systematic. The cell also reads
`status: SUCCESS` with `isCoerced: true` and no value, so nothing announces the mismatch.

The two modes also return different envelope metadata: claygent adds `reasoning`, `stepsTaken`,
`timeTakenInSeconds`, `forcedToFinishEarlyBecauseOfCost`; use-ai adds `tokensUsed`, `inputTokens`,
`outputTokens`.

**Next time.**

- Diagnose an unresolved extraction formula by probing the real keys, not by guessing:
  `Object.keys({{action_field}}||{}).join(',')` in a temporary formula column.
- Write multi-word extraction formulas casing-tolerant from the start:
  `{{action}}?.roleBucket ?? {{action}}?.role_bucket`
- If you change `useCase` on a column that already has rows, **every multi-word extraction formula
  below it is suspect**, even though the AI column itself reports SUCCESS on all rows.

**Rex follow-up:** Code + test + skill. Backlog #2 (DONE 2026-09-24).

---

## 2026-09-24 · An AI action cell reads back as the string `"Response"` over the API even on success.

**What happened.** The two-row proof of the qualifier returned `status: SUCCESS` but
`value: "Response"` on both cells. I was one step from reporting the column broken.

**What is actually true.**

- The cell carries `isStreamingProgress: true` and a `streamingProgressKey`. The API's `value`
  field is showing a **streaming display placeholder**, not the resolved output.
- The real structured JSON **is** present and **is** readable by Clay formulas.
- Proof: the July qualifier shows `"Response"` on **all 1,973** of its SUCCESS cells, every one
  flagged `isStreamingProgress: true`, and its downstream `isRelevant` formula had resolved to
  **1,776 true / 197 false**. The column had worked all along.
- Re-reading the cell later does **not** clear it. The placeholder persists.

**Next time.**

- **Never judge an AI column by the action cell's API `value`.** It is not the output.
- To verify an AI column, create the extraction formula (`{{action_field}}?.yourKey`), run it, and
  read **that**. That is the only reliable readback path over the API.
- The genuine failure signal is the **downstream formula being empty**, not the action cell showing
  `"Response"`. Distinguish the two before declaring anything broken.
- This applies to the skill's "read the actual cell, HTTP success is not enough" instruction: over
  the API, reading the action cell is also not enough.

**Rex follow-up:** Code + docs. Backlog #3 (DONE 2026-09-24).

---

## 2026-09-24 · `Send table data` auto-extracts every routed column as plain text.

Routed identity columns land as `formula` / `dataTypeSettings.type: "text"`. Retype before any
enrichment: company domain → `url`, personal LinkedIn → `url` (name it `LinkedIn Profile`),
resolved email → `email`. Text-typed identity columns are accepted at creation and fail later at
`Enrich Person`, LinkedIn scrapers and some email finders, and they lose UI click-through and
format validation.

Reversible, formula preserved:
```python
clay.update_column(tid, fid, {"typeSettings": {"dataTypeSettings": {"type": "url"}}})
```

A bare hostname is **not** coerced to `https://` by the url type (verified), so domain matching is
unaffected. Caught by diffing against a build known to work rather than by reasoning about it:
**check a proven table's column types before accepting Clay's auto-extraction defaults.**

Full rule: `.claude/skills/build-clay/SKILL.md`, starter-kit override #4.

**Rex follow-up:** Code + test. Backlog #4 (DONE 2026-09-24).
