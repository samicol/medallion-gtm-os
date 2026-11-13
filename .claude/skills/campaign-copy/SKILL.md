---
name: campaign-copy
description: Gated procedure for writing, rendering, editing or reviewing outbound campaign copy (cold emails + LinkedIn DMs). Copy only ever runs on a saved STRUCTURE-APPROVED workflow spec from /build-workflow-spec (output/campaigns/<workflow-slug>/workflow-spec.md). It turns the approved angles into narrative through hard gates (mode check, structure check, facts gate, angle read-back, per-showing QA), one approved unit at a time, from verified facts only, then appends the approved copy to the same spec file. Use when asked to write campaign copy, a copy album, cold email or DM sequences for a workflow, to edit copy line by line, or to review existing copy.
argument-hint: [write|render|review|full] [workflow-slug]
---

# Campaign Copy Skill

The copy discipline for every outbound workflow. The skill contains **zero company-specific content**: everything specific (names, claims, banned words, voice) is loaded from your `context/` files, above all `context/messaging/facts.md`. The rules below are not suggestions, they are gates. A gate marked **STOP** means: show the unit, wait for approval, do not continue.

**Why gates exist:** every rule in this file traces to a real correction. Copy discipline failed when it lived in reference docs and judgment calls. It holds when it's a procedure that cannot be skipped.

## The Pipeline

```
GATE 0   Mode check: write | render | review | full   (render = diff-only)
GATE 1   Workflow spec: saved, STRUCTURE-APPROVED, fully fleshed. Else bounce to /build-workflow-spec
Phase 0  Context + FACTS GATE (context/messaging/facts.md; create if missing) + banned lists
GATE 2   ANGLE VERIFY: read the approved angles from the spec, confirm, then transform
Phase 1  Writer: one unit at a time, locked shape. STOP per unit
QA       Per-SHOWING QA gate: runs before EVERY display, one confirmation line
Phase 2  Persona review + human test
Phase 3  OPTIONAL: export for your sequencer
Save     Save on approval into the spec file; status claims only from files
```

---

## GATE 0: Mode Check

Read `$ARGUMENTS` and the user's message to determine the mode **before doing anything else**:

- **`write`**: writer phases only (gates + copy album).
- **`render`**: the user provided the text (a skeleton, their own copy, an edit request). Diff-only rules apply (below).
- **`review`**: review existing copy (and regenerate the export if one exists).
- **`full`** (default): write, then review.

**Auto-detect render:** if the user pasted copy, a skeleton, or line-by-line instructions, the mode is `render` even if they didn't say so. When in doubt whether something they showed is a base to edit or a reference to learn from, **ask one question** before writing.

**Render mode rules (non-negotiable):**
1. **The user's text is the base.** Change only the tokens they flagged. Add zero words they didn't ask for. "Improving" their draft is a violation, not a favor.
2. **Unit scope:** "redo email 1" means touch email 1 only. Nothing else moves.
3. **Reference ≠ instruction:** when the user shows approved copy or an example, extract the standard from it and say what you're taking ("keeping the value-framed bullet cadence"). Never transplant it verbatim. Never ignore it.
4. **Trust the direction:** build inside the user's stated approach first. Propose an alternative only after delivering their version.
5. **Open spintax slots** (`{option|X}`): fill `X` with a same-meaning variant, nothing more.

**Workflow:** the `workflow-slug` argument names a folder in `output/campaigns/`. If it's missing, list the folders that contain a `workflow-spec.md` and ask which one.

---

## GATE 1: The Structure File (hard requirement, no exceptions)

**Copy only ever runs on a fully fleshed, SAVED structure.** This applies to every workflow, to partnership plays, and to EVERY mode including `render`. There are no escape hatches.

