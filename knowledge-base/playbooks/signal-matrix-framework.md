# Signal Matrix Framework

How to build targeting matrices for your company. Save the result to `context/icp/signal-matrix.md`; `/campaign-strategy` and `/build-workflow-spec` read it when it exists.

> **This is not a template.** The matrix structure changes per company. This doc teaches the thinking process, not a fill-in-the-blank format.

---

## The Core Question

Every matrix answers: **"What are we selling, to whom, and how do we find them?"**

The process has five steps. Each step must be completed before the next:

1. Understand the company and its products
2. Understand who could buy this
3. Choose the right grouping axes for the matrix
4. Assess maturity and penetrability of each segment
5. Map signals to find and reach priority segments

---

## Step 1: Understand the Company

Before touching any matrix, research deeply:

- **What do we sell?** Products, features, pricing model
- **What pain does it solve?** In the buyer's words, not marketing language
- **Who do they sell to today?** Current customers, win patterns
- **Who are their competitors?** How do buyers compare them?
- **What market are they in?** US, LatAm, EU, emerging. This determines data availability

Sources: `CLAUDE.md`, `context/` (ICP, positioning, competitors, `context/docs/research/`), call notes in `meetings/`, website, competitor analysis.

If you don't deeply understand the product, you can't build a useful matrix. A matrix for a payroll SaaS looks nothing like one for open-source core banking infrastructure.

---

## Step 2: Understand Who Could Buy This

Cast a wide net. List ALL potential buyer groups before filtering:

- Which industries could use this?
- Which company sizes?
- Which personas make the buying decision?
- Which use cases does the product serve?
- Are there adjacent markets (not just obvious ones)?

The goal is completeness first, filtering later. Don't narrow too early.

**Multi-product companies:** If the company has multiple products (e.g., a banking platform with separate ledger, reconciliation, tracing, workflow and reporting products), different buyer groups may care about different products. The matrix needs a product dimension.

---

## Step 3: Choose the Right Grouping Axes

This is the critical thinking step. The axes of the matrix depend entirely on the company. There is no default.

### How to choose: What makes these buyers DIFFERENT from each other?

Ask: "What is the primary dimension that determines whether a company in this market is a good fit, and how urgently they need this product?"

### Real examples (anonymized)

| Company | Product | Axis 1 (Rows) | Axis 2 (Columns) | Why These Axes |
|--------|---------|---------------|-------------------|----------------|
| **Banking infrastructure company** | Open-source core banking (5 products) | Infrastructure maturity: Already Built It / Building or Struggling / Haven't Built Yet | Vertical: Neobanks, BaaS, Payments, Lending, Crypto, Vertical SaaS, MX Fintechs | Product adoption varies by how far along they are in building their own infra. A company that already built a ledger needs displacement messaging. One that hasn't started needs greenfield messaging |
| **Payroll SaaS** | Colombian payroll SaaS | Payroll complexity: Simple Payroll / Payroll is Breaking | Industry: Restaurantes, Seguridad Privada, Hoteleria, Retail, Manufactura, Logistica, BPOs, Salud | Fit is determined by payroll complexity. A 10-person restaurant has no pain. A 200+ location chain with variable comp, shifts, and regulatory exposure is drowning |
| **B2B fintech** | Argentine B2B fintech (payments, collections, FX) | Bank frustration: Happy with bank / Frustrated but stuck / Already exploring alternatives | Business type: B2B Services, E-commerce, Cash-heavy, Startups, Profesionales, Contadores, PyMEs Industriales | Switching intent varies by frustration with current bank. Happy companies won't switch. Frustrated ones need a push. Explorers need a comparison |

### Other possible axes

- **By product**: Which of our products fits which buyer group (when products serve distinct markets)
- **By use case**: Different ways the product gets used (e.g., "compliance reporting" vs "operational visibility" vs "developer tooling")
- **By geography**: When market dynamics differ significantly (US vs LatAm vs EU)
- **By company stage**: Seed / Series A-B / Growth / Enterprise (when buying behavior correlates with stage)
- **By existing solution**: Using a competitor / Built in-house / Using nothing (displacement vs greenfield messaging)

