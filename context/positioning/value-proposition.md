# Value Proposition: Medallion

> Built from research files only. Every claim traces to context/docs/research/.
> Source files: company.md, customers.md, market.md, voice.md

---

## By Persona

### Persona 1: VP/Director of Provider Operations (Champion)

**Job to be done:**
Get every new provider credentialed, licensed in all required states, and enrolled with every relevant payer — fast enough that the clinical team can see patients and bill without an operational bottleneck.

**The pain:**
Manual credentialing across multiple states and payers takes 60–120 days per provider and breaks completely at scale. Every new state expansion multiplies the licensing workload. Spreadsheet management fails at ~20–50 providers.
Source: context/docs/research/market.md

**The gain:**
Providers go from hired to billing in days, not months. Multi-state licensing and payer enrollment run in parallel, automatically. The ops team manages more providers with the same headcount.
Source: context/docs/research/company.md ("2x faster time-to-revenue", "66% administrative cost reduction" — self-reported)

**The proof:**
- WellBe Senior Medical: 80% reduction in credentialing time; turnaround now 6 days (self-reported)
- Ivy Rehab: Scaled to 700+ clinics without adding headcount (self-reported)
- CareBridge: Scaled multi-state licensing without increasing credentialing team
Source: context/docs/research/customers.md

---

### Persona 2: CFO / VP Finance (Economic Buyer)

**Job to be done:**
Maximize revenue per provider by minimizing the time between hire and first billable claim, while keeping administrative cost per provider low and scalable.

**The pain:**
Every 90-day payer enrollment delay on a provider earning $200K/year is ~$45K in unbillable care. At scale, this is a material revenue gap. Administrative costs grow linearly with provider count under a manual model — there is no leverage.
Source: context/docs/research/market.md (60–120 day enrollment average); calculation INFERRED

**The gain:**
Time-to-billing compresses to days. Administrative cost per provider drops dramatically. Revenue forecasting from new hires becomes predictable.
Source: context/docs/research/company.md (66% admin cost reduction, self-reported)

**The proof:**
- Tampa General Hospital: $2.4M in documented ROI (self-reported)
- PM Pediatric Care: 50% reduction in credentialing denials (self-reported)
Source: context/docs/research/customers.md

---

### Persona 3: CCO / General Counsel (Influencer)

**Job to be done:**
Maintain continuous, audit-ready compliance across all provider credentials, licenses, and payer enrollments — across every state where the company operates — without manual monitoring or spreadsheet tracking.

**The pain:**
Provider licenses lapse. Credential files fall out of date. Telehealth providers see patients in states where they're not licensed. Any of these is a regulatory violation, a CMS penalty risk, or a malpractice liability.
Source: context/docs/research/market.md

**The gain:**
Real-time dashboards surface compliance gaps before they become incidents. License renewals are automated. CMS monitoring requirements are met continuously without manual review cycles.
Source: context/docs/research/company.md (NCQA-aligned, SOC 2 Type II — verify directly with Medallion)

**The proof:**
- PM Pediatric Care: 50% reduction in credentialing denials (fewer gaps reaching payer review)
- WellBe Senior Medical: 99.9% file accuracy (self-reported)
Source: context/docs/research/customers.md

---

## Cross-Persona Value Summary

| Dimension | Before Medallion | After Medallion | Evidence |
|---|---|---|---|
| Time-to-billing | 60–120 days | ~6 days average (self-reported) | WellBe, company.md |
| Admin cost per provider | INFERRED: high and growing linearly | 66% reduction (self-reported) | company.md |
| Credentialing turnaround | 60–120 days | ~1 day average (self-reported) | company.md |
| Denial rate | Baseline unknown | -50% at PM Pediatric Care | customers.md |
| Headcount needed to scale | Grows with provider count | Decoupled (scales without adding ops staff) | Ivy Rehab, CareBridge |
| ROI | — | $2.4M at Tampa General | customers.md |

---

## Gaps

- Exact pre-Medallion baseline metrics per customer not publicly available
- 66% admin cost reduction is self-reported; independent verification not found
- Pricing not public; value-to-cost ratio cannot be calculated from public information
