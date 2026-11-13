---
name: miro-gtm-flowchart
description: Draw a GTM system (outbound, inbound, partner, any motion) as a clean, editable flow chart on a Miro board. Steps, diamond decisions, branches, exits, tool logos and a feedback loop, laid out in rows that snake across the board. Use when someone says "draw my GTM system on Miro", "map this workflow as a flowchart", "put my Context OS workflow on a board", or wants a visual of how signals, enrichment, outreach, replies and CRM connect. Needs the Miro MCP connected.
---

# Miro GTM flow chart

Turns a GTM system into a Miro flow chart in three moves: describe it as a small JSON spec, run `scripts/build_flowchart.py` to lay it out, then send the result to Miro and polish it from a screenshot. The script does the layout maths, so the chart comes out aligned and consistent every time.

Worked example: `examples/reliance-hmo.json` (an illustrative outbound system for a Nigerian HMO, 37 boxes in 3 rows).

## Before you start

1. **Miro MCP connected.** In Claude Code run `/plugin marketplace add miroapp/miro-ai` then `/plugin install miro@miro-ai`, restart, and sign in to Miro when the browser opens (pick the team whose boards you want). Check with the `user_who_am_i` tool. Install it one way only: never also add `https://mcp.miro.com/` by hand, or the tools duplicate.
2. **Python 3.** Pillow is optional and only needed for the local preview (`pip install pillow`).

## Step 1: get the system

Pull it from the user's Context OS (the target workflow) if they have one, or ask. You need, in order:
- where it starts (usually the Context OS: ICP, personas, offer)
- the signals and how accounts are found and enriched
- every decision (fit, size, existing tool, valid email, already in CRM) and what each answer leads to
- how people are found, how the message is personalised, how it is sent
- how replies are handled and what each outcome triggers
- the pipeline stages, and how results feed back
- which tool does each step

Group it into 2 to 4 rows (phases). Rows snake: row 1 left to right, row 2 right to left, row 3 left to right. That keeps every row-to-row link short.

## Step 2: write the spec

Save it in the user's repo, for example `diagrams/<name>.json`. Shape:

```json
{
  "title": "Acme: outbound GTM system",
  "subtitle": "One line on what this is. Say 'illustrative example' if it is about a real company you do not work with.",
  "rows": [
    {"title": "Find and qualify accounts", "direction": "ltr", "columns": ["1A", "1B", "1C", ["1D", "1E"]]},
    {"title": "Pick the people and write the message", "direction": "rtl", "columns": ["2A", "2B"]}
  ],
  "nodes": {
    "1A": {"kind": "start", "title": "Context OS", "sub": "ICP, personas, offer", "tools": ["claude_code", "github"]},
    "1B": {"kind": "step", "title": "Buying signals", "sub": ["Hiring 3+ roles", "Recent funding"], "tools": ["clay"]},
    "1C": {"kind": "decision", "title": "ICP fit?"},
    "drop": {"kind": "exit", "title": "Drop", "below": "1C"}
  },
  "edges": [["1A", "1B"], ["1B", "1C"], ["1C", "1D", "Yes"], ["1C", "drop", "No"]],
  "loop": {"from": "3G", "to": "1A", "label": "Weekly loop: results update the Context OS"}
}
```

Rules that keep it clean:
- **Kinds:** `start` (the first box and the review at the end), `step`, `decision` (drawn as a diamond), `branch` (a track, angle or reply outcome), `exit` (drop, exclude, fallback).
- **Ids:** use `1A`, `1B`, `2A`... and the id is shown in front of the title, so people can say "step 2D". Exits and helpers can use plain ids (`drop`, `li`); those are not shown.
- **Columns:** a string is one box; a list is a vertical stack (tracks, angles, reply outcomes).
- **Exits under decisions:** give the exit `"below": "<decision id>"` and leave it out of `columns`.
- **Decisions stay short:** 3 words or fewer ("ICP fit?", "Staff size?", "In HubSpot?"). The diamond only has room in its middle. Put the detail in the branch boxes it leads to. The script warns when a decision is too long.
- **`sub`:** a string for one line of detail, or a list for bullets (bullets are left-aligned).
- **Tools:** `claude`, `claude_code`, `github`, `clay`, `hubspot`, `n8n`, `plusvibe` get a logo and name in a chip on the box's top edge. Any other string shows as a name only. Override the chip text with `"tool_label"`.
- **Sizes:** boxes size themselves from their text. Set `"w"` or `"h"` to force a size (keep siblings the same).
- **Edge labels:** the third item (`"Yes"`, `"No"`, `"20+"`). Do not label links that leave a box from the same side as their neighbours (a stack fed round its outside edge): the lines overlap and hide the label. The script drops those labels and tells you; say it inside the target box instead.
- **Loop:** set `"align": "bottom"` on the loop's source box so the loop runs underneath everything.
- **Writing:** short labels, plain words, no em dashes.

## Step 3: build and check locally

```bash
python3 .claude/skills/miro-gtm-flowchart/scripts/build_flowchart.py diagrams/<name>.json -o diagrams/<name>.svg --preview diagrams/<name>.png
```

Fix every warning (long decisions, overlaps, unknown ids) and look at the preview PNG before going near the board. The preview is rough (straight lines, cut-off labels); it is for spotting layout problems, not judging looks.

On a board that already has content, place the chart in free space with `--x` and `--y` (find space first with the Miro `canvas_search` and `canvas_read_as_svg` tools).

## Step 4: send it to Miro

1. Get the board: use the URL the user gives you, or create one with `board_create`, but only after the user confirms (it cannot be undone).
2. Miro requires its own guide first: call `canvas_get_canvas_composer_skill` with no step, then with `step="design"`, then `step="dsl"`. The dsl answer is long and may be saved to a file; read the CONNECTOR, SHAPE, TEXT and protocol sections.
3. Call `canvas_create_from_svg` with the board URL and the full contents of the `.svg` file.
4. Read the result: `failed_items` must be empty. Keep the `result_svg`: it holds the `data-miro-id` of every item, which every later edit needs. Never invent or guess those ids.

## Step 5: polish from a screenshot

You cannot see the board. Ask the user for a screenshot and check:
- text cut off or touching the edges, especially in diamonds and stacked boxes
- chip names clipped, or logo and name not centred
- labels sitting on lines that overlap
- lines crossing a box or a row header

Fix with `canvas_update_from_svg`, starting from the latest `result_svg`. Updates are patches: send the `data-miro-id` plus only what changes, for example `<rect data-miro-id="..." data-font-size="19" />`. Restate x, y, width and height together when moving or resizing a shape; connectors must be restated in full.

Fixes that work:
- **Text overflows a box:** shorten it, drop the font size by 1 or 2, or make the box taller.
- **Chip text clipped or off-centre:** read the text's `data-rendered-bounds` from the result, then resize the pill to text width plus logos plus 28, and set the text's `data-width` a little wider than its measured width so it never wraps.
- **A label hidden by lines:** clear it with `data-content=""` on the connector and say it inside the target box.
- **"locked by session" error:** the user has that item selected in Miro. Ask them to click empty canvas, then retry.
- **Deleting anything:** confirm the exact items with the user first. Deletes cannot be undone from here.

## Style

Miro's Bright Paper palette: purple steps (`#dedaff`), yellow diamonds (`#fff6b6`), blue branches (`#c6dcff`), white exits, deep purple start and review (`#6631d7`), faint grey row lanes, Noto Sans. Change colours in the `KIND` table at the top of the script if you want your own brand.
