# Workflow: Digital Health Provider Hiring

**Status:** STRUCTURE-APPROVED 2026-11-13 · copy pending

---

## 1. Mother Intent (Trigger) [ENGINE]

A digital health or telehealth company is actively hiring clinical providers (NPs, PAs, MDs, therapists, nurses) across two or more US states, signaling that its credentialing and licensing workload is about to exceed what manual operations can handle.

*Catalog match: "Provider workforce scaling" — a company adding clinical headcount in multiple jurisdictions simultaneously creates an immediate, quantifiable need for licensing and payer enrollment infrastructure.*

---

## 2. Inclusion / Exclusion [ICP]

### Include

**ICP box:**
- **Geography:** United States only
- **Industry:** Digital health, telehealth, virtual care, behavioral health, in-home primary care
- **Company size:** 10–500 employees
- **Provider roster:** 10–500 credentialed providers (proxied by clinical hiring volume)
- **Funding stage:** Seed through Series C (VC-backed; not bootstrap or PE-owned)
- **Growth signal:** Actively posting 3+ clinical provider roles across 2+ US states in a 60-day window

**Trigger definition:**
- Job titles include at least one of: "nurse practitioner", "NP", "physician assistant", "PA", "MD", "physician", "therapist", "psychiatrist", "LCSW", "LMFT", "clinical psychologist"
- Job locations span 2+ distinct US states in the same 60-day posting window
- Job posted within last 60 days

**Recipient (who we contact):**
- Primary: VP/Director of Provider Operations, Head of Provider Success, VP Clinical Operations, Director of Credentialing
- Secondary (if primary not found): Chief Operating Officer, VP Operations (at companies <100 employees)
- Fallback: CEO (at companies <30 employees where no ops title exists)

### Exclude

- Already a Medallion customer (maintain and check suppression list)
- Already using symplr, VerityStream, or CredentialStream (if detectable via BuiltWith or LinkedIn tech stack)
- Currently in active pipeline (check CRM before enrolling)
- Consumer health apps that do not employ or credential providers
- Companies outside the US
- Companies with <10 employees (not enough volume to justify software)
- Companies with >1,000 employees (likely already have an enterprise solution; different outreach required)
- Staffing agencies (different buying motion — they credential for clients, not themselves)

---

## 3. Sources [ENGINE]

| Source | What it provides | Access method |
|---|---|---|
| **Apollo via Clay "Discover Jobs"** | Job postings: title, location, company domain, date posted | Clay built-in enrichment; Apollo API |
| **Apollo "Enrich Company"** | Employee count, HQ state, website, LinkedIn URL, industry classification | Clay built-in enrichment |
| **Crunchbase via Clay "Find Organization"** | Funding stage, last round date, total raised, investors | Clay built-in enrichment |
| **Apollo "Find Person"** | Contact name, title, LinkedIn URL, work email (waterfall with verification) | Clay built-in enrichment |
| **Millionverifier via Clay HTTP** | Email validity verification (fallback if Apollo confidence < 95%) | Clay HTTP action |
| **BuiltWith via Clay** | Technology stack on company website (EHR, HRIS detection if web-facing) | Clay built-in enrichment (web-facing only; mark fields as INFERRED if not confirmed) |

---

## 4. Signals Table [ENGINE]

| # | Signal | Role | How it's read | Output |
|---|---|---|---|---|
| 1 | Clinical provider job postings in 2+ US states | **Trigger** | Apollo "Discover Jobs": count of unique job states for clinical title keywords in last 60 days ≥ 2 | Boolean: TRUE / FALSE |
| 2 | Number of open clinical provider roles | **Router** | Apollo "Discover Jobs": count of matching clinical job postings in last 60 days | Integer: 1–2 / 3–5 / 6–10 / 11+ |
| 3 | Number of distinct states in job postings | **Router** | Apollo "Discover Jobs": count of unique US state values across matching postings | Integer: 2–3 / 4–6 / 7+ |
| 4 | Funding stage | **Context-clause** (not router) | Crunchbase "last_funding_type": seed / series_a / series_b / series_c | String label |
| 5 | Days since last funding round | **Context-clause** (not router) | Crunchbase "last_funding_announced_on": calculate days elapsed | Integer |
| 6 | Company employee count | **Context-clause** | Apollo "Enrich Company": "num_employees" | Integer |
| 7 | Recipient title | **Context-clause** | Apollo "Find Person": job title of matched contact | String |