1. **The spec must exist** at `output/campaigns/<workflow-slug>/workflow-spec.md` with a status line of `**Status:** STRUCTURE-APPROVED` (or later). Open it and read it: verify the status in the file, never assume it.
2. **Verify it is fully fleshed** against `/build-workflow-spec`'s definition of done: mother intent, inclusion/exclusion + recipient, sources, signals table with every read deterministic and every signal's ROLE declared (trigger / router / context-clause), count clusters for any routing count, routing matrix WITH angles per cell (or the explicit `Routing: none (static play)` declaration), branch coverage, variables contract, engine/ICP markers, cadence & channel. **Any item missing means the structure is not done, which means no copy.** Bounce to `/build-workflow-spec` to complete it.
3. **No file, no copy.** If the user pastes a structure in chat, it isn't built yet: run it through `/build-workflow-spec`'s checklist, SAVE it with the status line, then continue. If there's no structure at all, **stop and say so** and offer `/build-workflow-spec`. Never improvise structure, routing or meaning inside this skill.
4. **Partnership plays are NOT exempt.** Their spec exists like any other (mother intent, ICP, detection, sequence plan) and declares `Routing: none (static play)`.
5. **Every dynamic variant maps to a route in the spec.** A variant may only exist if the spec defines the deterministic condition that fires it. Copy adds zero routes.

The division of labor: `/build-workflow-spec` owns ALL the thinking (signals, routing, angles: the meaning). This skill owns the SPEAKING: turning approved angles into narrative under the line laws. Structure thinks, copy speaks.

---

## Phase 0: Context + Facts

**Before writing anything you MUST have the full picture. Never guess. Always ask.**

### Step 1: Load company context (automatic)
1. `CLAUDE.md`: company overview (READ FIRST)
2. `context/icp/icp.md` + `context/icp/personas.md`: personas, industry, size, triggers
3. `context/positioning/positioning.md`, `context/positioning/value-proposition.md`, `context/positioning/competitors.md`
4. `context/messaging/messaging.md` + `context/brand-kit/brand.md`: core message, pillars, tone of voice
5. Earlier approved copy in `output/campaigns/*/workflow-spec.md`: voice reference. **Open the actual files. Never work from memory of what earlier copy says.**

Any file that doesn't exist: note it and continue; ask for what's missing when it matters.

### Step 2: THE FACTS GATE
Read `context/messaging/facts.md`. This file is the **only** source of:
- **Authorized social-proof names:** the only customer names allowed in prospect-facing copy
- **Approved claims & numbers:** exact phrasings ("20+ years", "SOC 2 Type 2", timeframes)
- **Proof caveats:** what the proof does and does not support (e.g. "dev work, not AI builds: logo-drop only")
- **Banned words and banned angles** specific to your company
- **Sender identity and voice notes**

**Rules:**
- Every name, number and claim in copy must trace to this file. Anything not in it renders as `{{placeholder}}`: never from memory, never from another company's copy, never invented. (Case studies in `context/docs/case-studies.md` become usable proof only once their approved phrasing is in facts.md.)
- **If the file doesn't exist:** collect the facts from the user (names, claims, caveats, banned items, sender), CREATE `context/messaging/facts.md` from `knowledge-base/playbooks/templates/facts-template.md`, then continue. Never write copy without a facts file.
- **Internal data stays internal:** benchmarks, funnel metrics and anything marked internal never enters prospect-facing copy.
- **No transplant:** methodology travels between workflows and companies; data, proof, claims and copy lines never do.
- **Provenance on demand:** be able to trace any fact in the copy to its file and line instantly.

### Step 3: Load banned lists
Global: `knowledge-base/playbooks/copy-bans.yaml` (banned characters incl. em dashes, words incl. "curious" and "free", phrases incl. "just following up", "circling back", "I'll be direct", "hope you're doing well", and opener patterns incl. "I saw", "I noticed"). Company-specific: the banned words and banned angles in facts.md.

