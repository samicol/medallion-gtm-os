# Workflow Anatomy

How outbound workflows are structured, from mother intent to campaign execution.

## The Workflow Structure

Every workflow has four layers:

```
┌─────────────────────────────────────────────────────┐
│  MOTHER INTENT                                       │
│  The primary signal that defines the workflow        │
│  Example: "Companies hiring GTM Engineers"           │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│  ICP FILTER                                          │
│  Firmographic qualification                          │
│  Size, geography, industry, stage                    │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│  SECONDARY ENRICHMENTS (2-4 signals)                 │
│  Additional context that routes the narrative        │
│  Tech stack, team composition, funding, leadership   │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│  NARRATIVE ROUTING                                   │
│  Message adaptation based on signal combination      │
│  Different paths = different copy angles             │
└─────────────────────────────────────────────────────┘
```

## Layer 1: Mother Intent

The mother intent is the **primary signal** that defines what the workflow is looking for. It answers: "Why would this company be relevant right now?"

### Mother Intent Catalog

Below is the complete list of mother intents we can build. Items marked with ⭐ are the ones most commonly built.

#### Hiring & Team Composition

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ Hiring specific roles | Companies posting jobs for target personas | Clay "Find Jobs at Company", LinkedIn Jobs via Apify, Indeed via Apify, Job Boards via n8n or Instant Data Scraper | Consider industry-specific job boards for relevance |
| Hiring offshore | Companies hiring remote/international | Job boards with location filters | - |
| ⭐ Have/don't have specific team | Companies with or without a department | Clay enrichment, Apollo, Prospeo | - |
| Have/don't have team offshore | Distributed vs centralized teams | Clay enrichment, Apollo | - |
| ⭐ New hires in target dept | Recent additions to relevant teams | Clay "Find People" enrichment, Apollo, Prospeo | - |

#### Leadership & People Movement

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ New leadership (past 90/180 days) | Recent C-suite or VP appointments | Clay "Find People" enrichment filtering by title + start date, Apollo, Prospeo | - |
| New target persona promotion | Internal promotions to decision-maker roles | Clay "Find People" enrichment, Apollo | - |
| ⭐ Champion/user migration | Past buyers who moved to new companies | CRM export + Clay People Enrichment | Only for past customers who moved; don't combine with other intents |

#### Funding & Growth

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ Companies fundraising (pre-announcement) | SEC Form D filings before press | SEC EDGAR via n8n scrape, Crunchbase via Clay, PitchBook via Clay | **Only use when prospect sells to tech startups** - other industries don't raise as much |
| ⭐ Companies in hypergrowth (headcount) | 25%+ headcount growth in 6 months | Clay "Company Headcount" enrichment, Apollo headcount, Prospeo headcount | - |
| ⭐ Companies in hypergrowth (hiring velocity) | Multiple open roles simultaneously | Clay "Find Jobs" + job count aggregation, Apollo headcount growth | - |
| Recently Incorporated Businesses | Scrape companies recently incorporated in the US | - | Not all States |
| Founders in Stealth Mode | Founders in or recently out of Stealth Company | Clay "Find People" → search for founders at Stealth Company | - |

#### Technology & Competitive

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ Companies using specific software | Technographic signals | BuiltWith, Bloomberry, Clay via Sumble or HG Insights | **Must verify tech is detectable** in BuiltWith/Bloomberry first |
| Competitor customers | Companies using competing products | Technographic scrape, BuiltWith, job posts mentioning competitor tools | Does not count toward mother intent coverage |
| Closed lost reactivation | Past opportunities that didn't close | CRM data | - |

#### Events & Engagement

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ Companies attending an event | Conference registrations, attendee lists | Event platforms, Apify scrapers | - |
| Companies sponsoring an event | Event sponsors (higher budget signal) | Event websites, Instant Data Scraper | - |
| ⭐ LinkedIn content engagement | People engaging with relevant content | LinkedIn (1st or 3rd party) | - |