**Count clusters for Signal 2 (open clinical roles):**
- 1–2 roles: Early-stage hiring; credentialing volume is growing but not yet critical
- 3–5 roles: Active scaling; manual credentialing management is likely straining
- 6–10 roles: High-volume hiring; credentialing ops is almost certainly a bottleneck
- 11+: Aggressive growth; credentialing infrastructure is essential now

**Count clusters for Signal 3 (distinct states):**
- 2–3 states: Multi-state but manageable manually with a small team
- 4–6 states: Multi-state at scale; licensing tracking across this many states is a known operational problem
- 7+ states: Near-national footprint; manual licensing management is impossible without software

**Note on Signal 4 (funding) as context-clause:** Funding stage and recency are strong context variables that inform the angle's urgency framing, but funding alone does not change the core narrative. It adds color ("just closed your Series B last month") but does not route to a different story. Routing is driven entirely by Signals 2 and 3.

---

## 5. Routing Matrix with Angles [ENGINE]

**Axes:**
- **Axis A:** Clinical role volume (Signals 2 count clusters: Low=1-2, Mid=3-5, High=6-10, Very High=11+)
- **Axis B:** State count (Signals 3 clusters: Few=2-3, Many=4-6, National=7+)

Simplified routing: 3 angle lanes based on hiring volume + state spread. Full 4×3 matrix below; cells with identical angles are collapsed.

| Cell | Deterministic read | Inferred situation | Angle |
|---|---|---|---|
| **Low roles / Few states** (1–2 roles, 2–3 states) | Signal 2 = 1–2, Signal 3 = 2–3 | The company is beginning to hire across state lines. Credentialing is not yet a crisis, but licensing applications are starting to pile up. The ops person is probably still managing this manually but is beginning to feel the strain. | "You're starting to scale across state lines — before it becomes a full-time job, here's how [similar company] built a process that scales automatically." (Education + early-mover framing) |
| **Mid roles / Few states** (3–5 roles, 2–3 states) | Signal 2 = 3–5, Signal 3 = 2–3 | The company is in a steady hiring cadence. Multi-state volume is real but contained. The ops team is spending meaningful time on credentialing but hasn't hit a wall yet. | "With 3–5 providers in the pipeline across [State A] and [State B], your ops team is spending real hours on licensing applications. Here's what that time cost [similar company] before they switched." (Time-cost framing) |
| **High roles / Few states** (6–10 roles, 2–3 states) | Signal 2 = 6–10, Signal 3 = 2–3 | High hiring volume concentrated in a few states. The company is densely building in a specific market. Payer enrollment is likely the primary bottleneck since they're doing high volume in the same states repeatedly. | "Hiring {{open_role_count}} providers in [State A] means {{open_role_count}} payer enrollment applications, all with different timelines. Here's how [similar company] cut their enrollment delay from 90 days to 6." (Enrollment speed framing) |
| **Low–Mid roles / Many states** (1–5 roles, 4–6 states) | Signal 2 = 1–5, Signal 3 = 4–6 | The company is spreading thinly across many states. The challenge is coordination: each state has different licensing requirements, different payer rules. The ops person is tracking many parallel processes. | "Hiring across {{state_count}} states means {{state_count}} sets of licensing rules, {{state_count}} payer enrollment requirements. Here's how [similar company] managed that in one dashboard instead of one spreadsheet per state." (Coordination framing) |
| **High roles / Many states** (6–10 roles, 4–6 states) | Signal 2 = 6–10, Signal 3 = 4–6 | High volume across many states. This is the critical zone: manual management is breaking. Each new state adds a full new compliance layer. The ops team is likely behind and knows it. | "{{open_role_count}} providers across {{state_count}} states: that's roughly {{open_role_count * state_count}} licensing applications in progress right now. Here's the ROI [similar company] got by automating that." (Scale math framing — use {{calculated_app_count}} variable) |
| **Any / National** (any roles, 7+ states) | Signal 3 = 7+ | National footprint in progress. Every state has different requirements; this is the most complex credentialing scenario. The company is either already struggling or has built a credentialing team that is expensive to maintain. | "With providers in 7+ states, you're either building a credentialing team or buying software — and [similar company] found that the team route costs 3x more at this scale. Here's their math." (Build vs. buy framing for national scale) |
| **Very High roles / Any states** (11+ roles, any) | Signal 2 = 11+ | Aggressive hiring wave. Volume alone is the signal. The company is in a rapid growth phase and credentialing is almost certainly behind. Speed is the story. | "{{open_role_count}} open clinical roles means your credentialing team is already behind. Here's how [similar company] cleared a backlog of {{placeholder}} providers in {{placeholder}} days." (Backlog / speed framing) |

