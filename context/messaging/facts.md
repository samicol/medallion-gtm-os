# Medallion - Authorized Copy Facts

> Filled from context/docs/research/ and context/docs/case-studies.md.
> Every claim traces to a public source. Anything not listed here renders as {{placeholder}} in copy.
> No invented numbers. No INFERRED claims in prospect-facing copy.

**Last updated:** 2026-11-13 by Olusola Isaac Ayomide

---

## Sender identity

| Field | Value |
|---|---|
| Sender name(s) | Per inbox, resolved by the sequencer signature |
| Title | Varies by sender; default to "Growth, Medallion" |
| Signature format | "First / Title / Medallion" |
| Sender persona notes | Peer-to-peer voice; writes in first person singular; direct, no fluff |

## What we do (locked value prop)

The value-prop line in copy states one of these, flat and confident:

- **Variant A:** "Medallion is an AI platform that handles credentialing, multi-state licensing, and payer enrollment automatically, so providers go from hired to billing in days instead of months."
- **Variant B:** "Medallion helps digital health companies scale their provider network without scaling their credentialing ops team."

Product one-liner (context, not copy): AI-powered provider operations platform; automates credentialing, payer enrollment, and cross-state licensing for growth-stage digital health and telehealth companies; delivered as SaaS with AI agents; serves 300+ healthcare organizations across the US.

Source: https://medallion.co | Checked: 2026-11-13

## Approved claims and numbers (use these exact phrasings)

| Claim | Approved phrasing | Source | Approved by / date |
|---|---|---|---|
| Credentialing speed | "credentialing file ready in about one day" | https://medallion.co | Public, 2026-11-13 |
| WellBe Senior Medical turnaround | "WellBe Senior Medical went from weeks-long credentialing to a 6-day turnaround" | https://medallion.co/resources/case-studies | Public, 2026-11-13 |
| WellBe time reduction | "80% reduction in credentialing time" | https://medallion.co/resources/case-studies | Public, 2026-11-13 |
| Tampa General ROI | "$2.4M in ROI" | https://medallion.co/resources/case-studies | Public, 2026-11-13 |
| Ivy Rehab scale | "Ivy Rehab scaled to 700+ clinics without adding credentialing headcount" | https://www.casestudies.com/company/medallion/case-study/ivy-rehab-network-scales-provider-onboarding-across-700-clinics-with-medallion | Public, 2026-11-13 |
| PM Pediatric denials | "50% reduction in credentialing denials" | https://www.casestudies.com/company/medallion/case-study/pm-pediatric-care-slashes-credentialing-denials-by-50-with-medallion | Public, 2026-11-13 |
| File accuracy | "99.9% average file accuracy" | https://medallion.co | Public, 2026-11-13 |
| Admin cost reduction | "66% reduction in administrative costs" | https://medallion.co | Public, 2026-11-13 |
| Time-to-revenue improvement | "2x faster time-to-revenue" | https://medallion.co | Public, 2026-11-13 |
| Customer count | "300+ healthcare organizations" | https://medallion.co | Public, 2026-11-13 |
| CareBridge multi-state | "CareBridge scaled multi-state licensing without building a larger internal credentialing team" | https://medallion.co/resources/case-studies | Public, 2026-11-13 |
| Ginger | "Ginger maintained market leadership as a unicorn digital mental health platform while scaling credentialing with growth" | https://www.medallion.co/resources/case-studies/how-ginger-scaled-credentialing | Public, 2026-11-13 |

**Formatting rules for proof:**
- Write customer names exactly as above (e.g. "WellBe Senior Medical" not "Wellbe" or "WellBe").
- Do not use currency symbols in subject lines; "2.4M in ROI" not "$2.4M in ROI" in subjects.
- Counts that come from scraped data (open_role_count, state_count) are stated as found; do not round up or down.

## Numbers to keep fuzzy (never quote as hard numbers)

- Employee count at Medallion (use "hundreds of employees" at most; not confirmed from public sources)
- Medallion's own revenue (not public)
- Average ROI across all customers (only Tampa General $2.4M is confirmed)
- Per-provider credentialing cost (not public)
- Time-to-revenue improvement per segment (only "2x overall" is approved)

## Authorized social-proof names

