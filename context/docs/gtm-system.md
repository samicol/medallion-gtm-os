# GTM System Architecture: Medallion

> Outbound GTM system designed end to end for Medallion's digital health and multi-site provider group segments.
> Built from: context/icp/signal-matrix.md, context/icp/icp.md, context/icp/personas.md
> Four pillars check: clean data / always-on signals / composable workflows / tight feedback loops

---

## System Overview

```
Context OS
    ↓
Buying Signals (always-on monitoring)
    ↓
Company Discovery + ICP Filter
    ↓
Enrichment (company + contact)
    ↓
ICP Fit Check + Routing by Segment
    ↓
Contact Finding + Email Verification
    ↓
Sequence (Email + LinkedIn)
    ↓
Reply Handling
    ↓
CRM
    ↓
Weekly Feedback Loop → Context OS
```

---

## Step 1: Context OS

**What happens:** Every Claude Code session starts with CLAUDE.md loaded. The session reads the current ICP, signal matrix, and research before any GTM work. No action is taken in a session without reading context first.

**Tool:** Claude Code (this repo)

**Decisions:**
- Research up to date? → Yes: proceed → No: update relevant research file before continuing
- Signal matrix has 3+ priority signals? → Yes: proceed to step 2 → No: build signal matrix first

---

## Step 2: Buying Signal Detection (Always-On)

**What happens:** Clay tables monitor for the three priority signals continuously. New matches flow in automatically on a cadence.

**Signals and tools:**

| Signal | Source | Clay Method | Cadence |
|---|---|---|---|
| Clinical provider hiring across 2+ states | LinkedIn Jobs | Apollo "Discover Jobs" enrichment; filter: title = clinical roles, location = multi-state, posted ≤60 days | Weekly refresh |
| Series A/B funding round | Crunchbase | Clay "Find Organization"; filter: industry = digital health/telehealth, round = series_a/series_b, announced ≤30 days | Daily refresh |
| Credentialing/enrollment ops job posting | LinkedIn Jobs | Apollo "Discover Jobs"; filter: title = credentialing/enrollment ops roles, posted ≤60 days | Weekly refresh |

**Decision:**
- Company matches ≥1 signal → passes to Step 3 (ICP filter)
- Company matches 0 signals → not actioned; returned to monitoring pool

---

## Step 3: Company Discovery + ICP Filter

**What happens:** Each signal-matched company is checked against ICP criteria before enrichment spend is used.

**Tool:** Clay (ICP filter columns)

**ICP filters applied:**
1. Industry = digital health / telehealth / multi-site provider group / home care / behavioral health → Pass / Fail
2. Provider count INFERRED ≥10 (from employee count proxy + clinical job ratio) → Pass / Fail
3. Geography = US only → Pass / Fail
4. Already a Medallion customer (exclusion list) → Exclude / Pass
5. Already a known competitor customer (optional enrichment) → Flag / Pass

**Decision:**
- Passes all 5 filters → proceed to Step 4
- Fails any filter → reject; log rejection reason in Clay

---

## Step 4: Enrichment

**What happens:** Qualified companies are enriched with firmographic, technographic, and contact data needed for routing and personalization.

**Tool:** Clay (enrichment waterfall)

**Enrichment layers (in order):**

| Layer | What we're getting | Clay tool |
|---|---|---|
| Company basics | Employee count, HQ state, website, LinkedIn URL | Apollo "Enrich Company" |
| Funding data | Last round, total raised, investors | Crunchbase via Clay |
| Provider count proxy | Clinical job posting count, estimated provider roster size | Apollo "Discover Jobs" count |
| Technology stack | EHR in use (Epic, Cerner, Athena), if detectable | BuiltWith via Clay (web-facing only) |
| News / expansion events | Recent press releases, new state announcements | Clay HTTP → news scrape |
| Existing credentialing tool | symplr, VerityStream, manual/spreadsheet (if detectable) | BuiltWith or Clay AI research column |

