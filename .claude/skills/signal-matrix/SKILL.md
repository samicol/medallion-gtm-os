---
name: signal-matrix
description: Build ICP/Signal matrices for your company. Starts by understanding the product and buyers, then groups them into targetable segments, then maps signals to find and reach them. Use when setting up your Context OS or when expanding into new niches.
argument-hint: [segments|workflows|full|refresh]
---

# Signal Matrix Skill

**Methodology:** `knowledge-base/playbooks/signal-matrix-framework.md`

Build targeting matrices that answer: "What are we selling, to whom, and how do we find them?"

## Argument Parsing

Parse `$ARGUMENTS` for an optional mode:

**Mode** (first word, if it matches one of these):
- **`full`** (default, or no argument): All phases: understand → segment → prioritize → signals → save
- **`segments`**: Matrix 1 only (who to target)
- **`workflows`**: Matrix 2 only (how to find them). Requires existing Matrix 1
- **`refresh`**: Update existing matrices with new data or strategy session outcomes

---

## Phase 0: Understand the Company

**Before touching any matrix, you must deeply understand what this company sells and to whom.**

### Step 1: Load company context

Read in this order:

1. `CLAUDE.md` and everything in `context/`: READ FIRST, always
2. `context/icp/icp.md` and `context/icp/personas.md`: if they exist
3. `context/positioning/`: positioning, value proposition, competitors
4. All files in `context/docs/research/`: background research
5. Up to 3 recent files in `meetings/`: call notes and transcripts

If `CLAUDE.md` and `context/` say nothing about what the company sells, tell the user:
> "I need to understand what you sell before building matrices. Add it to `CLAUDE.md` or `context/`, or brief me now."

### Step 2: Load framework files

Always read:
1. `knowledge-base/playbooks/signal-matrix-framework.md`: methodology and guardrails
2. `knowledge-base/playbooks/workflow-anatomy.md`: Mother Intent Catalog (needed for Phase 3)

### Step 3: Check for existing matrices

Look for `context/icp/signal-matrix.md`:
- If matrices exist AND mode is `full` or `segments`: warn user that existing matrices will be overwritten. Ask to confirm or suggest `refresh` mode
- If matrices exist AND mode is `refresh`: load them as starting point
- If matrices DON'T exist AND mode is `workflows`: stop, tell user to run `segments` first

### Step 4: Synthesize and confirm

Present a brief company summary to the user:
- What they sell (products, features)
- What pain they solve
- Who they sell to today
- Their market (US / LatAm / EU)
- Key competitors
- Single-product or multi-product

**Ask the user to confirm this understanding before proceeding.** If anything is wrong or missing, fix it now. Wrong product understanding = wrong matrix.

---

## Phase 1: Define Buyer Groups + Matrix Structure

> **This is where the thinking happens. Do NOT default to a template. Reason about the right structure for THIS company.**

### Step 1a: Cast a wide net on potential buyers

Propose all potential buyer groups:
- Which industries could use this product?
- Which company sizes?
- Which personas make the buying decision?
- Which use cases does the product serve?
- Are there adjacent markets?

Present the full list to the user. This is brainstorming, not filtering.

### Step 1b: Choose the grouping axes

Ask: "What is the primary dimension that makes these buyers DIFFERENT from each other in terms of fit, urgency, and reachability?"

Propose rows and columns with reasoning. Consider:
- **Maturity/readiness**: How far along are buyers in solving this problem themselves?
- **Complexity**: How acute is the pain at different scales?
- **Switching intent**: How ready are they to change from their current solution?
- **By product**: Which of our products fits which buyer group?
- **By use case**: Different ways the product gets deployed
- **By geography**: When market dynamics differ significantly
- **By company stage**: When buying behavior correlates with funding/growth stage
- **By existing solution**: Using competitor / built in-house / using nothing

Rules for good axes (from `knowledge-base/playbooks/signal-matrix-framework.md`):
- **Observable**: You can detect which segment a company belongs to using available data
- **Mutually exclusive**: A company fits one cell, not multiple
- **Actionable**: Each segment implies different outreach strategy
- **Sufficient volume**: Each segment contains hundreds+ companies

Present the proposed matrix structure. **Use AskUserQuestion to confirm before proceeding.** This is the highest-stakes decision in the entire skill. If the axes are wrong, everything downstream is wrong.

### Step 1c: Fill each cell

For each cell in the grid, generate:

**Target Definition** (REQUIRED):
- Factual, observable criteria. NOT vague pain descriptions
- Must be filterable by a Clay operator
- Good: "Series A-C US neobanks, 50-200 employees, building on BaaS partner or basic in-house ledger"
- Bad: "Companies frustrated with their current infrastructure"

**Company Examples** (REQUIRED):
- Use WebSearch to find REAL company names matching the target definition
- Search pattern: "{niche} companies {cluster description} {geography}"
- Verify companies exist and fit before including
- 5-15 names per cell (more for high-priority cells)
- **NEVER fabricate company names.** If search returns nothing, say: "Requires Clay research with filters: [specific filters]"
- For LatAm markets: digital footprint is weaker. Fewer examples per cell is OK

**Product/Angle** (for multi-product companies):
- Products 1 (Lead): Which product gets the foot in the door
- Products 2 (Upsell): Natural next sale
- These are hypotheses, not decisions. Validate them with sales and leadership

**Priority flag**: High / Medium / Low with one-line reasoning.

Present the full Matrix 1 grid. **Use AskUserQuestion to confirm.**

---

## Phase 2: Assess and Prioritize