### Rules for good axes

- **Observable**: You can detect which segment a company belongs to using available data. "Frustrated with their vendor" is NOT observable. "Hiring infrastructure engineers and has 50-200 employees" IS observable
- **Mutually exclusive**: A company should clearly fit one cell, not multiple
- **Actionable**: Each segment implies a different outreach strategy, message angle, or product positioning
- **Sufficient volume**: Each segment must contain enough companies to build workflows around (hundreds to thousands, not dozens)

---

## Step 4: Fill Each Cell

For each cell in the matrix, define:

### Target Definition (REQUIRED)
Specific, factual, observable criteria. NOT vague descriptions of pain.

**Good**: "Multi-location restaurant chains, 50-500+ employees across 5-50+ locations. Variable comp: tips, shifts, overtime, holiday premiums. Multiple cost centers per location. Payroll = 25-40% of revenue."

**Bad**: "Companies that are frustrated with their payroll system and need better software."

The test: Could a sales rep read this and know exactly which companies qualify? Could a Clay operator build filters for this?

### Company Examples (REQUIRED)
REAL company names. Researched. Verified. Not "companies like X."

- Use web search to find actual companies matching the target definition
- Name 5-15 companies per cell (more for high-priority cells)
- For LatAm markets: digital footprint is weaker, some cells may need fewer examples. That's OK, acknowledge it honestly
- **NEVER hallucinate company names.** If you can't verify a company exists and fits, don't include it

### Product/Angle (REQUIRED for multi-product companies)
Which product leads for this cell and why. For single-product companies, the angle changes per cell instead.

- Products 1 (Lead): The product most likely to get the foot in the door
- Products 2 (Upsell): The natural next sale after the lead product proves value
- These are HYPOTHESES to validate with stakeholders, not decisions

### Priority Assessment
- Is this cell high, medium, or low priority?
- If low priority, say so explicitly and say why (small TAM, no signal density, no product fit)
- If high priority, explain the product-market fit

---

## Step 5: Map Signals (Matrix 2)

**Only after Matrix 1 is built and priority cells are selected.**

For each priority cell, identify signals that indicate a company is ready to buy RIGHT NOW.

### The Iron Law Forcing Question

> **"Could I send this to a Clay operator RIGHT NOW with zero ambiguity?"**

Every signal must specify:
- **Exact signal**: What observable event are we detecting?
- **Exact data source**: URL, API endpoint, or tool name
- **Clay access method**: Which Clay enrichment action, how many credits, what fields returned
- **Key filters**: Keywords, date ranges, geographic constraints
- **Volume estimate**: Hundreds? Thousands? Per month or per query?

If you can't name the exact data source, you can't include the signal.

### Universal vs Niche-Specific Signals

**Universal signals** work across multiple niches with keyword swaps. Build once, replicate across segments:

| Signal | Data Source | Clay Action | Notes |
|--------|-----------|-------------|-------|
| **Hiring for specific roles** | Apollo via Clay "Discover Jobs" | Filter by title keywords + target domains | HIGHEST VOLUME. Keywords change per niche. Proven across every market |
| **New leadership** | Apollo via Clay "Find Person" + job change tracking | Filter by title + start date < 90 days | New leaders evaluate tools in first 90 days |
| **Fundraising** | Crunchbase via Clay "Find Organization" | Filter by industry + round + date | **Only for VC-backed markets.** Useless for Colombian mid-market, bootstrap companies |
| **Headcount growth >20-25%** | Apollo via Clay "Enrich Company" | Monthly snapshots, delta comparison | Scaling = infrastructure strain |
| **Technographics** | BuiltWith via Clay "Find Technology Stack" | Detect specific tools on web-facing stack | **COMPOUND signal only.** BuiltWith can't detect backend tools. Must pair with hiring or leadership signal |
| **GitHub/OSS evaluation** | GitHub API via Clay HTTP | Stargazers/forks on target repos + employer match | Only for open-source products |
| **Content/intent** | Company blog RSS via Clay HTTP | Keyword monitoring on known blog URLs | Partial coverage. Requires known URLs upfront |

