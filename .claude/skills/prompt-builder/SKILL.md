---
name: prompt-builder
description: "Build or repair a reusable prompt, most often the per-row prompt for a Clay AI column (Use AI or Claygent) or another mass pipeline. Use it when a prompt will run on many records without the conversation that wrote it. It produces the prompt with its real input bindings and JSON output schema, teaches the decision method through explicit reasoning and worked examples, and checks the behavior on the exact model that will run it."
---

> **Starter-kit paths.** Run commands from the repository root. Rex (`clay_client.py`, `clay_flow.py`,
> `rex-config.json`, `clay-session.json`, `action-registry.md`, `clay-api-reference.md`) lives in `tools/rex/`;
> the table registry is `tools/rex/registry/`; each campaign's files (brief, contract, table JSON, receipts)
> live in `output/campaigns/<slug>/`; company context (ICP, positioning, messaging) is in `context/`.
> Use `tools/rex/.venv/bin/python` where a command says `python3`.
> More Clay prompt patterns and worked examples: [`knowledge-base/playbooks/clay/prompts.md`](../../../knowledge-base/playbooks/clay/prompts.md).

# Prompt Builder

Use this skill to write a prompt that another model will run. Do not use it to answer the prompted task yourself.

The job has two reasoning steps. First establish the judgment the task requires, then teach the model that will run the prompt how to make it. Start by working through a representative situation using the accepted purpose and evidence. A polished explanation of an inherited wrong rule still produces the wrong result. Build the prompt from the demonstrated decision, its evidence and its boundaries; choose the output format for the consumer afterward.

In Rex, the usual product is the prompt for one Clay AI column: a "Use AI" (Create Content) or Claygent column that runs once per row, returns JSON through `answerSchemaType`, and feeds formula extractors or later columns. The `build-clay` skill calls this skill whenever a workbook needs such a column.

## Choose the execution route first

The executor's world determines the authoring method. A prompt that runs repeatedly on
records without this conversation needs more than a good task description.

**Reusable pipeline prompt:** for Clay columns, batch/API calls, qualification, enrichment,
scoring, extraction or repeated copy generation, read
[the mass-pipeline method](references/pipeline-prompts.md) in full before drafting or editing.
Use it for repairs too, even when an existing prompt looks close. It owns isolation,
transfer of reasoning, worked few-shot examples, real bindings and target-model proof. The
shared steps below support that route; they do not replace its teaching method. A specific
request for a mass-pipeline prompt takes precedence over generic zero-shot advice or a
wording-only rewrite.

**Other prompt artifacts:** use the shared workflow below. For an existing prompt, diagnose
its actual failure before choosing an edit or rebuild. A local wording revision is fine when
the method is sound; a missing method needs this skill's repair path, because cosmetic editing will not add it.

Look for an existing prompt before rebuilding: a known-good AI column in another table, a
prompt the team already uses, or one the user points to. Read a candidate's full prompt,
inputs, purpose and proof boundary. Do not judge it by its title. Reuse a compatible method, adapt the
distinctions the new task changes, and record where it came from in the authoring note. Reuse
never waives the isolation or method-transfer checks. General prompting advice, including
model-specific claims, needs current verification before you rely on it.

## Scope Check

Proceed when the user asks to create, repair, review, or improve a prompt that will guide model behavior beyond a one-off casual answer.

Do not use this skill when the task is only:

- answering a factual or coding question;
- executing an already-approved prompt without changing it;
- choosing models, routing providers, handling retries, or designing runtime infrastructure;
- designing benchmark architecture, fixtures, thresholds, or eval suites;
- formatting a final answer after requirements are already fixed.

If the task crosses those boundaries, write the prompt-related piece only and hand off the rest.

## Build Note

Before drafting the prompt, keep a compact working note. Do not turn this note into a rigid user-facing template unless the user asked for it.

```markdown
## Prompt Contract
Objective:
Prompt user:
Output consumer:
Runtime/model context:
Success criteria:

## SOURCE_BACKED
- ...

## WORKING_ASSUMPTIONS
- ...

## Questions Or Stop Conditions
- ...

## Instruction Strategy
Stable instructions:
Dynamic context slots:
Examples:
Output contract:
Revision hooks:
```

## Workflow

### 0. Objective Intake For Prompt Sets

