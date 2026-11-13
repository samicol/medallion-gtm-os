---
name: inbox-placement-test
description: Run an end-to-end inbox placement test on your cold email sending fleet (EmailBison + MailReach): build one real Bison campaign per sender pool, send production-shaped copy to MailReach seeds, pull the raw 4-way placement split, and score each pool against the recipient segment it actually serves (KILL/MARGINAL/KEEP). Use when the user says "placement test", "inbox placement", "are we landing in spam", "spam test", "check deliverability", "MailReach test", "should we kill these inboxes", "/inbox-placement-test", or when reply rates drop and list quality has already been ruled out. Self-contained - prompts for every piece of operator input it needs. Also covers fingerprint-isolation mode, which separates burned copy from dead infrastructure.
argument-hint: "[Bison workspace name]"
---

# Inbox Placement Test

Measures where a fleet's mail actually lands. Not a "send a test email and look"
check: it builds one real Bison campaign per sender pool, sends to a full
MailReach seed set, and scores placement per pool.

**Read `reference/sop.md` before your first run.** It is the methodology and
every gotcha in it broke a real run. This file is the orchestration.

**Setup-agnostic by design.** Nothing here assumes a particular workspace, key,
vendor, or sheet. Ask for what you need; never guess the setup.

## When to run it

- Before a kill/keep decision on a pool of inboxes
- When reply rates drop and placement is suspected, after list quality is ruled out
- After someone on the team reports deliverability problems
- As a periodic fleet health check, or batched by tier after a reply-rate analysis

## Step 1 - gather what only the operator knows

**STOP and ask before touching anything.** Ask all of these in one message, and
say plainly that you cannot infer them:

1. **Which Bison workspace**, and **which API key** to use. The env key is
   `EMAILBISON_API_KEY` (or `BISON_API_KEY_<WORKSPACE>` if you run several), plus the
   instance's base URL. Confirm the exact variable name, never assume, and never
   cross-use a key suffixed for a different workspace.
2. **Which MailReach account's key to bill against**, if more than one exists
   (e.g. `MAILREACH_API_KEY_TEAM_A` vs `MAILREACH_API_KEY_TEAM_B`). This now
   matters more than it used to: Step 5's API path picks a specific key
   programmatically rather than whichever account the operator happened to be
   logged into in the dashboard, so a wrong guess silently spends someone
   else's credits.
3. **Which inboxes are in scope** - the whole fleet, one vendor, or a tier from a
   prior reply-rate analysis.
4. **Send to the full seed set, or work inboxes only?** Work-only finishes
   faster: fewer seeds (roughly 28-30 down to ~18) means fewer send rounds per
   inbox, which matters most on small pools (2-6 senders) racing a deadline.
   The tradeoff: personal seeds (Gmail, Outlook.com, Hotmail) are diagnostic-only
   and never change the KILL/MARGINAL/KEEP verdict anyway (see Step 7), so the
   only thing skipping them actually costs is the off-segment reference data,
   not the verdict itself. Filter `results[]` to non-personal `provider`/`desc`
   values before writing the seed CSV in Step 5 if the operator wants work-only.
5. **Which copy to send** - see Step 4. This is a real decision, not a detail.
6. **Whether results go to a spreadsheet**, and if so which sheet, tab, and row.
7. **Do they have MailReach credits?** One per pool per round, but only once a
   pool actually sends and the test collects data, see Step 5's credit-timing
   note. A 5-pool run that fully completes costs 5. If they are short, cut
   pools before building, not after. **Unverified: what a pool that only
   partially sends (a stuck-scheduling campaign that gets, say, 16 of 18 seeds
   out before being abandoned) does to the charge**: this skill has hit that
   exact scenario before (see Steps 14.5-14.7). Treat it as still costing a
   credit until proven otherwise, not as a free retry.

## Step 2 - set up the run

The scripts here are shared and may be read-only, so keep each run's files
outside the skill:

```bash
export PLACEMENT_RUN_DIR=~/placement-runs/<workspace>-<date>
cp .env.example "$PLACEMENT_RUN_DIR/.env"          # fill in the confirmed key
python scripts/discover_pools.py                    # see what pools exist
python scripts/discover_pools.py --emit             # draft config.json
```

`discover_pools.py` groups inboxes by auth type and domain. **Two things it
cannot decide, so you must:**

- **Split by vendor.** One auth type often spans two vendors. They place
  differently, and a blended pool hides which one is dead.
- **Set every pool's `segment`.** `GW` if that pool sends to Google recipients in
  production, `M365` if Microsoft. **Verify from the live campaigns** - pull
  `GET /campaigns/{id}/sender-emails` on each recipient-segment variant and tally
  sender types. Mappings are often deliberately crossed. Guessing here inverts
  the verdict. If you cannot confirm it, ask the operator.

