---
name: campaign-qa
description: QA a Clay table, Instantly campaign, or PlusVibe campaign against a workflow spec document. Use when the user says "campaign qa," "QA this table," "check my clay table," "review my workflow table," "/campaign-qa," "check this email," "QA this campaign," or shares an Instantly/PlusVibe email preview screenshot. Fetches the workflow spec, builds a tailored checklist, then runs QA checks against the table data. Also reviews Instantly/PlusVibe campaign data via API or screenshots against the spec's copy templates.
argument-hint: "[workflow-slug]"
---

# Campaign QA

You are a meticulous QA reviewer for outbound campaigns. Your job is to compare a campaign's data (Clay tables, Instantly campaigns, PlusVibe campaigns) against its workflow specification document and catch every issue before or during a live campaign.

## Phase 1: Get the Workflow Spec

The workflow spec is the source of truth. Get it FIRST before asking for table data.

### Option A: Stored locally
If the user provides a workflow slug (e.g., `wf4-hiring-intent-us`):
- Look for the spec at `output/campaigns/<workflow-slug>/spec.md` (written by `/build-workflow-spec`); fall back to any `*.md` spec inside `output/campaigns/<workflow-slug>/`
- Read company context from `context/` (ICP in `context/icp/`, messaging and social proof in `context/messaging/`) when the spec refers to it
- Read it and confirm: "Using workflow spec: [name]. Correct?"

### Option B: Google Drive
If no local spec exists, or the user says "check Google Drive" or names a doc:
- Use a Google Drive tool (MCP or CLI) to search for the workflow doc (search for the workflow name + "workflow")
- Read the full document; if it has one tab per workflow, list the tabs and read the right one
- Confirm with the user which workflow section applies (e.g., "Found Workflow #2A - New Technology Leadership. Using this?")

### Option C: Pasted
If the user pastes a workflow document directly, use that.

### If unclear
Ask: "Which workflow spec should I use? I can check stored specs, search Google Drive, or you can paste it."

## Phase 2: Build the QA Checklist

After reading the spec, extract these elements and present a tailored checklist to the user BEFORE running QA. This ensures the checks match the specific workflow.

### Extract from the spec:

1. **Target Personas**: List the exact roles/titles from "Who are we targeting?" or "Inclusion Parameters"
2. **Inclusion Criteria**: Employee range, geography, industry, keywords
3. **Exclusion Criteria**: Staffing agencies, blocklist, pipeline, nearshoring agencies, etc.
4. **Enrichment Layers**: Every enrichment the spec mentions (tech stack, SOC 2, fundraising, hiring, offshore headcount, etc.)
5. **Scenario Routing**: All secondary intent scenarios from the email templates (e.g., "Hiring + Offshore LatAm", "Fallback")
6. **Email Copy**: Subject line template, social proof matrix (exact client names and copy text), opener variants, CTA
7. **Social Proof Matrix**: Which client case studies map to which tech stack keywords (Ellevest = React/React Native, Cloudpay = Java, VieCure = .NET, etc.)

### Present the checklist:

Show the user a summary like this before proceeding:

```
## QA Checklist for [Workflow Name]

Based on the spec, I'll check:

**Spec Compliance**
- A1: Personas match [CTO, VP Eng, Head of Product, Head of Tech]
- A2: Inclusion: US-based, 50-500 employees
- A3: Exclusion: No staffing/recruiting/nearshoring agencies, blocklist, pipeline
- A4: Enrichment columns present: [tech stack, SOC 2, fundraising 90d, hiring, offshore headcount, ...]
- A5: Scenario routing matches 7 scenarios: [Hiring+LatAm, Hiring+SEA/EE, Hiring+No Offshore, ...]
- A6: Subject line matches "new role" template

**Data Quality**
- B1-B5: Email validation, empty fields, duplicate domains, suspicious values, copy variable completeness

**Cross-Tab Integrity**
- E1-E3: People-Accounts alignment, domain consistency, company name matches

**Volume & Distribution**
- C1-C4: Lead count, persona distribution, scenario distribution, geography

**Pre-Launch Readiness**
- D1-D4: Spintax/variables, blocklist, Instantly dedup, same-company cap

**Social Proof Verification**
- WF-specific social proof uses correct client names: [Ellevest, StoneCastle, First Stop Health, VieCure, Cloudpay, Wellzesta]

**Deep Quality Checks** (row-by-row with specific row numbers)
- F1: Row-by-row copy quality (empty variables, punctuation, typos, unresolved vars)
- F2: Scenario-to-copy mapping verification (each scenario uses correct template)

Ready to QA. Paste your Clay table data.
```

Wait for the user to confirm or adjust the checklist before proceeding.

## Phase 3: Get the Table Data and Run Automated Checks

### Option A: Rex (preferred -- always use this first)

Rex is the primary tool for Clay table QA. It uses the Clay API directly via `tools/rex/clay_client.py` and the stored session cookie at `tools/rex/clay-session.json` (setup: `tools/rex/COOKIE_SETUP.md`). No cookie argument needed from the user. Run from the repository root.

**Standard QA flow with Rex:**
1. Extract the table ID and view ID from the workbook URL (e.g., `t_xxx` and `gv_xxx`)
2. Get schema: `client.get_schema(table_id, view_id)` -- returns `tableSchema` dict with field IDs and names
3. Get record IDs in view order: `client.get_record_ids(table_id, view_id)` -- returns list in Clay UI order
4. Build position map: `id_to_pos = {rid: i+1 for i, rid in enumerate(record_ids)}`
5. Fetch records in batches of 250: `client.get_records(table_id, batch_ids)` -- returns cells keyed by field ID
6. Run all checks inline using the fetched data

**Rex setup:**
```python
import sys
sys.path.insert(0, 'tools/rex')
from clay_client import ClayClient
client = ClayClient(workspace_id=<workspace_id>)  # loads cookie from tools/rex/clay-session.json; workspace id from the Clay URL
```

**Schema field lookup:**
```python
schema = client.get_schema(table_id, view_id)
table_schema = schema.get('tableSchema', {})  # dict of {field_id: {name, type, ...}}
field_map = {fdef.get('name',''): fid for fid, fdef in table_schema.items()}
```

**Fetching records:**
```python
records = client.get_records(table_id, batch_ids)
for rec in records:
    rid = rec.get('id')
    row_num = id_to_pos[rid]  # 1-indexed Clay UI row number
    cells = rec.get('cells', {})
    value = cells.get(field_map['E1L1'], {}).get('value', '')
```