When the user asks for a prompt pipeline, prompt pack, or multiple prompts that work together,
do not start by drafting one prompt in isolation.

First ask a short batch of objective questions, and plan the pack before implementing it when
it needs a real plan. The goal is to understand:

- what business decision the prompt set supports;
- which records, sources, or prior outputs each prompt receives;
- what each prompt must decide, extract, transform, or score;
- which choices belong to the owner rather than the agent;
- what output will be reviewed by a human and what will be parsed by code.

After the objectives are clear, build the whole prompt set as one reviewable pack. Clarify
objectives first, then show all prompts together so the owner can give feedback on the
complete system instead of approving fragments one by one.

### 1. Define The Prompt Contract

Identify:

- the behavior the prompt must produce and the decision method that produces it;
- who or what will run it;
- who or what consumes the result;
- source, privacy, language, tone, and runtime constraints;
- representative inputs, examples, failures, or edge cases;
- how a good output will be recognized;
- what the executor actually receives, separately from what the authoring session knows.

If a wrong choice would change business behavior and only the owner can decide it, ask. If the choice can be inferred from explicit task text or local artifacts, continue with a labeled assumption.

### 2. Establish what each source can decide

A source can be authentic and still have no authority over the question at hand. An old
prompt proves what was implemented. A parser proves which output keys the consumer accepts.
Neither proves the targeting policy. An accepted writing sample calibrates communication;
it does not automatically verify every factual claim in it.

Recover the accepted purpose and decisions from the owner, then interpret domain evidence
within that purpose. Separate the expert judgment embodied in examples from incidental
wording. Resolve a conflicting old instruction according to what its source can establish.
Do not combine both rules, and do not treat the most detailed artifact as authoritative.
Explicit owner authorization of a claim is meaningful, but acceptance of tone alone does
not silently confer it. When claim authorization is unclear, use supported proof or omit an
optional claim; ask only if resolving the conflict is necessary to deliver the requested work.

Preserve genuine constraints and identify which contracts are implementation choices. An
existing output schema may bind the consumer while an inadequate input binding needs repair.
An explicit owner restriction to particular inputs is a closed decision; a field list in the
broken prompt is not the same thing. Inspect available fields and dependencies before deciding.
Mark unresolved business choices and proposed inference policies as assumptions, never as facts.

Before a source fact enters a decision or message, preserve its subject, relationship and time.
A parent company offering a service does not establish an employee's function; a department
name in a title path is not a personal responsibility; an undated account of a past rollout
does not establish one underway now. Work through the attribution contrast in the pipeline
teaching case. An exact quotation can still be used to support the wrong proposition.

### 2a. Make the decision before drafting the instruction

Use a representative raw situation to establish how a competent operator reaches the wanted
result. Identify the decisive evidence, what that evidence permits, the nearest plausible
wrong interpretation, and the changed fact that would change the decision. For copy, write
one complete example and explain the argument's function before extracting the generation
method. For qualification, distinguish what determines relevance from what merely changes
confidence, category or seniority. You are working through the job here; do not turn it into another form.

Check the explanation against accepted corrections and contrasting cases. If the judgment is
still wrong or depends on hidden context, resolve that before writing instructions or synthetic
examples. Do not infer new business policy from personal preference. Where the standard is
underdetermined, make a bounded proposal and test or clarify the load-bearing choice.

For mass-pipeline work, read the complete
[worked builder example](references/decision-to-prompt.md) with the pipeline reference.
It shows the missing transition: conflicting sources to a defensible decision, changed
bindings, complete runtime teaching, and behavior checked separately from author understanding.

### 3. Gather Context Before Drafting

Read discoverable context directly before asking for it:

- the Clay table itself: column names, a few real rows, and which fields are actually populated;
- schemas, examples, fixtures, and sample outputs before defining fields;
- failing outputs, reviewer defects, traces, or eval notes before revising;
- privacy and storage rules when inputs might include private topics;
- source lines when the prompt itself will make source-backed claims.

Keep the search proportional. Do not start broad research unless correctness depends on external authority.

### 4. Choose Instruction Strategy

Add a section only when the task needs it. Do not copy sections from a universal template.

Use direct instructions when the goal and constraints are clear.

Add procedural steps when the task needs a sequence, audit trail, or protection against known failure modes.

