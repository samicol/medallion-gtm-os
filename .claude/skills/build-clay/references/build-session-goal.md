# Goal for a Clay building session

Use this contract when the task is to build, repair, or materially extend a live Clay
campaign workbook. Replace every bracketed value before starting. The campaign-specific
facts in this goal outrank examples from old tables. The skill package defines how to build.
It has no authority to redesign the campaign.

## Session mode and outcome

```text
MODE: BUILD
CLIENT: [client]
CAMPAIGN / SEGMENT: [campaign]
TARGET WORKSPACE: [workspace name and ID]
TARGET WORKBOOK / DESTINATION: [link or exact destination]
BUSINESS OUTCOME: [what must become true in the live system]
OPERATOR: [who will use the finished workbook and what they need to do]
ACTIVATION AUTHORITY: [what may be built, run, imported, activated, or sent]
SPEND AUTHORITY: [approved limits, or NONE until explicit approval]
```

You are the builder for this session. Your job is to produce the authorized result in the
live system. Do not stop at a proposed structure, a script, or a list of next steps when the
remaining work is safe and already authorized. If the user changes a planning session into a
building session, explicitly replace the old mode with `MODE: BUILD` and restate the current
authority before writing.

Do not send, activate, schedule, import to a sending platform, or spend beyond the stated
authority. A list that is ready to send still needs explicit authorization before anything
is sent.

## Mandatory context receipt

Before designing columns or changing Clay:

1. Read completely:
   - `.claude/skills/build-clay/SKILL.md`;
   - `references/column-playbook.md`;
   - `references/technical-recipes.md`;
   - this goal contract;
   - Rex's `tools/rex/clay-api-reference.md` and `tools/rex/action-registry.md`;
   - any client-specific instructions and the build log, if one exists.
2. For new or adapted prompts, read the sibling `prompt-builder` skill and your approved
   prompt library, if you keep one, before authoring anything.
3. Prove the Clay session with `clay.me()` and confirm the target workspace.
4. Report a short context receipt: which files were read, the workspace, and the
   destination.

If a required file is missing or a referenced live component cannot be read, stop before
mutation. Name the exact missing or contradictory object. Never say that a file was read
unless it was actually opened in this session.

## Campaign manifest

Before implementation, write and maintain one compact manifest. It is the session's working
memory and must survive long runs and context compaction.

```text
Approved company definition: [definition]
Approved company exclusions: [DNC, clients, industries, geographies, sizes, history]
Approved persona: [responsibilities, seniority, titles, exclusions, geography]
Campaign groups: [the actual business groups]
Message sequences or variants: [the actual message paths]
Mapping from groups to sequences: [exact mapping]
Unknown-evidence policy: [exclude, include, hold, retry, or owner decision]
Company source of truth: [table, view, sheet, brief, or approved segment]
People discovery paths: [Find People, Claygent, other approved sources]
Canonical People destination: [one table]
Current-employment evidence policy: [accepted sources and exact verdict vocabulary]
Contact qualification policy: [what qualifies and what disqualifies]
Contactability policy: [email waterfall, validation, permitted statuses]
Copy source of truth: [approved copy, prompt library, evidence allowed]
Suppression and deduplication keys: [company and person]
Maximum contacts per company: [number or rule]
Final destination and hold state: [destination, no-send state, owner approval]
```

Do not infer a new campaign object from a Clay filter or an old table. In particular, do not
turn three company groups into three message sequences unless the approved campaign says so.
If two sources contradict one manifest item, resolve the authoritative source before build.

## Build logic

Design backward from the operator's next safe action. The visible causal chain is:

```text
source -> canonical identity -> evidence -> decision -> permitted action -> result
```

For normal account-first outbound, the production surface is:

```text
Companies
  -> company identity, exclusions, evidence, and company qualification
  -> one qualified Companies view
     -> Find People staging -> single-row Send table data
     -> People Search / Claygent -> contacts[] -> list Send table data
  -> one shared People table
     -> canonical person identity and real source lineage
     -> deduplication
     -> current-role evidence and Still Employed?
     -> one Company Table Data lookup
     -> Contact Qualification
     -> approved contactability actions
     -> approved copy
     -> held delivery or explicitly authorized activation
```

Use another archetype only when the approved campaign is signal-first,
people-first, or enrichment/export. Explain the chosen archetype in one sentence.

## Non-negotiable execution rules

- Make every Clay change through Rex's client (`from clay_client import ClayClient`), and
  prefer cloning a known-good live column (`clay.clone_column`) over hand-built payloads.
- Confirm the live workspace, workbook, source population, destination, model accounts, and
  auto-run state before the first write.
- Treat live Clay state as authoritative for configuration and run status. Documentation
  describes the intended pattern. It does not tell you what is complete in the live system.
