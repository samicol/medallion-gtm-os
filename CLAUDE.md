# Medallion GTM Context OS

## Company
Medallion (medallion.co) — AI-powered provider operations platform automating credentialing, payer enrollment, cross-state licensing, and provider data management. Serves 300+ healthcare organizations including digital health companies, telehealth platforms, multi-site provider groups, and health systems across the US. Founded by Derek Lo (CEO). $130M raised total; Series D ($43M) closed August 2025. Acquired Andros; describes itself as "the largest AI-native credentialing platform in the country."

Key files: context/icp/icp.md, context/icp/personas.md, context/icp/signal-matrix.md, context/docs/research/, context/docs/gtm-system.md, output/campaigns/digital-health-provider-hiring/workflow-spec.md

## How this folder works

| Folder | What goes there | When to read it |
|---|---|---|
| `context/docs/research/` | Raw facts about Medallion, every one with a source URL and date | Before any ICP, positioning, or copy work |
| `context/icp/` | ICP in five layers, buyer personas, signal matrix | Before building any workflow or sequence |
| `context/positioning/` | Value proposition, positioning statement, competitor landscape | Before writing copy or messaging |
| `context/messaging/` | Core message, pillars, persona angles, words to use/avoid | Before any outreach copy |
| `context/brand-kit/` | Medallion's tone of voice, key phrases from their own copy | Before any copy work |
| `knowledge-base/playbooks/` | GTM frameworks and methodology playbooks | When building or reviewing workflows |
| `knowledge-base/learnings/` | Retrospective notes and lessons from campaigns | After any campaign run |
| `meetings/` | Notes from calls, demos, and stakeholder conversations | Before any customer-facing work |
| `output/campaigns/` | Workflow specs and campaign deliverables | When building or reviewing outreach |
| `tools/` | Tool documentation and configuration notes | When setting up or debugging integrations |
| `weekly-priorities/` | Weekly focus areas and task lists | At the start of each week |
| `work-log/` | Timestamped log of every change made | Ongoing — log every change here |
| `.claude/skills/` | Claude Code skills for GTM workflows | Auto-loaded at session start |

## Rules
- Cite a source URL and check date for every company fact — never invent numbers
- No em dashes in any copy
- Ask before sending or publishing anything
- Log every change in this week's work log
- Mark anything inferred from research as INFERRED
- Mark internal knowledge (not from public sources) as "Source: internal"

## Skills
Skills live in `.claude/skills/`. Type `/` in Claude Code to list them.

| Skill | What it does |
|---|---|
| `/signal-matrix` | Build a scored signal matrix from ICP and research |
| `/build-workflow-spec` | Spec a signal-based outbound workflow for Clay |
| `/campaign-strategy` | Generate and rank outbound campaign ideas |
| `/campaign-copy` | Write email and LinkedIn copy inside a workflow spec |
| `/campaign-contract` | Define the contract (variables, facts) for a campaign |
| `/campaign-qa` | QA a campaign before launch |
| `/build-clay` | Build a Clay table from a workflow spec |
| `/design-clay-table-json` | Design a Clay table as a JSON flow blueprint |
| `/import-clay-table` | Import a Clay table from JSON |
| `/save-clay-schema` | Save a Clay table schema to file |
| `/export-tables` | Export Clay table data |
| `/calculate-costs` | Estimate Clay data credit costs |
| `/workspace-cost-audit` | Audit Clay workspace costs |
| `/agent-browser` | Browse web pages via headless browser |
| `/crawl4ai` | Crawl websites for structured data |
| `/miro-gtm-flowchart` | Draw GTM system architecture on a Miro board |
| `/prompt-builder` | Build Claude prompts from a decision tree |
| `/inbox-placement-test` | Test email deliverability and inbox placement |

## Tools
- Clay — data enrichment, signal detection, outbound workflows
- To be updated with other tools after research