## Step 3 - pre-flight token audit

```bash
python scripts/0_token_audit.py
```

`status: "Connected"` does **not** mean the OAuth token is alive; a whole pool
has read Connected with dead tokens and sent nothing. Exit code 2 means dead
tokens: exclude those pools and flag them for manual browser re-auth in the
Bison UI. There is no API fix. Custom-SMTP inboxes cannot be checked; the send
is the proof.

## Step 4 - choose the copy, then build

**ASK the operator which mode.** This determines what the test can prove:

- **Production-shaped (default).** Their real workflow Email 1, every variable
  except `{FIRST_NAME}` replaced with a sensible static rendering, one dynamic
  route picked, spintax kept. Tests placement on copy shaped like real sends.
- **Fingerprint-isolation.** Entirely fresh copy sharing no phrasing with any
  live campaign, spintaxed at phrase level for millions of renders. Use when a
  whole fleet fails on production copy. On a real run this flipped Microsoft
  placement from 0/8 to 8/8 on the same inboxes while Google stayed 0-2/8,
  proving Microsoft was fingerprinting content while Google's block was domain
  reputation. **Get sign-off on fresh copy before sending it.**

Avoid cold-email-cliche subjects ("quick question", "worth a look") in either
mode; they are themselves fingerprinted. Paste the chosen copy into
`config.json`, then:

```bash
python scripts/1_build.py            # dry run: prints the plan
python scripts/1_build.py --create   # drafts, no tags yet
```

**Do Step 5 (create the MailReach tests) next, before loading seeds**: when
using the API path, the seed list *comes from* that same `POST /v1/spam_tests`
call (its `results[]`), so there is nothing to load yet at this point. Write
**one** CSV to the single top-level `seed_csv` path in `config.json` (pools
have no per-pool seed file: the loader attaches the same list to every
campaign). Build it from any one pool's `results[]` (they are identical when
every pool uses the same `seedlist`), with columns `Email, First name, Last
name`, matching `results[].email` / `results[].first_name`, `Last name` left
blank (the loader backfills it). Then run:

```bash
python scripts/2_load_seeds.py --load
```