Only these customer names may appear in prospect-facing copy:

| Name | What it proves | Matches | Caveat |
|---|---|---|---|
| WellBe Senior Medical | 80% credentialing time reduction; 6-day turnaround | Home care / in-home senior care | Quote from CCO; best for compliance and speed stories |
| Ivy Rehab | 700+ clinics, no headcount increase | Multi-site provider group, rehab | Best for scale-without-headcount story |
| CareBridge | Multi-state licensing at scale | Digital health, home care coordination | Best for multi-state digital health prospects |
| Tampa General Hospital | $2.4M ROI | Health system | Best for CFO / ROI conversations; not a digital health match |
| PM Pediatric Care | 50% denial reduction | Pediatric urgent care, multi-site | Best for compliance and accuracy stories |
| Ginger (Headspace Health) | Scaled credentialing as a unicorn digital mental health platform | Digital mental health, VC-backed | Best for behavioral health / digital health VC-backed prospects |
| Family Care Center | Unified credentialing; improved provider experience | Behavioral health, mental health | Best for behavioral health, smaller digital health |

Everyone else stays out of copy until added here.

## Proof caveats

- **WellBe Senior Medical** proves speed and time reduction for a home care provider group. It does not prove results for digital health platforms or telehealth companies; use CareBridge or Ginger for those.
- **Ivy Rehab** proves headcount efficiency for a large multi-site rehab group. It does not prove results for digital health companies; it over-indexes on scale (700+ clinics).
- **Tampa General** proves ROI for a health system. Do not use in digital health or telehealth prospect copy without noting it's a health system.
- **CareBridge** and **Ginger** are the strongest matches for digital health / telehealth prospects. Use these by default for this workflow.
- **PM Pediatric** proves denial reduction. Use for compliance angle, not speed angle.

## Banned

### Banned angles
- Price or discount framing ("try it free", "lower cost than X")
- Guarantees in copy ("X meetings a month", "Y providers credentialed in Z days or your money back") -- these require Medallion's direct approval; do not imply guarantees unless facts.md is updated with an approved phrasing
- "Replace your team" framing (iron law 14 + insult test)
- Diagnosing the prospect's current credentialing setup as failing ("your credentialing process is broken")
- Competitive name-drops in cold outreach (do not name symplr, VerityStream, or Assured in emails)

### Banned words and phrasing (Medallion-specific)
See also: `knowledge-base/playbooks/copy-bans.yaml`
- "AI-powered" as a standalone claim (pair with an outcome or mechanism)
- "Streamline" (too generic; use a specific time or cost claim instead)
- "Revolutionize" or "transform"
- "Best-in-class" or "industry-leading" without a specific, sourced metric
- Em dashes (rule in CLAUDE.md)

### Never in copy, under any circumstance
- Pricing or contract terms
- Customer names not on the authorized list above
- INFERRED calculations stated as facts (e.g. "you're losing $X per day" without an approved source)

## Voice notes

- Register: direct, peer-to-peer, outcome-focused; sounds like a sharp ops person talking to another ops person
- Hedges about the prospect: "my guess is", "could be off", "not sure if this is relevant"
- House phrases: "Relevant?", "Worth a quick chat?", "How's that going for you?"
- Subjects: lowercase, 3–5 words, no variables in subject line, same subject across the thread
- Sentences: short and declarative; no filler openers; lead with the signal or the outcome

## CTA ladder

- **Email 1:** Single ask = 15-minute call. Never "book a demo." Never a calendar link. Use "Worth a quick chat?" or "Should I send the [CareBridge/Ginger] case study?"
- **Email 2:** Open question only ("How's that going for you on the credentialing side?") or a reframed ask if Email 1 had no reply
- **Email 3 (breakup):** Resource offer ("happy to send the case study") + opt-out ("if the timing's off, I'll leave you alone")
- **LinkedIn DMs:** No ask in DM 1 (connection context only); resource-only in DM 2

## Internal only (never in prospect copy)

- Pricing and contract terms
- Churn rate or customer win/loss data
- Internal campaign performance metrics (reply rates, open rates)
- Full customer roster beyond the authorized list above
- CredAlliance partnership terms or technical details
- Medallion's own cost per acquisition
