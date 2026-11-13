# Clay Expert Knowledge Base

The comprehensive reference for Clay mastery, GTM engineering methodology, and industry context. This document makes the agent operationally useful for all Clay-related work.

Last updated: 2026-02-16 (v3: corrected HTTP API, ZeroBounce, signal-first workflow guidance, updated Mother Intent implementations)

---

**Companion file**: See [`iron-laws.md`](iron-laws.md) for the non-negotiable rules we follow every time we work in Clay.

## Table of Contents

1. [Platform Mastery](#1-platform-mastery)
   - [Clay University Course Map](#10-clay-university-course-map)
   - [Core Concepts](#11-core-concepts)
   - [Tables & Data Structures](#12-tables--data-structures)
   - [Enrichment & Data Providers](#13-enrichment--data-providers)
   - [Waterfall Enrichment](#14-waterfall-enrichment)
   - [Claygent & AI Features](#15-claygent--ai-features)
   - [Formulas & Data Transformation](#16-formulas--data-transformation)
   - [HTTP API & Custom Integrations](#17-http-api--custom-integrations)
   - [Webhooks](#18-webhooks)
   - [Signals & Intent Monitoring](#19-signals--intent-monitoring)
   - [Chrome Extension & Web Scraping](#110-chrome-extension--web-scraping)
   - [CRM Integrations](#111-crm-integrations)
   - [Email Platform Integrations](#112-email-platform-integrations)
   - [Credits & Pricing](#113-credits--pricing)
   - [Platform Limitations](#114-platform-limitations)
   - [Latest Features (2025-2026)](#115-latest-features-2025-2026)
2. [GTM Engineering Methodology](#2-gtm-engineering-methodology)
   - [The 4-Layer Workflow Architecture](#21-the-4-layer-workflow-architecture)
   - [Mother Intent Catalog](#22-mother-intent-catalog)
   - [ICP Filtering](#23-icp-filtering)
   - [Signal Stacking](#24-signal-stacking)
   - [Narrative Routing](#25-narrative-routing)
   - [Workflow-Campaign Hierarchy](#26-workflow-campaign-hierarchy)
   - [Periodicity & Scheduling](#27-periodicity--scheduling)
   - [Deduplication & Suppression](#28-deduplication--suppression)
   - [Documentation Workflow](#29-documentation-workflow)
   - [GTM Alpha](#210-gtm-alpha)
   - [Email Finding Waterfall](#211-email-finding-waterfall)
   - [Building a New Workflow](#212-building-a-new-workflow)
   - [Reporting & Tracking](#213-reporting--tracking)
   - [Client Delivery Model](#214-client-delivery-model)
3. [Industry Context](#3-industry-context)
   - [GTM Engineering Landscape](#31-gtm-engineering-landscape)
   - [AI GTM Evolution](#32-ai-gtm-evolution)
   - [Clay's Market Position](#33-clays-market-position)
   - [Competitors & Alternatives](#34-competitors--alternatives)
   - [Industry Trends](#35-industry-trends)
   - [Communities & Resources](#36-communities--resources)
   - [Notable Creators & Thought Leaders](#37-notable-creators--thought-leaders)

---

# 1. Platform Mastery

## 1.0 Clay University Course Map

Clay University (university.clay.com) offers 9 structured courses. Reference these when recommending learning paths.

| Course | Lessons | Duration | Focus |
|--------|---------|----------|-------|
| **Clay 101: GTM Automation** | 17 | ~2h | FETE framework, finding companies/people, enrichments, Claygent, formulas, export to CRM |
| **Limitless Research** | 7 | ~35m | Web scraping, Claygent, Chrome Extension, Apify, ZenRows, prompt engineering |
| **AI-Powered GTM Automation** | 18 | ~1.5h | FETC framework for AI, AI-driven discovery, Claygent last-mile, Perplexity, financial filings, AI classifications, Twain sequences |
| **Automated Outbound** | 16 | ~2h | Company/people waterfalls, AI formulas, Claygent 11-prompt research, AI snippets, 24 copy prompts, SmartLead, HeyReach, Clay Sequencer |
| **Signals & ABM** | 7 | ~40m | Signal types, setup, custom signals, multi-signal scoring, ClayBM (ABM), ad intelligence |
| **CRM Enrichment** | 7 | ~30m | CRM import, HubSpot/Salesforce actions, data freshness, enrichment, action on enriched data |
| **Automated Inbound** | 10 | ~1h | Inbound sources, enrichment stack, lead scoring, lead routing, web intent (15m deep dive), messaging |
| **TAM Sourcing** | 7 | ~40m | ICP definition, TAM workflows, advanced techniques, SMB sourcing, third-party scrapers |
| **HG Insights in Clay** | - | - | Enterprise technology intelligence |

### Key Lessons to Reference

- **"11 AI Prompts to Automate Prospect Research with Claygent"** (20m, Automated Outbound): Core Claygent prompt patterns
- **"We Made 24 Prompts So You Don't Have To"** (3m, Automated Outbound): Ready-to-use copy prompts
- **"Best Practices To Maximize Your Credits"** (6m, AI-Powered GTM): Credit optimization
- **"Deep Dive: Web Intent"** (15m, Automated Inbound): Website visitor identification
- **"Building Custom Signals in Clay"** (6m, Signals & ABM): Custom signal creation
- **"Deep Dive: Clay Sequencer"** (12m, Automated Outbound): Native email sequencing

### Documentation Hub (docs.clay.com)

| Collection | Articles | Key Topics |
|------------|----------|------------|
| Integrations & Enrichments | 296 | Every provider's setup, configuration, and use cases |
| Get Started | 13 | Platform basics, first table, first enrichment |
| Edit and Format a Table | 14 | Column types, views, filtering, sorting |
| AI, Formulas, and Other Tools | 10 | Claygent, formulas, lead scoring, formatters |
| Credits, Plans, & Billing | 14 | Credit system, pricing, conservation |
| Account & Settings | 7 | Workspace, team, permissions |
| Signals and Triggers | 7 | Web intent, job changes, hiring, news, custom signals |

---

## 1.1 Core Concepts

### The FETE Framework

Clay's fundamental workflow methodology:

1. **Find**: Discover companies/people using 130+ built-in data sources or import your own (CSV, CRM, webhook, API)
2. **Enrich**: Expand data using waterfalls, AI research (Claygent), web scraping, and 150+ integration providers
3. **Transform**: Use formulas, AI, and conditional logic to clean, format, score, and generate personalized copy
4. **Export**: Push enriched data to CRMs, email sequencers, Google Sheets, or downstream systems

**Evolution**: The FETC framework ("Fetch") replaces "Export" with "Create" to emphasize AI-generated outreach content as a core output, not just data export.

### Key Terminology

| Term | Definition |
|------|-----------|
| **Table** | Core data structure (spreadsheet-like). Contains rows (records) and columns (enrichments/transforms) |
| **Workbook** | Container for related tables. Can hold multiple tables with linked relationships |
| **Enrichment** | Adding data to a record from an external provider (e.g., finding email from LinkedIn URL) |
| **Waterfall** | Sequential search across multiple providers until valid data is found |
| **Claygent** | Clay's AI research agent that can browse the web and answer questions about companies/people |
| **Sculptor** | Clay's AI assistant that helps build tables, write formulas, and configure enrichments |
| **Formula** | JavaScript/FormulaJS expression for data transformation within a column |
| **Source** | Where data enters a table (import, webhook, built-in search, API) |
| **Column** | A data field or enrichment step in a table. Can be static data, enrichment, formula, or AI |
| **View Graph** | Visual representation of relationships between linked tables |
| **Group Column** | Reusable column templates that can be saved and applied across tables |

---

## 1.2 Tables & Data Structures

### Table Types

- **Company Table**: Rows represent companies. Built-in fields for domain, name, industry, size
- **People Table**: Rows represent individuals. Built-in fields for name, title, email, LinkedIn
- **Custom Table**: Flexible structure for any data type

### Data Sources (Finding)

Clay can source data from:

**Built-in searches:**
- Find Companies (by industry, size, location, technology, etc.)
- Find People at Company (by title, department, seniority)
- Find Jobs at Company (current openings)
- Company Headcount (growth tracking)
- Lookalike Companies (similar to seed list)

**Imports:**
- CSV upload
- CRM sync (HubSpot, Salesforce)
- Webhook (auto-receive data from external apps)
- HTTP API as Source (import from any API endpoint)
- Chrome Extension (scrape lists from any webpage)
- Copy/paste from spreadsheets

### Table Features

- **Auto-dedupe**: Prevents duplicate records based on configurable keys
- **Auto-updates**: Scheduled re-enrichment on defined cadence
- **Auto-delete**: Remove rows that don't meet criteria after enrichment
- **Linked tables**: Relate records across tables (companies ↔ people)
- **Saved Searches**: Save and reuse filter criteria
- **Column Progress Bar**: Visual breakdown of row status (success, running, failed, pending)

---

## 1.3 Enrichment & Data Providers

### Provider Ecosystem

Clay aggregates **150+ premium data providers** into one platform. Instead of subscribing to each individually, you access them all through Clay credits.

### Enrichment Categories

**Company Data:**
| Provider | Best For | Notes |
|----------|----------|-------|
| Apollo | Company firmographics, employee count | Large database, good coverage |
| Clearbit | Company enrichment, technographics | High accuracy for tech companies |
| People Data Labs | Company and people data | Broad coverage |
| Crunchbase | Funding, investors, financial data | Best for VC-backed companies |
| PitchBook | Detailed financial/investment data | Premium data source |
| BuiltWith | Technology stack detection | Detects web technologies |
| HG Insights | Enterprise tech stack | Better for enterprise software detection |
| Bloomberry | Technology detection | Alternative to BuiltWith |
| Sumble | Technology detection | Another tech detection option |

**People & Contact Data:**
| Provider | Best For | Notes |
|----------|----------|-------|
| Prospeo | Email finding | Recommended default first choice |
| Icypeas | Email finding | Second in waterfall |
| Leadmagic | Email finding + validation | Third in waterfall |
| Findymail | Email finding | Fourth in waterfall |
| Apollo | Contact database lookup | Large people database |
| Hunter | Email finding | Domain-based email search |
| Snov.io | Email finding + outreach | Combined data + sending |
| Bounceban | Email validation | Recommended primary validation tool |

**Technographic Data:**
| Provider | Best For | Notes |
|----------|----------|-------|
| BuiltWith | Web technology detection | Frontend frameworks, analytics, CMS |
| HG Insights | Enterprise software detection | Better for installed software vs web tech |
| Bloomberry | Technology signals | Community-sourced tech signals |
| Sumble | Technology signals | Broader tech detection |

**Intent & Signal Data:**
| Provider | Best For | Notes |
|----------|----------|-------|
| 6sense | Account intent scoring | Enterprise intent platform |
| Bombora | Topic-level intent | B2B intent data |
| Demandbase | ABM intent signals | Account-based platform |
| RB2B | Website visitor identification | US companies with 20K+ monthly visitors only |
| Clay Signals | Job changes, hiring | Native Clay feature |

### Full Provider Catalog (97+ enrichment integrations)

Key providers by category (from Clay's enrichment docs):

**Email Finding**: Prospeo, Icypeas, Findymail, DropContact, Hunter, Snov.io, SignalHire, Leadmagic, Nimbler, Enrichley, Enrow, Wiza, LeadIQ, FullEnrich, SureConnect, SMARTe, Swordfish, Reverse Contact, Bytemine
**Email Validation**: Bounceban, Debounce, NeverBounce, EmailBison, Listmint, ZeroBounce (outdated, most teams have moved away from it)
**Company Data**: Apollo, Crunchbase, PitchBook, Dealroom, Owler, Harmonic.ai, HitHorizons, Firmable, Store Leads, Ocean.io
**Technology Detection**: BuiltWith, HG Insights, TheirStack, SimilarWeb, Sumble, Semrush, SerpStat
**People Data**: Apollo, Wiza, Lusha, Nimbler, LeadIQ, SMARTe, Swordfish, Loxo, ContactOut, Surfe, LiveData, Upcell, Trestle
**Intent & Signals**: Madkudu, PredictLeads, Intellizence, Forager, Identity Matrix
**Social/Content**: X.com, Instagram, Reddit, LinkedIn (professional posts), YouTube, Hacker News, Loom
**AI/Research**: Perplexity, Claygent, Oakie.ai, Minerva
**Creative**: Twain (AI copywriting), SendSpark (video), Tavus (video), ElevenLabs (voice), Sendspark
**Maps/Location**: Mapbox, Google Maps, Yelp, Google Shopping
**CRM/Export**: HubSpot, Salesforce, Marketo, ActiveCampaign, Stripe, Notion, Google Docs, Google Slides
**Translation**: Google Translate, DeepL

### Credit Costs (Approximate)

| Action | Credits | Notes |
|--------|---------|-------|
| Free actions | 0 | Data cleaning, formatting, basic formulas |
| Basic enrichment | 1-2 | Simple data lookups |
| Email finding | 2-3 | Per provider in waterfall (per successful match) |
| Company enrichment | 1-3 | Firmographic data |
| Claygent research | 5-25 | Depends on complexity and model |
| Phone number finding | 3-10 | More expensive than email, restricted to higher tiers |
| Technographic lookup | 2-5 | Per provider |
| Web intent | ~0.008/IP | Per IP enriched, 30-day caching prevents duplicate charges |
| Full prospect enrichment | 8-12 | Email + phone + LinkedIn + company data (optimized) |
| Comprehensive profile build | 15-25 | Full enrichment with AI research |
| Failed lookups | Refunded | Credits returned when no data found |

> **Rule**: The majority of Clay actions are either free or cost 1-2 credits. Advanced AI research is the most expensive category. Full enrichment per prospect typically costs 8-12 credits when optimized.

---

## 1.4 Waterfall Enrichment

### How It Works

Waterfall enrichment is Clay's signature feature. It searches **sequentially** across multiple providers until finding valid data:

```
Provider 1 (Primary) → Found? → Use it ✓
    ↓ Not found
Provider 2 (Secondary) → Found? → Use it ✓
    ↓ Not found
Provider 3 (Tertiary) → Found? → Use it ✓
    ↓ Not found
Provider 4 (Fallback) → Found? → Use it ✓
    ↓ Not found
→ No data available ✗
```

### Key Properties

- **Pay only for what you find**: Failed lookups get credits refunded
- **2x coverage increase**: Waterfall doubled email coverage in testing: 40% (single provider) → 78% (waterfall) (Source: Hackceleration 2026 review)
- **Validation step**: Always add a validation step (e.g., Bounceban) after the waterfall to catch bad emails
- **Stops on first match**: Once valid data is found, remaining providers are skipped (saves credits)
- **Reusable templates** (2025): Save waterfall configurations as templates for reuse across tables

### Best Practices

**Email finding waterfall (recommended default order):**
1. Prospeo (highest accuracy for our use cases)
2. Icypeas (good secondary coverage, from 0.1 credits)
3. Leadmagic (includes validation)
4. Findymail (broadest database fallback)

**Waterfall optimization for credits:**
- Put the **most accurate** provider first (fewer false positives = fewer wasted credits)
- Put the **cheapest** provider as fallback
- Limit waterfall depth to 3-4 providers (diminishing returns after that)
- Use validation gates between enrichment steps to catch bad data early
- Use conditional runs to skip enrichment on rows that don't meet criteria
- Use boolean formulas to check if enrichment has finished before triggering dependent enrichments (from Clay docs: "use a boolean formula to check if an enrichment has finished, then use that in a conditional formula to control when another enrichment runs")

**When to use waterfall vs single provider:**
- **Waterfall**: Email finding, phone numbers, any contact data where coverage matters
- **Single provider**: Company data where one source is definitive (e.g., Crunchbase for funding data)

### Hybrid Stack Approach (Advanced Credit Optimization)

For teams processing 5,000+ leads/month, a hybrid approach cuts costs by ~90% (Source: Ziellab):

| Approach | Credits/Lead | Monthly (10K Leads) |
|----------|-------------|-------------------|
| Pure Clay (complex) | ~30 | $3,000-$5,000 |
| Hybrid stack | ~3 | $300-$700 |

**The hybrid pattern:**
1. **n8n** handles orchestration (self-hosted = free, or $20/month cloud)
2. **Apify** handles email finding first (~$0.001-0.01/action, ~98% success rate)
3. **Direct Anthropic API** handles AI tasks ($3/M input tokens vs Clay credit overhead)
4. **Clay** handles edge cases, presentation, CRM sync, and light enrichment

**When to use hybrid**: 5K+ monthly leads, complex multi-step AI workflows, budget-sensitive teams
**When pure Clay works**: <1,000 monthly leads, simple enrichments, non-technical teams, rapid prototyping

---

## 1.5 Claygent & AI Features

### Claygent Overview

Claygent is Clay's AI research agent. It can:
- Browse and analyze websites
- Research companies and people
- Find specific information (office locations, certifications, pricing, podcast appearances)
- Answer structured questions about any entity
- Extract data from complex web pages

### Model Options & TPM Requirements

| Model | Best For | Cost | TPM Requirement |
|-------|----------|------|-----------------|
| **Clay Neon** | Data extraction, formatting into structured columns | Lowest | - |
| **GPT-4** | Deep reasoning, complex research | Medium | 30,000 TPM (any paid tier) |
| **Claude** | Nuanced analysis, longer context | Medium | Tier 4+ (≥400,000 TPM) for Claygent |
| **GPT-5** (2026) | Latest OpenAI capabilities | Higher | - |
| **Gemini 3 Pro** (Q1 2026) | Google's model, Flash only for Claygent | Higher | Tier 2 (Gemini 2.0 Flash only) |

**AI Tokens**: Tokens are ~3-4 characters each. A 100-word passage ≈ 125-135 tokens. Input tokens (prompts) and output tokens (responses) are tracked separately. Configure max output length in model settings to manage costs.

**BYOK (Bring Your Own Key)**: Connect your own OpenAI, Anthropic, or Gemini API keys to potentially reduce costs. Clay handles tier management automatically with its own keys. With personal keys, monitor usage independently via each provider's dashboard.

### Prompt Engineering for Claygent

**Structure prompts for best results:**

```
Role: You are a research analyst.
Task: Find [specific data point] for [entity].
Context: [What you already know about the entity]
Output format: [Exactly how you want the answer]
Fallback: If you cannot find [X], return "Not found"
```

**Best practices (from Clay docs + creators):**
- Be specific about what you want: "Find the CEO's name" not "Tell me about the company"
- Specify output format: "Return as JSON: {name, title, email}" or "Return only the number"
- Include fallback instructions: Tell Claygent what to return when data isn't available
- Use binary search approach: Have Claygent progressively narrow its search
- Start with the company website: Give Claygent the domain to search first
- Use the **Generate tab** (recommended): Describe your task in plain English → Clay builds the column setup, optimized prompt, recommended model, and output fields
- Use the **Configure tab** for advanced manual control

**The 11 Core Claygent Research Prompts** (from Clay University's Automated Outbound course, 20-minute lesson):
These are the foundational Claygent prompts for automated prospect research. Each one targets a specific research task that feeds into personalization:
1. Company mission/focus area
2. Target personas/who they sell to
3. Product/service descriptions
4. Recent news and announcements
5. Team structure and key hires
6. Technology stack indicators
7. Competitive landscape
8. Growth signals (hiring, funding)
9. Content and thought leadership
10. Industry-specific data points
11. Custom research based on campaign angle

**24 Ready-to-Use AI Personalization Prompts** (from Clay blog + University):

*Single-message prompts:*
1. Company mission → "I was on your company page and it looks like the mission..."
2. Target personas → Find job titles the company sells to
3. Job focus → "As the [Title], I'd imagine you focus on..."
4. News summary → "I saw the recent news article about..."
5. Job opening as problem → "I saw your company was hiring for [Title]. This means you're trying to improve..."
6. B2B vs B2C classification → Output "B2B" or "B2C"
7. Content summary → "I saw your post about..."
8. SaaS identification → Return true/false
9. Hiring rationale → Link job openings to company mission

*Multi-step prompts:*
10. Previous company news → Reference their former employer's achievements
11. Job title cleaning → Standardize messy titles
12. Product use-case ideas → 3 creative campaign ideas with relevant job titles
13. Job tenure analysis → How long in role/industry
14. Local restaurant reference → Yelp scrape for personal touch
15. Technology stack → BuiltWith data reference
16. Role start date → "I noticed you've been the [title] since [date]..."
17. Graduation year → Connect to industry events
18. Company phone → Reference attempted call
19. Employee headcount → Reference in breakup emails
20. Profile keywords → Search for relevant mentions
21. Podcast appearances → ListenNotes search
22. Blog post reference → Summarize their writing
23. College connection → Low-effort attention hack
24. Experience level → Reference profile experience count

### Claygent Builder (2025+)

Workspace-level tool for designing, testing, and versioning AI agents:

**Creation process:**
1. Navigate to `Claygents` → `+ Create Agent` from Clay home
2. Select preferred AI model
3. Draft prompt logic using variables in the editor
4. Test with sample cases by clicking `+ Add Test Case`
5. Save with access to version history for comparisons

**Key features:**
- **Test cases**: First 5 rows are free. Standard runs follow normal billing
- **Version control**: Compare and restore previous saved versions
- **Workspace-level deployment**: Agents are reusable across all tables (not siloed per table)
- **Permissions**: Editors create/modify agents; viewers can reference approved agents

**Agent types you can create:**
- ICP qualification agents that score LinkedIn profiles for outreach
- Cold email composition agents that gather params, research, and draft personalized outreach
- Email timing agents that pull CRM data and score account readiness

### AI Formula Generation

Clay uses **Clayscript**, a JavaScript-based language that evaluates expressions row-by-row.

**AI-powered formula generator:**
1. Enter transformation instructions using `/` to insert column references
2. Click "Generate formula" for AI creation

**Example prompts for the generator:**
- "Extract the domain from /Email"
- "Use /LinkedIn URL if available; otherwise use /LinkedIn Profile.url"
- "Extract text after @ in /Twitter Handle"
- "Split /city by comma, keep content before first comma, remove 'Area'"
- "Calculate days between /Created Date and /Closed Date"

**Available tools in formulas:**
- JavaScript standard objects: `Math`, `String`, `Array`, `Date`, `RegExp`, `Number`, `Object`
- **Lodash** via `_` for advanced data manipulation
- **Moment.js** via `moment` for date/time operations
- **FormulaJS** for spreadsheet functions like `VLOOKUP`, `IF`, `SUM`, `CONCATENATE`

**Draft without running**: Select "Save and don't run enrichments" to edit formulas without triggering credit-consuming operations. Outdated enrichment columns appear greyed out.

### Sandbox Mode (Pro and Enterprise)

Test enrichments, formulas, and waterfalls without burning credits on full data:

- **Auto-duplicates top 10 rows** as sample data (expandable to 50)
- **Add rows**: Next top rows, random selection, or manual pick from "All data" tab
- **Outbound actions disabled**: All exports, Write to Other Table, etc. automatically blocked
- **Can still test**: Formulas, waterfalls, enrichments on sample rows
- **Publish options**: "Publish" (sync config only) or "Publish and run" (sync + run all rows)

> **Credit saving**: Always build and test in sandbox mode before running on full tables.

### Metaprompter (Enhanced 2025)

AI-assisted prompt writing that suggests:
- Which AI model to use for the task
- Optimal prompt structure
- JSON output formats for structured data
- "Metaprompter-first" experience (August 2025) makes this the default AI setup flow

---

## 1.6 Formulas & Data Transformation

### Available Libraries

Clay formulas support:

**FormulaJS**: Spreadsheet functions:
- `IF(condition, then, else)`: Conditional logic
- `VLOOKUP(value, range, col)`: Lookup values
- `CONCATENATE(a, b, c)`: Join strings
- `SUM()`, `AVERAGE()`, `COUNT()`: Aggregation
- `LEFT()`, `RIGHT()`, `MID()`: String extraction
- `UPPER()`, `LOWER()`, `PROPER()`: Case formatting
- `TRIM()`, `CLEAN()`: Text cleaning
- `IFERROR(expression, fallback)`: Error handling
- `REGEXMATCH()`, `REGEXEXTRACT()`: Pattern matching

**Standard JavaScript:**
- String methods: `.includes()`, `.replace()`, `.split()`, `.trim()`
- Array methods: `.map()`, `.filter()`, `.reduce()`, `.join()`
- Math: `Math.round()`, `Math.max()`, `Math.min()`
- Date: `new Date()`, date arithmetic
- RegExp: `/pattern/.test(string)`, `.match()`
- Number: `parseInt()`, `parseFloat()`
- Object: `Object.keys()`, `Object.values()`

**Lodash** (via `_`):
- `_.get(obj, 'path.to.value', default)`: Safe deep access
- `_.compact(array)`: Remove falsy values
- `_.uniq(array)`: Deduplicate
- `_.flatten(array)`: Flatten nested arrays
- `_.groupBy(array, key)`: Group by property
- `_.sortBy(array, key)`: Sort
- `_.pick(obj, keys)`: Select specific keys
- `_.omit(obj, keys)`: Remove specific keys

**Moment.js**: Date/time operations:
- `moment().format('YYYY-MM-DD')`: Format dates
- `moment().diff(date, 'days')`: Date differences
- `moment().subtract(90, 'days')`: Date arithmetic
- `moment(date).isAfter(other)`: Date comparison

### Column Referencing

Reference other columns in formulas using double curly braces:
```
{{Email}}           → Value of the "Email" column for current row
{{Company Name}}    → Value of the "Company Name" column
{{Enrichment.email}} → Nested value from enrichment result
```

### Common Formula Recipes

**Domain extraction from URL:**
```javascript
{{Website}}.replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0]
```

**Name cleaning (remove titles/suffixes):**
```javascript
{{Full Name}}.replace(/\b(Mr|Mrs|Ms|Dr|Jr|Sr|III|II|IV)\b\.?/gi, '').trim()
```

**Conditional enrichment routing:**
```javascript
IF({{Employee Count}} > 50, "Enterprise", IF({{Employee Count}} > 10, "Mid-Market", "SMB"))
```

**Check for specific technology:**
```javascript
{{Technologies}}.toLowerCase().includes("clay") ? "Uses Clay" : "No Clay"
```

**Date-based filtering:**
```javascript
moment({{Start Date}}).isAfter(moment().subtract(90, 'days')) ? "Recent" : "Old"
```

**LinkedIn URL to profile ID:**
```javascript
{{LinkedIn URL}}.replace(/.*linkedin\.com\/in\//, '').replace(/\/.*/, '')
```

### Lead Scoring in Clay

Three scoring types (from Clay docs):

1. **Customer/Account Fit Scoring**: Alignment with ICP based on company size, industry, tech stack
2. **Lead/Account Engagement Scoring**: Email responses, website visits, event participation
3. **Lead Grade**: Combines fit + engagement for comprehensive assessment

**Setup (3 steps):**
1. Add Formula column
2. Use Formula Generator for scoring logic (number-based, grade-based, or binary fit criteria)
3. Verify and save

**Combine multiple fields for personalization:**
```javascript
IF({{Uses Clay}} && {{No GTM Engineers}},
  `${{{First Name}}}, you're spending at least $800 on Clay's Pro Plan, but I noticed you don't have GTM engineers on your team yet.`,
  IF({{Recent Funding}},
    `${{{First Name}}}, with your recent ${{{Funding Amount}}} round, you're probably investing in growth...`,
    `${{{First Name}}}, I noticed ${{{Company Name}}} is ${{{Signal}}}.`
  )
)
```

---

## 1.7 HTTP API & Custom Integrations

### What It Does

Connect Clay to **any service with a web API**: if it has an API, Clay can talk to it.

### Two Modes

1. **Enrichment**: Add data to existing records by calling an external API for each row
2. **Source**: Pull a list of records from an API to create/populate a table

### Configuration

**Setup approaches:**
- **Generate tab**: AI-assisted (Sculptor helps configure the API call)
- **Configure tab**: Manual setup with endpoint, headers, params, body

**Supported methods:** GET, POST, PUT, DELETE

**Requirements:** Explorer plan or higher ($349+/month)

### HTTP API AI Autofill (2026)

Configure APIs using natural language:
- Describe what you want to fetch
- Clay generates the API configuration
- Review and apply

### Common HTTP API Use Cases

- Pull data from internal systems not natively supported
- Query custom databases or data warehouses
- Call AI APIs (Claude, GPT) for custom processing
- Integrate with niche industry data providers
- Connect to government databases (SEC EDGAR, state registries)

### What HTTP API is NOT

**The HTTP API is NOT a web scraper.** It calls structured API endpoints that return JSON/XML data. You cannot use it to scrape job boards (LinkedIn, Indeed, Glassdoor) because those sites don't have public APIs returning structured hiring data. For scraping unstructured web pages, use Apify or the Chrome Extension instead.

### Important Note

**Clay does NOT have a public API for programmatic access to Clay itself.** You cannot create tables, add rows, or run enrichments via API. The HTTP API feature is for Clay to call *external* APIs, not for external systems to call Clay. Enterprise plans have a REST API for some operations.

---

## 1.8 Webhooks

### Inbound Webhooks

Auto-receive data from other apps via HTTP POST:
- Each table can have a webhook URL
- Data arrives as JSON
- Tables update instantly when data is received
- **Limit**: 50,000 submissions per webhook (then create a new one)
- **Enterprise**: Auto-delete/passthrough tables enable unlimited submissions

### Common Webhook Sources

- RB2B (website visitor data)
- Workflow IO (LinkedIn engagement data)
- n8n (automation triggers)
- Zapier/Make (workflow automation)
- Custom applications
- CRM webhooks (HubSpot, Salesforce)

### Webhook + n8n Pattern

n8n can both send to and receive from Clay:
- **n8n → Clay**: n8n webhook sends data to Clay table for enrichment
- **Clay → n8n**: Clay exports/webhooks trigger n8n workflows for downstream processing

---

## 1.9 Signals & Intent Monitoring

### Clay Signals (Native Feature)

Monitor and detect changes across your target accounts. Access via `+ Add` → `Custom signal` in workbooks, or `Actions` → `Import` → `Custom signal` in tables.

**Pre-Built Signal Types (from Clay docs):**

| Signal | What It Monitors | Clay Docs URL |
|--------|-----------------|---------------|
| **Job Changes** | Contacts moving to new organizations | `/docs/job-change-signal-overview` |
| **New Hires** | Recent hires at target companies | `/docs/new-hire-signal-overview` |
| **Promotions** | Role advancement within current companies | `/docs/promotion-signal-overview` |
| **News & Fundraising** | Significant events at monitored companies | `/docs/monitor-for-news-fundraising` |
| **LinkedIn Brand Mentions** | Company mentions and feedback | `/docs/monitor-for-linkedin-brand-mentions` |
| **Web Intent** | Website visitor identification | `/docs/website-tracking` |
| **Custom Signals** | Any data source change on schedule | `/docs/custom-signals` |

### Web Intent (Website Visitor Identification)

**Setup process:**
1. Go to account settings → `Web intent` → `Add connection`
2. Copy tracking snippet → install via direct HTML, Google Tag Manager, or Twilio Segment
3. Configure de-anonymization providers (Clay provides defaults)
4. Add filters (countries, page paths with wildcards like `/blog*`)
5. Toggle "Connection enabled" → In workbook, select `Web intent` source

**Key details:**
- **Identifies companies** (domains), not individual people
- **Pricing**: ~$0.008 per IP enriched, 30-day caching prevents duplicate charges
- **Data captured**: Pages visited, session duration, traffic sources, UTM parameters, referrers
- **Delay**: Up to 30 minutes (sessions must complete before display)
- **Cost reduction tips**: Set minimum session duration (20-30 seconds), require 2+ unique pages visited
- **Scale**: Supports hundreds of thousands of daily visitors (enterprise)

### Custom Signals (Build Your Own)

Create signals to monitor any data source for changes:
- Monitor technology adoption, hiring profiles, feature rollouts
- Track compliance changes (e.g., GDPR trust center updates)
- Set up RSS feeds for web mentions
- Schedule automated AI-powered runs for unique signal creation

**Configuration:**
1. Select data source (each shows credit cost per result)
2. Configure the source (some require your API key, others use Clay's)
3. Set monitoring frequency
4. Optionally add enrichments (Slack notifications, Salesforce updates)

**Advanced: Converting Enrichments to Signals (4-table workflow):**
1. Table 1: Scheduled enrichment runs with change detection
2. Table 2: Run history tracking
3. Table 3: Lookup + AI to identify differences between runs
4. Table 4: Signal results with timestamps

### Signal Velocity

Signals move at different speeds. This determines how often to check:

| Signal Type | Velocity | Check Frequency |
|-------------|----------|-----------------|
| Job postings | High | Weekly |
| Job changes | Medium-High | Weekly-Biweekly |
| Funding rounds | Medium | Biweekly-Monthly |
| Tech adoption | Medium | Monthly |
| Leadership changes | Low | Monthly |
| Headcount growth | Low | Quarterly |

### Intent Data Integration

Clay integrates with enterprise intent providers:
- **6sense**: Account intent scoring
- **Bombora**: Topic-level intent data
- **Demandbase**: ABM intent signals
- **Madkudu**: Predictive lead scoring
- **TrustRadius** (2025): Buying intent signals from review activity

**Pattern**: Pull intent scores → set rules (e.g., intent surge + pricing page visit = High Priority) → trigger alerts or auto-progress accounts.

---

## 1.10 Chrome Extension & Web Scraping

### Chrome Extension

**Visual web scraping without code:**
1. Navigate to any webpage with a list (directory, team page, search results)
2. Click the Clay Chrome Extension icon
3. Click two items in the list to define what to scrape
4. Clay auto-detects the pattern and extracts all items
5. Export as CSV, copy to clipboard, or add directly to Clay workspace

**Best for:**
- Conference attendee lists
- Company directory pages
- Job board listings
- Team/About pages
- Product catalogs
- Search results

**After scraping:** Enrich with 150+ data providers directly in Clay workspace.

---

## 1.11 CRM Integrations

### HubSpot (Native, Bidirectional)

**Actions available:**
- Lookup contacts, companies, deals
- Create new records
- Update existing records
- Sync data both directions
- Trigger workflows based on CRM changes

### Salesforce (Native, Bidirectional)

Similar capabilities to HubSpot integration.

### Other CRMs

- PipeDrive
- Close
- Copper

### CRM Enrichment Pattern (from Clay University CRM Enrichment course)

```
CRM → Import to Clay → Enrich missing data → Validate → Push back to CRM
```

**Clay University CRM Enrichment course (7 lessons):**
1. Intro to CRM Enrichment: fundamentals
2. Importing from your CRM: extraction techniques
3. Clay x HubSpot Actions: specific HubSpot workflows
4. Clay x Salesforce Actions: specific Salesforce workflows
5. Enriching your CRM Data: augmenting incomplete records
6. Keeping your CRM data fresh: automated refresh cycles
7. Taking action on enriched CRM data: converting to outcomes

**Key capabilities**: Data normalization, deduplication automation, bidirectional sync, continuous refresh automation.

> **Patrick Spychalski's take**: "CRM data cleaning is the biggest missed opportunity for most companies." Clean CRM data is the foundation for all GTM success. Prioritize it before exotic outbound tactics.

---

## 1.12 Email Platform Integrations

### Supported Platforms

| Platform | Integration Type | Notes |
|----------|-----------------|-------|
| **Instantly** | Native export | Recommended primary sending platform |
| **Smartlead** | Native export | Alternative for some clients |
| **Lemlist** | Native export | When LinkedIn automation needed |
| **Mailshake** | Native export | Alternative |
| **HubSpot Sequencer** | Native (2026) | New integration |

### Export Pattern

```
Clay Table → Filter qualified rows → Map fields → Export to sending platform
```

Fields typically mapped:
- Email address
- First name, last name
- Company name
- Personalization variables (signal-specific lines)
- Custom fields for campaign segmentation

---

## 1.13 Credits & Pricing

### Credit Philosophy

**Pay only for what you use.** Failed lookups get credits refunded.

### What's Free

- Data cleaning and formatting (formulas)
- Basic data transformations
- Table management (filtering, sorting, deduplication)
- CSV imports
- Manual data entry

### What Costs Credits

- Enrichment from data providers
- Claygent AI research
- Phone number lookups
- Email finding
- Technology detection
- Company/people data lookups

### Pricing Tiers (2026)

| Plan | Price/Month | Credits/Month | Key Features |
|------|-------------|---------------|--------------|
| **Starter** | $149 | 2,000 | Basic enrichment, tables |
| **Explorer** | $349 | 10,000 | HTTP API access, more integrations |
| **Pro** | $800 | 50,000 | Advanced features, higher limits |
| **Enterprise** | Custom | Custom | REST API, unlimited webhooks, white-glove support |

### Credit Management

- **Rollover**: Unused credits accumulate (capped at 2x monthly limit)
- **Credit spend limits** (2026): Set maximum spend per import/enrichment to prevent accidents
- **Credit warnings**: Estimated costs shown before importing/running enrichments
- **Table Credit Usage Dashboard**: Track usage by time period and column
- **Calculator**: https://www.clay.com/credits-calculator

### Cost Optimization Strategies (from Clay docs + community)

**Official Clay Credit Conservation Guide** (university.clay.com/docs/clay-credit-conservation):

1. **Disable auto-update during setup**: Turn off auto-update while building your table. Turn it on only when ready to launch. Access via Run Settings or table menu → "Auto-Update Columns"
2. **Leverage your own API keys (BYOK)**: If you have paid subscriptions with data providers (OpenAI, Anthropic, Apollo, etc.), integrate your own keys. Saves 60-75% on AI processing
3. **Qualify leads before enriching**: Filter contacts early using conditional runs or AI formulas based on location, company size, industry. Only qualified contacts get enriched
4. **Test small before full runs**: Begin with ~10 rows to identify errors and refine prompts. Fix errors in advance before committing to full enrichments
5. **Implement conditional runs**: Use "Only run if" feature in Run Settings to limit enrichments to relevant rows only, or use filtered views
6. **Reuse existing data**: Use Lookup columns to pull previously enriched data from CRM or other Clay tables. Avoid duplicate enrichments
7. **Use Sandbox Mode**: Pro/Enterprise: Test on 10-50 sample rows without burning credits on full data
8. **Order waterfall by accuracy**: Best provider first = fewer providers called per row
9. **Use free columns first**: Formulas and data cleaning are free; do those before paid enrichments
10. **Set credit spend limits** (2026): Prevent accidental overuse on large imports
11. **Monitor the usage dashboard**: Identify which columns/enrichments consume most credits
12. **Use Clay Neon for simple tasks**: Cheapest AI model; save GPT-4/Claude for complex research
13. **Use Recipes**: Pre-configured enrichment sequences that combine multiple steps efficiently

---

## 1.14 Platform Limitations

**No native email sending:**
- Clay enriches and prepares data; sending requires external platforms (Instantly, Smartlead, Lemlist)
- No email warm-up or deliverability tools built in

**No public API to Clay itself:**
- Can't programmatically create tables, add rows, or run enrichments from external code
- Enterprise plans have limited REST API access
- The HTTP API feature is for Clay calling *out* to external APIs

**Webhook submission limits:**
- 50,000 submissions per webhook (then create new webhook)
- Enterprise: auto-delete/passthrough tables for unlimited

**Credit complexity:**
- Advanced workflows can burn credits quickly if not managed
- UX doesn't always make costs clear before running
- Per-lead enrichment costs add up at scale

**Performance:**
- Some enrichments take time to complete (especially Claygent)
- Large tables (10K+ rows) can be slow to manipulate
- Scheduled enrichments have execution time limits

**Learning curve:**
- Powerful but complex: requires 5-6 hours to master advanced features (Source: Hackceleration 2026 review)
- Not self-explanatory for non-technical users
- Credit costs unpredictable for new users: easy to waste credits on poorly configured sequences
- Recommended for teams processing 200+ prospects monthly; simpler tools (Apollo) better for low volume

**Will Breton's 1-Month Learning Plan** (1,000+ hours in Clay):
- Week 1: Copy to learn, rebuild flows from top creators (Eric, Patrick, Nathan, Tim)
- Week 2: Build basic enrichment workflows
- Week 3: Master formulas and conditional logic
- Week 4: Advanced waterfalls, Claygent, and integrations

---

## 1.15 Latest Features (2025-2026)

### Full Changelog (from clay.com/changelog)

**February 2026**
- Sendoso integration for automated gifting workflows
- BuyerCaddy Technographics (90,000+ technologies)
- Increased results for Find Contacts and Find Jobs
- LinkedIn Monitoring Enhancement (reactions/comments)
- Twain Custom Variables (up to 10 per outreach)
- Crunchbase API Key integration
- FullEnrich Mobile Numbers via Clay Credits
- CSV bulk enrichment for enterprise-scale workflows

**January 2026**
- **Clay in Claude**: Clay as a connector in Claude for end-to-end GTM workflows
- **Clay in ChatGPT**: Find people and enrich contacts in ChatGPT conversations
- **Gemini 3 Pro** model support
- **Credit spend limits**: Set spending caps on workbooks
- Better credit warnings (estimated costs before importing)
- **Column Progress Bar**: Visual breakdown of row status
- **HTTP API as Source**: Import data from any API endpoint
- Saved Searches for People, Companies, Jobs
- Resource tagging with custom labels
- SOQL queries for Salesforce imports
- **22x faster enrichment, 10x faster AI processing**
- HubSpot Sequencer enrollment capability
- Optional OAuth scopes for access control
- Better table keyboard shortcuts, bulk copy/paste, pattern fill, undo/redo

**December 2025**
- Sumble Technographics (live job posting data)
- Gong Engage flow actions
- EmailBison integration (premium deliverability)
- Listmint email verification
- Microsoft Teams OAuth

**November 2025**
- Bulk enrichment without row limits
- Web Intent company de-anonymization
- Google Slides image integration
- Snov.io email and domain actions
- HG Insights software category filtering

**October 2025**
- Surfe EMEA data (300M+ profiles)
- Rox agent platform integration
- Salesforge email sequencing
- TheirStack job posting intelligence

**September 2025**
- HG Insights Corporate Hierarchy mapping
- Minerva cost-effective profile enrichment
- Enrich Job action for tech stack extraction

**August 2025**
- **$100M Series C** at $3.1B valuation (CapitalG)
- **Claygent Navigator**: web automation capabilities
- **Metaprompter-First AI Experience**
- **Icypeas** integration (from 0.1 credits)
- Twain 3.0 AI sequence generation
- Autobound 300+ AI insights
- B2D Developer Profile Discovery

**July 2025**
- **Slack approval workflows** for enrichments
- **AI-augmented company search filters**
- **Visual workflow builder** for complex automation
- Natural language company search
- The Org integration (hierarchy mapping)
- Ad Intel advertising spend analysis
- Identity Matrix hashed email identification

**June 2025**
- **Sandbox Mode**: Test without credit burn
- AI troubleshooting and debugging
- Table-aware enrichment suggestions
- Inter-table data routing
- Natural language formula column references
- Dealroom investor intelligence

**May 2025**
- TrustRadius buying intent signals
- Ocean IO people lookalikes
- AI semantic integration search
- AI image generation at scale
- Google Slides personalized deck creation
- SMARTe data provider

**April 2025**
- **Signals hub** for centralized tracking
- Gong call transcripts
- LinkedIn official API brand monitoring
- Marketo CRM integration

**March 2025**
- Webflow landing page personalization
- Reddit brand monitoring
- **Waterfall templates** for reuse
- The Swarm warm introduction network
- Credit usage reporting dashboard
- Claude Sonnet and Gemini 2.0 model options

**February 2025**
- **Scheduled columns and sources**: Auto-run enrichments
- **Group column templates**: Reusable column configurations
- **Enhanced Metaprompter**: AI model suggestions
- Email waterfall from social profiles
- HeyGen avatar video generation, ElevenLabs voiceovers

**January 2025**
- SimilarWeb website analytics
- Enhanced people search filtering
- Better Contact verified data
- Natural language YouTube search
- AI-assisted API configuration

---

# 2. GTM Engineering Methodology

## 2.1 The 4-Layer Workflow Architecture

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

**This is what differentiates this approach from generic outbound.** Most campaigns do layers 1-2 (intent + ICP). Signal stacking (layers 3-4) is what creates messages that are impossible to ignore.

---

## 2.2 Mother Intent Catalog

The complete list of mother intents you can build, with Clay data source implementations.

### Hiring & Team Composition

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **Hiring specific roles** ⭐ | Clay "Find Jobs" (primary: filter by role title + location), Apify for boards Clay doesn't index | Always start with the signal (the job posting), then qualify companies against ICP |
| **Hiring offshore/Latam** | Clay "Find Jobs" with location filters (e.g., dev roles + Latam locations), Apify for Latam-specific boards (GetOnBoard, Torre.co) | Signal-first: source job postings → extract company → ICP filter (US HQ, right size) → enrich → export |
| **Have/don't have specific team** ⭐ | Clay enrichment, Apollo, Prospeo | Great for "no GTM engineers" angle |
| **Have/don't have team offshore** | Clay "Find People" (dev titles + offshore locations) + Prospeo + Apollo → import to Clay → dedupe on company domain → ICP filter | Multi-source signal detection for broader coverage |
| **New hires in target dept** ⭐ | Clay "Find People" enrichment, Apollo, Prospeo | - |

### Leadership & People Movement

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **New leadership (past 90/180 days)** ⭐ | Clay "Find People" filtering by title + start date | Filter for C-suite/VP appointments |
| New target persona promotion | Clay "Find People", Apollo | Internal promotions to decision-maker roles |
| **Champion/user migration** ⭐ | CRM export + Clay People Enrichment | Only for past clients who moved |

### Funding & Growth

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **Fundraising (pre-announcement)** ⭐ | SEC EDGAR via n8n scrape, Crunchbase via Clay, PitchBook via Clay | **Only when prospect sells to tech startups** |
| **Hypergrowth (headcount)** ⭐ | Clay "Company Headcount" enrichment | 25%+ growth in 6 months |
| **Hypergrowth (hiring velocity)** ⭐ | Clay "Find Jobs" + job count aggregation | Multiple open roles simultaneously |
| Recently incorporated | State registry scraping | Not all states available |
| Founders in stealth | Clay "Find People" → search for founders at "Stealth Company" | - |

### Technology & Competitive

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **Using specific software** ⭐ | BuiltWith, Bloomberry, Clay via Sumble or HG Insights | **Must verify tech is detectable first** |
| Competitor clients | Technographic scrape, BuiltWith, job posts mentioning competitor | Does NOT count toward mother intent coverage |
| Closed lost reactivation | CRM data | - |

### Events & Engagement

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **Attending an event** ⭐ | Event platforms, Apify scrapers | Conference registrations/attendee lists |
| Sponsoring an event | Event websites, Instant Data Scraper | Higher budget signal |
| **LinkedIn content engagement** ⭐ | LinkedIn (1st or 3rd party), Workflow IO | - |

### Intent Signals

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| **Website visitors** ⭐ | RB2B | **US companies with 20K+ monthly visitors only** |
| **Lookalike of clients** ⭐ | Clay lookalike, enrichment | - |
| Website content mentions | Website scraping via Apify or Instant Data Scraper | - |
| Regulatory changes | News, industry sources | - |
| New product launches | Press, Product Hunt | - |

### Network & Relationships

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| LinkedIn 1st degree connections | LinkedIn export → Clay enrichment | - |
| University Alumni | LinkedIn Sales Nav / Clay | Get ICP personas from same college as client; can also target non-ICP personas for intros |

### Recruiting

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| Candidate Outreach | Prospeo, Apollo, Clay, Sales Nav | Just for companies that need to source candidates: talent sourcing + outbound |

### General

| Intent | Clay Implementation | Notes |
|--------|-------------------|-------|
| Niche-specific play | Client-specific | Tailored to a client's unique market niche |
| Mass sending campaigns | - | High-volume campaign sends |

### Choosing a Mother Intent

Good mother intents have:
- **Clear buying signal**: Why this matters to them NOW
- **Sufficient volume**: Enough prospects to sustain campaigns
- **Data availability**: Can reliably detect the signal
- **Natural narrative**: Easy to reference in outreach

---

## 2.3 ICP Filtering

Firmographic qualification applied to ensure prospects match the client's target market.

### Typical ICP Filters

| Filter | Example | Clay Implementation |
|--------|---------|-------------------|
| Employee count | 10-250 | Clay company enrichment |
| Geography | US, CA, UK, DE | Company data |
| Industry | B2B SaaS | Company classification |
| Stage | Late Seed / Series A | Crunchbase/PitchBook via Clay |
| Revenue | $1M-$50M | Company enrichment |
| Tech stack | Uses HubSpot, Clay | BuiltWith, HG Insights |

### Two Approaches: Choose Based on Workflow Type

**Approach 1: ICP First → Intent**
- Start with pre-qualified accounts matching ICP
- Then search for intent signals within that list
- Use when: You have a defined target account list, ABM campaigns, or the signal is expensive to detect

**Approach 2: Intent First → ICP (MANDATORY for signal-led workflows)**
- Search for companies showing the intent signal broadly
- Then filter to only those matching ICP
- Use when: The workflow is driven by a signal (job postings, hiring patterns, job changes, funding)

**Critical rule**: For signal-led workflows, you MUST start with the signal, not the ICP. Starting with ICP and then checking for signals wastes credits on companies that don't have the signal. Example: if you're targeting "companies hiring in Latam," start with Clay Find Jobs (Latam dev roles) → extract companies → then ICP filter. Don't start with US companies and check if they're hiring in Latam. That burns credits on thousands of companies that aren't hiring there.

---

## 2.4 Signal Stacking

The **secret sauce** of these workflows. Stack 2-4 secondary signals on top of the mother intent to create context that routes the narrative.

### Common Secondary Enrichments

| Enrichment | What It Reveals | Narrative Use |
|------------|-----------------|---------------|
| Team composition | Who they have/don't have | "I noticed you don't have X on your team yet" |
| Tech stack | What tools they use | "You're spending $X on Y, but..." |
| Funding status | Recent capital raised | "With your recent round, you're probably..." |
| Leadership tenure | How long in role | "Since you joined as CRO 3 months ago..." |
| Hiring patterns | What else they're hiring | "You're hiring for X AND Y, which tells me..." |
| Competitor usage | Uses competitor product | "Companies moving from X to us typically..." |

### The Golden Example

**Mother Intent**: Companies hiring GTM Engineers

**Secondary Enrichments:**
1. No existing GTM Engineers (first hire) ← team composition
2. Uses Clay (tech stack) ← technographic
3. Has RevOps team (team composition) ← people search
4. New CRO in last 6 months (leadership change) ← people enrichment + date filter

**Resulting Narrative:**
> "Laura, you're spending at least $800 on Clay's Pro Plan, but I noticed you don't have GTM engineers on your team yet. Who's building your Clay workflows to make the most out of those 50k Clay credits? Maybe someone from your RevOps team?"

Each signal earned its place in the message.

### Rules

- **Don't over-filter**: 2-4 secondary enrichments max. More than that kills volume
- **Each signal must earn its place**: If it doesn't change the narrative, drop it
- **Balance relevance vs volume**: Stacking too many signals = 1 prospect from 1,000

---

## 2.5 Narrative Routing

Based on signal combinations, route prospects to different message templates.

### Routing Logic Pattern

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
- `{company_name}`: Company name
- `{person_name}`: Prospect's first name
- `{signal_specific_line}`: The line referencing their specific situation
- `{social_proof}`: Relevant case study or reference

### Implementation in Clay

Use Clay formulas with conditional logic to:
1. Check which signals are present for each row
2. Generate the appropriate personalization line
3. Assign the correct campaign/template tag
4. Export with routing metadata to the sending platform

---

## 2.6 Workflow-Campaign Hierarchy

### One Workflow, Multiple Campaigns

A single workflow spawns multiple campaigns with different angles:

```
Workflow: Companies Hiring GTM Engineers
├── Campaign 1: Hiring remote GTMEs (targeting distributed companies)
├── Campaign 2: Hiring in SF (targeting Bay Area companies)
├── Campaign 3: First GTME hire (no existing GTMEs)
└── Campaign 4: Expanding GTME team (already has GTMEs)
```

### Campaign Iterations

| Iteration Type | What Changes | Example |
|----------------|-------------|---------|
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

## 2.7 Periodicity & Scheduling

### Periodicity by Signal Velocity

| Signal Type | Velocity | Run Frequency | Example |
|-------------|----------|---------------|---------|
| Job postings | High | Weekly | Companies hiring |
| Job changes | Medium-High | Weekly-Biweekly | Champion migration |
| Funding announcements | Medium | Bi-weekly/Monthly | Recently funded |
| Tech adoption | Medium | Monthly | New Clay users |
| Leadership changes | Low | Monthly | New CROs |
| Hypergrowth | Low | Quarterly | 25%+ growth in 6mo |

### Standard Engagement: 6 Workflows in 90 Days

| Period | Focus |
|--------|-------|
| Days 1-14 | Discovery, ICP validation, GTM Alpha identification |
| Days 15-45 | Build workflows 1-3, launch first campaigns |
| Days 46-75 | Build workflows 4-6, iterate existing campaigns |
| Days 76-90 | Optimization, documentation, team enablement |

---

## 2.8 Deduplication & Suppression

When running workflows repeatedly:
- Track prospects already contacted
- Suppress for X days after outreach
- Allow re-entry if new signal detected
- Maintain block lists

### Block List Structure (4 segments)

1. **Active Deals**: Synced from CRM (HubSpot/Salesforce)
2. **Customers**: Current clients, synced from CRM
3. **Competitors**: Manual upload, maintained by client
4. **Manual Uploads**: Ad-hoc exclusions

---

## 2.9 Documentation Workflow

### Sculptor → Client Guide Transformation

Document every workflow for client handoff using this process:

**Step 1: Extract from Sculptor**

Use this exact prompt in Clay Sculptor:
```
Give me a complete technical breakdown of this table. Include:
- The purpose of this table (what it's trying to accomplish)
- All columns with their data types and what they contain
- Every enrichment step, in order, with the source/provider used
- Any formulas or logic (Clay formulas, conditionals, filters)
- How data flows in (source) and out (integrations, webhooks, exports)
- Any Claygent prompts, include the full prompt text
- Dependencies between columns (what feeds what)

Format as structured markdown.
```

**Step 2: Group Columns by Function**

Organize columns into logical step groups:
1. Data Import
2. Data Extraction
3. Name Cleaning
4. Company Normalization
5. Email Finding (waterfall)
6. Email Validation
7. Deduplication
8. Qualification
9. Routing
10. Export

**Step 3: Generate Client-Friendly Documentation**

Transform technical Sculptor output into operational guide using template structure:
- Overview (what the workflow does, in plain English)
- Accessing the workflow (Clay login steps)
- Step-by-step walkthrough (grouped by function, with tips and warnings)
- Quick reference checklist
- Troubleshooting guide

**Key principles:**
- Group columns by function, not column order
- Simplify technical details: clients don't need formula syntax
- Explain the "why": not just "run this column" but "this validates emails to prevent bounces"
- Use Tips (helpful hints) and Warnings (critical information) callouts
- Include screenshot placeholders with clear descriptions

### Automation Tool

You can automate Step 1 with a small Playwright-based script that:
1. Opens Clay table URL
2. Opens Sculptor chat
3. Sends the standard documentation prompt
4. Extracts markdown response
5. Saves to file

---

## 2.10 GTM Alpha

### Definition

**GTM Alpha** is the unique advantage you find in go-to-market to hijack the interest of your target market.

### Three Components

1. **Experimentation**: Testing hypotheses about what resonates
2. **Unique Data**: Using data your competitors don't have access to
3. **Compelling Narratives**: Crafting messages that cut through noise

### Why It Matters

> "Everyone's using Clay. Everyone's sending 'personalized' emails. When everyone has the same tool, the tool isn't the advantage anymore."

**The problem**: Same Clay workflows = commoditized signals. If everyone is finding "companies hiring GTM Engineers" and sending "Hey, I saw you're hiring...", the signal is no longer unique.

**The solution**: GTM Alpha = finding signals, data, or angles that competitors don't have or aren't using. This might be:
- First-party product usage data
- Creative data sources (Slack profiles, forum activity, event attendance)
- Unique signal combinations that create impossible-to-replicate narratives
- Timing advantages (catching signals before competitors)

Every client engagement starts with finding their GTM Alpha.

---

## 2.11 Email Finding Waterfall

### Recommended Default Order

1. **Prospeo**: Primary provider (highest accuracy for our use cases)
2. **Icypeas**: Secondary provider
3. **Leadmagic**: Tertiary (includes validation)
4. **Findymail**: Fallback (broadest database)

### Validation

- **Bounceban**: Recommended primary email validation tool. Run after the waterfall to catch bad emails before export

### Implementation in Clay

Set up as waterfall enrichment column:
1. Configure each provider in sequence
2. Clay automatically tries each until valid email found
3. Built-in validation checks the result
4. Failed lookups get credits refunded
5. Final "Work Email" column merges the first valid result

---

## 2.12 Building a New Workflow

### Step-by-Step Process

1. **Define Mother Intent**: What signal indicates buying intent? Is data available? Expected volume?
2. **Configure ICP Filters**: Apply client's ICP criteria. Test volume at each filter stage
3. **Select Secondary Enrichments**: 2-4 signals that create natural narrative hooks. Don't over-filter
4. **Design Narrative Routes**: Map signal combinations to copy templates. Write signal-specific lines. Create fallback for prospects without secondary signals
5. **Set Periodicity**: Determine signal velocity. Set run schedule. Configure deduplication rules
6. **Document**: Use the documentation workflow to create client-facing guide

### Quality Checklist

Before launching a workflow:
- [ ] Mother intent has clear buying signal
- [ ] ICP filters match client's target market
- [ ] 2-4 secondary enrichments selected (not more)
- [ ] Narrative routing creates distinct, relevant messages
- [ ] Expected volume is sustainable (not too low, not overwhelming)
- [ ] Periodicity matches signal velocity
- [ ] Email finding waterfall configured
- [ ] Deduplication/suppression rules set
- [ ] Block lists updated (active deals, customers, competitors)
- [ ] Documentation complete for client handoff

---

## 2.13 Reporting & Tracking

### Two Dimensions

**Workflow Level** (Strategic): "Are we building the right things?"
- Workflows built vs target (6 in 90 days)
- Workflow health (producing results?)
- Campaign count per workflow

**Campaign Level** (Tactical): "Are we executing well?"
- Emails sent, reply rate, positive replies, meetings booked
- Which angles/iterations are working
- What needs iteration or retirement

### Workflow Status Codes

| Status | Meaning |
|--------|---------|
| Active | Running on schedule, producing results |
| Paused | Temporarily stopped |
| Building | Currently in development |
| Planned | In roadmap, not yet started |
| Retired | No longer relevant |

### Reporting Cadence

| Report | Frequency | Focus |
|--------|-----------|-------|
| Campaign metrics | Daily (async) | Tactical adjustments |
| Weekly review | Weekly | Performance + planning |
| Workflow summary | Bi-weekly | Strategic progress |
| 90-day review | Quarterly | ROI, roadmap planning |

### Data Sources

- Clay tables → workflow/campaign structure
- Instantly/Smartlead/Lemlist → sending metrics (sent, replied, bounced)
- CRM → meetings booked, deals created
- Manual classification → positive reply identification

---

## 2.14 Client Delivery Model

### Done-With-You Model

- Build everything in client's systems (Clay account, CRM, email infrastructure)
- Full transparency and documentation
- Team enablement alongside execution
- Client owns everything: can go solo after engagement

### Scope

**Included**: 6 workflows, campaigns, iterations, documentation, weekly reporting, team training
**Not included** (client responsibility): Tool subscriptions (Clay, Instantly), email infrastructure, data provider credits

### Client Folder Structure

```
{client-name}/
├── .env                    # API keys (NEVER commit)
├── context.md              # Master context file (READ FIRST)
├── onboarding.md           # Onboarding call notes + strategy
├── icp.md                  # ICP definition
├── workflows.md            # Active workflows tracker
├── meetings/               # Call transcripts
├── copy/                   # Messaging assets
│   ├── sequences/          # Email sequences
│   ├── linkedin/           # LinkedIn messages
│   └── templates/          # Reusable templates
├── research/               # Background research
└── .env                    # Client-specific API keys
```

### Engagement Structure

**Strategy & Planning**: GTM Alpha discovery, ICP validation, workflow roadmap
**Build & Launch**: Clay development, email infrastructure, copy, campaign launch
**Operate & Optimize**: Monitoring, iteration, A/B testing, reporting
**Enable & Transfer**: Documentation, team training, process handoff

---

# 3. Industry Context

## 3.1 GTM Engineering Landscape

### The Discipline (2026)

GTM Engineering sits at the intersection of growth, sales operations, and automation. It's a formal engineering discipline that emerged from creative operators using tools like Clay.

**Key statistics (January 2026):**
- 3,000+ GTM Engineer job postings (doubled YoY for 2 consecutive years)
- $160,000 median salary (20% above traditional sales ops)
- ~100 new job listings every month
- Hiring peaks in January and July
- Companies hiring: OpenAI, Anthropic, Cursor, Webflow, Notion, Lovable, Canva, Intercom, Rippling

### GTM Engineer vs Sales Ops vs RevOps

| Dimension | GTM Engineering | Sales Ops / RevOps |
|-----------|----------------|-------------------|
| Core activity | Build systems from scratch | Optimize what exists |
| Technical depth | Write code (Python, SQL, APIs) | Configure tools |
| Mandate | Drive innovation, experimentation | Operational stability |
| Focus | Build the "plumbing" | Process standardization, governance |
| Example task | Build real-time lead routing automation | Set lead routing rules in CRM |

**GTM Engineers drive innovation; RevOps provides stability.**

### Required Skills

- CRM platforms (Salesforce, HubSpot)
- Clay and data enrichment tools
- Marketing automation
- Coding: Python, SQL, JavaScript (38% of postings require SQL and Python)
- API integrations and cloud automation
- Prompt engineering and AI workflow design (mentioned in 2/3 of new roles)

---

## 3.2 AI GTM Evolution

### Current State (2026)

- 90% of companies have implemented AI or plan to in 2026
- 53% of GTM leaders see little to no impact from AI adoption (the gap between experimentation and execution)
- Successful adopters report 3-5x productivity gains and 40-60% cost reductions
- **The shift**: From rep-driven to AI-directed decision making

### Key AI-Powered GTM Motions

**AI SDRs / Agentic Outbound:**
- Automated prospect research (LinkedIn, company websites, news, tech stack)
- Real-time signal detection (job changes, funding, hiring, tech installs)
- First-touch personalization at scale
- Lead scoring and routing based on fit + intent

**Conversational AI Agents:**
- AI-powered voice calling for outbound SDR work
- ElevenLabs, Artisan, Warmly, Smartlead offer AI agent products

**Signal-Based Outreach:**
- Multi-signal monitoring at scale
- Trigger-based campaigns that double conversion rates vs traditional
- 99% of companies report higher ROI after implementing intent data

### The Emerging AI GTM Engineer Role

A specialized role blending:
- RevOps process design
- Prompt engineering
- Data workflow skills
- AI agent orchestration

**Responsibilities**: Architecting bridges between tech stack layers, ensuring AI agents work on right tasks with right data, translating business goals into automated workflows.

---

## 3.3 Clay's Market Position

### Valuation & Growth

- **August 2025**: Raised $100M Series C at $3.1B post-money valuation (more than doubling previous)
- **Investor**: CapitalG (Google's growth equity arm)
- **Community**: 15,000+ members in Clay Slack
- **Customers**: OpenAI, Anthropic, Cursor, Canva, Intercom, Rippling, Webflow, Notion, Lovable

### Positioning

Clay is a **programmable outbound engine** and **GTM automation platform**, distinct from pure data providers. It essentially created the GTM Engineering category.

**Who Clay is for:**
- Lean GTM teams building custom prospecting workflows
- Outbound-focused teams needing personalization at scale
- ABM programs requiring multi-signal account scoring
- GTM engineers who want to build vs buy

### Strategic Advantage

Clay's moat is **extensibility**:
- 150+ data providers aggregated
- HTTP API for connecting to any service
- AI research (Claygent) for unstructured data
- Formula engine for custom transformation
- Integrates with every major CRM, email, and automation platform

---

## 3.4 Competitors & Alternatives

### Direct Competitors

| Platform | Positioning | Pricing | Best For |
|----------|-------------|---------|----------|
| **Apollo.io** | All-in-one with dialer | $49/user/month | Teams wanting to consolidate stack. 80% of Clay capability, 20% complexity |
| **ZoomInfo** | Enterprise proprietary data | $15,000+/year | Enterprise teams needing compliance-grade data. 420M+ contacts, 92% accuracy |
| **Lusha** | Ease of use, instant access | Mid-range | Non-technical teams needing quick contact data |
| **Cognism** | GDPR compliance, European markets | Mid-high range | European market focus, mobile number accuracy |
| **ZoomInfo GTM Studio** (May 2025) | Replicates Clay's functionality | Enterprise | Enterprise teams already on ZoomInfo |

### How Clay Differentiates

**vs Apollo**: Clay is more flexible but requires more skill. Apollo has built-in sequences/calling but less data customization
**vs ZoomInfo**: Clay is more affordable and accessible. ZoomInfo has deeper proprietary data but locked into enterprise contracts
**vs Instantly**: Instantly is for high-volume sending execution. Clay is for data intelligence/enrichment. They're complementary, not competitive

### Where a GTM Engineering Partner Fits in the Ecosystem

A done-with-you GTM engineering partner sits between strategic consulting and fractional GTM engineering:

| Approach | Delivers | A GTM Engineering Partner Delivers |
|----------|---------|------------------|
| Agency (ColdIQ, etc.) | Done-for-you campaigns | In-house system + training |
| Consultant | Strategy docs | Live workflows + implementation |
| Tool (Clay, Apollo) | Software platform | Platform expertise + GTM engineering |
| Freelancer | Tactical execution | Strategic architecture + playbooks |

---

## 3.5 Industry Trends

### Trend 1: Precision Over Volume

The fundamental shift in outbound isn't about sending more. It's about **precision, integration, and systems that scale without sacrificing quality**.

- SDRs achieved 13.3% answered rate with cold calling in 2025 (nearly equal to AEs calling warm contacts at 14.4%)
- Implication: SDRs are reaching the right people at the right time: dialing smarter, not more

### Trend 2: Signal-Based Selling

A GTM strategy built on capturing and acting on buyer signals in real time:

- **Fit signals**: Firmographic/demographic (industry, size, region, title)
- **Intent signals**: What accounts are researching (articles, competitor searches)
- **Behavioral signals**: Website activity (pricing page visits, feature pages)

**Impact:**
- Trigger-based campaigns double conversion rates vs traditional
- Early intent-based outreach increases win rates by 35-50%
- 99% of companies report higher ROI after implementing intent data

### Trend 3: Multi-Channel Outreach

Multi-channel (email + LinkedIn + phone + video) achieves 3.5x higher response rates than email-only.

Effective cadence: 6-8 touchpoints over 2-3 weeks, mixing channels and personalized to buyer signals.

### Trend 4: Stricter Compliance & Deliverability

- AI-driven carrier filtering is hyper-strict
- Spam complaints instantly tank sender reputation
- Domain warming takes weeks, not days
- Caller ID health is critical: ignoring it drops connect rates 40-70%
- Deliverability expertise is now a core GTM engineering competency

### Trend 5: Integration Over Accumulation

Teams pulling ahead have **stopped adding tools and started integrating**:
- Consolidating tools
- Building bridges between platforms (middleware layer)
- Eliminating redundancy
- The future is connected, intelligent, and simple

### Trend 6: Middleware as Critical Layer

Tools like Clay and Zapier sit between CRM and endpoint solutions:
- Enable custom logic without code
- Automate enrichment workflows
- Route signals in real-time
- Connect disparate systems

This layer is where GTM Engineers spend most of their time.

---

## 3.6 Communities & Resources

### Clay Community

- **Clay Slack**: 15,000+ members, 70+ enterprise channels. Join: clay.com/slack
- **Clay University**: 9 courses, cohorts, certifications. university.clay.com
- **Claymation Newsletter**: #1 GTM Engineering newsletter

### GTM Engineering Communities

- **Cargo Community**: #1 community for GTM Engineers. Cohort-based learning, mentorship
- **GTM Engineer School**: Hands-on, expert-led sessions for operators
- **theGTME**: Newsletter, case studies, job board
- **Maven x Clay**: Formal GTM Engineering course

### Events

- **GTM Engineering Summit San Francisco 2026**: Major industry event

### Learning Resources

- **Clay University**: 9 official courses, 96+ lessons, certifications, cohorts. Includes docs hub (369 articles across 7 collections). university.clay.com
- **Clay AI Skills Cohort**: Applications due Feb 27, starts March 11, 2026
- **Clay Bootcamp** (Nathan Lippi): 10-week accelerator, 150+ graduates
- **UnlockClay** (Tim Yakubson): 5-hour intensive course, 50+ testimonials in 2 months
- **ClayMBA**: 30-day mastery program
- **Growth Engine X** (Eric Nowoslawski): Agency-focused training, 53-page outbound document
- **GTM Engineer School** (Patrick Spychalski): Hands-on sessions
- **The Kiln Learn** (thekiln.com/learn): Webinars on creative data sources, LeadMagic integration, HeyReach LinkedIn outreach

---

## 3.7 Notable Creators & Thought Leaders

### Eric Nowoslawski (Growth Engine X)

**Background**: Worked at Clay for a year building the product. Founded Growth Engine X. Sends 1.5M+ cold emails per month across clients. Manages 7,767+ inboxes via Smartlead. Known as "the OG Clay master." Featured in Clay University's training content.

**Core Philosophy**: "The best email you send is the one where you do 10 minutes of research and send a cold email to a prospect. Our goal is to send that same email you would send manually but to send it to your whole market."

**Eric's Cold Email Engine (7-step Clay workflow):**
1. Enrich target accounts with company data, tools used, recent news, open roles
2. Deploy trigger detection rules using available data providers
3. Generate first lines using GPT, prompted for human-sounding single sentences
4. Map each trigger to relevant case study metrics
5. Score prospects combining trigger strength, logo relevance, persona alignment
6. Push enriched data to email sender with personalized fields
7. Sync CRM replies to auto-remove engaged contacts

**Signal Detection Strategy**: Map observable triggers to business outcomes:
- Hiring signals → manual research friction
- Traffic patterns → pipeline urgency
- Technology shifts → replacement opportunities
- Leadership changes → reset operational playbooks
- Funding/launches → growth priorities
- Compliance/expansion → operational needs

**AI Personalization Approach**: "The best way to use AI in a prospecting sequence is to first look at the data, analyze it, make an inference about that data, and then change the way you're doing the copywriting in snippets (not the whole email at once)."

**Follow-Up Sequence**:
- Day 3: 2-4 line teardown of their specific workflow with actionable fix
- Day 7: 3-minute video demonstrating outcomes on similar accounts
- Day 12: Single-line check offering specific playbook

**Key Metrics**: Track positive reply rates (not total replies), meetings per 100 sends, email-to-deal ratio, time-to-meeting per angle, correlation between trigger presence and positive responses.

**Target Client Profile**: ACV above $10K, sales cycles under 6 months, non-commoditized products backed by case studies.

**53-Page Outbound Document**: Eric's comprehensive guide includes 58 anonymized campaigns with metrics, 10 campaign angles, 21 tutorials on common data workflows, 3 high-performing copywriting scripts, list segmentation processes, and email sequencing approaches.

**Offer Angles That Work**: Custom videos, workflow audits, data sprints with qualified lead handoffs, ROI models, pre-written sequences ready to deploy.

### Patrick Spychalski (The Kiln)

**Background**: Co-founded The Kiln (one of the original "Claygencies"). Clay's first marketing contractor when they had 4 employees. Built Clay's early YouTube and LinkedIn presence. Created 100+ YouTube videos for Clay. Generated $100M+ in pipeline for clients. **The Kiln was acquired by 2X** (January 2026). Smartlead Certified Partner.

**Core Philosophy**: "Clients don't pay for crazy. They pay for effective." Prioritizes effectiveness over complexity.

**Patrick's Framework, Offer Over Personalization**:
1. Understand the value proposition deeply: know distinct benefits you actually deliver
2. Identify available offers: what can you realistically provide to prospects
3. Work backwards to find data points: use Clay to locate specific information that quantifies and personalizes benefits for each prospect

> "Rather than obsessing over custom details, successful campaigns prioritize a compelling value proposition that resonates with target audiences."

**Clay's Most Underutilized Use Case**: CRM data cleaning and enrichment. Patrick identifies this as "the biggest missed opportunity for most companies." Clean CRM data underpins all GTM success. Before exotic outbound tactics, prioritize:
- Automated data validation and enrichment
- Removing duplicate and outdated records
- Enriching existing contacts with missing information

**The Viral Lovable Integration**: Built a campaign using Lovable's API (vibe-coding platform) programmatically within Clay to generate custom web apps for each prospect at scale. This demonstrates building functional applications through natural language for enterprise outreach.

**Creative Data Sources, Slack Profile Reverse Engineering**:
In a webinar with Fabian Herhold, Patrick demonstrated scraping Slack communities to:
- Extract profile pictures and names from relevant Slack groups
- Reverse engineer LinkedIn profiles from Slack profile data
- Enrich with emails via Clay waterfall
- Result: 40% increase in response rates from this creative data sourcing

**Credit Engineering (BYOK)**: Patrick's cost-reduction technique using strategic API key configurations reduced Clay project costs from $60,000 to $7,000-$10,000 for one client, essentially recovering the client's investment. "If you're not using API keys in Clay, you're doing it wrong."

**"Avengers Assembly" System Design**: Rather than forcing single-platform solutions, identify the best tool for each use case. Treat each platform as a value vehicle, not a Lego set for experimentation.

**Technical Stack**:
- Clay: Primary enrichment and workflow orchestration
- n8n: Automation for AI agents and trigger-based processes
- Lovable: Vibe coding for rapid custom application development
- HubSpot: Current preferred CRM
- Attio: Future CRM bet as enterprise features develop

**What Clay Fundamentally Is**: "It's just an aggregate of every enrichment tool. Fundamentally, that's what Clay is." This positioning makes it superior for data foundation work.

**GTM Engineer Definition**: "Someone capable of running automated go-to-market systems while understanding broader GTM leadership principles." Combines technical ability with strategic business intuition.

**Beyond Cold Outbound**: The Kiln rebuilt an entire recruiting firm's operations in Clay. Inbound lead scoring use case: marketing leaders use Clay to verify they're attracting the right audience, help sales teams qualify leads, and prepare call context.

### Nathan Lippi (Clay Bootcamp)
- Developer turned GTM engineer
- Founded Clay Bootcamp (10-week accelerator, 150+ graduates)
- Focus: Bespoke 1-on-1 training and mentorship

### Tim Yakubson (B2B Boosted)
- One of the first UK-based Certified Clay partners
- Created "UnlockClay" course (5 hours, 50+ testimonials in 2 months)
- Philosophy: "1 person using Clay and Smartlead can be more effective than 10 sales reps"

### Clay Blog: 6 Campaigns in 1 Workflow Pattern

A proven Clay workflow pattern (from Clay's official blog) for automating multiple campaigns from a single table:

**5-Step Process:**
1. **Email Verification**: Debounce verifies emails. For unverified: Clay's "get email" generates educated guesses. Results feed master email column
2. **Company Description Pull**: Extract via Apollo or Clay's "enrich company data" (sourcing from LinkedIn pages) into master column
3. **B2B Classification**: OpenAI prompt: "Tell me if the company is B2B or B2C. Only respond with 'B2B' or 'B2C.'" Only B2B advances
4. **Campaign Sorting & Personalization**: Industry column sorts into buckets (e.g., management consulting, recruiting, financial services, 1-10 employees, replaceable CRM, catch-all). ChatGPT generates custom opening lines for catch-all
5. **Continuous Refilling**: Import new CSV prospects via "add to current table." System auto-deduplicates against previously contacted leads

**Key Clay features used**: OpenAI column formulas, email enrichment/verification, ChatGPT for copywriting, data deduplication, Google Sheet sync, multi-source data mapping.

### Fabian Herhold (Automindz Solutions)
- Machine learning & data science background
- Notable: "Creative Data Sources" webinar with Patrick Spychalski: reverse engineering LinkedIn profiles from Slack profile pictures

### Will Breton
- 1,000+ hours in Clay
- Created viral learning guide: "How I'd learn Clay in 1 month from zero"
- Copy-to-learn method: Rebuild flows from top creators to understand structure

---

## Appendix: Quick Reference

### Clay Quick Facts
- Valuation: $3.1B (August 2025, $100M Series C from CapitalG)
- Community: 15,000+ Slack members
- Data providers: 150+ (97+ enrichment integrations documented)
- Pro plan: $800/month, 50,000 credits
- Explorer plan: $349/month, 10,000 credits (HTTP API access)
- Starter plan: $149/month, 2,000 credits
- Enterprise: Custom pricing, REST API, unlimited webhooks
- Documentation: 369 articles across 7 collections (docs.clay.com)
- University: 9 courses, 96+ lessons (university.clay.com)
- Templates: 700+ pre-built workflows
- Waterfall coverage improvement: 40% → 78% (nearly doubles email find rates)
- January 2026: 22x faster enrichment, 10x faster AI processing
- Key customers: OpenAI, Anthropic, Cursor, Canva, Intercom, Rippling, Webflow, Notion, Lovable

### Related Files in This Kit
- `knowledge-base/playbooks/clay/iron-laws.md`: Non-negotiable Clay build rules
- `knowledge-base/playbooks/clay/prompts.md`: Reusable Claygent / AI column prompts
- `knowledge-base/playbooks/clay/formulas.md`: Reusable Clay formula expressions
- `knowledge-base/playbooks/workflow-anatomy.md`: Master playbook for building workflows
- `knowledge-base/playbooks/signal-matrix-framework.md`: ICP and signal matrices
- `tools/rex/`: Python SDK for Clay (see `tools/rex/LEARNINGS.md` before any build)
