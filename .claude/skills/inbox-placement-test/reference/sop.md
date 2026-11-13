# Inbox Placement Test SOP (Email Bison → MailReach)

**Purpose:** Verify inbox placement (inbox vs spam) for a pool of Email Bison sender inboxes using MailReach seed addresses. Run this before deciding to kill inboxes, after deliverability concerns emerge, or as a periodic fleet health check.

**Provenance:** field-tested across eight production runs on multiple sending fleets between June and August 2026, covering five sender pools per run across a mix of inbox vendors and auth types, e.g. Winnr (custom SMTP), Zapmail Google and IceMail Google (Google Workspace OAuth), Zapmail Microsoft and IceMail Microsoft (Microsoft OAuth). Every gotcha below is something that actually broke a run. The most instructive findings:

- One fleet-wide failure isolated **copy fingerprinting from infrastructure reputation**: rerunning the identical inboxes with entirely fresh, heavily spintaxed non-campaign copy flipped Microsoft/O365 placement from 0/8 to 8/8 fleet-wide while Google stayed at 0-2/8. Microsoft was fingerprinting the content; Google's block was domain reputation. See Step 4, fingerprint-isolation mode.
- A one-hour "active but zero sends" stall was caused entirely by **repeated pause/resume resetting the first-send clock**, not by a broken config. See Step 5.
- Blended placement scores hid the truth on a crossed inbox-to-recipient mapping. **Segment-aware scoring** (Step 13) was the fix.

---

## When to run

- Before a kill/keep decision on a pool of inboxes
- When reply rates drop and inbox placement is suspected (not just list quality)
- After deliverability issues are reported by a teammate or stakeholder
- Batched by tier after a per-inbox reply-rate analysis

---

## What you need

| Item | Where to get it |
|------|----------------|
| MailReach API key | `.env` as `MAILREACH_API_KEY`, needed to create tests (Step 2) and to pull results. If your org has several MailReach accounts, confirm which one should hold (and pay for) the run's tests before creating them. |
| MailReach CLI (optional) | Any thin wrapper over the MailReach API. Not required, `POST /v1/spam_tests` creates tests directly (Step 2), the raw API works fine on its own for both creation and results. |
| Email Bison API key | `.env` as `EMAILBISON_API_KEY` (one per workspace if you run several) |
| Bison API base URL | `.env` as `EMAILBISON_BASE_URL`, e.g. `https://<your-bison-host>/api/` |
| Sender IDs for each pool/batch | Pull from `GET /api/sender-emails`, token-audit them first (Step 0) |
| `mlrch-` tag per batch + fresh seed list | `POST /v1/spam_tests` (Step 2), or from the operator via the MailReach dashboard on the manual fallback |
| Copy | Your real workflow Email 1, `{FIRST_NAME}` as the only variable, spintax kept, Step 4 |

---

## Key concepts

### 1 MailReach credit per test (not per inbox)
Creating a test costs 1 credit. The seed addresses are sent to by the Bison campaigns. MailReach scans whether each seed received the email in inbox or spam.

### One Bison campaign per batch
Each campaign targets ALL seeds in the test and uses ALL inboxes in that batch as its sender pool. The campaign sends one email per seed. MailReach tracks placement at the pool level, not per inbox.

### Unique MailReach tag per campaign
Each MailReach test has a unique code (`mlrch-{hash}`). This tag must appear in the email body. MailReach uses it to match incoming emails to the correct test. Without it, emails will not be tracked.

### Stable seed set across tests
MailReach returns the same seed set within a period, so you can reuse seed leads already in Bison via `POST /leads/attach-leads` rather than re-creating them. Do NOT assume this across runs, see Step 2.

---

## Step-by-step execution

### Step 0: Pre-flight token audit (do this BEFORE building anything)

`GET /sender-emails` returning `status: "Connected"` does NOT prove an OAuth token is alive. On one run an entire 10-inbox pool showed Connected with fully dead tokens.

Sweep `GET /api/sender-emails/{id}/oauth-access-token` across every `google_workspace_oauth` / `microsoft_oauth` inbox in scope: 200 = alive, 400 "No token found" = dead. **Exclude dead pools from the test** and flag them for manual reconnection (browser re-auth in the Bison UI; there is no API fix). Custom-SMTP inboxes (e.g. Winnr) cannot be token-checked, their proof is the test send itself.

### Step 1: Create the Bison campaign (one per batch): the FIRST step

Bison campaigns are created FIRST. MailReach tests are created manually by the operator in the MailReach dashboard, who then provides the `mlrch-` tag (`code`) and `public_id` for each batch. Build everything that does not need a tag (campaign, settings, schedule, senders, seeds), then wait for the tags before adding the sequence steps (Step 4).

**Naming convention:** `Inbox Placement Test - {Mon DD YYYY} - {Pool}`, pool name only, no inbox counts or extra qualifiers. The pool name is the vendor plus auth type, e.g. `Winnr`, `Zapmail Google`, `Zapmail Microsoft`, `IceMail Google`, `IceMail Microsoft`.

```python
resp = api("POST", "/campaigns", {
    "name": "Inbox Placement Test - Aug 06 2026 - Zapmail Google"
})
campaign_id = resp["data"]["id"]
```

**Interrupted-run cleanup:** if a creation script is interrupted mid-run it leaves stray partial campaigns. Before proceeding, list the workspace's placement campaigns, verify against the intended set, and `DELETE /api/campaigns/{id}` any duplicates (confirm draft status, 0 sends, and no steps first).

