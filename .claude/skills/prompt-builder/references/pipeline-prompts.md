# Reusable prompts in mass pipelines

This route builds the unit of intelligence that will run repeatedly without its author.
Its product is a runnable prompt whose method transfers to the target model on unfamiliar
records. A qualification label, a schema and an instruction to use good judgment do not
carry that method. Explain the judgment the model would otherwise have to invent.

Use this route for both new and repaired prompts in Clay columns, API batches, enrichment,
classification, scoring, extraction and repeated copy generation. Scale means mistakes repeat;
it does not mean every task needs several model calls or an elaborate framework around it.
Keep one call when it can perform the agreed decision well.

## Establish the executor's actual world

The builder and executor have different knowledge. The builder can read the conversation,
accepted examples, campaign decisions and repository. The executor receives only the rendered
messages, inserted record data, and tools actually available to that call. Design from that
boundary even when the builder is a much stronger model than the production executor.

Inspect a real invocation or representative row before drafting. Establish what one call
operates on, what upstream decisions are already settled, what result the next consumer uses,
and which model and settings will execute it. Use the configured campaign/runtime as authority.
The user picks the target model. For per-row work at scale, a cheap but capable model is
usually the right default because every token is paid once per row; if the user has not chosen,
propose one and label it as an authoring assumption. Do not silently change a live column's
model. Write down the exact model id that will run (the `model` input on the Clay column) and
confirm that id is available in the user's Clay workspace; `clay-api-reference.md` lists known
ids, but availability changes, and a retired id fails at run time. Testing on a stronger model
does not establish that the prompt works on the cheaper one that will actually run it.

Compile the useful understanding from the build into the prompt:

- An approved ICP becomes its operative company definition, inclusion/exclusion criteria and
  uncertainty policy. A thread ID or “use the approved ICP” does not supply any of that.
- A source-backed campaign decision becomes a clear premise. When companies are already
  qualified, the person prompt receives that premise and does not reopen the employer gate.
- An accepted writing sample becomes both an example and an explanation of the choices that
  make it work. “Write like the examples we discussed” transfers nothing.
- A rule that varies by campaign belongs in a required, populated campaign-policy slot, so it
  does not silently become universal. Row facts belong in record slots. Stable method stays
  separate from both.

Keep task IDs, thread IDs, approval history, file provenance and build commentary in the
authoring note or external run metadata. Include an identifier inside the executor's prompt
only when the actual decision or output association needs it. Include a reference to another
document only when the executor can retrieve it with its available tools and doing so belongs
to this call. A URL can be evidence or a genuine research input; its presence is not proof that
the model has read it. Never make the executor reconstruct the build conversation.

The isolation test is concrete: render the final prompt with one row, hide the conversation
and repository, and read only what the executor will receive. Check that it can tell what is
being decided, which evidence supports each branch, and what the consumer expects. Supply missing
knowledge or repair the binding before adding more instructions.

## Recover the method before writing its instructions

Read [the full decision-to-prompt teaching case](decision-to-prompt.md) before authoring
this route. It teaches the builder's own judgment as well as the executor's procedure.
Start from the accepted job and a representative situation. Do not start from the old
prompt's table of contents. Existing prompts expose previous implementation choices to examine. They do
not acquire policy authority simply because they are detailed or already deployed.

Reconstruct one supported result before generalizing it. Explain why the receiver needs that
result, which raw evidence makes it appropriate, and what material change would reverse or
redirect it. Separate uncertainty about relevance from uncertainty between relevant labels,
and separate both from buying-role confidence. In writing, distinguish why someone entered
the list from why the message is worth reading. Use accepted work to understand these choices,
then test the explanation on a contrast. Only a sound distinction belongs in a teaching example.

Resolve source conflicts at this authoring stage. Preserve the consumer's actual contract,
but repair obsolete inputs and rules within the user's authorization. When the old prompt
omits a useful available source field, inspect and bind it instead of calling the limitation
irreparable. If the contract is fixed and prevents the result, surface that exact conflict;
do not conceal it in a plausible output. If an accepted example and factual evidence conflict,
retain the example's communicative function while choosing supported claims or omitting optional
proof. Do not make the isolated executor arbitrate the authoring conversation.