### Step 4: Gather campaign inputs
Same table as always: campaign name, mother intent (from the spec), **channel (must explicitly ask: email, LinkedIn, or both)**, enrichments/signals (from the spec), personas / industry / size (defaults from `context/icp/`, user confirms), sequence length and follow-up spacing. Present the derived values, ask for the missing ones, **confirm everything before writing**.

### Exhaustiveness rule
Any inventory presented to the user ("all plays", "all variants", "all workflows") is **re-searched in the source before presenting**, never assembled from memory. If asked "are you sure you have them all?", the answer must already be yes.

---

## GATE 2: Angle Verify (read the meaning, don't create it). STOP

**This skill does not invent meaning.** The angles were built and approved in the spec (`/build-workflow-spec`'s angle matrix: cell, deterministic read, inferred situation, angle). Here:

1. **Read the angle matrix from the spec** and show it back in one table, exactly as approved, so the user confirms it's still the meaning we're writing from.
2. **Then transform.** Copy's job is turning each approved angle into narrative under the line laws, nothing more. A line may only say what its cell's angle earns, using only that cell's variables.
3. **Bounce-back guardrail:** if copy work exposes an angle flaw (a branch without data, an inference that doesn't hold, a missing cell), do NOT patch the meaning inline. Fix the angle in the spec, get it re-approved there (status stays truthful), then resume copy. The spec is always the current truth.

**STOP. Show the read-back. Get confirmation. Only then, lines.**

---

## Phase 1: Writer

**MANDATORY reads before any line:** `knowledge-base/playbooks/copy-iron-laws.md` (the 14 laws), `knowledge-base/playbooks/copy-frameworks.md`, and `knowledge-base/playbooks/linkedin-dm-frameworks.md` (if LinkedIn).

### Working cadence
- **One unit at a time, STOP per unit.** A unit is what the user asked for: one line across scenarios, one email, one matrix. Show it, wait, continue. **Never dump the whole album.**
- **Lock the shape, then replicate.** Once a unit's shape is approved (e.g. "pressure, plain fact, we are the team"), every parallel unit follows it exactly. No drift between cell 1 and cell 8.
- **Completeness on request:** when the user says "all", show all: every cell, every variant, full text, zero abbreviation, zero truncation.

### Register selector (pick before writing)
- **SIGNAL play** (a trigger fired: hiring, funding, new role): pressure + research voice. L1 leads with the situation; dynamic lines show the homework.
- **PARTNERSHIP play** (the recipient is a potential partner or channel, not a lead): peer-to-peer, fraternal. "I run this. You run that. Does it make sense to collaborate?" Solidarity without pitching; offer to have their back, never diagnose their business. **Me-ratio:** their world + solidarity carry the email; "we" appears only as the helping hand. Partnership copy is typically **static** (no waterfall) with heavy spintax.
- **BAIT / NICHE plays:** per `knowledge-base/playbooks/copy-iron-laws.md` Law 1.

### Line laws: them
- **We ask, we don't assert.** Their situation is a question or a hedged guess, never a claim.
- **Assertive-us / probabilistic-them.** Deterministic facts stated flat ("I found one builder on the AI side"). Inferences hedged ("which probably means", "so my guess is"). Never state an inference as fact.
- **THE INSULT TEST.** Read every line as the most insecure recipient would. If ANY reading implies "you failed", "you only shipped a demo", "you can't deliver", rewrite. Blame is never shipped. This goes beyond Law 14: it catches blame-*readings*, not just gap-diagnosis.
- **Show the homework.** Dynamic lines surface the actual research finding that earned the email ("From what I could research on {{company_name}}'s headcount...").
- **Data-must-exist.** Every claim maps to a field the enrichment actually delivers. No tenure references if tenure isn't scraped. No invented timeframes or numbers: "90 days" or "2-3 weeks" only if they're in facts.md.
- **Richest-variable rule.** Use the deepest resolved enrichment available: `{{ai_hire_name}}` beats "your new hire"; `{{ai_builder_count}}` beats "a small team".

### Line laws: us
- **Value-prop discipline.** The value-prop line states what you do, flat and confident. Zero assumption about what the prospect wants. No "if that's the case". No conditional selling.
- **Zero meta-filler.** No "the setup is simple", no announcing what you're about to say. State the thing.
- **No fake scarcity.** No manufactured urgency. Position as a resource.

### Line laws: language
- **Grandmother clarity.** A stranger understands every sentence on first read. No jargon ("JD" becomes "job description"). No ambiguous references ("nothing coming" becomes "no open role to hire anyone").
- **No AI-flavored phrasing.** "A seat like that", "in the AI era", dramatic abstractions: if it smells like a model wrote it, it's out.
- **No padding.** Every clause earns its place. Adding words is not adding value.
- **No em dashes. No "curious". No clichés** (see `copy-bans.yaml`).
- **Nexus check.** The email is ONE argument: each line picks up the previous line's output (pressure, reality, answer). Two adjacent lines that don't connect is a fail.
- **Line-map integrity.** One thought per line. Lines connect logically but never merge physically. The line map (L1 mother intent, L2 secondary, L3 value prop, L4 social proof, L5 CTA, PS) is sacred.

### Structural rules (unchanged)
- **FALLBACK, never BASE.** Every dynamic line has a complete waterfall ending in a FALLBACK, **except** when the scenarios are exhaustive (they cover every lead by construction): then no fallback, because none can fire.
- **Fallback parity:** when a fallback exists, it reads as well as the routed variants. Never a lazy afterthought.
- Dynamic variants share the same skeleton; swap only the signal-specific angle.
- Social proof matched to the prospect's segment (Law 4). Generic proof is worse than no proof.
- Subject lines: lowercase, 3-5 words, no clickbait.

### Spintax rules
- **STATIC copy = heavy spintax.** Every swappable phrase gets variants (`{option1|option2|option3}`), all combinations grammatical. Static without spintax is a miss.
- **DYNAMIC lines (resolved per lead by your data tool) = NO spintax.** The data tool resolves one clean sentence per variant. Spintax inside a dynamic line is an error.
- Spintax is variation, never different messages (that's a conditional route).

### Variant & sequence quality
- **Cross-variant de-templating.** Across a waterfall, vary hedges and rhythm ("not 100% sure" / "could be off" / "my guess is") so N variants don't read stamped. No conspicuous word repetition within an email.
- **Sequence-wide checks:** no repeated lines across emails (identical PSs in every email is a fail: vary or drop them). The subject never changes mid-thread (follow-ups are `Re:` in the same thread). E2 opens straight on value: no preamble, no "following up". E2's opener may summarize E1's context in one clause, then new value; never re-argue E1. Each follow-up adds something E1 didn't (Law 10). No PS unless the user asked for one.

### LinkedIn DM rules (if the channel includes LinkedIn)
- Empty connection request (no note) by default.
- DM 1: one forward-looking question tied to their situation, dynamic by enrichment (same waterfall logic), answerable to a stranger, nothing sensitive.
- DM 2: brief context follow-up, static. Only 2 DMs total, no DM 3.
- Tone: reads like a text. No subject lines, no signatures, no PS.

### Variable syntax
- **Variables:** `{{snake_case}}` double braces: `{{first_name}}`, `{{company_name}}`, `{{social_proof}}`. Every one must exist in the spec's variables contract. If your sequencer uses a different syntax (single braces, uppercase, `{{RANDOM|...}}` spintax), convert at export; write the album in the kit syntax.
- **Spintax:** `{variant1|variant2}`.
- **Dynamic line tags:** `{{e1l1}}`, `{{e1l2}}`, `{{e2l1}}` (email number + line number), `{{social_proof}}`, `{{e1ps}}`. The waterfall defines what the data tool resolves into each tag; the tag is what the sequencer sees.
- **`{{first_name}}` stands alone** on its own greeting line, never nested inside a dynamic line. Dynamic tags resolve WITHOUT the greeting: the body is always `{{first_name}},` then `{{e1l1}}`.

---

## THE PER-SHOWING QA GATE

**Before EVERY display of copy (a line, an email, an album) run this checklist. Not once at the end. Every showing.** Then print one confirmation line so the user sees it ran, e.g.:
`QA: passed. insult ok, nexus ok, facts-traced ok, spintax ok, no-cliche ok [word counts: E1 98]`

- [ ] Mode honored? (render = diff-only, unit scope respected)
- [ ] Campaign type + register identified? (signal / bait / niche; signal / partnership voice)
- [ ] Every dynamic variant maps to a deterministic route in the spec? Waterfall complete? FALLBACK present (or exhaustive)? Fallback parity?
- [ ] **Insult test passed on every line?** (no reading blames the recipient)
- [ ] **Nexus:** one argument, every line picks up the previous?
- [ ] Facts: every name / number / claim traced to facts.md? No transplanted content? No internal data?
- [ ] Data-must-exist: every referenced datum actually enriched in this branch?
- [ ] Assertive-us / probabilistic-them split correct on every line?
- [ ] Spintax: heavy on static, none in dynamic, all combinations grammatical?
- [ ] De-templated across variants? No conspicuous repetition?
- [ ] Sequence: no repeated lines across emails, subject unchanged, follow-ups add new value, no unrequested PS?
- [ ] Under 120 words (aim for 60)? One thought per line? 3:1 prospect:us?
- [ ] CTA a question that earns the reply? No "book a call", no "free"?
- [ ] Grandmother clarity? No jargon, no ambiguity, no AI-flavored phrasing, no padding, no meta-filler?
- [ ] Nothing from `copy-bans.yaml` or facts.md's banned lists? No empty flattery, no fake scarcity?
- [ ] Social proof matched, spelled out in full in the album?
- [ ] Every `{{variable}}` in the variables contract and resolvable? Tag naming correct?
- [ ] If the user asked for "all": is it actually all, complete, untruncated?

---

## Phase 2: Persona Review + Human Test

After writing (or in `review` mode), step into the target buyer: **{target_persona}** in **{target_industry}** at a **{target_company_size}** company. The core question: *what would it take for me to actually reply to this?* Evaluate relevance, credibility, CTA friction, the stranger test (LinkedIn), peer tone, and whether it reads as AI-written. Improve what's weak, keep what works, preserve the waterfall structure. In `review` mode, read the current copy from the spec file, review it, and refresh the export if one exists.

**The HUMAN TEST, last:** a passing checklist is not approval-ready copy. Structure is not outcome. Final read as the recipient: *does this sound like a person wrote it to me specifically?* If it reads assembled, rewrite until it doesn't.

---

## Phase 3 (OPTIONAL): Export for Your Sequencer

Only when the user asks, or before a launch. **Skip for LinkedIn-only campaigns** (DMs go into your LinkedIn tool by hand or by its own import). Write `output/campaigns/<workflow-slug>/sequencer-export.md` in this plain, tool-neutral format, then convert syntax and field names to whatever your sequencer expects:

```
Campaign: <campaign name>
Recommended settings: plain text ON, open tracking OFF, ignore out-of-office replies ON
Suggested schedule: Mon-Fri, 08:00-17:00 in the prospect's timezone (confirm)

Custom variables (one column per variable in the lead upload):
- e1l1, e1l2, social_proof, e1ps, ...   (exclude built-ins such as first_name, last_name, company_name, email, sender signature)

Step 1 | wait: 0 days | new thread
Subject: {subj variant 1|subj variant 2|subj variant 3}
Body:
{{first_name}},

{{e1l1}}

Static line with {spintax|variation}.

{{social_proof}}

{Worth a conversation?|Open to exploring this?}

{{sender_signature}}

{{e1ps}}

Step 2 | wait: 3 days | same thread (subject "Re: <same subject>")
Body: ...

Step 3 | wait: 7 days | same thread
Body: ...
```

### Construction rules
1. **Campaign name:** from Phase 0.
2. **Schedule:** default Mon-Fri 08:00-17:00 in the prospect's timezone (e.g. America/New_York); ask for overrides.
3. **Settings, golden rules, no exceptions:** plain text ON, open tracking OFF, ignore out-of-office replies ON. Leave daily caps high on the campaign; throttle at the mailbox level.
4. **Sequence steps:** one per email. Subject variants as spintax; follow-ups reply in the same thread with the same subject (`Re:`), always. Wait days default `[3, 7, 14]` between steps; ask for overrides. Step 1 starts a new thread; every later step is a thread reply.
5. **Custom variables:** every non-built-in variable used, each from the spec's variables contract (your data tool fills those columns per lead). Exclude built-ins such as `first_name`, `last_name`, `company_name`, `email`, and the sender signature.
6. **`{{first_name}}` standalone in every body:** the data tool resolves dynamic tags WITHOUT the greeting; the body is always `{{first_name}},` then `{{e1l1}}`.
7. **Tag:** a campaign tag or name your sequencer and reporting can group by (from Phase 0).
8. **Regenerate the export whenever the copy changes** (review mode does this automatically). It must always match the latest approved copy in the spec.
9. LinkedIn DMs never go in the email export.

---

## Output Format: The Copy Album

Appended to the spec file under a `## Copy` heading (Email 1/2/3 with each dynamic line's waterfall listed under it, then a LinkedIn section if applicable). Requirements:

- **Albums are fully spelled out.** Every resolved line appears in full: social proof lines written out, PS written out. Tags like `{{social_proof}}` and `{{e1l1}}` belong in the sequencer export, never as the album's content.
- **Dynamic sections** list every variant under its deterministic condition (`+ CONDITION:` ... `FALLBACK:` if applicable), one clean sentence per variant, no spintax.
- **The album ends with one fully assembled sample email** exactly as a prospect receives it (a real cell, all lines resolved), so anyone reviewing sees the actual thing.

## Saving & Status

1. **Save on approval:** the moment the user approves a unit, append it to `output/campaigns/<workflow-slug>/workflow-spec.md` under `## Copy`, and advance the `**Status:**` line truthfully (e.g. `STRUCTURE-APPROVED 2026-07-30 · E1 approved · E2/E3 pending`, then `COPY-APPROVED 2026-07-31`). Don't batch saves for later.
2. **Status claims only from files.** Any statement about what's built (to the user, in a team update, anywhere) comes from reading the saved files in that same session. Never from memory. If it isn't in a file, it isn't built.
3. Log each save in `work-log/`.
4. Before launch, do a final manual read against `knowledge-base/playbooks/copy-iron-laws.md`. Copy QA is human-driven.

---

## Edge Cases

- **No ICP or context files:** ask for persona, industry, size and positioning directly. Don't guess.
- **No facts.md:** collect authorized facts from the user, create `context/messaging/facts.md` from `knowledge-base/playbooks/templates/facts-template.md`, then continue. Never write copy without a facts file.
- **No spec, or status below STRUCTURE-APPROVED (any mode, render included):** bounce to `/build-workflow-spec`. Don't improvise structure, don't write copy.
- **Partnership play:** spec required like any other, declaring `Routing: none (static play)`. Copy is then a static sequence, peer register, heavy spintax, no waterfall. GATE 2 reads back the play's premise and each email's role from the spec.
- **Voice undocumented:** ask for tone or examples. Don't default to a generic voice.
- **Very few secondary signals:** simpler album, fewer dynamic lines. FALLBACK-only is fine.
- **Review mode, no existing copy:** ask for the copy or switch to `full`.
- **LinkedIn-only:** skip the email export.
- **Partial context:** ask for what's missing. Never fill in targeting yourself.