**Niche-specific signals** use data sources unique to one industry. Modular additions per niche:

| Signal Type | Examples | Data Source |
|-------------|----------|-----------|
| Government registries | FDIC enforcement (US banking), OCC charters (crypto), SuperVigilancia (Colombian security), CNBV (Mexican fintech), RUES (Colombian branches) | Clay HTTP scrape of public registry pages |
| Physical-world signals | Google Maps location count (restaurants, retail, clinics) | Google Places API via Clay HTTP |
| Public procurement | SECOP II (Colombia), TED Europa (EU) | Clay HTTP scrape |
| Industry directories | ABFintechs (Brazil), BCB IF.data (Brazil financial institutions) | Clay HTTP or direct API |
| Licensing events | NMLS new licenses (US money transmitters), state business registrations | Clay HTTP scrape |

### The Compounding Insight

Most signals are universal. For the banking infrastructure company, 9 of 10 signals were the same Clay build across Neobanks and Crypto. Only the niche-specific signal changed (FDIC.gov for neobanks, OCC.gov for crypto). For the payroll SaaS, 7 of 13 signals were universal across Restaurantes and Seguridad Privada.

What changes between niches:
- **Keywords** in the Clay filters (different job titles, different industry terms)
- **Product routing** (same signal, different product pitched)
- **Message angle** (same structure, different pain language)
- **Niche-specific signal** (unique data source per vertical)

This is the "build once, validate many" principle. Show stakeholders how one Clay build becomes workflows across multiple niches.

### Signal Scoring (Optional)

When comparing signals, score on three dimensions:
- **IS (Intent Signal strength)**: 1-10. How strongly does this signal indicate buying intent?
- **B (Buildability)**: 1-10. How easily can this be built in Clay?
- **W (WOW factor)**: 1-10. How impressed will stakeholders be when they see this working?
- Total: /30

Used for prioritization when you have more signal ideas than workflow capacity.

---

## Signals That Usually DON'T Work (Learned the Hard Way)

- **Fundraising in non-VC markets**: Colombian mid-market, bootstrap companies, SMBs. No VC ecosystem means Crunchbase returns nothing. A mid-market restaurant chain's CFO isn't on Crunchbase
- **Content/intent on LinkedIn in LatAm**: Low volume. Colombian CFOs don't post about Reforma Laboral. US playbook doesn't translate
- **Technographics for backend tools**: BuiltWith can't detect payroll software, internal ERPs, backend APIs, or custody infrastructure. Only works for web-facing tech
- **Franchise announcements**: Low volume, hard to scrape reliably. Nice in theory, not enough throughput
- **Signals that require manual research**: If it can't be programmatically accessed, it's not a workflow. It's a one-time list build

---

## Market-Specific Data Realities

### US Market
Rich digital footprint. Standard B2B SaaS outbound playbook works:
- Crunchbase, Apollo, BuiltWith, GitHub, SEC EDGAR, FDIC, OCC, NMLS
- LinkedIn enrichment highly reliable
- Job board data abundant (Indeed, LinkedIn, Greenhouse, Lever)

### Colombian Market
WEAK digital footprint. 90% of accounting software lacks APIs. CRM adoption low. BuiltWith useless for most industries:
- Need physical-world signals: Google Maps location counts, RUES branch registrations, government registries (SuperVigilancia), public procurement (SECOP II)
- LinkedIn enrichment for contacts still works but company-level data is thin
- The CFO or owner defending every peso is the buyer persona for cost-focused products

