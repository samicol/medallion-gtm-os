#!/usr/bin/env python3
"""Steps 5 + 9 - set the compressed window, launch, verify sends land in-window.

Default window closes 60 minutes from now so the whole test sends within the
hour. The window must fit the ROUNDS, not just the seeds: each inbox sends at
~15 min intervals, so a pool of N inboxes needs ceil(seeds/N) rounds. A window
too short for a pool's rounds defers the rest to the next daily window.

Changing an existing schedule needs PUT. POST on a campaign that already has a
schedule returns success and silently changes nothing.

Do NOT pause/resume to kick a slow campaign afterwards: every resume pushes the
first-send clock ~5 min forward again. Launch once, then hands off.

    python scripts/5_launch.py                 # sizing check + window preview
    python scripts/5_launch.py --set           # PUT the window only
    python scripts/5_launch.py --set --launch  # PUT, then resume each campaign
    python scripts/5_launch.py --verify        # re-check /scheduled-emails only
"""
import sys, os, math, time, datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, bison_paginate, load_config, load_state  # noqa: E402

WINDOW_MIN = 60
ROUND_MIN = 15
ARM_MIN = 5


def sizing(state, minutes):
    seeds = state.get("seed_count", 30)
    worst, ok = None, True
    for c in state["campaigns"]:
        rounds = math.ceil(seeds / max(1, len(c["senders"])))
        needed = rounds * ROUND_MIN + ARM_MIN
        if worst is None or needed > worst[1]:
            worst = (c["pool"], needed, rounds, len(c["senders"]))
        if needed > minutes:
            ok = False
    return worst, ok


def verify(state, tz):
    print("\n=== /scheduled-emails (converted to campaign timezone) ===")
    for c in state["campaigns"]:
        rows = list(bison_paginate(f"/campaigns/{c['campaign_id']}/scheduled-emails", per_page=100))
        local = []
        for r in rows:
            raw = r.get("scheduled_date") or r.get("sent_at")
            if not raw:
                continue
            # scheduled_date_local is mislabeled: it returns UTC, identical to
            # scheduled_date. Convert here rather than trusting it.
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            local.append(dt.astimezone(tz))
        if not local:
            print(f"  #{c['campaign_id']} {c['pool']:22s} no rows queued yet")
            continue
        lo, hi = min(local), max(local)
        days = {d.date() for d in local}
        span = (hi - lo).total_seconds() / 60
        flag = "ok" if len(days) == 1 else f"SPILLS ACROSS {len(days)} DAYS"
        print(f"  #{c['campaign_id']} {c['pool']:22s} {len(local):3d} rows  "
              f"{lo:%H:%M}-{hi:%H:%M}  span {span:.0f}m  {flag}")


def main():
    cfg, state = load_config(), load_state()
    tz = ZoneInfo(cfg["timezone"])

    if "--verify" in sys.argv:
        verify(state, tz)
        return

    now = datetime.datetime.now(tz)
    minutes = WINDOW_MIN
    worst, ok = sizing(state, minutes)
    while not ok and minutes < 480:
        minutes += 15
        worst, ok = sizing(state, minutes)

    start, end = now, now + datetime.timedelta(minutes=minutes)
    print(f"window {start:%H:%M}-{end:%H:%M} {cfg['timezone']}  ({minutes} min)")
    print(f"tightest pool: {worst[0]} - {worst[3]} inboxes, {worst[2]} rounds, needs ~{worst[1]} min")
    if minutes > WINDOW_MIN:
        print(f"widened past the {WINDOW_MIN}-min default so that pool's rounds fit.")
    if "--set" not in sys.argv:
        print("\n[DRY RUN] pass --set to PUT this window (add --launch to resume too).")
        return

    camp = cfg["campaign"]
    schedule = {d: (d in camp["send_days"]) for d in
                ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
    schedule.update({"start_time": f"{start:%H:%M}", "end_time": f"{end:%H:%M}",
                     "timezone": cfg["timezone"], "save_as_template": False})

    print("\n=== PUT window ===")
    for c in state["campaigns"]:
        st, _ = bison("PUT", f"/campaigns/{c['campaign_id']}/schedule", schedule)
        print(f"  #{c['campaign_id']} {c['pool']:22s} PUT={st}")
    _, back = bison("GET", f"/campaigns/{state['campaigns'][0]['campaign_id']}/schedule")
    d = back.get("data") or back
    print("  readback:", {k: d.get(k) for k in ("start_time", "end_time", "timezone")})

    if "--launch" not in sys.argv:
        print("\n[window set only] pass --launch to resume. Get operator approval first.")
        return

    print("\n=== RESUME (sequential) ===")
    for c in state["campaigns"]:
        st, resp = bison("PATCH", f"/campaigns/{c['campaign_id']}/resume")
        status = (resp.get("data") or {}).get("status") or resp.get("status") or resp.get("__error")
        print(f"  #{c['campaign_id']} {c['pool']:22s} resume={st} status={status}")
        time.sleep(1)

    print("\nLaunched. Waiting 60s for the queue to populate, then verifying.")
    time.sleep(60)
    verify(state, tz)
    print("\nIf anything spills to another day, widen the window with a single PUT. "
          "Do not pause/resume to kick it.")


if __name__ == "__main__":
    main()
