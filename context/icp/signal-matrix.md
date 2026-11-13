# Signal Matrix: Medallion

> Built from: context/icp/icp.md, context/icp/personas.md, context/docs/research/
> Methodology: knowledge-base/playbooks/signal-matrix-framework.md, workflow-anatomy.md

---

## Matrix 1: ICP Segments × Personas

**Axes chosen:**
- **Rows = ICP Segments** — the type of healthcare organization. This is the primary dimension because Medallion's value proposition, outreach angle, and urgency trigger differ significantly across segment types. A telehealth company scaling providers in 10 states has a different story than a health system consolidating credentialing.
- **Columns = Buyer Personas** — who you're reaching in that organization. Same segment, different job title = different message angle and pain language.

| Segment | Champion: VP/Dir Provider Ops | Economic Buyer: CFO/VP Finance | Influencer: CCO/General Counsel |
|---|---|---|---|
| **Digital Health / Telehealth** (VC-backed, 10–500 providers, multi-state virtual care) | Angle: "You're hiring in 5 states and your spreadsheet is already breaking — here's how [similar company] got every new provider billing in 6 days instead of 90." | Angle: "Every 90-day enrollment delay on a $200K provider is $45K in lost revenue. You have X new hires pending — here's the number." | Angle: "Telehealth providers must be licensed in every patient's state. When was the last time you audited your license coverage?" |
| **Multi-site Provider Groups** (PE-backed or private, 50–1,000+ providers, clinic expansion) | Angle: "Adding a new clinic location means 10+ payer enrollment applications from scratch. Here's how Ivy Rehab scaled to 700 clinics without adding headcount." | Angle: "Credentialing denials are silent revenue leaks. PM Pediatric reduced denials 50% — here's the math at your volume." | Angle: "Every clinic you add is another credentialing file to maintain every 2 years. At 20+ clinics, manual review is a compliance risk." |
| **Home Care / In-home Medical** (home health agencies, hospice, in-home primary care) | Angle: "In-home care depends on providers being enrolled in every patient's county payer plan. How are you managing that?" | Angle: "Payer enrollment gaps mean home visits that can't be billed. How much unbillable care did you deliver last quarter?" | Angle: "Monitoring provider credentials across a home care network is high-risk. One lapsed license on a home visit is a liability event." |
| **Health Systems** (hospital networks, academic medical centers, large IDNs) | Angle: "Your credentialing team is processing files in 30–60 days. Tampa General got to same-day turnaround and $2.4M ROI — here's how." | Angle: "$2.4M in ROI at Tampa General. What's your current cost per credentialing file, and how many files do you process per year?" | Angle: "CMS monitoring requirements are tightening. Real-time dashboards give you audit-ready compliance status across every provider." |

**Highest-priority cells for outbound:**
1. **Digital Health / Telehealth × Champion** — highest signal density (VC-funded, LinkedIn hiring data rich), clearest urgency story
2. **Multi-site Provider Groups × Champion** — PE-backed expansion is detectable via funding events and job postings
3. **Digital Health / Telehealth × Economic Buyer** — CFOs at Series B+ companies are evaluating cost efficiency now

---

## Matrix 2: Buying Signals

> For each segment, signals are scored on four tests:
> - **C** (Clear buying reason): Does this signal indicate a specific, immediate need for Medallion? (1–10)
> - **V** (Volume): How many companies per month match this signal? (1–10)
> - **D** (Data you can get): Is there a named data source and tool that can detect it? (1–10)
> - **S** (Natural story): Does the signal lead to a compelling, natural outreach narrative? (1–10)

---

### Signal 1: Digital health or telehealth company hiring clinical providers across multiple states

**Mother intent:** Operational scaling — a growing virtual care team is about to overwhelm manual credentialing
**Target segment:** Digital Health / Telehealth
**Target persona:** VP Provider Operations (Champion)

| Attribute | Detail |
|---|---|
| Exact signal | Company has 3+ open roles for NPs, PAs, MDs, therapists, or nurses in 2+ different US states in a 60-day window |
| Data source | LinkedIn Jobs (via Apollo "Discover Jobs" enrichment in Clay) |
| Clay method | Filter: title keywords = ["nurse practitioner", "NP", "physician assistant", "PA", "therapist", "psychiatrist", "physician"], job location = multi-state, company industry = digital health / telehealth, posted in last 60 days |
| Supporting filter | Company is VC-backed (Crunchbase: last_funding_type = seed/series-a/series-b, funded in last 24 months) |
| Volume estimate | ~200–400 companies/month matching across the US digital health market (INFERRED — validate in Clay Week 2) |