- Create components in dependency order. Read every created action back before running it.
- For each action, verify name, action family, model, client account, prompt, native JSON
  Schema, mapped outputs, bindings, run condition, and manual or automatic run mode.
- Author or adapt prompts with the `prompt-builder` skill. Store the final prompt directly
  in the action, preserve prompt provenance, and use a native strict JSON Schema.
- Use native mapped child outputs for visible business values. Do not create formulas merely
  to extract an AI or source property for the next action.
- Use formulas only for real deterministic work such as normalization, deduplication,
  ranking, suppression, exact gates, fallback selection, and provider merging.
- A text field named `Source` or `Prospecting Source` is not source lineage. The destination
  must contain a real Clay source field and traceable source IDs.
- Build the shared People table before routing, but never call it complete while it is empty
  or unsourced. Prove one routed destination row from every source path.
- Deduplicate before paid person enrichment. Verify employment before contact
  qualification. Qualify before finding email. Find and validate email before copy when
  email is required by the campaign.
- Use one canonical company lookup in People and one canonical contact qualification. Do
  not recreate company fit in People or add a second AI copy-eligibility verdict.
- Price AI/model spend in USD and non-AI Clay spend in credits. Obtain explicit approval
  before each paid batch that is not already covered by the stated authority.
- Test one real eligible record before scale. Read the actual cell. HTTP success or a
  preview is not enough. Then test a mixed control set covering positive, negative, unresolved,
  fallback, duplicate, and former-employee paths.
- Reconcile eligible, attempted, succeeded, skipped, errored, and awaiting-callback counts.
  A processed-versus-eligible gap is a finding. Do not delete rows to close it.
- Keep one active mechanism for each job. After choosing the winning mechanism, repoint consumers,
  retest, remove obsolete actions and helpers, and clean the physical graph as well as the
  default operator view.

## Anti-satisficing rules

The following do not count as completion:

- a workbook, table, or field existing;
- a schema accepted by Clay;
- an API returning success;
- an empty People table with prepared text columns;
- prompts described in chat but absent from Clay;
- source labels without native lineage;
- formula copies of native action outputs;
- hidden clutter that remains active in the dependency graph;
- a plan for the next step when execution is already authorized;
- a safe stop used merely to avoid finishing available work;
- a representative sample without reconciliation of the full eligible population.

If any of these is the current state, report `WORK IN PROGRESS`, continue the authorized
work, and do not call the build done.

## Definition of done

Do not report completion until every applicable item has direct evidence.

### Context and campaign

- The context receipt is recorded.
- The campaign manifest is complete and contains no unresolved contradiction.
- The build preserves the approved groups, sequences, exclusions, unknown-evidence policy,
  persona, destination, and activation boundary.

### Architecture and implementation

- Every production column has a named role and a real downstream consumer or operator use.
- Companies, Find People staging, Claygent discovery, and shared People follow the selected
  architecture.
- Both people routes target the same People table with the correct single-row and list modes.
- Native source lineage, prompt content, strict schemas, mapped outputs, groups, bindings,
  model accounts, and run conditions were read back from live Clay.
- No paid action can run before the cheapest applicable exclusion and qualification gates.

### Execution proof

- One real row from each source path was traced from origin to destination.
- Each AI or enrichment action was proven on an eligible real cell before scale.
- The mixed control set produced the expected positive, negative, fallback, unresolved,
  duplicate, and former-employee behavior.
- Full-run counts reconcile, including errors and callbacks still in flight.
- Spend is reported in the correct units against the approved authority.

### Clean instrument and handoff

- The default views tell the workflow story from left to right.
- Obsolete experiments, duplicate decisions, dead formulas, duplicate triggers, temporary
  tables, and unused fields are removed rather than merely hidden.
- Runtime helpers that remain are still consumed and hidden from the default operator view.
- Auto-run and delivery authority match the agreed hold state.
- Exact table links, source filters, prompts, schemas, accounts, conditions, costs, and
  reproducibility artifacts are recorded in a short build log.

### Three final tests

- Labor test: name the human work that has actually disappeared.
- Truth test: trace every material output through identity, evidence, decision, and permitted
  action.
- Handoff test: confirm that another competent operator can run and diagnose the workbook
  without reconstructing the author's memory.

If any applicable test fails, the build is not finished. Repair the canonical mechanism,
rerun the revealing cases, and repeat the completion check.

## Progress and final report

During the build, report facts rather than intentions: what was read, what was created, what
one-row proof showed, what was repaired, what is running, and what remains blocked. Do not
repeatedly narrate the same next step.

The final report must contain:

1. the live result and direct links;
2. the campaign population and reconciled run counts;
3. proof from both people sources and every material decision path;
4. model spend, Clay credits, errors, callbacks, and retry tail;
5. the clean operator surface and hold or activation state;
6. the labor, truth, and handoff verdicts;
7. only the owner decisions or external blockers that still remain.