### Argentine Market
Similar to Colombia but with additional data sources:
- ARCA/AFIP public records (tax status changes), BCRA Central de Deudores, Boletín Oficial (new incorporations)
- BuiltWith usable for e-commerce (Tiendanube, VTEX are detectable)
- LinkedIn works for contacts

### European Market (DACH, etc.)
GDPR constraints on enrichment. Different data sources:
- German job boards (Indeed.de, Stepstone), government registries (Bundesanzeiger/Handelsregister), EU tender system (TED Europa)
- LinkedIn works but enrichment tools may have compliance limitations

---

## Matrix 3: Workflow Tracker (Template)

Once Matrix 2 signals are validated, pre-fill a tracker with one row per workflow:

| Column | Description |
|--------|------------|
| W # | Workflow number |
| Status | Building / Live / Paused / Planned |
| Workflow Name | Descriptive name |
| Mother Intent | Primary signal |
| Campaigns | Number of campaigns under this workflow |
| Campaign Status | Per-campaign status |
| Launch Date | When campaign went live |
| Campaign Name | Specific campaign name |
| Persona | Target persona for this campaign |
| Industry | Target niche |
| Company Size | Size filter |
| Enrichment 1-5 | Secondary enrichment layers |
| Channel | Email / LinkedIn / Both |
| # Iteration | Copy iteration count |
| Changelog | What changed per iteration |
| Clay URL | Link to Clay table |
| Copy URL | Link to copy doc |
| Total Leads | Leads loaded |
| Steps | Email steps in sequence |
| Total Emails | Emails sent |
| Progress | % through the list |
| Bounce | Bounce rate |

---

## Quality Checklist (Before Any Matrix Ships)

- [ ] Every company name is real and researched
- [ ] Every data source is specific (URL, tool name, Clay action)
- [ ] Every workflow passed the Iron Law forcing question
- [ ] Universal vs Niche-Specific correctly categorized
- [ ] The angle is in the buyer's language, not marketing speak
- [ ] A Clay operator could start building within 10 minutes of reading this
- [ ] No generic data sources ("LinkedIn data," "public databases")
- [ ] No signals that require manual research (not programmatically accessible)
- [ ] Signals indicate TIMING, not just static company attributes
- [ ] Target definitions are observable and filterable, not vague pain descriptions
- [ ] Matrix is framed as work-in-progress, not final deliverable

---

## Guardrails (From Real Corrections)

- **Matrix is a work-in-progress.** Never present it as a final deliverable. It gets validated and refined in strategy sessions with stakeholders
- **Don't hallucinate company names.** If web search returns nothing for a cell, say so. Ask the team. Use "Requires Clay research with these filters: [...]" as placeholder
- **Don't diagnose gaps.** Guess their SITUATION, not their problems. "With the AE team growing" not "your pipeline is broken"
- **Don't raise topics nobody asked about.** If they didn't mention IP concerns, don't bring up IP
- **Don't overload the matrix with noise.** The matrices are for strategic alignment. Operational details (enrichment layers, routing matrices, copy) come later in the campaign-copy skill
- **Signal-led workflows must start with the signal, then ICP filter.** Don't build ICP-first lists and then look for signals. The signal IS the trigger
- **Universal signals are universal but the angle is NOT.** Same data source, same Clay build, but the message, product, and positioning change per niche. That's the value
- **Physical-world signals are alpha in weak-data markets.** Google Maps delta for restaurant chains, SuperVigilancia for security companies. These are competitive advantages because no one else is monitoring them programmatically
- **If a signal looked good on paper but doesn't work, kill it.** Document why in the framework. Fundraising for Colombian mid-market is dead. Content/intent where buyers don't post is dead. Don't keep trying

---

## Cross-References

- `knowledge-base/playbooks/workflow-anatomy.md`, Full Mother Intent Catalog with 40+ intents and data sources
- `knowledge-base/playbooks/copy-frameworks.md`, Signal stacking and conditional waterfall routing for copy
- `knowledge-base/playbooks/copy-iron-laws.md`, Quality rules for campaigns