**Four tests:**
| Test | Score | Reasoning |
|---|---|---|
| Clear buying reason | 9/10 | Each new multi-state hire = multi-state licensing application. The bottleneck is immediate and direct. |
| Volume | 8/10 | Digital health hiring is active. LinkedIn Jobs has strong coverage for clinical roles. |
| Data you can get | 9/10 | Apollo via Clay "Discover Jobs" is the standard workflow. Well-tested. |
| Natural story | 9/10 | "You're hiring in 3 states this month — here's how [similar company] got each provider billing in 6 days." |
| **Total** | **35/40** | |

---

### Signal 2: Digital health or telehealth company raises Series A or Series B funding

**Mother intent:** Growth acceleration — post-funding = provider hiring wave incoming in 60–90 days
**Target segment:** Digital Health / Telehealth
**Target persona:** CFO / VP Finance (Economic Buyer) + VP Provider Ops (Champion)

| Attribute | Detail |
|---|---|
| Exact signal | Company in digital health, telehealth, behavioral health, or home care raises $3M–$50M Series A or Series B in last 30 days |
| Data source | Crunchbase (via Clay "Find Organization" enrichment) |
| Clay method | Filter: industry = ["Digital Health", "Telehealth", "Mental Health Tech", "Home Health Care"], funding_round = ["series_a", "series_b"], announced_on >= 30 days ago, funding_total_usd >= $3M |
| Supporting filter | Company has LinkedIn headcount 10–300; not already a Medallion customer (exclusion list) |
| Volume estimate | ~50–120 qualifying rounds/month across US digital health (INFERRED from Crunchbase data density) |

**Four tests:**
| Test | Score | Reasoning |
|---|---|---|
| Clear buying reason | 8/10 | Post-funding = provider hiring plan = credentialing need. 1–2 quarter lag, but very strong intent signal. |
| Volume | 7/10 | VC-backed digital health is active but not unlimited. Series A/B filter narrows field appropriately. |
| Data you can get | 10/10 | Crunchbase via Clay is standard. Well-documented data source with clean API. |
| Natural story | 8/10 | "Congrats on the round — most Series B digital health companies end up hiring 2x their current clinical team in year 1. Here's how to avoid the 90-day billing delay that usually follows." |
| **Total** | **33/40** | |

---

### Signal 3: Multi-site provider group opens in a new state (new clinic or new service area)

**Mother intent:** Geographic expansion — entering a new state triggers licensing + payer enrollment for every provider in that state
**Target segment:** Multi-site Provider Groups
**Target persona:** VP Provider Operations (Champion) + CCO/GC (Influencer)

| Attribute | Detail |
|---|---|
| Exact signal | Multi-site provider group (rehab, urgent care, pediatrics, behavioral health) announces a new clinic location or service area in a state where they were not previously operating |
| Data source | LinkedIn company updates + press releases (via Clay web scrape + Apollo enrichment) |
| Clay method | Apollo "Enrich Company" for multi-site providers; pair with Clay HTTP scrape of company news/blog; keyword filters: "opening", "new location", "expanding to [state]", "new market" |
| Supporting filter | Company has 50–2,000 employees; industry = healthcare provider group; has 5+ existing locations (Google Maps via Clay HTTP) |
| Volume estimate | ~100–300 qualifying expansion events/month (INFERRED — multi-site groups expand continuously) |

**Four tests:**
| Test | Score | Reasoning |
|---|---|---|
| Clear buying reason | 9/10 | New state = all providers need new state licenses + all payers in that state = immediate credentialing volume spike. |
| Volume | 7/10 | Multi-site provider expansion is constant but press releases are inconsistent. Signal detection reliability is medium. |
| Data you can get | 6/10 | LinkedIn updates and press releases require scraping; signal detection is less reliable than job postings. Needs testing. |
| Natural story | 9/10 | "Congrats on entering [state] — enrolling all your providers with [state]'s Medicaid and top commercial payers usually takes 90–120 days manually. Here's how Ivy Rehab did it at 700 clinics." |
| **Total** | **31/40** | |

---

### Signal 4: Company posts for a Director/Manager of Credentialing or Provider Enrollment

**Mother intent:** Manual process breaking — posting this role means credentialing volume is now painful enough to need a dedicated owner
**Target segment:** Digital Health, Multi-site Provider Groups, Home Care
**Target persona:** VP Provider Operations (Champion) + CEO/COO at smaller companies