Compile the resolved job positively. A company decision may need offer, payer and reachability;
it does not need an explanation of the person stages that were removed. Carry exclusions when
they distinguish plausible runtime inputs under the real policy. Remove authoring-history
concepts. Do not document all the reasons they are irrelevant. Every retained input or
instruction should do identifiable work in the decision or the consumer contract.

Start with the hardest distinction the output must get right. “Is this B2B?” is not yet a
method. A usable method explains that B2B concerns who pays for the primary commercial offer,
how to identify that offer behind marketing language, and why sponsors or investors do not
necessarily make the audience-facing business an outbound fit. The exact policy still comes
from the owner; this example is not a universal ICP.

For every judgment on which the result depends, explain the phenomenon in plain language,
the evidence that reveals it, the inference that evidence permits, the nearest misleading
alternative, and what to do when the evidence cannot distinguish them. Write the relationships
between decisions: which fact must be established first, what can override another finding,
and which tempting inference is unsupported. Preserve useful exceptions instead of replacing
them with a slogan such as “be conservative”.

Work from accepted examples and real corrections when available. Reconstruct why the accepted
decision follows from its inputs. An example's brand, phrasing or layout may be incidental;
its payer distinction, temporal precedence or claim boundary may be essential. When no method
is established, develop a candidate on representative records and mark its assumptions. Do
not put an invented threshold or unaccepted business exclusion into the runtime as fact.

In a repair, locate the earliest incorrect decision. A wrong greeting may come from trusting
a malformed First Name while an intact Full Name is available. A generic question may come
from a fixed question template that ignores the implementation mandate. “Improve the style”
does not repair either mechanism. Update the method, all affected examples and the inputs that
feed it. A change to eligibility must also change any exclusion that could still override it.

## Teach more reasoning where the decision needs it

Write an explicit, task-specific decision procedure. Give the executor enough reasoning to
perform the work. Do not assume it will supply the builder's missing expertise. This
is required even when the target has built-in reasoning. Model-family advice to avoid generic
chain-of-thought requests is not a reason to omit domain method or procedural explanation.

For a company qualifier, a procedure might teach the executor to identify the sellable offer,
identify the payer and purchase purpose, separate them from users/partners, apply the supplied
segment rules, resolve mixed evidence according to the policy, then choose a verdict. For
person qualification it may need to establish current function before assigning current
buying authority; a prior manager role is evidence of history and does not show present seniority.

For copy, teach argument construction. Identify what changed at the recipient's company,
what concrete decision that change creates, how the sender's offer relates to that decision,
and what the evidence does not allow the message to assert. A new appointment can determine
whom to contact without supplying the reason to buy. More company facts do not fix a missing
connection between the observation and the question.

Explain why the sequence matters so the executor can apply it to a new record. Avoid both
extremes: a list of labels such as “analyze, reason, decide”, and an exhaustive script of
microsteps unrelated to consequential choices. Length is useful when it carries recognition,
decision logic and causal contrasts. Remove repeated warnings and build history. Keep the teaching.

Separate the taught method from the output's explanation. A concise evidence-and-rule
justification can help audit a classification; it is not a request to reveal private internal
thought. If the consumer accepts a reason field, define what evidence and decisive criterion
it should cite. If the consumer accepts only a label or copy body, preserve that contract.
Do not add a reasoning field that breaks parsing or leaks analysis into outreach. Diagnostic
explanations can be collected separately during authoring without claiming that their presence
proves the decision was sound.

## Use worked examples to transfer distinctions

For judgment-heavy pipeline prompts, include worked few-shot examples by default. Choose
them for the distinctions they teach. Do not add examples to reach an arbitrary count. Use the actual input
shape and demonstrate the exact final output shape. Include concise teaching commentary that
connects evidence to the decisive rule and explains the plausible wrong answer. Make clear
which commentary teaches the method and which text is the runtime output.

A set of attractive positive outputs is weak when every example can be solved by the same
keyword. Choose meaningful contrasts: a close positive and near-miss, a different positive
route, or missing/conflicting evidence when the real task encounters it. For a simple literal
transformation, fewer examples may suffice. Omit examples only when the task is sufficiently
unambiguous and target-model evidence supports that choice; explain the exception in the
authoring note. Do not inherit a zero-shot default merely because the task involves reasoning.