**Decision (after enrichment):**
- Enough data to route and personalize? → Yes: proceed to Step 5
- Key fields missing (e.g., no contact found, company size unclear)? → Waterfall to next enrichment source; if still missing, hold in "needs manual review" queue
- Enrichment reveals disqualifying fact (e.g., already using Medallion)? → Reject

---

## Step 5: ICP Fit Check + Routing by Segment

**What happens:** Based on enrichment data, each company is routed into the right segment lane. Segment determines the outreach angle, persona target, and copy variant.

**Tool:** Clay (routing column with IF/THEN logic)

**Routing logic:**

```
IF industry = digital health/telehealth AND funding_stage = series_a OR series_b
  → Segment: Digital Health / Signal: Funding round
  → Persona target: Champion (VP Provider Ops) + Economic Buyer (CFO)
  → Angle: Post-funding provider scaling story

ELSE IF clinical_job_postings ≥3 AND states ≥2
  → Segment: Digital Health / Signal: Multi-state hiring
  → Persona target: Champion (VP Provider Ops)
  → Angle: Multi-state licensing bottleneck story

ELSE IF credentialing_job_posting = TRUE AND employee_count ≤500
  → Segment: Provider Group / Signal: Ops job posting
  → Persona target: Champion (VP Provider Ops) + CEO/COO (small companies)
  → Angle: Build vs. buy decision story

ELSE IF multi_site = TRUE AND expansion_signal = TRUE
  → Segment: Multi-site Provider Group / Signal: New state expansion
  → Persona target: Champion (VP Provider Ops) + CCO/GC
  → Angle: State expansion compliance story

ELSE
  → Hold: insufficient signal for routing; return to monitoring pool
```

---

## Step 6: Contact Finding + Email Verification

**What happens:** For each routed company, find the right 1–3 contacts matching the target persona for that segment.

**Tool:** Clay (contact finding waterfall) → email verification

**Contact finding waterfall:**
1. Apollo "Find Person" → filter by title keywords for target persona, company domain
2. If Apollo misses → LinkedIn Sales Navigator export (manual or automated)
3. If still missing → Clay AI research column to find person from LinkedIn URL

**Title targeting by segment:**
- Digital Health / Champion: VP Provider Operations, Director of Credentialing, Head of Provider Success, VP Clinical Operations
- Digital Health / Economic Buyer: CFO, VP Finance, VP Revenue Operations
- Provider Group / Champion: VP Operations, Director of Provider Services, VP Payor Strategy

**Email verification waterfall:**
1. Clay built-in email finder → verify
2. If bounces/unverified → Millionverifier via Clay HTTP
3. If still unverified → remove from sequence (do not send to unverified addresses)

**Decision:**
- Verified work email found → proceed to Step 7
- No verified email found → route to LinkedIn DM only (Step 7, LinkedIn lane)
- Contact is a VP or above at >500-person company → flag for AE review before sending

---

## Step 7: Sequence (Email + LinkedIn)

**What happens:** Contacts enter a signal-based sequence. The first touch references the specific buying signal that triggered the outreach.

**Tool:** Outreach / Apollo Sequences / Instantly (email); LinkedIn (DMs)

**Sequence structure (3-email + 2 LinkedIn DMs):**

| Step | Channel | Timing | Focus |
|---|---|---|---|
| Email 1 | Email | Day 1 | Signal reference + specific pain + relevant case study result |
| LinkedIn DM 1 | LinkedIn | Day 3 | Short connection request with signal context |
| Email 2 | Email | Day 7 | Different angle (ROI / cost framing) + open question |
| Email 3 | Email | Day 14 | Breakup email + resource offer (relevant blog or case study) |
| LinkedIn DM 2 | LinkedIn | Day 21 | Final touch — resource share only, no ask |