### Step 2: Get MailReach tags + fresh seed list

**Confirmed working 2026-09-21, create tests via the API directly, no operator hand-off needed:**

```
POST https://api.mailreach.co/api/v1/spam_tests
X-Api-Key: Bearer {MAILREACH_API_KEY}
Content-Type: application/json

{"seedlist": 1}
```

Call once per pool. The response is the full test in one shot:
- `public_full_id`, the `mlrch-{hash}` tag, embed verbatim in the campaign body
- `public_id`, same value minus the `mlrch-` prefix, used for polling (`GET /v1/spam_tests/{public_id}`)
- `results[]`, the fresh seed list for **this** run (`email`, `first_name`, `provider`), already labeled with `desc` (Google Workspace, Office 365, Gmail personal, etc.) so you know each seed's bucket before a single email goes out

Since each call is scoped to one pool, there's no tag-to-pool mapping step and no swapped-tag risk from a hand-off, you generated the tag, you know which pool it's for. `seedlist` is optional (1-4, default 1), **use the same value for every pool in a run**, do not rotate it per pool. `2_load_seeds.py` and `config.json` assume one shared seed list per run, loaded once and attached identically to every pool; a different `seedlist` value per pool would silently break that (different addresses per pool, no script support for tracking which pool got which). Verified empirically that the same `seedlist` value returns identical seed addresses across calls made minutes apart, matching the "stable within a period" behavior this skill already assumed. Not verified across a run spanning hours, several real runs on this skill have taken that long (contention fixes, stuck-scheduling retries); spot-check a pool's `results[]` again before trusting the cross-pool comparison if a run drags on.

**Credit timing, verified empirically (not just from the docs, which are misleading here):** the response's `paid: true` field is set immediately on creation and does **not** mean a credit was actually spent from the visible balance, a real test was created, showed `paid: true`, and the MailReach dashboard credit count did not move. Sending a real email to that test's seed list and letting it collect results is what actually decremented the dashboard balance (confirmed 90→89 on a live account). So a created-but-never-sent-to test appears to cost nothing in practice; don't rely on that indefinitely, but it means creating a test slightly ahead of having copy ready is safe.

**Manual fallback still works** if the API is unavailable or you'd rather not automate a given run: the operator creates one test per pool in the MailReach dashboard and hands over, per test, the `mlrch-{hash}` tag and the fresh seed CSV. Ask explicitly for "the mlrch tag for each campaign plus the seed lead list," and record which tag maps to which pool carefully, a swapped tag from a manual hand-off still silently corrupts both tests' results, same risk as always existed on this path.

Either way, do NOT reuse seed addresses from a prior run's campaign leads, MailReach's seed set can change between tests, and stale seeds silently reduce the scanned count.

**Seed CSV conventions:** the operator export has columns `Email, First name, Last name`. Personal Gmail/Outlook seeds often arrive with BOTH names blank, backfill both from the email prefix with trailing digits stripped (`rita.johnson2r@...` → first `Rita`, last `Johnson`). Every seed must end up with a non-empty first name (Bison 422s on a blank `first_name`, and `{FIRST_NAME}` is in the copy).

### Step 3: Apply settings (PATCH /campaigns/{id}/update)

```python
api("PATCH", f"/campaigns/{campaign_id}/update", {
    "plain_text": True,          # plain text only (no HTML)
    "open_tracking": False,      # no tracking pixels
    "include_auto_replies_in_stats": False,
    "sequence_prioritization": "new_leads",  # fills step 1 first
    "max_emails_per_day": 1000,
    "max_new_leads_per_day": 30  # = the ACTUAL seed count; must submit both together
})
```

**Gotcha:** `max_emails_per_day` and `max_new_leads_per_day` must be submitted in the same PATCH call. If you submit only one, Bison validates the submitted value against 0 for the missing one and returns 422. Always send both fields together.

**Gotcha:** MailReach's seed set is a range (roughly 28-30), not a fixed number. One run had 30 seeds, 28 of which mapped to the four work/personal buckets. Set `max_new_leads_per_day` to the actual seed count you attach so all seeds fire in the first pass, and read scores out of the count that actually scanned (report it as "Seeds scanned N/30").

### Step 4: Add the sequence step (1 step only)

**Copy sourcing, two modes; pick based on what you are testing:**

- **Default (production-shaped):** use your REAL workflow Email 1, rendered with `{FIRST_NAME}` as the ONLY variable. Replace every other variable (`{COMPANY}`, `{ROLE}`, etc.) with a sensible static rendering, pick one dynamic-line route, and **keep the spintax in both subject and body** (variation only). This tests placement on copy shaped like production sends. Use the same subject/body across all pools; only the `mlrch-` tag differs per campaign. End the body with the tag on its own line.

- **Fingerprint-isolation mode:** when a whole fleet fails placement on production copy, the copy itself may be **content-fingerprinted** by the receiving filters rather than the infra being dead. To separate "copy is burned" from "infra is dead," rerun with **entirely fresh copy that shares NO phrasing with any live campaign**, spintaxed at the **phrase level** (spintax nearly every sentence, aiming for millions of unique renders, not the handful production copy carries).

  On a real run this flipped Microsoft/O365 placement from 0/8 to 8/8 across every pool on the same inboxes, while Google stayed at 0-2/8, proving Microsoft was fingerprinting the campaign copy while Google's block was domain/reputation and therefore copy-independent.

  Get stakeholder sign-off on the fresh copy before running. Keep `{FIRST_NAME}` the only variable (seeds lack `{COMPANY}`), and avoid cold-email-cliché subjects ("quick question", "worth a look"), they are themselves fingerprinted. Cap the subject to a short 2-3 word phrase grid.