The following fictional miniature shows what teaching looks like. It illustrates one
particular owner policy. Do not reuse it as a definition of every B2B campaign.

**Closed policy:** qualify repeatable products or services sold to organizations for business
use. Exclude media, events and communities, even when they sell sponsorship. Return UNCLEAR
when the webpage cannot establish the commercial offer or payer. Funding and company size
are not gates. Input is website text only; there is no browsing tool. Output is exactly one
of QUALIFIED, DISQUALIFIED or UNCLEAR.

Weak prompt: “Read the website and decide if this company is a good B2B fit. Use our approved
ICP. Be accurate. Return the verdict.” It leaves both the ICP and the means of applying it
outside the call.

A stronger instruction explains: “Identify the primary offer and who pays for it. Judge the
purchase purpose rather than industry-sounding words. Apply the campaign exclusions after
identifying the business: a corporate sponsor does not override the event exclusion. Do not
use funding as a substitute for knowing the product. If you cannot establish offer and payer
from the supplied text, use UNCLEAR rather than inventing them.” It then teaches with:

| Supplied website text | Teaching explanation | Exact output |
|---|---|---|
| “LedgerOak: monthly reconciliation software for finance teams; organizations subscribe per legal entity.” | A repeatable software offer is bought by organizations for a business workflow. | QUALIFIED |
| “FoundersCircle: founder events and a member community; enterprise sponsors can purchase partner packages.” | Corporate sponsors exist, but the primary business is expressly excluded events/community. Sponsor presence does not override that exclusion. | DISQUALIFIED |
| “NorthLab: outsourced compliance reviews on a recurring retainer for manufacturers.” | This is a repeatable business service. Requiring a software product would invent an additional restriction. | QUALIFIED |
| “TomorrowWorks: venture-backed innovation transforming how people connect.” | Funding and aspirational language establish neither an offer nor its payer. Lack of evidence calls for UNCLEAR, not a guessed fit or an invented disqualifier. | UNCLEAR |

The useful contrast is between commercial roles. The invented names do not matter. A new
example should change the evidence or boundary so the executor has to apply that distinction
instead of memorizing a brand. Synthetic examples must be labeled as synthetic in the authoring note and remain
consistent with the actual owner's policy. They do not establish that the policy is correct.

For writing, carry the same depth through complete input-to-output examples. Suppose a finance
job asks someone to build AI workflows and a company signal confirms a billing-system change.
The relevant question concerns how those workflows will operate around the new system. If a
second company's signal says the system is already deployed, a generic “are you considering
automation?” question ignores known progress. Teach the change in question selection, then
show complete sample messages using the actual sender, offer and claim limits. Do not paste
this hypothetical campaign into unrelated copy prompts.

Before shipping, apply each instruction and prohibition to the accepted examples themselves.
If the rule rejects an accepted opening, find the distinction the ban erased. “Do not flatter
someone's profile” need not prohibit a factual observation about their responsibility. Adding
more examples will not resolve an instruction that explicitly forbids their successful move.

## Assemble the runnable prompt and its separate authoring note

The runnable artifact contains the task, the relevant campaign policy, the taught method,
worked examples, runtime context slots, uncertainty behavior and the consumer's output
contract. Choose readable sections and delimiters for this task; no universal tag set or word
count is required. Define the output only after the reasoning and inputs are understood.

The separate authoring note carries source provenance, unresolved owner choices, target model
and settings, real field bindings, prompt version and test evidence. Review both, but do not
paste that note wholesale into every call. Resolve owner-only decisions at build time. A
noninteractive batch row should return its specified missing-data outcome or use a defined
runtime error path. It should never ask the owner a question in its output. Never invent a new verdict or
change the parser to make a prompt appear complete.

Inspect actual nested input paths, enums and output keys against the consumer. Confirm the
rendered values are present. A column with the intended name existing is not enough. A
company-level premise may need Company Name and Domain; it does not automatically benefit
from two entire employment histories. A broken field split may need the original Full Name.
Choose context according to the inference it supports. Do not apply a blanket “more” or “less” rule.

### Wiring the prompt into a Clay AI column