Seeds must be **this run's** fresh list either way. Never recycle addresses
from a prior run: MailReach's seed set changes and stale seeds silently cut
the scanned count. (If you're on the manual/dashboard fallback instead, the
operator's CSV export can be dropped in at this point as before, that path's
ordering hasn't changed.)

## Step 5 - create the MailReach tests

**MailReach exposes a real test-creation API** (confirmed working 2026-09-21;
see `reference/sop.md` Step 2 for the verified flow and the credit-timing
finding). Create one test per pool directly:

```
POST https://api.mailreach.co/api/v1/spam_tests
X-Api-Key: Bearer {MAILREACH_API_KEY}
Content-Type: application/json

{"seedlist": 1}
```

The response gives you `public_full_id` (the `mlrch-...` tag) and `results[]`
(the fresh seed list, with `email`/`first_name`/`provider` per seed) in one
call: no operator hand-off, no manual dashboard step, no risk of a swapped
code between pools since each call produces its own tag deterministically.

**Use the same `seedlist` value (default 1) for every pool in a run.**
Verified empirically: two calls with the same `seedlist` value made minutes
apart returned the *identical* 28 seed addresses, matching the existing
"MailReach's seed set is stable within a period" behavior this skill has
always assumed, now confirmed for the API path too. Don't rotate `seedlist`
per pool: `2_load_seeds.py` and the run's `config.json` are built around
**one shared seed list per run**, loaded once and attached identically to
every pool's campaign. A different `seedlist` value per pool would produce a
different seed list per pool with no script support for tracking which pool
got which list; that's a real rework, not something to reach for by default.

**Not verified: stability across a run that spans hours**, which several real
runs on this skill have (contention fixes, stuck-scheduling retries, etc.).
If a run drags on, it's worth spot-checking that a freshly-pulled `results[]`
for one pool still matches what was loaded hours earlier before trusting the
cross-pool comparison at the end.

**Pace test-creation calls if building many pools in a loop.** MailReach
enforces no hard rate limit today but explicitly reserves the right to add
one; their own guidance is to stay under ~20 req/s per key and back off
cleanly on a 429. A run with 14-28 pools firing `POST /v1/spam_tests` back to
back is exactly the kind of burst worth a small delay between calls (a few
hundred ms is plenty), even though nothing enforces it yet.

**Credit gotcha, confirmed empirically:** the response's `paid: true` field
lights up immediately on creation and is **not** a reliable signal that a
credit was actually spent: a live test (created, never sent to) showed
`paid: true` while the MailReach dashboard's credit balance did not move.
The dashboard balance only decremented once a real email was sent to the
seed list and the test collected data. So an unsent test costs nothing in
practice, but don't leave one dangling indefinitely: send to it or don't
create it yet.

**Manual fallback (dashboard) still works** if you'd rather not use the API
for a given run: create one test per pool in the MailReach dashboard, then
paste each pool's `mlrch-` code into its `tag` in `config.json` as before. If
falling back to manual, record which code belongs to which pool carefully; a
swapped code still silently corrupts two tests at once.

Once you have each pool's tag (via either path), paste it into its pool's
`tag` in `config.json`, then:

```bash
python scripts/3_arm_tags.py --arm
```

## Step 6 - QA gate, then the operator's launch gate

```bash
python scripts/4_qa_preflight.py
```

Sweeps copy and spintax integrity, tag uniqueness and cross-contamination,
seeds, settings, pool overlap, and token liveness. **Exit code 2 means do not
launch.** Fix every FAIL. All-green is not optional.

**STOP again.** Present a review table - campaign #, pool, tag, seed count,
sender count - plus the rendered copy, and wait for explicit approval. The
operator reviews in the Bison UI. Only launch on their go.

```bash
python scripts/5_launch.py --set --launch
```

The window defaults to 60 minutes and widens automatically if a small pool needs
more rounds. Each inbox sends at ~15 min intervals, so a pool of N inboxes needs
`ceil(seeds/N)` rounds; too short a window defers the rest to the next day.

**Then hands off.** Every pause/resume resets the first-send clock ~5 minutes
forward. A campaign that looks stuck at 0 sends is usually just armed. To see
what is actually queued, use `python scripts/5_launch.py --verify`, never a
pause/resume.

## Step 7 - poll, then score

```bash
python scripts/6_poll.py       # exits when every test is completed, scored, >0 scanned, and stable for 2 polls
python scripts/7_results.py
```

Scoring has two rules, and both matter:

1. **Personal inboxes are diagnostic only.** B2B campaigns never send to consumer
   Gmail or Outlook. The verdict comes from work seeds alone.
2. **Score each pool only against the segment it serves.** The off-segment column
   is real information about latent capacity ("we have an unused Microsoft
   channel") but it never changes the verdict.

Verdicts, in-segment: **KILL** under ~50%, **MARGINAL** ~50-80%, **KEEP** ~80%+.

## Step 8 - write it up

```bash
python scripts/8_write_sheet.py --peek     # read the previous block first
python scripts/8_write_sheet.py --write
```

Results append as a new **block below the previous round in the same tab**, never
a new tab. Mirror the previous block's formatting cell for cell. Needs a Google
OAuth access token in `GOOGLE_ACCESS_TOKEN`. Skip this step entirely if the
operator does not keep a sheet.

## If a pool fails

A KILL says a pool is broken, not why. **Do not recommend new infrastructure
before diagnosing.** Not scripted here - run by hand and report evidence:

- **Auth:** SPF, DKIM, DMARC enforced (not `p=none`) via `dig TXT` on each domain
  and `_dmarc.<domain>`
- **Real sending path:** read the SPF `include:` (e.g. `amazonses.com`, which
  Microsoft filters hard)
- **Blacklists:** `<domain>.multi.surbl.org` and `<domain>.dbl.spamhaus.org`
  across three resolvers plus a clean control, to rule out a resolver false
  positive. Listing often tracks the domain **vendor**, not the ESP.
- For Google/Microsoft-hosted boxes the sending IP is the ESP's shared range, so
  use Google Postmaster or Microsoft SNDS rather than IP DNSBLs.

And before concluding the infra is dead: if the whole fleet failed on production
copy, rerun in fingerprint-isolation mode first. That single test has flipped a
"buy new infrastructure" conclusion into "rotate the copy."

## Notes

- Every mutating script is a dry run until you pass its arm flag. Walk the whole
  sequence dry first.
- Python 3.9+, standard library only. On Windows only, step 5 needs
  `pip install tzdata`.
- Run files (`config.json`, `.env`, state, results) live in `PLACEMENT_RUN_DIR`,
  never in this skill folder.
- `weekly/discover.py` (optional, read-only) lists every active campaign and its
  sender pools in a workspace. Handy before Step 2 when you run this weekly.
- Built on the EmailBison and MailReach APIs. Scripts and SOP are MIT licensed
  (see `LICENSE`).
- The MailReach CLI is **not** required and is not bundled. Its `test get`
  collapses results into a gmail/outlook rollup and hides the 4-way split this
  scoring depends on, so the scripts call the raw API directly.