| Attribute | Detail |
|---|---|
| Exact signal | Company posts for "Director of Credentialing", "Manager of Provider Enrollment", "Credentialing Coordinator", "Provider Enrollment Specialist", or "Head of Provider Operations" |
| Data source | LinkedIn Jobs (via Apollo "Discover Jobs" in Clay) |
| Clay method | Filter: title keywords = ["credentialing director", "credentialing manager", "provider enrollment", "credentialing coordinator", "payer enrollment"], company industry = healthcare, posted in last 60 days, company size = 10–500 employees |
| Supporting filter | Company has 10–50 providers on LinkedIn (profile search approximation) |
| Volume estimate | ~150–300 postings/month across US healthcare companies (INFERRED) |

**Four tests:**
| Test | Score | Reasoning |
|---|---|---|
| Clear buying reason | 8/10 | Posting this role means credentialing is broken AND they're at a build-vs-buy decision point. Perfect timing. |
| Volume | 7/10 | These roles are posted constantly across healthcare. LinkedIn Jobs has strong coverage. |
| Data you can get | 9/10 | Apollo via Clay "Discover Jobs" is standard workflow. Same as Signal 1. |
| Natural story | 8/10 | "You're hiring a credentialing director — that usually means volume is high enough to need dedicated ops. Before you hire, here's what [similar company] built instead." |
| **Total** | **32/40** | |

---

### Signal 5: Home care or home health agency announces new payer contract or value-based care agreement

**Mother intent:** New payer = new enrollment = new credentialing cycle for all contracted providers
**Target segment:** Home Care / In-home Medical
**Target persona:** CFO/VP Finance (Economic Buyer) + VP Provider Operations (Champion)

| Attribute | Detail |
|---|---|
| Exact signal | Home care, hospice, or in-home primary care company announces a new payer contract, Medicare Advantage agreement, or value-based care arrangement |
| Data source | Press release scrape + LinkedIn company updates (Clay HTTP) + Globe Newswire / PR Newswire (Clay HTTP) |
| Clay method | Clay HTTP scrape targeting PR Newswire, BusinessWire, LinkedIn updates; keyword filters: "new contract", "value-based", "Medicare Advantage", "payer agreement", company type = home health / hospice / home care |
| Supporting filter | Company has 50–1,000 employees; operates in 3+ states |
| Volume estimate | ~50–100 qualifying announcements/month (INFERRED — lower volume, higher signal strength) |

**Four tests:**
| Test | Score | Reasoning |
|---|---|---|
| Clear buying reason | 9/10 | A new payer contract means every provider seeing patients under that plan must be enrolled. Direct and immediate. |
| Volume | 5/10 | Home care press releases are less frequent than digital health hiring. Volume may be thin monthly. |
| Data you can get | 6/10 | PR Newswire/BusinessWire scraping is feasible but requires setup. Less clean than Crunchbase or LinkedIn Jobs. |
| Natural story | 8/10 | "Congrats on the [Payer] contract — getting all your providers enrolled in time to bill from day one is the hardest part. Here's how to cut that timeline from 90 days to 6." |
| **Total** | **28/40** | |

---

## Priority Signals: Top 3 to Build First

| Rank | Signal | Score | Segment | Why first |
|---|---|---|---|---|
| 1 | **Hiring clinical providers across multiple states** | 35/40 | Digital Health / Telehealth | Highest volume, most reliable data source, clearest urgency story. Can be live in Clay in 1 session. |
| 2 | **Series A/B funding round** | 33/40 | Digital Health / Telehealth | Crunchbase is the cleanest data source in the whole matrix. Easy to build, predictable volume, strong narrative. |
| 3 | **Posting for Director of Credentialing or Provider Enrollment** | 32/40 | Digital Health + Provider Groups | Same Apollo/Jobs workflow as Signal 1. Build once, runs across two segments. Perfect timing signal. |

**Signals 4 and 5 are build-when-ready:**
- Signal 4 (new state expansion) is high-intent but signal detection is less reliable — test detection quality in Clay before committing.
- Signal 5 (home care payer contract) is high-intent but lower volume — good for a niche campaign, not a primary workflow.

---

## Notes

- Signals 1 and 3 use the same Clay workflow (Apollo Discover Jobs). Build once, deploy two workflows.
- Signal 2 (funding) pairs well with Signal 1 (hiring) as a compound filter: funded AND hiring = highest-priority account.
- All signals are based on US data sources. The US market has rich digital footprint (Crunchbase, LinkedIn, Apollo) — standard B2B SaaS outbound playbook applies.
- Volume estimates are INFERRED. Validate actual monthly volume in Clay Week 2 before committing to sequencing capacity.
