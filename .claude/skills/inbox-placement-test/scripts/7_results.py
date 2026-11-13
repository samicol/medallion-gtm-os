#!/usr/bin/env python3
"""Steps 11-13 - pull raw results, split 4 ways, score segment-aware.

Must hit the raw MailReach API: the CLI's `test get` collapses everything into a
gmail/outlook rollup and hides the split this scoring depends on.

Scoring rules:
  1. Personal inboxes are diagnostic only. B2B campaigns never send to consumer
     Gmail/Outlook, so the verdict comes from work seeds (GW + M365) alone.
  2. Each pool is scored ONLY against the recipient segment it actually serves,
     set per pool in config.json. A pool can look strong on the off-segment
     column while being dead in the one it serves; the blend hides that.

Writes results.json for 8_write_sheet.py.

    python scripts/7_results.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import (bison, mailreach_test, bucket_counts, verdict, die,  # noqa: E402
                       bare_public_id, load_config, load_state, ROOT)

SEG_KEY = {"GW": "gw", "M365": "m365"}


def main():
    cfg, state = load_config(), load_state()
    seeds = state.get("seed_count", 30)
    out = []

    for c in state["campaigns"]:
        if not c.get("tag"):
            print(f"  {c['pool']}: no tag, skipped")
            continue
        pid = bare_public_id(c["tag"])
        t = mailreach_test(pid)
        counts = bucket_counts(t)
        # `total` counts every seed ROW, scanned or not, so it reads 28/28 even
        # when nothing has landed. Scanned means a row with a real placement.
        scanned = len([r for r in (t.get("results") or []) if r.get("received_in")])
        # Guard: a test with nothing delivered scores 0/8 everywhere and would
        # be written up as KILL on healthy infra. Refuse to score it.
        if scanned == 0 or t.get("score") is None:
            die(f"{c['pool']} (test {pid}): {scanned} seeds scanned, score "
                f"{t.get('score')}. Nothing has landed yet -- scoring this now "
                f"would report KILL on every pool. Keep polling (6_poll.py).")

        seg = c["segment"]
        seg_bucket = counts[SEG_KEY[seg]]
        off_bucket = counts[SEG_KEY["M365" if seg == "GW" else "GW"]]
        work_inbox = counts["gw"]["inbox"] + counts["m365"]["inbox"]
        work_total = counts["gw"]["total"] + counts["m365"]["total"]
        overall_inbox = sum(b["inbox"] for b in counts.values())

        _, camp = bison("GET", f"/campaigns/{c['campaign_id']}")
        uuid = (camp.get("data") or {}).get("uuid")

        row = {
            "pool": c["pool"], "auth": c["auth"], "segment": seg,
            "campaign_id": c["campaign_id"], "uuid": uuid,
            "public_id": pid, "tag": c["tag"],
            "inboxes": len(c["senders"]),
            "seeds": seeds, "scanned": scanned,
            "gw": f"{counts['gw']['inbox']}/{counts['gw']['total']}",
            "gmail": f"{counts['gmail']['inbox']}/{counts['gmail']['total']}",
            "m365": f"{counts['m365']['inbox']}/{counts['m365']['total']}",
            "outlook": f"{counts['outlook']['inbox']}/{counts['outlook']['total']}",
            "work": f"{work_inbox}/{work_total}",
            "overall": f"{overall_inbox}/{scanned}",
            "score": t.get("score"), "btob_score": t.get("btob_score"),
            "in_segment": f"{seg_bucket['inbox']}/{seg_bucket['total']}",
            "off_segment": f"{off_bucket['inbox']}/{off_bucket['total']}",
            "verdict": verdict(seg_bucket["inbox"], seg_bucket["total"]),
            "completed": bool(t.get("completed")),
        }
        if counts["unknown"]["total"]:
            row["unknown_desc"] = counts["unknown"]["total"]
        row["rationale"] = (
            f"In-segment ({seg}): {row['in_segment']}. "
            f"Off-segment {'M365' if seg == 'GW' else 'GW'}: {row['off_segment']} "
            "(latent capacity only, does not change the verdict)."
        )
        out.append(row)

    hdr = f"{'pool':22s} {'seg':>5s} {'in-seg':>8s} {'off-seg':>8s} {'work':>7s} {'overall':>8s} {'score':>6s}  verdict"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in out:
        print(f"{r['pool']:22s} {r['segment']:>5s} {r['in_segment']:>8s} {r['off_segment']:>8s} "
              f"{r['work']:>7s} {r['overall']:>8s} {str(r['score']):>6s}  {r['verdict']}")
        if r.get("unknown_desc"):
            print(f"    NOTE: {r['unknown_desc']} seeds had an unrecognised provider "
                  "desc; add it to DESC_BUCKETS in bison_api.py.")
        if not r["completed"]:
            print("    NOTE: test not marked completed; numbers may still move.")

    path = os.path.join(ROOT, "results.json")
    with open(path, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwrote {path}")
    print("Personal Gmail/Outlook, work /16 and overall are diagnostic only. "
          "The verdict is the in-segment column.")


if __name__ == "__main__":
    main()