```python
api("POST", f"/campaigns/v1.1/{campaign_id}/sequence-steps", {
    "title": "Inbox Placement Test - Round N - Batch X",   # required top-level field
    "sequence_steps": [{                                    # key is "sequence_steps", NOT "steps"
        "email_subject": "{<subject variant A>|<subject variant B>|<subject variant C>}",
        "email_body": "<p>{FIRST_NAME}, <opening line>.</p><p><br></p>...<p>mlrch-BATCH_SPECIFIC_TAG</p>",
        "order": 1,
        "wait_in_days": 1,   # must be >= 1 (API validation); step 1 still sends immediately on launch
        "thread_reply": False,
        "variant": False
    }]
})
```

**Gotchas:**
- The outer payload key is `sequence_steps`, not `steps`
- A top-level `title` field is required (the API returns 422 without it)
- `wait_in_days` must be >= 1 even for step 1 (validation rejects 0; Bison still sends step 1 immediately on launch)
- The body must include the MailReach tag verbatim as a line (anywhere in the body, the end is conventional)

**Pre-build-then-arm flow + tag-append UPDATE gotcha:** when tags are not in hand at build time, add the sequence step FIRST with the copy but WITHOUT the tag line (the campaign stays draft), then **append each pool's `mlrch-` tag later** once the operator provides it.

Appending uses **`PUT /campaigns/sequence-steps/{sequence_id}`** with the full `sequence_steps` array, and each entry MUST include the existing step **`id`** (from `GET /campaigns/{id}/sequence-steps`), or you get `422 "The sequence_steps.0.id field is required."` The POST-create endpoint does not need the id; the PUT-update one does. **The PUT ALSO requires a top-level `title` field**, exactly like the create call, omitting it returns `422 "The title field is required."`

`sequence_id` comes from `GET /campaigns/{id}.data.sequence_id`. Confirm the tag is in the body after the PUT via `GET .../sequence-steps`.

### Step 5: Set the send window

```python
api("POST", f"/campaigns/{campaign_id}/schedule", {
    "monday": True, "tuesday": True, "wednesday": True,
    "thursday": True, "friday": True,
    "saturday": False, "sunday": False,
    "start_time": now_local_hhmm,     # current time in the campaign timezone, e.g. "11:18"
    "end_time": plus_60min_hhmm,      # +60 min, e.g. "12:18", compressed same-hour default
    "timezone": "America/New_York",
    "save_as_template": False
})
# NOTE: to CHANGE an existing schedule, use PUT (POST is a silent no-op); read back to confirm.
```

**Gotcha:** the schedule endpoint requires individual boolean fields per day (`monday`, `tuesday`, …), NOT a `"days"` array. Sending a days array returns 422 "monday field is required".

**Gotcha:** `POST /campaigns/{id}/schedule` on a campaign that ALREADY has a schedule returns success but the effective schedule does not change, a silent no-op. Changing an existing schedule requires `PUT /campaigns/{id}/schedule`. Always read back `GET /campaigns/{id}/schedule` after any schedule write. Note the schedule is NOT embedded in `GET /campaigns/{id}` (there is no `schedule` key there); only the dedicated endpoint shows it.

**Gotcha:** even a successful `PUT` schedule change does NOT retroactively move already-queued `scheduled-emails` rows. A campaign launched with a wide window and later narrowed keeps its OLD per-lead send times (some of which may now fall outside the new window, or spill to the next day) until something forces a recompute.

**Fix: `PATCH /campaigns/{id}/pause` then `PATCH /campaigns/{id}/resume`**, this recomputes the full schedule against the current window. This is safe (and does not conflict with the "don't pause/resume a stalled campaign" rule below) specifically when `emails_sent == 0`: nothing has fired yet, so there is no in-progress send clock to disrupt. Verify via `/scheduled-emails` that all rows now land in-window before walking away.

**DEFAULT: a COMPRESSED window that closes ~60 min from launch** so the whole test sends within the hour instead of trickling across the afternoon. Set `start_time` to the current local time and `end_time` to +60 min (launching 11:18 → `11:18`-`12:18`). This is the single most important setting for a fast result, and it interacts with pool size, see the round-fit gotcha below. The 60-min window must still fit the longest pool's rounds, and it does for a standard 5-pool fleet (smallest pool 10 inboxes × 30 seeds = 3 rounds ≈ 45 min, leaving ~15 min buffer). Only widen past an hour if a pool is small enough that its rounds do not fit.

**Gotcha: the window must fit the ROUNDS, not just the seeds.** Each inbox sends at ~15 min intervals. If `seeds > inboxes`, each inbox has to send `ceil(seeds/inboxes)` rounds, ~15 min apart. A small pool needs a long window: 30 seeds on 10 inboxes = 3 rounds, so you need at least ~30 min AFTER the first send just for that pool, and in practice much more headroom. A too-short window fits only the rounds that span it and **defers the rest to the next daily window** (you will see a ~1,430-minute jump in `scheduled_date`).