#### Intent Signals

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| ⭐ Website visitors | Individual traffic deanonymization | RB2B | **US companies with 20k+ monthly visitors only** for individual-level |
| ⭐ Lookalike of customers | Companies similar to existing customers | Clay lookalike, enrichment | - |
| Website content mentions | Companies mentioning specific things (PLG, Enterprise) | Website scraping via Apify or Instant Data Scraper | - |
| Regulatory changes | Companies affected by new regulations | News, industry sources | - |
| New product launches | Companies launching new products/features | Press, Product Hunt | - |

#### Network & Relationships

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| LinkedIn 1st degree connections | Enriching and reaching existing network | LinkedIn export | - |
| University Alumni | Get ICP personas that went to same college as your founder or sender | LinkedIn Sales Nav / Clay | Can also target non-ICP personas for intros |

#### Recruiting

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| Candidate Outreach | Talent sourcing + outbound campaign to recruit candidates | Prospeo, Apollo, Clay, Sales Nav | Just for companies that need to source candidates |

#### General

| Intent | Description | Data Source | Notes |
|--------|-------------|-------------|-------|
| Niche-specific play | Niche-specific workflow tailored to a unique market | - | - |
| Mass sending campaigns | High-volume campaign sends | - | - |

### Choosing a Mother Intent

Good mother intents have:
- **Clear buying signal** - Why this matters to them NOW
- **Sufficient volume** - Enough prospects to sustain campaigns
- **Data availability** - Can reliably detect the signal
- **Natural narrative** - Easy to reference in outreach

### Adapting to Your Company

The catalog above is comprehensive but not every intent works for every company. Selection depends on:

- **Your product/service** - What triggers make someone need it?
- **Target persona** - What changes in their world matter?
- **Sales cycle** - Long cycles need earlier signals
- **Data access** - Can we reliably detect this signal?
- **Volume requirements** - Do you need 100 or 10,000 prospects/month?

## Layer 2: ICP Filter

Firmographic qualification applied to ensure prospects match your target market (`context/icp/icp.md`).

### Example ICP Filters

Every company defines its own ICP. Here's an example:

| Filter | Example Value | Notes |
|--------|---------------|-------|
| Employee Count | 10-250 | Varies by company |
| Geography | US, CA, UK, DE, etc. | Based on your market |
| Industry | B2B SaaS | Company-specific |
| Stage | Late Seed / Series A | Company-specific |

### ICP + Intent: Two Approaches

ICP filtering can be applied **before or after** the mother intent:

**Approach 1: ICP First → Intent**
- Start with a pre-qualified list of accounts that match ICP
- Then search for intent signals within that list
- Use when: You have a defined target account list

**Approach 2: Intent First → ICP**
- Search for companies showing the intent signal
- Then filter to only those matching ICP
- Use when: Casting a wide net for signals

Both approaches work. The choice depends on whether you're starting from a target account list or from a signal search.

## Layer 3: Secondary Enrichments

This is the **secret sauce**. Secondary enrichments reveal the company's actual situation so we can craft highly relevant messages.

### The Signal Stacking Principle

We stack 2-4 secondary signals on top of the mother intent. Each signal adds context that helps route the narrative.

**Rule**: Don't stack so many signals that you end up with 1 prospect from 1000. Find the balance between relevance and volume.

### Common Secondary Enrichments

| Enrichment | What It Reveals | Use In Narrative |
|------------|-----------------|------------------|
| Team composition | Who they have/don't have | "From what I can see, there's no X on your team yet" |
| Tech stack | What tools they use | "You're spending $X on Y, but..." |
| Funding status | Recent capital raised | "With your recent round, you're probably..." |
| Leadership tenure | How long in role | "Since you joined as CRO 3 months ago..." |
| Hiring patterns | What else they're hiring | "You're hiring for X AND Y, which tells me..." |
| Competitor usage | Use competitor product | "Companies moving from X to us typically..." |

### Example: Full Signal Stack

**Mother Intent**: Companies hiring GTM Engineers

**Secondary Enrichments**:
1. No existing GTM Engineers (first hire)
2. Uses Clay (tech stack)
3. Has RevOps team (team composition)
4. New CRO in last 6 months (leadership change)

**Resulting Narrative**:
> "Laura, you're spending at least $800 on Clay's Pro Plan, but from what I can see, there are no GTM engineers on your team yet. Who's building your Clay workflows to make the most out of those 50k Clay credits? Maybe someone from your RevOps team?"