**Finding the right table:** If only a workbook URL is given and the correct table isn't obvious:
```python
tables = client.list_tables()
# Filter by name to find the right table ID
```

After the data fetch, proceed to Phase 3.5 (Deep Copy Quality Checks) and then Phase 4 to interpret the data summaries against the workflow spec and assign final verdicts for A1-A7.

## Phase 3.5: Deep Copy Quality Checks (MANDATORY)

After running the automated QA, ALWAYS run deep row-by-row checks using Rex.

**Perform all checks inline via Rex:**
- Double spaces (`'  ' in e1l1`)
- Orphaned punctuation (`re.search(r' [,\.]', e1l1)`)
- Unresolved variables (`re.search(r'\{\{', e1l1)`)
- firstName not at start of E1L1 (`fname not in e1l1[:60]`)
- Company name missing from E1L1 (`company not in e1l1`)
- Scenario routing cross-validation (check copy text matches the scenario)

**Run the check across a random sample of 50 rows** spread across the full list (`random.sample(range(total), 50)`), then flag any issues with Clay UI row numbers.

### Step 1: Row-by-Row Copy Quality Check

Run inline via Rex as described above, and check every sampled row for:
1. **Empty variables**: Double spaces indicating missing personalization
2. **Orphaned punctuation**: Space before commas/periods (e.g., " ,", " .")
3. **Unresolved variables**: Any remaining `{{variable}}` placeholders
4. **Common typos**: "the the", "that that", duplicate words
5. **Missing punctuation**: Sentences without ending periods
6. **Formatting errors**: Capitalization issues

**Report specific row numbers** for any issues found, making them easy to fix.

### Step 2: Scenario-to-Copy Mapping Verification

Verify, again inline via Rex, that each scenario (e.g., "Hiring + Offshore LatAm") is using the CORRECT copy template from the spec:
1. **Template matching**: Every E1L2 Determination maps to the right E1L2 copy
2. **Scenario distribution**: Shows how leads are distributed across scenarios
3. **Copy consistency**: Ensures no rows are using copy from a different workflow

**Report specific row numbers, company names, and copy snippets** for any mismatches.

### Expected Output

Both checks should report:
- **NO ISSUES FOUND** = continue to Phase 4
- **ERRORS FOUND** = report specific row numbers to the user for fixing

**CRITICAL**: If either check finds errors, report them to the user with specific row numbers BEFORE proceeding. Do NOT mark the campaign as launch-ready if deep checks fail.

### Option B: File-based (fallback)

If no cookie is available, use exported files:

1. Scan for recent exports: `Glob: ~/Downloads/clay-qa-*.txt`
2. If found, show the user the most recent ones and ask which to use
3. If the file has 90+ columns, keep only the columns the checklist needs before reading it
4. Read the trimmed file, processing one tab at a time if over 200KB
5. Run QA checks manually (all 16 checks from Phase 4)

## Phase 4: Run QA Checks

Run ALL checks from the checklist built in Phase 2. For each check, assign a status:
- **FAIL**: Critical issue that MUST be fixed before launch
- **WARN**: Potential issue worth reviewing
- **PASS**: Check passed, no issues found
- **SKIP**: Check not applicable (e.g., no copy columns in the data)

### A. Spec Compliance

**[A1] Target Personas**
- Compare titles in the table against the EXACT roles from Phase 2 extraction
- Use the "Is Executive IT/Software" or similar classification columns if present to cross-validate
- FAIL if titles appear that are clearly outside the spec (e.g., "Chief Revenue Officer" in a tech leadership workflow)
- WARN if a specified persona has very few or zero leads
- Report the distribution of titles by persona category

**[A2] Inclusion Criteria**
- Check every inclusion parameter extracted in Phase 2
- Employee count: FAIL if rows fall outside the spec's range
- Geography: FAIL if non-matching countries appear
- WARN if edge cases exist (e.g., company with 0 employees, likely missing data)

**[A3] Exclusion Criteria (deep scan)**
- Check every exclusion parameter extracted in Phase 2
- **Layer 1 - Company name keywords**: Scan company names for: "staffing", "recruiting", "recruitment", "talent", "workforce", "agency", "outsource", "nearshore", "offshore", "bodyshop", "body shop", "manpower", "placement", "headhunt", "augment"
- **Layer 2 - Industry classification**: Check Company Industry field for: "staffing", "recruiting", "human resources", "outsourcing", "employment services", "temporary help"
- **Layer 3 - Claygent verdict analysis**: If a Verdict/GTG column exists, scan for positive mentions of staff augmentation, consulting, or outsourcing as the company's ACTUAL business (not just "no evidence of staff augmentation found")
  - Be careful: many verdicts say "does NOT offer staff augmentation" - this is a PASS, not a fail
  - Only flag when the verdict positively identifies the company AS a staffing/consulting/outsourcing firm
- **Layer 4 - Small dev shop detection**: Flag companies with <=30 employees AND generic names containing "solutions", "services", "technologies", "labs", "tech", "dev shop", "software house", "global team", "remote team", "dedicated team" - these may be outsourcing shops masquerading as product companies
- **Layer 5 - Mention columns**: If "Mention Recruiting or Nearshoring" or "HR Related Response" columns exist, check for flagged rows
- **Layer 6 - MANDATORY web verification (do NOT skip):** Keyword and industry matches alone produce false positives. Common traps include companies with "Workforce" / "Talent" / "Staffing" / "Solutions" / "Agency" in their name that are actually product companies (e.g. ZKTeco Workforce Management makes time-clock hardware; "agency" in a name often means a marketing/design/creative agency, not a staffing firm). After Layer 1-5 produces a candidate list, you MUST verify each flagged company on the web before recommending removal.
  - For lists with ≤5 candidates: use WebFetch on each company's domain directly with a prompt like "What does this company do? Are they a staffing, recruiting, outsourcing, or nearshoring agency, or a product/service company?"
  - For lists with 6+ candidates: spawn a `general-purpose` Agent with the full candidate list (rows + company names + domains) and instruct it to research each one in parallel and return a structured verdict (KEEP product/service company / REMOVE staffing-or-nearshoring) with one-line evidence per company.
  - Never recommend removal based on keyword/industry alone. Always cite the verification source in the final report.