**Sizing rule for the compressed default:** window ≥ `ceil(seeds ÷ smallest-pool inboxes)` rounds × ~15 min + ~15 min buffer, plus the ~5 min first-send arm. A pool under ~8 inboxes with 30 seeds needs 4+ rounds (>60 min), so widen the window just enough to fit its rounds; never force a sub-round window. Confirm every pool's rounds land in-window via `/scheduled-emails` before walking away.

**Gotcha: do NOT use pause/resume to "re-pack" or "kick" a slow campaign.** On launch Bison schedules the first send ~3-5 min in the future, and **every pause→resume RESETS that clock forward again.** Repeatedly kicking a campaign that looks stuck is self-defeating; it was the entire cause of a ~1 hour "active but 0 sends" stall on a real run, where nothing was actually broken. **Launch once, then hands-off.** If you must change the window, do it in a single `PUT /campaigns/{id}/schedule` and accept that the first send re-arms ~5 min out. To confirm what is actually queued instead of kicking it, use the `scheduled-emails` endpoint (Step 10).

### Step 6: Attach the batch's sender inboxes

```python
api("POST", f"/campaigns/{campaign_id}/attach-sender-emails", {
    "sender_email_ids": [str(sid) for sid in batch_sender_ids]  # list of strings, not ints
})
```

**Gotcha:** Bison's `POST /duplicate` does NOT copy sender emails. If you duplicated a base campaign, you must re-attach sender emails to each copy manually.

### Step 7: Attach the MailReach seed leads

Use the **fresh seed list from THIS run's test creation** (Step 2), the same `results[]` returned by `POST /v1/spam_tests` when you created the tag, not a separately-sourced list. Never lead IDs or addresses recycled from a prior placement campaign, in this workspace or another. (On the manual/dashboard fallback, this is the operator-provided seed CSV instead, same rule applies.)

```python
# Create fresh leads from this run's seed addresses (results[] from Step 2, or the operator's CSV on the manual fallback)
for seed_email in seed_addresses:
    name_parts = seed_email.split("@")[0].replace(".", " ").split()
    first_name = name_parts[0].capitalize()
    last_name = name_parts[1].capitalize() if len(name_parts) > 1 else "Seed"
    api("POST", "/leads", {
        "email": seed_email,
        "first_name": first_name,
        "last_name": last_name
    })
```

**Gotcha: `allow_parallel_sending` must be on the ATTACH call, not just lead-create.** Setting `allow_parallel_sending: true` only when creating the leads is not enough. `POST /campaigns/{id}/leads/attach-leads` must ALSO carry `"allow_parallel_sending": true` in its payload.

Without it, the first campaign's attach succeeds and "claims" the leads, then every subsequent campaign returns `422 "No leads were added because they are either in other sequences, have previously bounced, or unsubscribed"`, the seeds look like they are already committed elsewhere. Pass `{"lead_ids": [...], "allow_parallel_sending": true}` on every attach. Re-attaching to a campaign that already has them returns the same 422 harmlessly, so verify with `total_leads == 30`, not with the attach response.

**Gotcha:** some MailReach seeds (often the personal Gmail ones) come with a **blank first name**, and Bison's `leads/create-or-update/multiple` returns **422** on an empty `first_name`. Backfill it from the email prefix before loading (`seed_email.split("@")[0]` → capitalize) so every seed has a name. `{FIRST_NAME}` is the only variable in the placement body, so a blank one also breaks the copy.

### Step 8: Verify before launch

Check via `GET /api/campaigns/{id}`:
- `total_leads` equals the seed count
- The body contains the correct MailReach tag (check `GET /campaigns/{id}/sequence-steps`)
- The sender pool is attached (total sender count matches batch size)

```python
# Quick sender count check
count = 0
page = 1
while True:
    r = api("GET", f"/campaigns/{id}/sender-emails?page={page}&per_page=15")
    count += len(r["data"])
    if page >= r["meta"]["last_page"]:
        break
    page += 1
print(f"Senders attached: {count}")  # should match batch size
```

**Gotcha:** `GET /campaigns/{id}/sender-emails` paginates at 15/page. Checking only page 1 always shows 15, paginate to get the real count.

### Step 8.5: End-to-end pre-launch QA (do this before the launch gate)

A one-line `total_leads`/sender count check is not enough. Run a real QA sweep across all campaigns and only launch on all-green:

- **Copy / spintax integrity (per campaign):** braces balanced in subject AND body (`count('{') == count('}')`); every `{...}` group is either spintax (contains `|`) or a known variable (`FIRST_NAME`, `SENDER_EMAIL_SIGNATURE`), flag any unknown token; no empty spintax options (`||`, `{|`, `|}`); render 5 random variants and confirm no double spaces, orphan punctuation, or leftover braces.
- **Tag correctness + no cross-contamination:** each pool's `mlrch-` tag appears **exactly once** in its own body, all tags are **unique across the batch**, and **no foreign tag** appears in any other campaign's body. A swapped or duplicated tag silently corrupts both tests, so check every body against all tags.
- **Seeds:** exactly the expected count per campaign, **0 blank first names**, 0 duplicate emails, and the **same seed set across all campaigns** in the run.
- **Settings:** all `draft`, `plain_text` on, `open_tracking` off, `include_auto_replies_in_stats` off, `sequence_prioritization = new_leads`, `max_new_leads_per_day` = seed count.
- **Sender pools:** counts match the intended batch sizes, and **no inbox is shared across two pools** (an overlap confounds which segment a placement result belongs to).
- **OAuth token audit (Step 0, run again here as the launch gate):** sweep `GET /sender-emails/{id}/oauth-access-token` across every `*_oauth` inbox, 200 alive, 400 dead. Any dead inbox will silently send nothing and drag the pool's result; exclude and flag it for manual reconnection. Custom-SMTP inboxes (e.g. Winnr) cannot be token-checked; the send is the proof.