Each signal earned its place in the message.

## Layer 4: Narrative Routing

Based on signal combinations, we route prospects to different message templates.

### Routing Logic

```
IF has_signal(Clay) AND NOT has_signal(GTM_Engineers):
    → Route to "Clay without GTME" template

IF has_signal(New_Leadership) AND has_signal(Funding):
    → Route to "New leader + capital" template

IF has_signal(Hiring_Remote):
    → Route to "Remote hiring" angle
ELSE:
    → Route to "In-person hiring" angle
```

### Template Variables

Each route has a template with placeholders:
- `{{company_name}}`
- `{{first_name}}`
- `{{signal_specific_line}}` - The line that references their specific situation
- `{{social_proof}}` - Relevant case study or reference

---

## Workflow → Campaign Relationship

### One Workflow, Multiple Campaigns

A single workflow can spawn multiple campaigns:

```
Workflow: Companies Hiring GTM Engineers
├── Campaign 1: Hiring remote GTMEs (targeting distributed companies)
├── Campaign 2: Hiring in SF (targeting Bay Area companies)
├── Campaign 3: First GTME hire (no existing GTMEs)
└── Campaign 4: Expanding GTME team (already has GTMEs)
```

### Campaign Iterations

Each campaign gets iterated to improve results:

| Iteration Type | What Changes | Example |
|----------------|--------------|---------|
| Copy angle | Different narrative hook | "Building Clay workflows" vs "Scaling outbound" |
| Enrichment layer | Add/remove secondary signals | Add "uses Instantly" signal |
| Data source | Where prospects come from | LinkedIn jobs → Indeed → Wellfound |
| Sequence structure | Email cadence/steps | 3-step vs 5-step sequence |

**Key insight**: The core workflow stays constant. Iterations are lightweight because the infrastructure is already built.

### Campaign Naming Convention

```
{Workflow Name} - {Angle/Segment} - {Version}

Examples:
- Hiring GTMEs - Remote First - v1
- Hiring GTMEs - Remote First - v2 (new copy)
- Hiring GTMEs - Bay Area - v1
- Hiring GTMEs - First Hire - v1
```

---

## Periodicity

How often to run each workflow depends on signal velocity.

### Periodicity Matrix

| Signal Type | Velocity | Run Frequency | Example |
|-------------|----------|---------------|---------|
| Job postings | High | Weekly | Companies hiring |
| Funding announcements | Medium | Bi-weekly | Recently funded |
| Tech adoption | Medium | Monthly | New Clay users |
| Leadership changes | Low | Monthly | New CROs |
| Hypergrowth | Low | Quarterly | 25%+ growth in 6mo |

### Deduplication

When running workflows repeatedly:
- Track prospects already contacted
- Suppress for X days after outreach
- Allow re-entry if new signal detected

---

## Building a New Workflow

### Step 1: Define Mother Intent
- What signal indicates buying intent?
- Is data available and reliable?
- What's the expected volume?

### Step 2: Configure ICP Filters
- Apply your ICP criteria (`context/icp/icp.md`)
- Test volume at each filter stage

### Step 3: Select Secondary Enrichments
- What additional context would make outreach more relevant?
- Prioritize signals that:
  - Are detectable at scale
  - Create natural narrative hooks
  - Don't over-filter volume

### Step 4: Design Narrative Routes
- Map signal combinations to copy templates
- Write templates with signal-specific lines
- Create fallback for prospects without secondary signals

### Step 5: Set Periodicity
- Determine signal velocity
- Set run schedule
- Configure deduplication rules

### Step 6: Document
- Save the workflow spec with `/build-workflow-spec` (`output/campaigns/<workflow-slug>/workflow-spec.md`)
- Include all columns, enrichments, and routing logic

---

## Quality Checklist

Before launching a workflow:

- [ ] Mother intent has clear buying signal
- [ ] ICP filters match your target market
- [ ] 2-4 secondary enrichments selected (not more)
- [ ] Narrative routing creates distinct, relevant messages
- [ ] Expected volume is sustainable (not too low)
- [ ] Periodicity matches signal velocity
- [ ] Documentation complete for handoff