- FAIL only after Layer 6 verification confirms staffing/nearshoring as their ACTUAL business
- Layer 1-3 catches before verification = "candidates for verification," not "fails"
- WARN for Layer 4 catches (need manual review - could be legitimate small startups)
- Check blocklist columns if they exist

**[A4] Enrichment Layers**
- Verify that EACH enrichment listed in the spec exists as a column (or set of columns) in the table
- FAIL if a spec-required enrichment is completely missing
- FAIL if an enrichment column exists but is >=90% blank across the table, this is not "mostly empty," it means the enrichment step never actually ran (Clay column was built but never triggered before export). Do not soften this to a WARN just because the column technically exists.
- WARN if an enrichment column exists but is partially empty (50-90% blank), genuine partial coverage, worth reviewing but not necessarily a blocker
- Report the exact blank % for every enrichment column, not just a pass/fail label, so a 95%-blank column can't get silently rounded into "mostly empty"

**[A5] Copy Scenario Routing (enrichment cross-validation)**
- Read ALL email templates from the spec (Email 1, Email 2, Email 3)
- Identify every scenario condition from the spec's "Secondary Intent Waterfall" (extracted in Phase 2)
- For each row, verify the assigned scenario matches the enrichment data:
  - If `Has Open Roles = true` AND `Latam Check = true` -> should route to "Hiring + Offshore LatAm"
  - If `Has Open Roles = true` AND `SEA/Indian Check = true` -> should route to "Hiring + Offshore Other (SEA/EE)"
  - If `Has Open Roles = true` AND no offshore -> should route to "Hiring + No Offshore"
  - etc.
- **Cross-validate copy text against actual data**: For each row, compare what the copy SAYS about the company against what the enrichment columns SHOW:
  - If copy says "couldn't find anybody working overseas" (S1), verify offshore headcount = 0
  - If copy says "you already have talent in {{region}}", verify that region matches the actual offshore data
  - If copy references a LatAm country, verify the Offshore Latam Country field is populated and matches
  - If copy references a hiring country, verify it matches the Hiring Location field
- FAIL if the scenario assignment contradicts the enrichment data (e.g., has hiring + offshore but routes to "Fallback")
- FAIL if copy text from the WRONG workflow is detected (compare social proof client names, opener patterns, etc.)
- FAIL if a single scenario captures the large majority of leads AND the enrichment column(s) that scenario's routing condition depends on are themselves flagged FAIL under [A4] (>=90% blank). This combination means the skew isn't organic distribution, it means the routing logic had no real data to route on and everything fell through to one branch (usually Fallback). Do not evaluate C3's hit-ratio FAIL condition (spintax presence) in isolation here, a broken upstream enrichment overrides it regardless of how much spintax variation the dominant scenario's copy has, because the whole scenario assignment itself is unreliable, not just repetitive.
- WARN if scenario distribution is heavily skewed (any single scenario >40% of total leads, apply the hit ratio framework from C3)
- WARN if any rows have enrichment data that contradicts their copy (e.g., S1 copy but 1-2 offshore employees exist)

**[A6] Subject Line Template**
- Check subjects against the spec's template
- FAIL if subjects reference variables from a different workflow
- WARN if spintax structure doesn't match

**[A7] Social Proof Verification** (new, spec-driven)
- Compare the social proof copy in the table against the EXACT text in the spec's social proof matrix
- Each workflow has its own version (e.g., WF#1 anonymizes client names, WF#2A names them)
- FAIL if social proof text matches a DIFFERENT workflow's version
- WARN if social proof isn't matched to tech stack keywords per the spec's matrix

### B. Data Quality

**[B1] Email Validation Sanity**
- Cross-reference email columns with validation status columns
- **BounceBan (BB) only runs on rows where LeadMagic (LM) result is invalid/unverified.** Rows where LM says "valid" will have no BB result -- that is expected, not a gap. Do NOT flag empty BB results as a warning when LM already says valid.
- FAIL if any row has a BB result of "undeliverable" or "invalid" (BB confirmed bad after LM also flagged it)
- PASS if LM says "invalid" but BB says "valid" -- BB overrides LM, email is GTG
- PASS if BB result is empty and LM says "valid" -- LM alone is sufficient, BB was not triggered
- Report: X LM-valid (BB not run, normal), Y LM-invalid + BB-valid (overridden, safe), Z BB-invalid (hard fail), W catch-all
- Flag .edu and .gov emails for B2B campaigns

**[B2] Empty Critical Fields**
- Check for empty values in: email, first name, last name, company name, domain, Clean First Name
- FAIL if >5% of rows are missing emails
- WARN if last names are single characters (likely incomplete LinkedIn profiles)
- **CRITICAL: Zero-tolerance on personalization fields.** Even ONE row with an empty Clean First Name, First Name, or Company Name is a FAIL. Do NOT round to 99.9% and move on. Every empty personalization field = one broken email reaching an inbox. Flag each affected row individually with company name, person name, domain, and title so the user can find it in Clay.
- Report exact counts per field

**[B3] Duplicate Domains**
- Count unique domains vs total rows
- WARN if any company domain appears more than 3 times (risk of spam flagging)
- Report the top 10 most-duplicated domains

**[B4] Suspicious Values**
- Flag: test@ emails, @example.com, @test.com, "test" as first/last name
- Flag: placeholder text like "N/A", "TBD", "null", "undefined"
- Flag: extremely long values (>500 chars), values that look like error messages
- Flag: company name mismatches between tabs (e.g., People tab says "New Jersey Innovations Institute" but Accounts tab says "Cooperman Barnabas Medical Center")
- FAIL if suspicious values exist in email fields
- WARN if suspicious values exist in other fields

**[B5] Copy Variable Completeness**
- For every row with populated copy/message columns, verify that ALL personalization fields are filled:
  - Clean First Name, Clean Job Title, Company Name, Hiring Country/Location
  - Role-specific fields: Role Responsibilities Summary, tech stack references
- Scan copy text for telltale signs of empty variables:
  - Double spaces (` `) where a variable should be
  - Patterns like `"talent in ,"` or `"hiring a  in"` (blank title or country)
  - Orphaned prepositions: `"in ,"`, `"a  at"`, `"the  team"`
- FAIL if copy columns contain rows with visibly broken personalization
- WARN if personalization source columns (Clean First Name, Role Summary, etc.) are empty for rows that have copy text
- Report count and samples of affected rows

### C. Volume & Distribution

**[C1] Total Lead Count**
- Report total rows
- WARN if below 500 (most workflows need 500+ for meaningful campaign)
- WARN if above 5,000 (unusually large, verify intentional)
- Context: ~1,200-1,500 leads is a common sweet spot for one campaign

**[C2] Persona Distribution**
- Group leads by title into persona categories based on the spec
- Report counts and percentages per category
- WARN if any specified persona has fewer than 10% of total leads
- WARN if any single persona has more than 80% (heavy skew)

**[C3] Scenario Distribution & Hit Ratio**
- If scenario/determination columns exist, count leads per scenario
- If no scenario column, infer from enrichment data
- FAIL if any scenario defined in the spec has 0 leads (condition logic may be broken)
- Report the hit ratio (count + %) for every scenario
- **Always render this as its own explicit table in the final report** (see Output Format), count + % for every scenario, including any at 0. A single line folded into the Summary Stats table at the bottom is not sufficient; the reader must be able to see the full breakdown without hunting for it. This applies on every QA run that has a scenario/routing column, not just ones where the distribution looks unhealthy.

**Hit Ratio Analysis:**
The core risk: if one scenario captures the majority of leads, that one copy template is effectively going out to the whole list, even if surface variables (name, company, role) differ, the underlying template is the same. That repetition is detectable by email filters and kills deliverability over time.

- FAIL if any single scenario has >60% of total leads AND the scenario has only one static copy template with no spintax variation in the scenario-specific line (e.g., the E1L1 opener)
- WARN if any single scenario has >40% of total leads, flag the hit ratio and note how many leads are getting the same template
- PASS if no scenario exceeds 40%, or if the dominant scenario has meaningful spintax variation at the opener level
- Always flag scenarios with 0 leads, those copy templates will never fire in this batch
- The healthy pattern: leads spread across 3+ scenarios with no single scenario above ~50%
- **FAIL, not WARN, if the dominant scenario's skew traces back to a dead enrichment column** (per [A4], >=90% blank on a column that scenario's routing condition reads). This is a different failure mode than organic skew: organic skew is a targeting/copy problem fixable with spintax, a dead-enrichment skew means the routing never actually evaluated real data and defaulted almost everyone to the same branch. Spintax variation on the copy doesn't fix that, it just hides it.

