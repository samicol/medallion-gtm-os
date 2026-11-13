# Buyer Personas: Medallion

> Every claim traces to research files. Direct quotes from case studies are marked.
> Source files: context/docs/research/customers.md, company.md, market.md, voice.md

---

## Persona 1: The Champion — VP/Director of Provider Operations

**Job titles:**
- VP of Provider Operations
- Director of Credentialing
- Director of Provider Success
- Head of Clinical Operations
- VP of Payor Strategy and Relations

**What they're measured on:**
- Time-to-billing (days from hire to first billable claim)
- Credentialing turnaround time
- Payer enrollment completion rate
- Compliance audit results (zero findings)
- Provider experience / onboarding satisfaction
- Headcount efficiency (providers managed per ops staff)

**Their top 3 pains (in their own words):**
1. "We're tracking everything in spreadsheets and it's completely falling apart — every new state we enter adds another column." (INFERRED from market.md: "companies still track provider data in spreadsheets")
2. "Providers are sitting on our payroll for 90 days while payer enrollment drags. It's direct money out the door." (Supported by market.md: 60–120 day enrollment average)
3. "We're hiring faster than our credentialing team can keep up. I'm either going to miss compliance deadlines or burn out my staff." (INFERRED from signals.md signal 1 and 5)

**What makes them start looking:**
- Headcount is growing and manual management is breaking
- A credentialing denial or compliance incident triggers immediate urgency
- A new state expansion is announced and they realize the licensing volume is unmanageable manually
- Their current process failed an audit or created a billing hold

**Their objections:**
- "We already have a process — it works, mostly." (Status quo bias; counter with time-to-billing cost)
- "I don't have the bandwidth to implement new software right now." (Counter: Medallion handles implementation; average onboarding time is [not found — verify])
- "Our EHR has credentialing features." (Counter: EHR credentialing is basic; Medallion handles multi-state licensing and payer enrollment which EHRs don't)

Source: customers.md (Matthew Ortiz quote), market.md, signals.md

---

## Persona 2: The Economic Buyer — CFO / VP of Finance

**Job titles:**
- Chief Financial Officer
- VP of Finance
- VP of Revenue Operations
- Controller (at smaller companies)

**What they're measured on:**
- Revenue per provider (productivity)
- Administrative cost per provider per year
- Time-to-revenue for new hires
- Payer denial rate (revenue impact)
- Operational leverage (revenue growth without proportional headcount growth)

**Their top 3 pains (in their own words):**
1. "Every time we hire a provider, there's a 60–90 day lag before they generate revenue. At scale, that's a massive cash flow hole." (Supported by company.md: "time-to-billing directly impacts financial performance")
2. "We're growing the operations team as fast as the clinical team. That's not a scalable model." (Supported by voice.md: "scale efficiently without increasing headcount")
3. "I have no visibility into where enrollment applications are stuck. I can't forecast revenue from new hires." (INFERRED from Medallion's real-time dashboard feature)

**What makes them start looking:**
- Operations headcount is growing unsustainably alongside provider headcount
- A board or investor review flags provider time-to-billing as a KPI gap
- A CFO peer mentions they solved this with software (referral trigger)
- Payer denial rate is rising and causing revenue cycle disruption

**Their objections:**
- "What's the ROI?" (Counter: Tampa General got $2.4M ROI; WellBe cut credentialing time 80%; Medallion offers performance guarantees)
- "We can hire a credentialing coordinator for less." (Counter: software scales infinitely; a coordinator maxes out at ~50 providers)
- "I'd rather own this process internally." (Counter: internal build requires ongoing maintenance of payer rules that change constantly)

Source: customers.md (Tampa General $2.4M ROI), company.md (66% administrative cost reduction claim), voice.md

---

## Persona 3: The Influencer — Chief Compliance Officer / General Counsel

**Job titles:**
- Chief Compliance Officer
- VP of Compliance
- General Counsel
- Chief Legal Officer
- VP of Risk and Quality

**What they're measured on:**
- Zero compliance incidents in credentialing audits
- Provider license expiration rate (zero expired licenses billing)
- Payer credentialing file accuracy
- NCQA / accreditation status
- Regulatory change response time

**Their top 3 pains (in their own words):**
1. "We had a provider see patients in a state they weren't licensed in. That's a liability exposure I cannot have again." (Supported by market.md: "inadvertently running afoul of a state's medical practice and licensure regulations")
2. "License renewals are falling through the cracks. Someone renews late, and we don't find out until a claim is denied." (INFERRED from Medallion's monitoring feature)
3. "Every state has different rules. I can't keep up with what changed in Connecticut versus Massachusetts this quarter." (Supported by market.md: "requirements differ widely, such as Connecticut's approach versus Massachusetts's verification requirement")

**What makes them start looking:**
- A compliance incident (billing in unlicensed state, expired credential, payer audit)
- CMS releases new guidance tightening credentialing requirements
- The company enters a new state and the CCO does a gap analysis on licensing
- An acquisition or merger that suddenly doubles the provider roster

**Their objections:**
- "How do I know the platform is accurate?" (Counter: 99.9% file accuracy, NCQA-aligned, SOC 2 Type II — verify NCQA and SOC 2 status directly)
- "We can't risk a gap in coverage during transition." (Counter: Medallion handles migration with existing files; ask for case study on transition process)
- "I need this to integrate with our existing systems." (Counter: Medallion integrates with CAQH; ask about EHR/HRIS connectors)

Source: customers.md (Joshua Autry quote re: turnaround time), market.md, company.md

---

## Notes on persona interactions

- The **Champion** (ops) typically finds Medallion and builds the internal case
- The **CFO** approves the budget and needs an ROI story
- The **CCO/GC** will block if compliance and accuracy concerns aren't addressed
- At smaller companies (under 50 employees), the CEO/COO often plays all three roles

A winning deal typically requires all three to be aligned. The Champion drives, the CFO approves, and the CCO/GC gives their blessing.
