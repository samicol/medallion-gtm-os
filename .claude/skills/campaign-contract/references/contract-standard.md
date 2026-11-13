# Campaign contract standard

A campaign contract is a build sheet. One operator reads it with Clay open on the other screen and
builds the campaign from it without asking anyone a question. Everything in the file is something
they create or type; everything else belongs somewhere else.

That sentence decides every rule below. When a rule seems unclear, ask what the operator would do
with the sentence in front of them. If the answer is nothing, it does not belong here.

## The unit is the Clay object

One section per Clay object that exists in this build, numbered 1..N in the order the build runs.
There is no fixed count, no fixed list and no placeholder.

A Clay object is a source, a column (AI action, native enrichment, formula, cross-table lookup),
or a view that a named later step consumes. A concept, a phase, a policy or a check with no column
behind it is not an object and gets no section.

- A column that does not exist gets no section. Never write `Not applicable`: the operator reads a
  paragraph to learn there is no work.
- Two columns never share a section. The operator building the third column scrolls to the third
  section.

## Section 1 is the only section without an object

`## 1. Campaign Overview` carries two things:

- `Campaign in a nutshell`, inside `<details><summary>Campaign in a nutshell</summary> ... </details>`:
  short paragraphs in ordinary language on how rows are sourced and qualified, who is targeted, what
  the offer is, and what the copy opens on.
- `Starting Point`: one sentence naming the source in plain words.

Nothing else. The title line already carries the campaign, `DRAFT` and the date.

## Section anatomy

A heading, one table, the prompt block when the object has a prompt, a horizontal rule (`---`).
In that order, with nothing between them. If a sentence is not a table row and is not prompt text,
it does not go in the file.

## Section naming

A section whose object carries a prompt is `## N. Prompt / <plain-language job>`. Every other
section is `## N. <plain-language operation>`. The heading names the job; the exact Clay column
name lives in the `Column` row, where the operator copies it from.

## Deriving the rows

Every table has two columns with a `Field | Contract` header. Derive its rows from the object:
the table answers the questions an operator must answer to build this object. Seven questions
cover nearly everything:

1. What is it in Clay? `Source` for a source, `Column` for a column, plus `Type` when the kind is
   not obvious.
2. What does it do? `Role`, in one line. When the job is a decision with two sides, `We Qualify`
   and `We Exclude` say more.
3. What does it read? `Entry`, naming the upstream columns and exact fields.
4. What configures it? An AI action needs `Model` and `Model Account`. A source needs its filter
   fields in the order Clay's panel shows them, and its limit. A formula needs its expression. A
   lookup needs the table it reads and the key it matches on.
5. When does it fire? `Runs when`, as a plain trigger.
6. What does it produce? `Result`, the exact values or fields.
7. Does its result change what a later column does? `Downstream`, only then.

Include a row only when it carries a value. Write `-` when the field exists in Clay but is
deliberately unset. Reuse a row name whenever it answers the same question. A column type with no
example here still gets a section derived the same way.

Worked examples of the method. They do not cover every column type:

- **A source.** `Source`, `Table`, `Geography`, the filter fields in Clay's order, `Limit`,
  `Stage result`.
- **An AI column.** `Column`, `Role` or `We Qualify` and `We Exclude`, `Entry`, `Model`,
  `Model Account`, `Runs when`, `Result`.
- **A native enrichment or formula.** `Column`, `Type`, `Role`, `Runs when`, `Result`.
- **A cross-table lookup.** `Column`, `Type`, `Role`, `Reads from`, `Matched on`, `Runs when`,
  `Result`.

`Acceptance rule` rows do not appear. Acceptance belongs to the build and its verification.

## Facts and decisions

A **fact** is already true somewhere: a table's display name, which model account a workspace uses,
what a native enrichment is called, what a provider named a field. A fact is never a reason to
stop. Find it in the workspace (`clay_client.py`, `clay_browser.py`), on the web, or by opening the
thing and looking.

A **decision** is something nobody has made yet: which segment is in scope, what disqualifies a
company, what the copy may claim, how much may be spent. It is not yours. Name it and stop.

## What goes in a cell

A value. Do not write a sentence about the value: `Company Size | -` beats a line explaining that
size is judged downstream. Use Clay's own labels, in Clay's own grouping, with a blank line (`<br><br>`
inside a Markdown table cell) between groups:

```
Industry / Included:<br><br>Food and Beverage Manufacturing, Food and Beverage Services<br><br>Description / Contains:<br><br>brewery, brewing, craft beer
```

`Source` is the action's name in Clay's picker, such as `Find Companies` or `Find People`.
`Column` is `<exact column name> / <action type> / <model>`. `Model Account` is the account's Clay
display name.

Never put these in a cell: a workbook, table, source, field, view or account id (`wb_`, `t_`, `s_`,
`f_`, `gv_`, `aa_`), an `actionKey`, a raw API parameter name, or the data vendor behind a native
Clay source.

## Prompt blocks

One block per prompt-bearing column, directly under its table:

````
<details><summary>Prompt - <exact column name> / <action> / <model></summary>

```text
<the complete production prompt, verbatim>
```

JSON Schema

```json
<the output schema>
```

</details>
````

No summary above the prompt, no drafting notes. A column without a prompt gets no block.

## What never goes in the contract

A campaign map, a limits list, a list of what the campaign leaves behind, any live count or run
result, provider status, defect log or retry history, provenance ("which probe validated the
filters"), and any claim that a table already exists. A number belongs here only when it is a rule,
a limit or a criterion.

The contract ends at the last Clay column. It approves a build specification. It never authorizes
export, launch, scheduling or sending.