In Clay, the runnable prompt is the column's `prompt` input: a formula that concatenates the
stable instructions as string literals with column references for the dynamic slots, for
example `"...instructions...\n\nRECORD TITLE: " + {{f_title}} + "\nCOMPANY: " + {{f_company}}`.
Keep long instructions in `prompt`; `systemPrompt` is limited to roughly 1,000 characters.
Choose `useCase` deliberately: "use-ai" (Create Content) sees only the bound row data, while
"claygent" can browse and costs more. The prompt must describe the tools the executor actually
has. For JSON output, define the schema in `answerSchemaType` and read fields with formula
extractors such as `{{f_ai_col}}?.qualification`. The enums and keys in the prompt text must
match that schema. See `clay-api-reference.md` for the exact input shapes and encoding pitfalls.

The safest way to deploy a new prompt is to copy a known-good AI column and swap only what
changed: `clay.clone_column(source_table_id, source_field_id, table_id, name,
input_overrides=..., condition=..., view_id=...)` keeps the working auth account, model and
schema wiring while you override the `prompt` (and `model`, as a quoted formula string, if it
changes). `input_overrides` sets `formulaText` only, so to change the output schema, clone a
column that already has the schema you need, or send the full `answerSchemaType` binding
(with its `formulaMap`) through `update_column`. To revise an existing column, `clay.update_column(table_id, field_id, updates)` merges
`inputsBinding` entries by input name, so you can send only the inputs you are changing. Read
the column back after saving and check that the rendered references point at populated fields.

## Prove transfer on the target executor

Test the serialized prompt with only the declared inputs and tools in fresh target-model
calls. Use the exact model id that will run in production. Give the executor no build
conversation, hidden answer key, author diagnosis or repository method beyond what the
runnable prompt actually includes. For a tool-using prompt, provide the same retrieval
capability. A fixture run on the target model outside Clay can establish bounded prompt
behavior but does not prove the column's settings, Clay bindings or live-table execution
unless those surfaces were actually exercised.

In Clay, the first live check is one record:
`clay.run_and_wait(table_id, [ai_field_id], [record_id])`, then read the cell's value and
status. Knowing that it ran is not enough. Confirm the JSON parsed, every extractor column shows a value,
and the decision is right for the right reason. Only then run a small canary, then the rest.
Use the `calculate-costs` skill on the canary to check per-row cost before scaling.

When evaluating a prompt builder, give it the accepted purpose, business policies, source
corrections and actual consumer requirements. Those define the job and are not answer leakage.
Withhold evaluated row answers, previous generated outputs and the evaluator's diagnosis.
A historical prevention test is different: score only requirements knowable at that original
time. Do not withhold a later policy while requiring the builder to reproduce it. Do not
instruct preservation of the defective prompt's inputs or policy unless the owner actually
closed that choice.

Use representative raw inputs that were not copied into the few-shots. Choose them to test
the consequential distinctions and realistic failure distribution. Establish expected
decisions from the owner policy/evidence before looking at the new outputs. Judge the work:
whether it made the right decision for the right supported reason, preserved meaning and
claims, and supplied usable output. Syntax, plausible explanations and successful execution
cannot substitute for that judgment. Keep false acceptance and false rejection visible; a
favorable average may conceal a broken critical boundary.

When a test fails, separate three explanations: the author selected the wrong judgment,
the runnable prompt failed to carry a sound judgment or required evidence, or the executor
failed to apply a judgment that was actually supplied. Inspect the relevant artifact. Do
not assume a wrong output means the executor needs more reasoning. Also check that the
test supplied the business policy it scores. Find whether source authority, data, method,
example, binding or output contract caused the failure. Repair that cause and repeat the affected cases and relevant passing cases on the
final version. Examples used to repair the prompt become calibration cases; reserve fresh
cases before claiming generalization. If reasoning is weak, teach the missing distinction
and show a causal contrast. Asking for more effort or a stronger model will not fix it.

Before mass use, run an authorized small canary through the actual consumer and inspect its
outputs. Confirm they were generated by the current prompt rather than stale cached results.
Only then assess whether cost or latency warrants reducing examples or wording. Compare the
reduced version on the same meaningful cases so compression cannot silently delete competence.

Report exactly what is known: authored, saved/read back, fixture-tested on the named model,
live-canary-tested, or approved for the stated rollout. A final prompt that has not been rerun
remains untested at that revision. Keep reusable production maturity scoped to the cases,
model/settings and surface that were proved; broader evaluation design belongs to its own
workflow.
