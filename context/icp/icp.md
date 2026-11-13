# ICP: Medallion

> Every claim traces to a research file. Claims not supported by research are marked as INFERRED or listed as open questions.
> Source files: context/docs/research/company.md, customers.md, market.md, signals.md

---

## Layer 1: Firmographic

**Who is a fit:**

| Attribute | Criteria | Evidence |
|---|---|---|
| Industry | Digital health, telehealth, virtual care, home care, behavioral health, multi-site provider groups, health systems | customers.md: Iris Telehealth, Ginger, CareBridge, Ivy Rehab, Tampa General, WellBe Senior Medical |
| Geography | United States | company.md: "hundreds of healthcare organizations nationwide" |
| Provider count | 10–1,000+ credentialed providers on the roster | PRIMARY filter. Manual management breaks at ~20–50 providers. customers.md: Ivy Rehab (700+ clinics), Ginger (unicorn scale), Tampa General (health system). Below 10 providers = not enough volume to justify. |
| Company size | 10–5,000 employees | INFERRED — provider count is a stronger filter than employee count; employee size alone is not predictive |
| Growth stage | Active hiring (adding providers); or Series A+ for digital health segment | Key qualifier is GROWTH, not stage label. A slow-growing $50M company is weaker than a fast-hiring seed company. |
| Business model | B2B healthcare; sells care to patients or manages a provider network | company.md: Medallion's buyer is the company operating the provider network |

**Who is NOT a fit:**
- Solo practitioners or single-provider practices — not enough volume to justify software
- Consumer health apps that don't employ or credential providers
- Companies outside the US (Medallion is US-focused)
- Non-healthcare companies
- Companies with fully outsourced credentialing already under a long-term contract (timing issue, not permanent disqualification)
- Pure SaaS health tech companies that don't manage clinical providers

---

## Layer 2: Technographic

**Signs of a fit:**
- Currently tracking credentialing in spreadsheets, email, or a generic project management tool (Asana, Monday, Notion) — clearest "tool they will replace" signal
- Has a CAQH ProView account — means they're already in the credentialing ecosystem and have provider volume
- Uses an EHR (Epic, Cerner, Athena) — credentialing workflow must integrate; also signals established provider operations
- Has a revenue cycle management system — enrollment completion directly impacts RCM billing
- Multi-state footprint OR announced plans to expand to new states (technographic + intent combo)

**Signs of a NOT fit:**
- Already using symplr, VerityStream, or Medallion itself
- Fully outsourced to a credentialing vendor with no intent to bring in-house (rare)

Source: competitors.md, company.md

---

## Layer 3: Intent Signals

**Strongest signals (evidence a company needs Medallion now):**

| Signal | Urgency | Why |
|---|---|---|
| Hiring 5+ clinical providers in 90 days | High | Immediate credentialing + enrollment workload increase |
| Raised Series A/B funding in last 60 days | High | Growth plan activated; operations infrastructure needed |
| Announced expansion to 2+ new states | High | Multi-state licensing requirement triggered immediately |
| Posting for Director of Credentialing or Provider Enrollment | High | Manual process breaking; about to hire team OR buy software |
| Posting clinical + operations/credentialing roles simultaneously | High | Operational strain evidence |
| New payer contract signed or announced | Medium | Enrollment must complete before first billable claim |
| New CMO, VP of Operations, or Head of Provider Success hired | Medium | New leader evaluates and upgrades ops tools in first 90 days |

Source: signals.md, market.md

---

## Layer 4: Persona

**Champions (the people who evaluate and advocate for Medallion internally):**
- VP/Director of Provider Operations
- Head of Credentialing
- Director of Provider Success
- VP of Clinical Operations

**Economic buyers (the people who approve the spend):**
- CFO / VP of Finance (owns the budget; cares about ROI and cost reduction)
- CEO/COO at smaller companies (makes all ops tool decisions)
- CRO / VP Revenue at larger companies (owns time-to-billing metric)

**Influencers / blockers:**
- CTO / VP Engineering — may have opinions on data integrations with EHR/HRIS
- General Counsel / Chief Compliance Officer — cares about NCQA compliance and audit risk
- Head of HR / People Ops — involved in provider onboarding workflow

Source: company.md (buyer personas from website), customers.md (titles in quotes)

---

## Layer 5: Engagement Readiness

**Ready to buy now:**
- Has active provider hiring (5+ in pipeline or just hired)
- Just closed a funding round
- Currently tracking credentialing in spreadsheets or email
- Has had a credentialing denial or compliance incident in the last 90 days
- Operations team is manually managing payer enrollment and hitting delays

**Not ready yet (nurture):**
- Pre-Series A with fewer than 10 providers
- Currently under contract with a credentialing vendor (12+ months remaining)
- No active provider growth plan

**Disqualified:**
- Already a Medallion customer
- Not in the US
- Not a healthcare provider organization

---

## Who is NOT a fit (summary)

1. Solo practitioners or practices with 1–5 providers
2. Consumer health apps (no providers to credential)
3. Companies outside the United States
4. Pure pharma, medical device, or non-care delivery companies
5. Organizations with no active growth plan and stable, small provider rosters managed adequately by existing staff

---

## Open questions

- What is Medallion's minimum viable provider count for a customer? (not found in public sources)
- Do health systems above ~500 providers use a different product tier? (INFERRED to be yes, given CredAlliance targeting large payers)
- Is there a geographic sweet spot within the US (urban markets, specific states)? (not confirmed)