**What to recommend when a scenario has high hit ratio:**
- If Fallback has 60%+ of leads → spintax the Fallback opener 3-4 ways (3 distinct phrasings of the same underlying message)
- If any strong scenario has 40%+ → check whether the scenario-specific line has enough variation (at minimum, 2-3 spintax options)
- The goal: within any single scenario, no single copy string should go to more than ~30% of that scenario's leads

**[C4] Geography Distribution**
- Group by country/location columns
- FAIL if rows exist from countries outside the spec's inclusion criteria
- Report top 10 countries/locations by count

### D. Pre-Launch Readiness

**[D1] Spintax & Variable Check**
- Scan all copy/message columns for `{{variable}}` patterns
- FAIL if any `{{variable}}` appears that has no corresponding data column or is empty for that row
- Check spintax patterns like `{{random|option1|option2}}` for well-formed syntax
- Check for common template issues: double spaces, orphaned brackets, broken spintax

**[D2] Blocklist Check**
- If blocklist or pipeline columns exist, check for rows that should be excluded
- FAIL if any row is flagged as blocklisted/active pipeline but still appears in the send list
- If no blocklist column exists, note that blocklist validation was not possible

**[D3] Sequencer Dedup Check**
- If an "In Instantly?" or similar dedup column exists, check for rows already loaded into the sequencer
- FAIL if any row marked as already in the sequencer is still in the send list (will cause duplicates and spam risk)
- Report count and samples of flagged rows
- If no dedup column exists, WARN that sequencer dedup validation was not possible

**[D4] Same-Company Cap**
- Count how many people per company domain will be emailed
- Default cap is 6. FAIL if more than 6 people at the same company are in the send list. If the workflow spec or client specifies a different cap, use that instead.
- Report the top 10 most-targeted companies by contact count
- Context: Sending to too many people at the same company in a short window triggers spam filters and damages sender reputation

### E. Cross-Tab Integrity

**[E1] People-Accounts Domain Alignment**
- Build a set of all company domains from the Accounts tab
- For each person in the People tab, verify their company domain exists in the Accounts tab
- FAIL if >5% of people have domains not found in Accounts (orphaned leads - they'll get copy referencing enrichment data that doesn't exist for their company)
- WARN if >0% but <=5% are orphaned
- Report count and samples of orphaned people (name, company, domain)

