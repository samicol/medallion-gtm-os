---
name: build-workflow-spec
description: The STRUCTURE step for any outbound workflow. Takes one play (usually one idea from /campaign-strategy) and builds it into a fully fleshed workflow spec, section by section with approval gates (mother intent, inclusion/exclusion, sources, deterministic signals, routing matrix WITH an angle per cell, variables contract, cadence), then saves it to output/campaigns/<workflow-slug>/workflow-spec.md with a STRUCTURE-APPROVED status line. Writes NO copy; /campaign-copy is gated on this file. Use when drafting, building, porting or fixing the structure of an outbound workflow, or when someone says "spec this campaign", "build the workflow for idea X", or "/build-workflow-spec".
argument-hint: [workflow name, mother intent, or campaign idea from campaign-strategy.md]
---

# Build Workflow Spec (Structure)

The procedure for building the STRUCTURE of an outbound workflow. **The framework is constant; only the signals, the enrichments and the ICP change.** Fill the framework, never re-architect it.

**This skill writes no copy.** Structure thinks, copy speaks: this skill produces the approved spec (including the angle for every routing cell); `/campaign-copy` turns those approved angles into narrative and refuses to run without this skill's saved file.

## Position in the chain

```
/campaign-strategy    -> 15-20 ideas, each tagged with a Mother Intent and a Tier; pick one
/build-workflow-spec  -> THIS SKILL: one idea -> one fully fleshed structure, saved + status-marked
/campaign-copy        -> narrative: turns the approved angles into copy, appends to the same file
```

**Methodology:** `knowledge-base/playbooks/workflow-anatomy.md` (4-layer anatomy + Mother Intent Catalog) and `knowledge-base/playbooks/signal-matrix-framework.md` (segments and signals).
**Reference:** any earlier approved spec in `output/campaigns/*/workflow-spec.md`.

---

## Hard rules

1. **Mirror the framework, never re-architect it.** Same sections, same order, every time.
2. **Adapt structure, transplant no content.** A reference workflow gives the skeleton only. Re-derive everything for this workflow. If an element doesn't apply, drop it; never force it.
3. **Invent nothing.** No name, number or claim unless it's in `context/messaging/facts.md` or the `context/` files. Unverified means `{{placeholder}}`.
4. **Section by section, STOP for approval** before the next. Never dump the whole structure.
5. **Deterministic signals only.** Every read is buildable in your data tool (Clay, a spreadsheet enrichment tool, a script): a boolean, a count, or a regex/keyword match. If routing would need someone to eyeball a profile, it is not a route: collapse it, or define an AI classification column with a hard enum output. No mental-jerk routing.
6. **Expensive-to-fake beats marketing.** Signals that cost money to fake (hiring, headcount, filings, registrations) beat marketing claims (every SaaS website says "AI"). Never route on a claim anyone can put on a landing page.
7. **Simplify before granularizing.** The fewest axes that route the narrative win. When the user names the axes ("it's simple: alone/team x hiring"), granularity happens WITHIN those axes, never by adding new ones. Over-engineering the matrix is a failure, same as under-building it.
8. **Assertive delivery.** State counts flat ("8 hiring x 8 headcount = 64 stacked"). One recommendation, not a menu. "Are you sure?" means re-verify in the source, then answer yes or no. Every cell's logic in plain declarative sentences. Nothing abbreviated, ever.

---

## The canonical structure (fill this, don't change it)

Each section is tagged **[ENGINE]** (the reusable part: signals, reads, routing, angles) or **[ICP]** (the variable: the ONLY thing that changes when this workflow is replicated for another segment, market or product).

1. **Mother Intent (Trigger)** [ENGINE]: the always-true signal that defines the workflow, one sentence, signal-led (not vertical-led). Pick from, or check against, the Mother Intent Catalog in `knowledge-base/playbooks/workflow-anatomy.md`.
2. **Inclusion / Exclusion** [ICP]: **Include:** the ICP box (geo, size, industry, from `context/icp/icp.md`) + the trigger definition (titles, keywords, event) + the **recipient** (who we contact, from `context/icp/personas.md`). **Exclude:** who's out and why (competitors, customers, blocklist, active pipeline).
3. **Sources** [ENGINE]: the exact data source for the trigger + every enrichment scrape (Apollo, JSearch, Clay, LinkedIn, registries).
4. **Signals table** [ENGINE]: every read, deterministic, with how it's built:

| # | Signal | Role | How it's read (boolean / count / regex) | Output |
|---|---|---|---|---|

   - **Role is mandatory, one of three:** `trigger` (fires the send), `router` (picks the narrative), `context-clause` (one small line of color in copy, **NEVER routes**). Funding and growth are usually context-clauses, not routers: declare it.
   - **Count clusters:** when a count routes, declare the clusters and what each means (e.g. AI builders: 0 / 1 / 2-5 / 5+ = none / solo / small team / established). No raw counts handed to copy.
5. **Routing matrix WITH angles** [ENGINE]: see below. For partnership or niche plays with no routing, declare it explicitly: **`Routing: none (static play)`**. The declaration is required; absence is not a declaration.
6. **Variables contract** [ENGINE]: every `{{variable}}` copy is allowed to use, each mapped to the field that delivers it:

