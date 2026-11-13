#!/usr/bin/env python3
"""Step 10 - poll every MailReach test until all are done.

Exit condition is NOT scanned >= seed count: tests routinely finish at 27/30
with completed true because one seed never scans, so keying on the count leaves
the poller running forever.

But `completed == true` alone is not enough either. A MailReach test that has
received NOTHING yet ALSO reports completed=true, with score None and every
received_in null -- so polling right after launch exits instantly and
7_results.py then scores every pool 0/8 and reports KILL on healthy infra.
(Hit for real on a production run: exited 2 min after launch,
0/28 scanned, before Bison had sent a single email.)

Real exit condition: completed AND score is not None AND scanned > 0 AND the
scanned count is unchanged across two consecutive polls.

    python scripts/6_poll.py                    # 5 min interval, 4 h cap
    python scripts/6_poll.py --interval 300 --max-hours 4
"""
import sys, os, time, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import mailreach_test, load_state, bare_public_id  # noqa: E402


def arg(flag, default):
    return type(default)(sys.argv[sys.argv.index(flag) + 1]) if flag in sys.argv else default


def main():
    state = load_state()
    interval = arg("--interval", 300)
    deadline = time.time() + arg("--max-hours", 4.0) * 3600

    tests = [(c["pool"], bare_public_id(c.get("tag"))) for c in state["campaigns"] if c.get("tag")]
    if not tests:
        raise SystemExit("No tags in .placement_state.json. Run 3_arm_tags.py first.")

    done, prev, stable = set(), {}, {}
    while time.time() < deadline:
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        for pool, pid in tests:
            if pid in done:
                continue
            t = mailreach_test(pid)
            scanned = len([r for r in (t.get("results") or []) if r.get("received_in")])
            total = t.get("seeds_total") or len(t.get("results") or [])
            # `completed` alone is NOT enough: a test that has received nothing
            # yet also reports completed=true, with score None and every
            # received_in null. Exiting on it scores every pool 0/8 -> KILL.
            # Require a floor (scored + something scanned) and a stabiliser
            # (scanned unchanged across 2 polls) so a mid-scan test is not read
            # as final. Still never keys on scanned >= total: tests routinely
            # finish at 27/28.
            complete = bool(t.get("completed"))
            scored = t.get("score") is not None
            stable[pid] = stable.get(pid, 0) + 1 if prev.get(pid) == scanned else 0
            prev[pid] = scanned
            ready = complete and scored and scanned > 0 and stable[pid] >= 2
            if ready:
                done.add(pid)
            print(f"[{stamp}] {pool:22s} {pid:16s} scanned {scanned}/{total} "
                  f"score {t.get('score')} completed={complete} stable={stable[pid]}"
                  f"{' DONE' if ready else ''}")
        if len(done) == len(tests):
            print(f"\nAll {len(tests)} tests completed. Run 7_results.py.")
            return
        time.sleep(interval)

    print(f"\nTimed out with {len(done)}/{len(tests)} completed. "
          "Pull what exists with 7_results.py, or keep polling.")
    raise SystemExit(3)


if __name__ == "__main__":
    main()