For each cell, score on:
- **Signal density**: How many programmable signals can identify companies here? (High/Med/Low)
- **Product-market fit**: How strong is the match? (High/Med/Low)
- **Penetrability**: Can we reach them with available data in their market? (High/Med/Low)

Consider market data realities:
- US companies: high penetrability (rich data)
- LatAm companies: low penetrability for digital signals, but physical-world signals (Google Maps, government registries) can be high
- Early-stage companies: harder to identify than established ones

Recommend top 3-5 priority cells ranked by combined score. Explain why each is prioritized.

**Use AskUserQuestion to confirm which cells to pursue.** The user may override your ranking based on customer and sales conversations you don't have.

---

## Phase 3: Build Matrix 2 (Signals)

**Only for confirmed priority cells from Phase 2.**

### Step 3a: Signal ideation

For each priority cell, cross-reference the Mother Intent Catalog from `knowledge-base/playbooks/workflow-anatomy.md`:

**Universal signals to evaluate for every cell:**
- Hiring for specific roles (Apollo via Clay "Discover Jobs")
- New leadership in target roles (Apollo via Clay "Find Person" + job change tracking)
- Fundraising / recent funding (Crunchbase via Clay "Find Organization"): **only for VC markets**
- Headcount growth >20-25% (Apollo via Clay "Enrich Company")
- Technographics (BuiltWith via Clay): **compound signal only, must pair with another**
- GitHub/OSS evaluation (GitHub API via Clay HTTP): **only for open-source products**
- Content/intent (blog RSS via Clay HTTP): **partial coverage, requires known URLs**

**Niche-specific signals to research:**
- Government registries relevant to this industry?
- Physical-world signals (Google Maps, location counts)?
- Public procurement systems?
- Industry directories or licensing databases?
- Regulatory triggers or compliance deadlines?

Use WebSearch to verify data sources exist and are accessible.

### Step 3b: Iron Law validation

For EVERY signal, answer the forcing question: "Could I send this to a Clay operator RIGHT NOW with zero ambiguity?"

Document per signal:
- **Signal**: What observable event are we detecting?
- **Data Source**: Exact URL, API, or tool
- **Clay Action**: Which enrichment action, how many credits
- **Key Filters**: Keywords, dates, geography
- **Volume Estimate**: How many leads per month/quarter?
- **Status**: VERIFIED / VERIFIED (COMPOUND) / VERIFIED (PARTIAL) / KILLED

Kill signals that fail the forcing question. Document why.

### Step 3c: Categorize

- **Universal**: Works across multiple segments with keyword/filter swaps. The Clay build is the same, only inputs change
- **Niche-Specific**: Unique data source per vertical. New Clay build required

Highlight the compounding insight: how many signals are universal (build once) vs niche-specific (unique build). This is what makes the approach scalable.

### Step 3d: Assemble Matrix 2

Structure:
- Column A: Cross-functional indicator (Universal / Niche Specific)
- Column B: Signal name
- Per priority segment: Play column (signal description + data source for THIS segment) + Product column (which product to pitch)

For the primary priority cell: fully populate Play + Product.
For secondary cells: populate if the universal signal applies (usually just keyword swaps). Leave empty for niche-specific signals that don't apply.

Present for validation. **Use AskUserQuestion to confirm.**

---

## Phase 4: Generate Tracker + Save

### Step 4a: Generate Matrix 3

Pre-fill a workflow tracker with one row per validated signal from Matrix 2:
- W #: Sequential number
- Status: "Planned" for all
- Workflow Name: From signal name
- Mother Intent: From signal category
- All other columns empty (filled as campaigns launch)

### Step 4b: Save outputs

Save one file, `context/icp/signal-matrix.md`, with three sections:
1. **Matrix 1: Segments**: full segment grid
2. **Matrix 2: Signals**: signal matrix with Iron Law details
3. **Matrix 3: Workflow tracker**: pre-filled tracker

### Step 4c: Optional Google Sheets push

Check if a Workflow Tracker spreadsheet is configured:
```bash
source .env && echo $WORKFLOW_TRACKER_SPREADSHEET_ID
```

If set, push matrices to Google Sheets:
```bash
gws sheets spreadsheets values batchUpdate --params '{"spreadsheetId":"$ID"}' --json '{...}'
```

### Step 4d: Summary

Report to the user:
- How many segments defined in Matrix 1
- How many priority cells selected
- How many signals validated in Matrix 2 (universal vs niche-specific)
- How many workflows planned in Matrix 3
- Files saved and their paths

---

## Edge Cases

- **No company context**: Tell the user to add it to `CLAUDE.md` or `context/`. Don't guess about the product
- **LatAm market**: Flag weak digital footprint from `signal-matrix-framework.md`. Suggest physical-world signals. Ask user for company examples when web search fails
- **Single-product company**: Skip product columns in Matrix 1. Angle changes per cell but product is always the same
- **Multi-product company**: Must include Product 1 (Lead) and Product 2 (Upsell) per cell. These are hypotheses
- **Matrices already exist + mode is not refresh**: Warn before overwriting. Suggest `refresh` mode
- **Web research returns garbage**: Ask user for real company names. Use "Requires Clay research: [filters]" as placeholder. Never fabricate
- **User wants to skip to Phase 3**: Allow if Matrix 1 exists in `context/icp/signal-matrix.md`. Read it and proceed to signal mapping
- **Very narrow niche (1-2 segments)**: Skip the grid. Do a single-segment deep dive instead
- **Fundraising signal in LatAm**: Don't include it. Explicitly note it was considered and killed (no VC ecosystem for most LatAm mid-market)