| Variable | Source field | Exists in branches |
|---|---|---|

   Variables are `{{snake_case}}` double braces (match your sequencer's syntax at export). Data-must-exist starts here: if the enrichment doesn't deliver it, copy can never say it.
7. **Cadence & channel** [ENGINE]: periodicity (always-on / monthly / one-shot) and channel (email / LinkedIn / both).

---

## The Angle Matrix (the heart of the structure)

**The routing matrix is not done until every cell carries its angle.** Required table:

| Cell | Deterministic read | What it tells us (inferred situation) | The angle it earns |
|---|---|---|---|

Rules:
- **Do the inference thinking explicitly.** The point of programmatic GTM is understanding what each signal combination says about the company: the situation that is probably happening. Write it so the user can challenge the reasoning, not just the wording. ("2-5 builders, not hiring" means the team is fully committed to the core roadmap and new builds have nowhere to go: overflow angle.)
- **Inference stops early:** infer what they're DOING, never how it feels or what's hard about it, unless the user approves that step.
- **Branch coverage:** every cell only uses data that exists in that cell ("what happens if they don't hire?" Then there is no `{{role_title}}` in that branch, and its angle cannot depend on one). Answer this here, not at copy time.
- **Niche-native test:** if any company in your category could send an angle unchanged, it isn't native enough. Sharpen it until it could only be about this exact situation.
- **Angles are meaning, not copy.** No email lines here. `/campaign-copy` turns angles into narrative under its own line laws.

### Matrix granularity process
Build matrices axis by axis:
1. Enumerate the permutations of ONE axis. State the count flat. Confirm with the user.
2. Same for the next axis.
3. Stack them. State the combined count. Confirm.
4. Show ALL cells with full narrative logic: no heat legends, no abbreviations, no "...".

---

## How to run

### Phase 0: Load context (silent, no output)
1. `CLAUDE.md` + `context/positioning/` + `context/icp/icp.md` + `context/icp/personas.md`. REQUIRED: if there's no ICP anywhere, stop and ask for it.
2. `context/messaging/facts.md`: authorized facts. If missing, flag it; every specific fact becomes `{{placeholder}}` (`/campaign-copy` will create the file later).
3. `output/campaigns/campaign-strategy.md`: if the user picked an idea from it, load that row (mother intent, tier, list filters, AI strategy, value prop, overview) as the starting brief.
4. `context/icp/signal-matrix.md` if it exists: segments and signals already agreed.
5. Existing approved specs in `output/campaigns/*/workflow-spec.md`, as reference skeletons only.
6. `knowledge-base/playbooks/workflow-anatomy.md` + `knowledge-base/playbooks/signal-matrix-framework.md`.

### Phase 1: Build the structure, section by section
Canonical order: Mother Intent, Inclusion/Exclusion, Sources, Signals table (roles + clusters), Routing matrix with angles, Variables contract, Cadence & channel. **STOP for approval at each section** (at minimum after the signals table and after the angle matrix: those two decisions drive everything).

### Phase 2: DEFINITION OF DONE, then SAVE immediately
A structure is **fully fleshed** only when ALL of these are present. This checklist is exactly what `/campaign-copy` GATE 1 verifies. Incomplete structure means no copy.

- [ ] Mother intent: one sentence, signal-led, matched to the catalog
- [ ] Inclusion: ICP box + trigger definition + recipient, tagged [ICP]
- [ ] Exclusion: who's out and why
- [ ] Sources: trigger + every enrichment
- [ ] Signals table: every read deterministic (boolean/count/regex), every signal's ROLE declared (trigger/router/context-clause)
- [ ] Count clusters declared for any count that routes
- [ ] Routing matrix WITH the angle column complete, or the explicit line `Routing: none (static play)`
- [ ] Branch coverage: every cell's angle survives on the data that exists in that cell
- [ ] Variables contract: every `{{variable}}` mapped to its source field
- [ ] Engine/ICP markers on every section
- [ ] Cadence & channel declared

**The moment the user approves the structure, SAVE it** to `output/campaigns/<workflow-slug>/workflow-spec.md` (kebab-case slug from the workflow name, e.g. `output/campaigns/hiring-first-gtm-engineer/workflow-spec.md`), with the status line as the first line under the title:

```
**Status:** STRUCTURE-APPROVED YYYY-MM-DD · copy pending
```

Status lines are truthful and advance as work advances, examples: `STRUCTURE-APPROVED 2026-07-30 · copy pending`, then `STRUCTURE-APPROVED 2026-07-30 · E1 approved · E2/E3 pending`, then `COPY-APPROVED 2026-07-31`. `/campaign-copy` appends approved copy to this same file and advances the status. **Never hold an approved structure in conversation only. If it isn't in a file, it isn't built.** Log the save in `work-log/`.

### Phase 3: Hand off to /campaign-copy
Structure ends here. **This skill writes no copy: not a line, not a draft.** Point to `/campaign-copy`: its GATE 1 reads the saved file and verifies the status + checklist; its GATE 2 reads these angles back for confirmation and turns them into narrative under the copy line laws. If copy work exposes an angle flaw, the fix happens HERE (in the spec, re-approved, status kept truthful), never patched inline in copy.

---

## What NOT to do
- Don't write copy, copy lines or "sample emails". That's `/campaign-copy`, gated on this skill's output.
- Don't route on eyeball judgments or marketing claims. Deterministic, expensive-to-fake reads only.
- Don't hand copy a raw count, an unlabeled enrichment, or a cell without an angle.
- Don't add axes the user didn't name. Granularity lives within their axes.
- Don't transplant content from another workflow or another company. The [ENGINE] travels; the [ICP] and the facts never do.
- Don't invent any specific fact. `{{placeholder}}` instead.
- Don't dump the whole structure. Section by section, approval gates.
- Don't leave an approved structure unsaved. Save on approval, status line first.