**Rules:**
- Email 1 must reference the specific signal (hiring in [state], funding round, credentialing job posting)
- No em dashes in copy
- No generic "I wanted to reach out" openers
- Maximum 3 sentences in Email 1 before the ask
- Ask = offer a 15-minute call, not a demo

**Decision (at each step):**
- Reply received → move to Step 8 (reply handling) immediately; remove from automated steps
- Unsubscribe → remove immediately; do not re-enroll
- No reply after all 5 steps → move to "long nurture" sequence (1 touch/quarter)

---

## Step 8: Reply Handling

**What happens:** Replies are categorized and routed to the appropriate next action.

**Tool:** CRM (HubSpot or equivalent) + human review

**Reply categories and routing:**

| Reply type | Routing |
|---|---|
| Interested / wants to meet | AE assigns meeting time; log in CRM as SQL (Sales Qualified Lead) |
| "Not right now" / timing objection | Log timing; set a 60-day follow-up task; move to nurture |
| "We already have a solution" (names competitor) | Log competitor; tag account; send competitor comparison resource; AE decides whether to pursue |
| "Not the right person — here's who is" | Update contact record; re-enroll new contact in sequence from Step 1 |
| "Unsubscribe / remove me" | Remove immediately; flag domain for suppression |
| Out of office | Auto-detect; resume sequence when OOO ends |
| No reply (all steps complete) | Move to quarterly nurture |

---

## Step 9: CRM

**What happens:** All account and contact activity is logged in CRM. CRM is the system of record for deal status, signal history, and feedback data.

**Tool:** HubSpot (assumed — INFERRED, Medallion's CRM not confirmed publicly)

**What gets logged:**
- Company: segment, signal that triggered outreach, enrichment fields, fit score
- Contact: title, email, reply category, meeting booked date
- Deal: stage, AE owner, signal-to-meeting days, source signal
- Notes: any context from replies that updates the ICP or signal scoring

**Key CRM properties to track for feedback loop:**
- Signal that triggered outreach → which signals produce the most meetings
- Days from signal detection to reply → signal freshness decay rate
- Segment that produces the most meetings → where to concentrate Clay workflow capacity
- Competitor mentioned in replies → update competitors.md

---

## Step 10: Weekly Feedback Loop → Context OS

**What happens:** Every Friday, review the week's signal-to-meeting data and update the Context OS files that inform the next week's outreach.

**Tool:** Clay (data export) + Claude Code (Context OS update)

**What gets reviewed:**
1. Signal performance: which signals generated replies this week?
2. Segment performance: which segment had the highest reply rate?
3. Copy performance: which email subject lines and openers got replies?
4. ICP accuracy: did any replies reveal a disqualifying fact we didn't catch in Step 3?
5. New signals: did any replies mention a pain or trigger we hadn't mapped?

**Context OS files updated based on findings:**
- `context/icp/signal-matrix.md` — update signal scores, add or retire signals
- `context/icp/icp.md` — tighten or expand ICP based on disqualification patterns
- `knowledge-base/learnings/` — log campaign retrospectives here

**Decision:**
- Signal generating ≥3 meetings/month → scale Clay table (increase list size)
- Signal generating 0 meetings after 50 contacts → review angle + copy; if still 0 after 100 contacts → retire signal
- New pain mentioned in replies → add to ICP or signals research; consider building new workflow

---

## Four Pillars Check

| Pillar | How this system addresses it |
|---|---|
| **Clean data** | Enrichment waterfall with verification at every step; unverified emails excluded; ICP filter rejects before enrichment spend |
| **Always-on signals** | Clay tables refresh daily/weekly; no manual list building; signal detection is automated, not a one-time scrape |
| **Composable workflows** | Signals 1 and 3 share the same Clay workflow (Apollo Jobs); routing logic separates them by segment after detection; build once, deploy to multiple segments |
| **Tight feedback loops** | Weekly CRM review updates Context OS files; signal scores are live metrics, not set-and-forget; reply data flows back to ICP and signal matrix |