Report a table (pool, PASS/FAIL per category) and only proceed to the launch gate when every row is PASS.

### Step 9: Operator review gate, THEN launch

**Do not launch straight from verification.** Present the operator a review table (campaign #, pool, tag, seed count, sender count) plus the rendered copy, and wait for explicit approval, they review in the Bison UI. Only launch on their go.

```python
api("PATCH", f"/campaigns/{campaign_id}/resume")
# Bison returns status "queued" on success, then moves to "active" within seconds
```

Launch campaigns in sequence, not in parallel, to avoid race conditions.

### Step 10: Monitor sends

Poll `GET /api/campaigns/{id}` every 30 min:
- `completion_percentage` rises as seeds are sent to
- `emails_sent` should reach the seed count per campaign
- When `status == "completed"` or `emails_sent` equals the seed count, the test is done

Expected completion: ~3-4 hours from launch on a wide window (~30 sends at ~7 min median), or within the hour on the compressed default.

**Diagnosing "active but 0 sends":** campaign-level stats cannot tell you WHY a campaign is not sending. Use `GET /api/campaigns/{id}/scheduled-emails` (paginate via `per_page` / `meta.last_page`). It returns per-lead `status` (scheduled/sent), `scheduled_date` (UTC), `scheduled_date_local`, `sent_at`, `lead`, and `sender_email`.

This is how you tell the difference between (a) the first send having just re-armed ~5 min out (wait, do not kick), (b) rounds deferred to the next daily window (a ~1,430-minute gap in `scheduled_date` → widen the window), and (c) an actual config problem. Do NOT pause/resume to investigate, that resets the clock (Step 5).

**Confirm all leads land in-window after launch:** right after resuming, pull `/scheduled-emails` and verify every lead's send time falls inside the window and on a single day. **Trap: Bison's `scheduled_date_local` field is mislabeled, it returns UTC, identical to `scheduled_date`.** Convert `scheduled_date` to your campaign timezone yourself before comparing against the window. A correct compressed launch shows all sends spanning ~35-40 min inside the hour; anything outside means you should widen the window, or the schedule did not recompute (Step 5).

**Automate the results wait with a background poller:** instead of watching manually, run a background loop that hits each test's `GET /api/v1/spam_tests/{public_id}` every ~5 min and exits when all are done. **The exit condition must be `completed == true` AND `score` is not null AND `scanned > 0` AND the scanned count unchanged across two consecutive polls** (this is what `scripts/6_poll.py` implements). Two traps, both hit on real runs. Keying on `scanned >= <seed count>` never exits: a test routinely finishes at 27/28 (one seed never scans) with `completed: true`. But keying on `completed` ALONE exits instantly, because **a test that has not yet received any mail also reports `completed: true` with `score` null and `scanned 0`**, started before the sends land, such a poller "finishes" in seconds and the results step then scores every pool 0/8 = KILL on healthy infra (hit on two separate real runs). Require a score, scanning to have started, and the count to have settled. `scripts/7_results.py` also refuses to score a test with 0 scanned or no score, as a second guard. Cap it (~4h safety) and log each poll line.

**Status check after all seeds are sent:** wait an additional 30-60 min for MailReach's scanning engine to categorize placements before pulling results.

### Step 11: Pull MailReach results

Via a CLI wrapper:

```bash
MAILREACH_API_KEY=<your-key> <mailreach-cli> test get <public_id> --agent
```

Or directly via the API, this is the ONLY way to get the true 4-way split, see Step 12:

```bash
curl -s "https://api.mailreach.co/api/v1/spam_tests/<BARE_public_id>" \
  -H "X-Api-Key: Bearer $MAILREACH_API_KEY" \
  -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"  # Cloudflare blocks without a browser UA
```

**Gotchas:**
- MailReach's API blocks requests without a browser User-Agent (Cloudflare 1010 error). Always include a realistic `User-Agent`.
- The endpoint needs the **bare** `public_id` (e.g. `abc123def456`), NOT the `mlrch-`-prefixed tag. The prefixed form returns "public_id is invalid".
- `curl` may be unavailable in your shell, use Python `urllib` instead.
- The **CLI `test get` collapses the result into a gmail/outlook rollup** and hides the 4-way split. To get the real per-provider breakdown you must hit the raw API and read `results[]` yourself.

### Step 12: Parse results

The raw response has a **`results[]`** array, one entry per seed. Each entry has:
- `desc`: the seed inbox provider (raw values are granular; map them to the four buckets below)
- `received_in`: **`INBOX` / `SPAM` / `PROMOTION`**, only `INBOX` counts as inbox. Promotions is NOT inbox.

**`desc` → bucket mapping:**

| `desc` value(s) | Bucket | Count |
|-----------------|--------|-------|
| "Google Workspace", "Google Workspace with smart features" | Google Workspace (GW), **work** | /8 |
| "Gmail account with smart features" | Gmail personal | /6 |
| "Office 365" | Office 365 (M365), **work** | /8 |
| "Hotmail account", "Outlook account" | Outlook/Hotmail personal | /6 |

### Step 13: Score it, SEGMENT-AWARE, work inboxes only

Two rules:

1. **Personal inboxes do not count.** B2B campaigns never send to consumer Gmail/Outlook, so Gmail-personal /6 and Outlook-personal /6 are **diagnostic only** and do NOT feed the verdict. Score on the **work** seeds only (GW /8 and M365 /8).

2. **Score each pool against ONLY the recipient segment it actually serves, not the blended /16.** Because the inbox-to-campaign mapping is often deliberately crossed, a pool typically only ever sends to one recipient type in production. Judging it on the blend hides the truth: a pool can look "mid" on /28 while landing 0 into the one segment it serves.
   - A pool that sends to **Microsoft/Outlook recipients** → score on **M365 /8** only.
   - A pool that sends to **Google recipients** → score on **GW /8** only.
   - The other work column is diagnostic, not the verdict.

   Map each pool to its production segment first (from the campaign's recipient-segment split), THEN read the matching /8.

**Verify the mapping from the live campaigns, do not assume it.** When the result is decision-critical (e.g. M365 strong but GW dead), confirm which pool serves which recipient segment by counting sender **types** attached to the real production campaigns: `GET /campaigns/{id}/sender-emails` on each recipient-segment variant and tally `custom` / `google_workspace_oauth` / `microsoft_oauth`.

On one run this proved that the Outlook-recipient campaigns were served entirely by the custom-SMTP pool (so that pool is scored on M365) while the Google-recipient campaigns were served by all the OAuth pools (scored on GW). A pool can look excellent on the OFF-segment column, the OAuth pools hit 8/8 into O365, while being dead in the segment it actually serves (0-2/8 into GW). The off-segment number is a real signal about *latent* capacity ("we have an unused Microsoft channel") but it does NOT change the in-segment verdict. Call that out separately in the Verdict cell.

**Verdict thresholds (in-segment, /8):**
- **KILL:** < ~4/8 (dead into its target)
- **MARGINAL:** ~4-6/8 (below keep but salvageable, flag yellow, do not write off)
- **KEEP:** ~7/8+ (≥ ~80% into the segment it serves)

If the mapping is NOT crossed (a pool serves both recipient types), fall back to the combined work score: KILL < 8/16, MONITOR 8-12/16, KEEP 13+/16.

### Step 14: If a pool fails, diagnose root cause before recommending a rebuild

A KILL verdict says the pool is broken, not WHY. Before recommending "buy new infra," run an infra forensic audit over the pool's sending domains so the recommendation is evidence-backed:

- **Auth:** SPF present, DKIM present, DMARC enforced (not `p=none`), via `dig TXT` on each domain plus `_dmarc.<domain>`.
- **Sending infra:** read the SPF `include:` to see the real path (e.g. `amazonses.com` = Amazon SES, which Microsoft filters hard; `_spf.google.com`; `spf.protection.outlook.com`).
- **Domain blacklist:** query `<domain>.multi.surbl.org` and `<domain>.dbl.spamhaus.org` across **3 resolvers** (8.8.8.8 / 9.9.9.9 / 208.67.222.222), plus a known-clean control (google.com) and SURBL's test point, to rule out a public-resolver false positive. `127.0.0.64` on multi.surbl.org confirmed across resolvers is a real listing. Blacklist status often tracks the domain **vendor**, not the ESP.
- **IP DNSBL** only helps for custom-SMTP relays. For Google/Microsoft-hosted boxes the sending IP is the ESP's shared range, so use domain reputation instead (Google Postmaster Tools / Microsoft SNDS).

### Step 14.5: A test campaign that never gets a schedule (0 rows, or leads keep re-deferring to a future day)

Symptom: `GET /campaigns/{id}/scheduled-emails` returns `meta.total: 0` for a healthy-looking campaign (senders Connected, leads attached, schedule window valid), or leads DO get scheduled but land on tomorrow (or the day after) no matter how many times the window is widened and the campaign paused/resumed. Seen on two consecutive placement rounds (2026-09-14, 2026-09-15), always concentrated on the SAME pools: small pools (2-6 inboxes) whose senders are ALSO attached to live, heavily-sending production campaigns.

**Root cause: the test campaign's senders are contended by live production campaigns sharing the same inboxes.** Bison appears to prioritize whichever campaign's queue it's already working through, starving a newly-launched test campaign of scheduling slots on a shared inbox. This is NOT fixed by:
- widening the send window (the campaign just gets a later slot, or none)
- raising the sender's `daily_limit` field alone (helped inconsistently, took multiple tries, and isn't the reliable fix)
- a single pause/resume (sometimes needs 2-3 cycles even when it does eventually work)

**The reliable fix:** compute the exact sender-ID overlap between the stuck test campaign(s) and every currently-active live campaign in the workspace (`GET /campaigns/{id}/sender-emails`, paginate, intersect sets, don't guess by name), **pause only the live campaigns that actually share senders** with the stuck pools (not the whole workspace), then pause/resume the stuck test campaign(s) again. This fixed 8 of 8 stuck campaigns on the first try once the true overlapping live campaigns were paused, after 2 rounds of window-widen+pause/resume alone had failed on the same 8. Track exactly which live campaigns you paused (workspace + campaign IDs) and get them resumed as soon as the test finishes, this is real production downtime, treat it with the same care as any other campaign pause.

### Step 14.6: A pool's last 1-2 leads never leave, direct send via Bison's test-email endpoint

A 2-inbox pool can hit a hard daily pacing ceiling where the last handful of its seed leads keep re-deferring to a future day even after the fix in 14.5, because there simply aren't enough inbox-rounds left in the day for 2 senders to clear the remainder. Rather than borrow senders from another pool (**never do this, it contaminates which pool the placement result actually reflects**) or wait a day, send those specific leads directly via Bison's one-off test-email endpoint:

```
POST /campaigns/sequence-steps/{sequence_step_id}/test-email
{"sender_email_id": <id>, "to_email": "<seed>", "use_dedicated_ips": true}
```

Requires ≥1 lead already on the campaign (400 otherwise). `sequence_step_id` comes from `GET /campaigns/{id}/sequence-steps`. Alternate across the pool's own sender IDs so the sends still originate from the correct pool, and verify the MailReach tag is already in the step body before calling (it renders whatever's currently on the step, unmodified per-call). **This sends real mail from the real inbox and MailReach scores it exactly like a normal send**, but it will NOT show up in the Bison campaign's own `emails_sent` count, so note the true vs. Bison-displayed total when writing up results.

### Step 14.7: verify a re-attached lead didn't silently no-op, and re-verify sheet writes after a mid-run schema/grid error

If a lead was detached (`DELETE /campaigns/{id}/leads`) and needs restoring, Bison's batch `attach-leads` silently no-ops on a previously-detached lead in the same campaign (`"Existing leads were not added"`, HTTP 200, looks like success). **Attach one lead at a time** when restoring, and re-verify via `GET /campaigns/{id}/leads` that the email is actually present, not just that the call returned 200.

Separately: if a Google Sheet write hits a `Range exceeds grid limits` error partway through a multi-block write, expanding the grid and retrying only the **formatting** batchUpdate (while forgetting to retry the **values** update) leaves the block formatted but empty, and a later single-cell patch elsewhere in that same range (e.g. fixing one column) will look like proof the whole block wrote correctly. Always re-read the full `A:P` range of every block you wrote back with `values.get` before calling a sheet write done, not just the cell you most recently touched.

---

## Summarized API calls

| Step | Call |
|------|------|
| Create campaign | `POST /api/campaigns` |
| Apply settings | `PATCH /api/campaigns/{id}/update` |
| Add step | `POST /api/campaigns/v1.1/{id}/sequence-steps` |
| Update step (append tag) | `PUT /api/campaigns/sequence-steps/{sequence_id}` |
| Set schedule | `POST /api/campaigns/{id}/schedule` (new) / `PUT` (change) |
| Attach senders | `POST /api/campaigns/{id}/attach-sender-emails` |
| Attach leads | `POST /api/campaigns/{id}/leads/attach-leads` |
| Launch | `PATCH /api/campaigns/{id}/resume` |
| Check status | `GET /api/campaigns/{id}` |
| Per-lead send schedule (diagnose stalls) | `GET /api/campaigns/{id}/scheduled-emails` |
| OAuth token liveness | `GET /api/sender-emails/{id}/oauth-access-token` |
| Pull results (raw, 4-way) | `GET https://api.mailreach.co/api/v1/spam_tests/<BARE_public_id>` |

---

## Caveats

1. **Sender pool size does not affect result quality.** MailReach measures placement at the test level (all seeds, from all inboxes in the pool). Each seed gets one email from one inbox in the pool. A larger pool spreads the sends across more inboxes but does not give more placement data points.

2. **One email per seed, per campaign.** Even with 100 senders, only ~30 emails go out. The sender pool just determines which inboxes send.

3. **MailReach scans are not instant.** Some seeds take 30-60 min to appear as scanned. "26/28 sent" in Bison alongside "20/28 scanned" in MailReach is a normal mid-run state. Pull final results only after all seeds are sent AND 30 min have elapsed.

4. **`sequence_prioritization: new_leads` is required.** Without it Bison defaults to `default_followups` and may not prioritize step 1 for the seed leads.

5. **Copy quality does not affect placement scores, but copy CONTENT does.** These are seeds, not real prospects, so persuasiveness is irrelevant. Content fingerprinting is not: see Step 4's fingerprint-isolation mode. The only variable that must work is `{FIRST_NAME}`.

6. **Never reuse a prior MailReach tag.** Each test needs its own unique tag. Reusing one mixes placement data across tests. Create a fresh test per batch via `POST /v1/spam_tests` (Step 2), or in the dashboard if falling back to the manual path.

---

### Step 15: Write results to a deliverability sheet (EXACT formatting, keep every round identical)

Results go into the deliverability sheet as a **new round BLOCK appended below the previous round in the SAME tab**, NOT a new tab. A working reference layout: a "MailReach Tests" tab where Round 1 occupies rows 1-8, Round 2 rows 10-17, Round 3 rows 19-26, with one blank separator row between blocks.

**The non-negotiable rule: before writing, READ the previous round's block first and mirror its formatting cell-for-cell.** This is the only way rounds stay consistent as the sheet grows. Pull the prior block with grid data and copy its colors and structure exactly:

```bash
gws sheets spreadsheets get --params '{"spreadsheetId":"<SPREADSHEET_ID>","ranges":["MailReach Tests!A1:P8"],"includeGridData":true,"fields":"sheets(properties(sheetId),data(rowData(values(formattedValue,hyperlink,userEnteredFormat(backgroundColor,textFormat(bold,foregroundColor))))))"}'
```

**Block structure (16 columns, A-P):**
- **Row 1 of block**: round title, e.g. `Round N - YYYY-MM-DD Bison→MailReach full-campaign protocol (<workspace>, <copy note>)`. Bold, no fill.
- **Row 2**: blank.
- **Row 3**: the header row. **Exact 16 headers, in order:** `Date | Bison C# | Segment | Inboxes | Seeds | MR public_id | MR tag | Seeds scanned | Google Workspace /8 (work) | Gmail Personal /6 | Office 365 /8 (work) | Outlook Personal /6 | Work Inbox /16 | Overall Inbox /28 | Score | Verdict`. Formatting: background **dark slate `{red:0.17, green:0.24, blue:0.31}`**, **bold**, **white** text (`foregroundColor {1,1,1}`).
- **Rows 4-8**: one row per pool. **Zebra stripe:** light gray `{red:0.96, green:0.97, blue:0.98}` on the 1st/3rd/5th data rows, white on the 2nd/4th (the same alternation as the prior round). Applies across cols A-O; the **Verdict col (P) is NOT zebra**, it takes the outcome color instead.

**Per-cell content:**

| Col | Content |
|-----|---------|
| A Date | `YYYY-MM-DD` |
| B Bison C# | HYPERLINK. Label `C###: Inbox Placement Test - Mon DD YYYY - <Pool>`, e.g. `C412: Inbox Placement Test - Aug 06 2026 - Zapmail Google`. Formula: `=HYPERLINK("https://<your-bison-host>/campaigns/{campaign_uuid}/leads","<label>")`, the uuid comes from `GET /campaigns/{id}.data.uuid`, NOT the numeric id |
| C Segment | `<Pool> - <auth type>`, e.g. `Winnr - Custom SMTP`, `Zapmail Google - Google Workspace OAuth`, `Zapmail Microsoft - Microsoft OAuth`, `IceMail Google - Google Workspace OAuth` |
| D Inboxes | sender-pool size |
| E Seeds | 30 |
| F MR public_id | HYPERLINK. `=HYPERLINK("https://spamchecker.mailreach.co/tests/{public_id}","{public_id}")` (bare public_id as the label) |
| G MR tag | `mlrch-{public_id}` |
| H Seeds scanned | `{scanned}/30` (actual scanned count, e.g. `27/30`) |
| I-L | GW `x/8`, Gmail `x/6`, M365 `x/8`, Outlook `x/6` (INBOX-only counts, from the 4-way split, Step 12) |
| M Work Inbox /16 | GW_inbox + M365_inbox, over `/16` |
| N Overall Inbox /28 | total INBOX across the 4 buckets, over `/28` |
| O Score | **`{score} (B2B {btob_score})`**, both pulled straight from the MailReach test JSON (fields `score` and `btob_score`; the response also carries `btoc_score` / `final_score`). Zebra like the data rows. |
| P Verdict | KILL / MARGINAL / KEEP plus a one-sentence in-segment rationale (Step 13). **Background = outcome color, wrap on:** KILL `{0.96, 0.8, 0.8}` (red), MARGINAL `{1, 0.89, 0.6}` (amber), KEEP `{0.85, 0.92, 0.83}` (green). |

**How to write it (Sheets API):**
1. **Values** (including the two HYPERLINK formulas) via `spreadsheets.values.update` with `valueInputOption: "USER_ENTERED"`, required so the formulas render as links. Write the whole block starting at the round's first cell, e.g. `MailReach Tests!A19`.
2. **Formatting** via `spreadsheets.batchUpdate` with `repeatCell` requests: one for the bold title, one for the slate/bold/white header, N for the zebra rows, and the Verdict-color requests (amber for MARGINAL, red for KILL, green for KEEP). Row indices in the API are **0-based** (a block starting at sheet row 19 = `startRowIndex: 18`).
3. **Cell alignment, easy to miss, checked and confirmed present on every prior round:** the header row and every data row (columns A-P) also carry `horizontalAlignment: "CENTER"`, `verticalAlignment: "MIDDLE"`, `wrapStrategy: "WRAP"`. This is a separate `repeatCell` request from the background/text-color ones in Step 2, applying color alone leaves cells left-aligned and top-aligned, which reads as visibly different from every earlier round even though the colors match. Apply it across the full header+data row range (`fields: "userEnteredFormat(horizontalAlignment,verticalAlignment,wrapStrategy)"`).
4. **A HYPERLINK label needs its batch/pool spelled out** (e.g. `C911: ... - B1 - Winnr`, not just `... - Winnr`) whenever more than one pool of the same name can appear in the same block (a workspace with two Winnr pools across B1/B2 makes an unlabeled pair genuinely ambiguous in the sheet). Put the batch in the Segment column too (`Winnr - B1 - Custom SMTP`).
5. **Read back** the block and diff it against the previous round's format before calling it done, including alignment, not just color. Confirm header color, zebra parity, both hyperlinks resolving, Score format, Verdict colors, and CENTER/MIDDLE/WRAP all match.

**Diagnostic vs verdict:** the personal Gmail/Outlook columns, Work /16, and Overall /28 are **diagnostic only**. The KILL/MARGINAL/KEEP verdict is driven by the **in-segment work /8** (Step 13). Blended diagnostic score if you need one: `work_inbox_count / 16 * 10`.