Choose representative examples that teach the distinctions that change the decision. Examples that only show the output shape are not enough. The pipeline route defaults to worked few-shot examples for judgment-heavy tasks; it explains when a simpler task can justify fewer or none.

Use delimiters or section tags when the prompt mixes stable instructions with dynamic context, row data, retrieved text, or file excerpts.

Do not substitute generic "think step by step" language for a method. Teach the actual evidence interpretation, decision sequence, precedence, exceptions and reasons for close calls. A concise rationale field may support auditing when the consumer accepts it. It does not replace the method, and it does not require exposing internal thought.

### 5. Draft Stable Instructions First

Write durable prompt content before runtime inputs:

- objective;
- scope and non-goals;
- decision rules;
- context-use rules;
- source-backed fact vs working-assumption handling;
- question and stop conditions;
- example policy;
- validation or review hooks.

Keep stable instructions separate from dynamic values such as user text, record fields, retrieved snippets, run IDs, variable file paths, previous outputs, or one-off examples.

For a prompt pack, every prompt should have its own narrow contract. Do not let later scoring or
outreach needs leak backward into early gates. If a later prompt needs company evidence, do not
add company evidence to a title-only prompt just to make the pack feel complete.

### 6. Define Dynamic Context Slots

Name what must be inserted each run. For each slot, mark it required or optional.

Common slots include user request, source material, file excerpts, schemas, sample rows, current record fields, previous output, reviewer defects, or eval failure notes. In a Clay column, each slot is a column reference concatenated into the prompt formula (see the pipeline reference).

For a missing required slot, make the prompt ask a specific question, proceed with a labeled assumption, or stop. Choose based on the prompt contract. A per-row Clay prompt cannot ask anyone anything, so it needs a defined missing-data output instead.

### 7. Put Output Contract Last

Choose the lightest output contract the consumer can use:

- prose for human judgment;
- Markdown sections for reviewable work;
- tables for comparison;
- labels for classification;
- JSON or schema-bound output for downstream parsing;
- trace fields when later review or eval needs them.

For structured output, specify fields or schema, distinguish valid syntax from semantic correctness, and require downstream validation outside the model when relevant. In Clay, the JSON schema lives in the column's `answerSchemaType` input; the field names and enums stated in the prompt text must match it exactly.

### 8. Add Revision Hooks

Make the prompt easy to improve from evidence. Add only the hooks the task can use:

- prompt version or identifier;
- inputs used;
- output produced;
- failure labels;
- concise rationale or trace fields;
- reviewer defect IDs;
- known risks;
- assumptions to revisit.

Do not design benchmark suites inside this skill. Leave fixture design, pass/fail thresholds, and eval architecture to a separate eval workflow.

## Review Pack Shape

For a load-bearing prompt or prompt pack, prepare a short review pack before implementation.
Keep it short enough to inspect. Use this order:

1. Objective and non-goals.
2. Source-backed choices and working assumptions, with load-bearing assumptions clearly labeled.
3. Open objective questions if any remain.
4. Draft prompts, all together when this is a prompt pack.
5. One worked input/output example per prompt.
6. Expected output contract or schema.
7. Eval or proof plan, without claiming quality before evidence exists.

Do not present a prompt as production-ready because it is well formatted. A prompt becomes
accepted only after the objective is accepted, the assumptions are visible, and the result is
checked against examples or eval output appropriate to the task.

## Self-Check

Before handing off the prompt, verify:

- each load-bearing instruction follows from a source authorized to settle that question, or is a visible working assumption;
- the builder has resolved a representative case and its causal contrast before deriving runtime instructions;
- objective questions were asked before drafting a prompt pack;
- prompt packs were reviewed as one complete pack;
- owner-only decisions went to the owner as questions and were not invented as rules;
- discoverable context was read directly;
- stable instructions are separate from dynamic inputs;
- examples teach the needed decisions and do not conflict with any instruction or prohibition;
- a pipeline executor can apply the method using only its rendered inputs and actual tools;
- target-model proof is distinguished from an authoring-model demonstration;
- output format appears after task, context, rules, and examples;
- structured output includes external validation expectations when needed, and the prompt's field names match the column's JSON schema;
- the prompt avoids default chain-of-thought requests;
- model routing, benchmark design, and runtime infrastructure stayed out of scope;
- a later reviewer or eval can produce actionable revision evidence.