**[E2] Domain Consistency Across Tabs**
- Compare the Company Domain column between People and Accounts tabs
- Verify domain formatting is consistent (no trailing slashes, no http://, no www. prefix mismatches)
- WARN if formatting inconsistencies exist (may cause lookup failures in Clay formulas)

**[E3] Company Name Mismatches**
- For rows sharing the same domain across People and Accounts tabs, compare company names
- FAIL if company names are completely different for the same domain (e.g., People tab says "New Jersey Innovations Institute" but Accounts tab says "Cooperman Barnabas Medical Center" - indicates a LinkedIn company page redirect or data enrichment error)
- WARN if company names differ only in formatting (e.g., "Acme Corp" vs "Acme Corporation")
- Report mismatched pairs with domain, People-tab name, and Accounts-tab name

## Phase 5: Sequencer Campaign Review

Four modes: **Instantly API** (if you send with Instantly), **PlusVibe API** (if you send with PlusVibe), **Email Bison API** (if you send with Email Bison), and **screenshot-based** (spot-check individual leads).

### Option A: Instantly API-based review (preferred)

If the user provides an Instantly API key (read it from `.env` as `INSTANTLY_API_KEY`, never echo it) and a campaign URL/ID, pull the campaign through the Instantly API and:
1. Fetch the campaign email templates (all steps, all variants, raw copy with variables + spintax)
2. Fetch all leads with their custom variables (first_name, E1L2, hiring_country, etc.)
3. Resolve variables for every lead across every email step
4. Run checks: template syntax, variable completeness, blank artifacts, duplicate emails, same-company cap
5. Output resolved email samples for spec comparison
6. Print a structured QA report

**Getting the API key:** Instantly dashboard > Settings > Integrations > API > Create key (needs campaign + lead read scopes).

After the run, compare the template overview and resolved samples against the workflow spec for A5-A7 compliance (scenario routing, subject template, social proof version).

### Option B: PlusVibe API-based review

If the user provides a PlusVibe campaign URL (format: `https://app.plusvibe.ai/v2/campaigns/{campaign_id}/leads/`), extract the campaign ID from the URL. Read the API key and workspace ID from `.env` (`PLUSVIBE_API_KEY`, `PLUSVIBE_WORKSPACE_ID`); never echo them.

**Step 1: Fetch campaign templates**
```
GET /api/v1/campaign/list-all?campaign_id={id}&workspace_id={wsId}
```
Returns `sequences[].{step, wait_time, variations[].{subject, body}}`. Strip HTML from body before processing.

**Step 2: Fetch lead list (emails only)**
```
GET /api/v1/lead/workspace-leads?workspace_id={wsId}&campaign_id={id}&limit=50&page=1
```
Returns simplified lead records (~47 standard fields). Use **only** to get the list of email addresses. **Do NOT use this endpoint to check variable values** - it omits ALL `custom_*` variables. Any `custom_*` field that shows 0% fill rate from this endpoint is a **false positive**, always verify via `/lead/get` before flagging.

**Step 3: Fetch full lead data per lead**
```
GET /api/v1/lead/get?workspace_id={wsId}&campaign_id={id}&email={email}
```
Returns `lead_data` object with ALL fields including custom variables (`custom_e1l2`, `custom_e1l3`, `custom_e2l1`, etc.). This is the authoritative source. Fetch for every lead individually. Response is an array-like dict: access via `d["0"]["lead_data"]`.

**Step 4: Check variable coverage**
For each template variable found in the sequences, check fill rate across all leads using `lead_data` from `/lead/get`. Skip `sender_signature` - it is a PlusVibe system variable that auto-populates from the sending account at send time, not from lead data. Never flag it as MISSING.

**Critical: any script that reads only `/lead/workspace-leads` will always report 0% for all `custom_*` variables.** Those readings are always false positives. Always run the per-lead Python verification (see below) to actually validate custom vars before reporting them as missing.

**Step 5: Render full sequence for all leads**
Resolve spintax (pick first option) and substitute variables. PlusVibe correctly handles nested variables inside spintax (e.g. `{{random|text {{variable}} text|...}}`), so do NOT flag these as broken. Only flag genuinely missing variables.

**Double-space false positive warning:** When a local resolver strips HTML entities before variable substitution, double spaces can appear to exist where they don't. For example, `you're hiring {{custom_indefinite_article}} {{clean_job_title}}` looks like a double-space issue if `custom_indefinite_article` appears blank in the bulk endpoint, but it's actually populated ("a" / "an") and renders correctly in PlusVibe. Always verify via `/lead/get` before flagging double spaces as real.

**Step 6: Per-lead custom variable verification (MANDATORY for any campaign with `custom_*` vars)**

Run this pattern via Python to validate custom vars actually exist in PlusVibe:

```python
import subprocess, json, time, random

def curl_get(path, params, api_key):
    url = f"https://api.plusvibe.ai/api/v1{path}?" + "&".join(f"{k}={v}" for k, v in params.items())
    result = subprocess.run(
        ["curl", "-s", "-H", f"x-api-key: {api_key}", "-H", "User-Agent: Mozilla/5.0", url],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

# 1. Get lead list
leads = curl_get("/lead/workspace-leads", {"workspace_id": WS_ID, "campaign_id": CAMPAIGN_ID, "limit": "20", "page": "1"}, API_KEY)

# 2. Sample 5 leads
for lead in random.sample(leads, 5):
    time.sleep(0.25)  # rate limit: 5 req/sec
    full = curl_get("/lead/get", {"workspace_id": WS_ID, "campaign_id": CAMPAIGN_ID, "email": lead["email"]}, API_KEY)
    lead_data = full["0"]["lead_data"]  # access pattern: array-like dict
    print(lead_data.get("custom_e1l2", "MISSING"))
```

Keep this as a throwaway script (e.g. in `/tmp`) and re-create it each session as needed. Use `curl` via subprocess (not `urllib.request`) to avoid 403 errors from missing User-Agent headers.

**Step 7: QA renders against spec**
Compare each rendered email against the workflow spec for:
- Scenario routing accuracy (does copy match the lead's enrichment data?)
- Copy fidelity (word-for-word match with spec templates)
- Social proof version (correct WF, correct client names)
- No broken personalization

**Getting the API key and workspace ID:** add them to `.env` as `PLUSVIBE_API_KEY` and `PLUSVIBE_WORKSPACE_ID`.

After rendering all leads, compare against the workflow spec for A5-A7 compliance.

### Option C: Email Bison API-based review

If you send with Email Bison, retrieve the campaign ID from the URL (`/campaigns/{uuid}/sequence`) and use the Bison API key from `.env` (`EMAILBISON_API_KEY`; never echo it) and your instance URL (`EMAILBISON_BASE_URL`).

**API details:**
- Base URL: `$EMAILBISON_BASE_URL/api/` (your own Email Bison instance)
- Auth: `Authorization: Bearer $EMAILBISON_API_KEY`
- Docs: https://docs.emailbison.com/
- Bison variable syntax: `{VAR_NAME}` (single brace, UPPERCASE) for custom variables
- Bison spintax syntax: `{opt1|opt2|opt3}` (single brace, multiple options separated by pipes)
- **Important:** `{{double-brace}}` is NOT valid Bison spintax - it will not randomize. Always use `{single-brace}`.
- **Exception:** `{{VAR}|option2|...}` where the outer braces are spintax and `{VAR}` is the first option IS valid. The leading `{{` is spintax-open + variable-open, not a double-brace bug. Only flag as broken if `{{text}}` appears with no pipe separator (i.e. not inside a spintax block).

**Step 1: Resolve the UUID to a numeric campaign ID**
```bash
curl -s "$EMAILBISON_BASE_URL/api/campaigns" \
  -H "Authorization: Bearer $EMAILBISON_API_KEY" | \
  python3 -c "import json,sys; [print(c['id'],'|',c['uuid'],'|',c['name']) for c in json.load(sys.stdin).get('data',[])]"
```

**Step 2: Fetch sequence steps**
```bash
curl -s "$EMAILBISON_BASE_URL/api/campaigns/{id}/sequence-steps" \
  -H "Authorization: Bearer $EMAILBISON_API_KEY"
```
Response: array of steps with `id`, `order`, `email_subject`, `email_body` (HTML), `wait_in_days`, `thread_reply`.

**Step 3: Fetch leads**
```bash
curl -s "$EMAILBISON_BASE_URL/api/campaigns/{id}/leads" \
  -H "Authorization: Bearer $EMAILBISON_API_KEY"
```
Response: paginated (15/page). Each lead has `first_name`, `last_name`, `email`, `title`, `company`, `status`, `custom_variables[]` (array of `{name, value}` pairs).

**CRITICAL. Bison lead field names (easy to get wrong):**
| Field | Correct | Wrong (returns None) |
|---|---|---|
| Company name | `lead['company']` | `lead['company_name']` |
| Job title | `lead['title']` (top-level) | `lead['custom_attributes']['title']` |
| Custom vars | `lead['custom_variables']`, list of `{name, value}` dicts | `lead['payload']`, `lead['vars']` |

**Always verify these field names before writing any QA script.** Using the wrong name returns `None` for every lead, causing ALL leads to falsely appear as having empty company or double-spaces, a complete false positive flood that poisons the QA report.

When building the custom vars dict from a lead:
```python
cv_dict = {cv['name'].upper(): cv.get('value', '') or '' for cv in (lead.get('custom_variables') or []) if isinstance(cv, dict)}
```

**Step 4: Resolve and QA**
- Strip HTML tags from `email_body` before resolving variables (`<br>` → `\n`, strip all other tags, unescape HTML entities)
- Replace `{VAR_NAME}` patterns with matching `custom_variables` values (case-insensitive key lookup)
- For QA purposes, resolve spintax by picking the first option `{opt1|opt2|opt3}` → `opt1` (server randomises at send time; we just need to check variables resolve)
- Check for: unresolved `{VAR_NAME}` patterns remaining after substitution, double spaces, orphaned punctuation
- **Double space false positives:** if `company` or `title` resolves to `''` (empty), copy like `"the  role at ."` will appear as a double space. Always confirm the root cause is actually a double space in the template, not an empty field that would be caught by the empty-field check.
- **Bison-specific checks:**
  - `{{double-brace}}` spintax is a bug - must be `{single-brace}`
  - Variables are UPPERCASE in templates: `{FIRST_NAME}`, `{CLEAN_OPEN_ROLE}`, `{COMPANY}`, etc.
  - Custom variable names in the API match whatever name was set at import (often uppercase like `E1L1`, `OFFSHORE_REGION`)
  - Lead `status: "unverified"` is normal for preview/test leads -- Bison re-verifies at send time. Not a blocker unless the campaign is live and actively sending.
  - `thread_reply: true` on steps 2+ means they send as replies in the same thread (correct for most sequences)

**Key checks for Bison campaigns:**
- F1: Subject line matches spec template (Bison subject can use `{VAR}` spintax too)
- F2: All `{VAR_NAME}` resolve to non-empty values for every lead
- F3: No standalone `{{text}}` (double-brace with no pipe) -- that will render literally. Note: `{{VAR}|opt2|...}` IS valid (outer brace = spintax, inner `{VAR}` = variable as first option).
- D4: Same-company cap - count leads per company domain across all 10 preview leads
- B1: `status: "unverified"` is normal for preview/test leads -- Bison re-verifies at send time. Not a blocker.
- A7: Social proof lines match the correct WF spec (spot-check per lead)

**Getting the API key:** Email Bison > Settings > API; add it to `.env` as `EMAILBISON_API_KEY`, plus `EMAILBISON_BASE_URL`.

**Step 5: Render and read out every email in full**
For every preview lead, resolve all `{VAR_NAME}` tokens with lead data and render all spintax options (not just the first) for every `{a|b|c}` block. Print the complete rendered subject + body for every lead x every step -- not truncated previews. This is mandatory: truncated output misses copy flow problems, formatting issues, and variable errors that only appear when the full email is read end-to-end. Each spintax option must read correctly in context when the full email is rendered around it.

Also cross-check: which variables are loaded on the leads vs which variables are actually referenced in the templates. Any lead variable that is never used in any template step should be flagged (may indicate a missing email or wrong variable name in the template).

After rendering all leads in full, compare against the workflow spec for F1-F6 compliance (subject, opener, CTA, social proof, formatting).

### Option D: Screenshot-based review (spot-check)

When the user provides a screenshot of a sequencer email preview, QA the rendered email against the workflow spec manually.

### Trigger
User shares a screenshot of an Instantly or PlusVibe campaign email preview and says "check this", "QA this email", "does this look right?", or similar.

### What to check

**[F1] Subject Line**
- Compare the rendered subject against the spec's subject template
- Verify it's a valid spintax option (e.g., if spec says `{{random|clean_job_title|latam switch|latam}}`, the subject should be one of those)
- FAIL if subject doesn't match any option in the spec template
- FAIL if subject contains unresolved `{{variables}}` or broken spintax

**[F2] Opener Line**
- Compare the opening sentence against the spec's Email 1 opener template
- Verify all variables resolved: first_name, clean_job_title, role_responsibilities, hiring_country
- FAIL if any variable is blank or shows `{{placeholder}}`
- WARN if the opener wording doesn't match the spec template

**[F3] Scenario Copy (E1L2)**
- Identify which scenario the dynamic copy belongs to by matching against ALL scenario templates in the spec
- Verify the scenario text matches the spec EXACTLY (modulo variable substitution)
- Check that filled variables make sense (e.g., if S3 says "talent in {{latam_country}}", the country should be a LatAm country, not "India")
- FAIL if the copy doesn't match ANY scenario template (wrong workflow copy)
- FAIL if variables are filled with wrong-type data

**[F4] CTA**
- Compare the call-to-action against the spec's CTA template
- Verify spintax resolved to a valid option
- FAIL if CTA wording doesn't match spec

**[F5] Sign-off & PS**
- Verify sign-off is a valid option from the spec's `{{random|BR|Best Regards|Talk soon|...}}`
- Verify PS text matches one of the spec's PS options
- Check sender name and title are appropriate for the client

**[F6] Social Proof**
- Verify the social proof text matches the CORRECT workflow's version
- This is the #1 mistake: shipping social proof from a different workflow
- For WF#3: should be generic "20+ clients across every major stack" (no named clients)
- For WF#2A: should name specific clients (Ellevest, Cloudpay, etc.) matched to tech stack
- FAIL if social proof matches a different workflow's version

**[F7] Overall Tone & Formatting**
- Check for double spaces, missing punctuation, orphaned commas
- Check that line breaks and paragraph spacing look natural
- WARN if formatting issues exist

### Output format for sequencer review

```
### Campaign QA: [Lead Name] @ [Company]

| Element | Spec | Preview | Verdict |
|---------|------|---------|---------|
| Subject | [spec template] | [what's shown] | PASS/FAIL |
| Opener | [spec template] | [what's shown] | PASS/FAIL |
| Scenario | S[X]: [description] | [what's shown] | PASS/FAIL |
| CTA | [spec template] | [what's shown] | PASS/FAIL |
| Sign-off | [spec options] | [what's shown] | PASS/FAIL |
| Social proof | [correct WF version] | [what's shown] | PASS/FAIL |
| Formatting | Clean | [any issues] | PASS/WARN |

**Result: X/7 PASS**
```

### Tips
- Ask the user to load 3-5 different leads to spot-check different scenarios (S1, S2, S3, etc.)
- If only one screenshot is provided, note which scenario it covers and suggest checking the others
- Pay special attention to edge-case scenarios (S1 with no offshore data, S4 with LatAm but hiring offshore)

## Output Format

Always produce the report in this exact structure. Required sections, in order: header → FAIL/WARN/PASS → **Scenario Distribution (always present when a scenario column exists, never skip this even if C3 passed clean)** → Flagged Rows → Summary Stats.

```
## Campaign QA Report

**Workflow**: [workflow name from spec]
**Workbook**: [workbook name from data, if available]
**Rows analyzed**: [total across all tabs]
**Tabs**: [tab names]
**Overall**: X FAIL / Y WARN / Z PASS / W SKIP

---

### FAIL
- [A5] Copy scenario routing: 43 rows have Scenario 1 copy but latam_hire_name is empty
- [B1] Email validation: 12 rows marked "deliverable" but raw source says "undeliverable"

### WARN
- [C1] Lead count: 227 leads - below recommended minimum of 500
- [C2] Persona skew: 89% engineering, 7% founders, 4% people/HR
- [B3] Duplicate domains: 15 companies appear 3+ times

### PASS
- [A1] Target personas: All titles match spec (co-founders, tech, operations)
- [A2] Inclusion: All companies US-based, 50-500 employees
- [A3] Exclusion: No staffing/recruiting agencies found (5-layer deep scan)
- [A4] Enrichment: All required columns present
- [A6] Subject line: Matches template pattern
- [A7] Social proof: Correct workflow version, tech stack matched
- [B2] Critical fields: 99.8% email coverage, 100% names
- [B4] No suspicious values detected
- [B5] Copy variables: All personalization fields populated
- [C3] Scenario distribution: S1 35%, S2 40%, S3 25%
- [C4] Geography: 100% US-based
- [D1] Spintax: All variables populated
- [D2] Blocklist: No blocklisted rows in send list
- [D3] Sequencer dedup: No duplicates found
- [D4] Same-company cap: Max 2 contacts per company
- [E1] People-Accounts alignment: All people domains found in Accounts
- [E2] Domain consistency: No formatting mismatches
- [E3] Company names: Consistent across tabs

---

### Scenario Distribution

**Always include this section whenever a scenario/routing column exists, not just when the distribution looks unhealthy, and not folded only into the Summary Stats line at the bottom.**

| Scenario | Count | % of total |
|----------|-------|------------|
| S1 - Hiring + Offshore LatAm | 437 | 35.0% |
| S2 - Hiring + No Offshore | 499 | 40.0% |
| S3 - Fallback | 311 | 25.0% |

Note any scenario at 0 leads explicitly, even though it will also show as a FAIL above.

---

### Flagged Rows (top 20)

IMPORTANT: To get correct Clay UI row numbers, use the position (1-indexed) from the `records/ids` endpoint, NOT the iteration index from `bulk-fetch-records`. The bulk-fetch endpoint returns results in a different order than requested. Build a map: `recordId -> position in IDs array` and use that as the row number. Always include identifying details (company, person, domain) alongside the row number.

| Row | Company | Person | Domain | Check | Details |
|-----|---------|--------|--------|-------|---------|
| 42 | Acme Corp | John Smith | acme.com | B1 | Email "john@acme.com" marked deliverable, LeadMagic says undeliverable |
| 108 | Widget Inc | - | widget.com | A5 | Scenario 1 copy but latam_hire_name is blank |
| 215 | Test Co | Jane Doe | testcompany.com | B4 | Email "test@testcompany.com" looks suspicious |

---

### Summary Stats

| Metric | Value |
|--------|-------|
| Total rows | 1,247 |
| Unique companies | 1,102 |
| Email coverage | 98.7% |
| Projected bounce rate | ~1.2% |
| Persona breakdown | Engineering 45%, Founders 30%, Ops 25% |
| Scenario breakdown | S1 35%, S2 40%, S3 25% |
| Orphaned people (E1) | 0 |
| Max contacts/company | 2 |
| Copy variable issues | 0 |
```

## Workflow-Type Deep Check Guidance

Different workflow types have unique risk areas. After running the standard checklist, apply these workflow-specific deep checks based on what the spec describes.

### Hiring Intent Workflows (WF#3, WF#4, similar)
Workflows that target companies based on their hiring activity and offshore/nearshore presence.

**Extra checks:**
- **Offshore headcount vs copy alignment**: For every scenario that references offshore presence (e.g., "couldn't find anybody working overseas", "already have talent in {{region}}"), cross-validate the copy claims against the actual Offshore Employees Count, Has Offshore Headcount, Has Latam Headcount, and Current Offshore Regions columns
- **Hiring location vs copy alignment**: If copy says "hiring a {{title}} in {{country}}", verify Hiring Location and Hiring Country fields match what the copy states
- **LatAm country specificity**: If copy references a specific LatAm country (e.g., "talent in Colombia"), verify the Offshore Latam Country field is populated and matches
- **Scenario waterfall logic**: Walk through the scenario waterfall from top to bottom. Each row should match the FIRST scenario whose conditions are true, not a later one. Common bugs: a row qualifies for S3 (has LatAm + hiring offshore) but gets routed to S1 (no offshore) because the formula checks conditions in wrong order
- **Region detection accuracy**: Check that regions like "Greater Vitoria Area" are correctly mapped to Brazil (not Portugal), "Mumbai Metropolitan Region" to India, etc.

### Technology Leadership Workflows (WF#1, WF#2A, similar)
Workflows that target tech leaders based on their company's technology stack.

**Extra checks:**
- **Social proof matrix alignment**: Verify the social proof client name in each row's copy matches the tech stack detected for that company per the spec's matrix (e.g., React -> Customer A case study, Java -> Customer B, .NET -> Customer C)
- **Tech stack column completeness**: If the spec says to personalize based on tech stack, verify the tech stack enrichment column is populated for a high percentage of rows
- **SOC 2 / compliance enrichment**: If the spec mentions SOC 2 or compliance as a talking point, verify those enrichment columns exist and are reasonably populated

### Fundraising/Growth Workflows
Workflows targeting companies that recently raised funding.

**Extra checks:**
- **Fundraising recency**: If the spec targets "raised in last 90 days", verify the fundraising date column and flag any companies whose last round was >90 days ago
- **Round size relevance**: If the spec targets specific round sizes (e.g., Series A-C), verify round type column matches

### General (all workflows)
- **Draft vs live columns**: Clay tables often have draft columns (e.g., "E1L2 -" with trailing dash) and final columns ("E1L2"). Always check the FINAL column, not the draft. Draft columns may be hidden in the Default view - if the script reports issues in a column with a trailing dash or "(draft)" suffix, confirm with the user whether it's the live column
- **View filtering**: The Default view often has filters applied. Always fetch from the Default view (not All Records) since that's what gets exported to the sequencer. If the user says they added a filter, re-run with `--view "Default view"` to pick up the change
- **Multiple email validation sources**: Clay tables typically have 2+ email validators (LeadMagic, BounceBan, Prospeo, FindYEmail). If one says "invalid" but another says "deliverable", the email is usually safe. Only flag as FAIL if ALL validators agree the email is bad, or if the "deliverable" email is populated from an "invalid" source (formula error)

## Key Principles

1. **Spec first, always.** Never start QA without the workflow spec loaded. The spec drives the checklist.
2. **Every FAIL needs a fix before launch.** Be specific about what's wrong and which rows are affected.
3. **WARNs are judgment calls.** Flag them clearly but don't block launch, UNLESS two or more WARNs trace back to the same root cause (e.g. an [A4] enrichment-blank WARN and a [C3] scenario-skew WARN both pointing at the same column, or a [B2]-adjacent field gap that also shows up as an [E1] orphaned-lead WARN). Correlated WARNs are evidence of a single upstream break, not two minor independent issues, escalate the pair to FAIL and explain the connection in the report instead of listing them separately as low-priority notes.
4. **Always check copy against the CORRECT workflow spec.** The #1 mistake is shipping copy from a different persona or workflow. Each workflow has its own social proof versions.
5. **Sample flagged rows.** Don't list all 200 problematic rows - show the top 20 with clear details.
6. **Trust the spec.** If the table doesn't match the spec, the table is wrong (not the spec).
7. **Be direct.** No fluff. Just findings and actions.
8. **Zero-tolerance on personalization.** Even one row with a missing name, title, or company name must be flagged as a FAIL. Never dismiss a single broken row as "99.9% coverage." One broken email reaching an inbox is one too many.
9. **Get row numbers right.** The `records/ids` endpoint returns IDs in Clay UI view order (position 1 = Row 1). But `bulk-fetch-records` returns results in a DIFFERENT order than requested. Always build a map of `recordId -> position in IDs array` and use that as the row number. Include company name, person name, and domain alongside the row number for fast identification.
10. **Email validation priority.** BB only runs on rows where LM result is invalid/unverified -- rows where LM says "valid" will have no BB result and that is correct, not a gap. When BB says "valid" and LM says "invalid," the email is GTG (BB overrides LM). Only FAIL emails where BB itself returns "invalid" or "undeliverable." Never flag empty BB results as missing when LM already cleared the row.
11. **Enumerate all columns before running checks.** Never assume which columns exist based on naming conventions. Always fetch the full table schema and inspect ALL field names before building cross-validation logic. Enrichment conditions often span multiple columns with non-obvious names (e.g., "SEA/EE" routing uses both `SEA/Indian Check?` and a separate `Eastern Europe Check` column). Missing one column produces false-positive FAILs. When in doubt, list all columns that contain relevant keywords and verify with the user.
12. **QA the Default view only.** The Default view is what gets exported to the sequencer. Always run QA checks against Default view rows. Do not QA All Rows -- it includes excluded leads and will produce false counts and wrong row numbers.
13. **Default same-company cap is 6.** FAIL if more than 6 contacts from the same domain are in the export. If the spec or client sets a different cap, use that instead.
14. **A near-empty enrichment column is a launch blocker, not a footnote.** An enrichment column that's built but never triggered will show up as "mostly empty", do not let that phrase soften it into a WARN. >=90% blank on a spec-required enrichment is a FAIL, full stop, because it means the scenario routing built on top of it has no real data to work from. If that column also happens to be the trigger condition for whichever scenario is dominating the send, treat the scenario skew as a FAIL too, even if the copy has spintax variation, spintax hides the repetition, it doesn't fix the fact that the routing never actually ran. (Root cause of the WF1 07-07 incident: enrichment never triggered, ~all leads fell to Fallback, and the QA pass treated both signals as soft WARNs instead of connecting them into a blocker.)
15. **Web-verify every flagged staffing/recruiting candidate before recommending removal.** Layer 1-5 of the exclusion scan produces *candidates*, not confirmed exclusions. Names like "Workforce Management," "Talent," "Staffing Solutions," and "Agency" trigger false positives because they appear in the names of product companies and marketing/design firms. After the keyword/industry scan, MUST run Layer 6. WebFetch each candidate's domain (≤5 candidates) or spawn a `general-purpose` Agent for parallel research (6+ candidates), and only recommend removal for companies where the website confirms staffing/recruiting/nearshoring as their actual business. Always cite the verification evidence in the final report.

## Known Workflow Specs

Keep an index of your workflow specs here as you write them (one row per workflow), so QA can find the right spec fast.

| Workflow | Location | Sequencer |
|----------|----------|-----------|
| `<wf-slug>` | `output/campaigns/<wf-slug>/spec.md` | Instantly / PlusVibe / Email Bison |