**Branch coverage check:**
- All cells use {{open_role_count}} (from Signal 2 count) and {{state_count}} (from Signal 3 count) — both always exist for trigger-qualified companies
- {{calculated_app_count}} (open_role_count × state_count) is a derived field, defined in Variables Contract
- [similar company] and case study results are {{placeholder}} until facts.md is populated; `/campaign-copy` will resolve them
- No cell's angle depends on funding data (context-clause only) — angles survive without it

---

## 6. Variables Contract [ENGINE]

| Variable | Source field | Exists in branches |
|---|---|---|
| `{{company_name}}` | Apollo "Enrich Company": name | All branches |
| `{{recipient_first_name}}` | Apollo "Find Person": first_name | All branches |
| `{{recipient_title}}` | Apollo "Find Person": title | All branches (context-clause only) |
| `{{open_role_count}}` | Apollo "Discover Jobs": count of matching clinical postings | All branches |
| `{{state_count}}` | Apollo "Discover Jobs": count of unique states in matching postings | All branches |
| `{{state_list}}` | Apollo "Discover Jobs": comma-joined list of unique states in matching postings | All branches (use first 2–3 for readability) |
| `{{calculated_app_count}}` | Derived: open_role_count × state_count | High roles / Many states branch only |
| `{{funding_stage}}` | Crunchbase "last_funding_type" | Context-clause; all branches (may be empty — handle gracefully) |
| `{{similar_company}}` | facts.md: approved customer reference name | All branches |
| `{{case_study_result}}` | facts.md: approved customer result metric | All branches |
| `{{case_study_days}}` | facts.md: approved customer time-to-result metric | All branches |

**Missing-variable handling:**
- If `{{funding_stage}}` is empty → omit context-clause sentence entirely (do not write "recently funded" if stage is unknown)
- If `{{state_list}}` has >3 states → use "{{state_count}} states" instead of listing all
- If `{{similar_company}}` is not in facts.md → use "one of our customers" until facts.md is populated

---

## 7. Cadence & Channel [ENGINE]

**Channel:** Email + LinkedIn DM

**Periodicity:** Always-on (Clay table refreshes weekly; new matches flow into sequence continuously)

**Sequence cadence:**

| Step | Channel | Day | Purpose |
|---|---|---|---|
| Step 1 | Email | Day 0 | Signal reference + routed angle + single ask (15-min call) |
| Step 2 | LinkedIn | Day 3 | Short connection request with signal context — no pitch |
| Step 3 | Email | Day 7 | Different angle (ROI or cost framing) + open question |
| Step 4 | Email | Day 14 | Breakup email + resource offer (case study or relevant guide) |
| Step 5 | LinkedIn | Day 21 | Resource share only — no ask |

**Exit conditions:**
- Reply received at any step → remove from automation immediately; route to reply handling (Step 8 of GTM system)
- Meeting booked → remove from automation
- Unsubscribe → suppress domain; do not re-enroll
- No reply after Step 5 → move to quarterly nurture (1 touch/quarter, resource-only)

---

*Copy not yet written. Run `/campaign-copy` to write Email 1 through Email 3 and LinkedIn DMs 1–2 into this file. Gate 1 of that skill reads this file and verifies STRUCTURE-APPROVED status before proceeding.*
