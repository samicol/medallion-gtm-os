#!/usr/bin/env python3
"""Steps 1, 3, 4, 5, 6 - build one draft campaign per pool.

Pre-build-then-arm: the sequence step goes in WITHOUT the mlrch- tag so the
campaign can be built before the operator has created the MailReach tests.
3_arm_tags.py appends each tag later.

    python scripts/1_build.py            # dry run, prints the plan
    python scripts/1_build.py --create
"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, load_config, save_state, die, confirm_flag  # noqa: E402


def main():
    cfg = load_config()
    camp, copy = cfg["campaign"], cfg["copy"]
    seeds = cfg.get("seed_count", 30)

    plan = [{
        "pool_key": p["key"], "pool": p["name"], "auth": p["auth"], "segment": p["segment"],
        "name": camp["name_template"].format(date=cfg["date_label"], pool=p["name"]),
        "senders": p["sender_email_ids"],
    } for p in cfg["pools"]]

    print(f"{len(plan)} campaigns to build:")
    for p in plan:
        print(f"  {p['name']}  ({len(p['senders'])} senders, serves {p['segment']})")
    if "mlrch-" in copy["body"]:
        die("config copy.body already contains an mlrch- tag. Tags are added by "
            "3_arm_tags.py, one per pool. Remove it from the shared copy.")
    if not confirm_flag("--create", "create these campaigns"):
        return

    # Send window is a placeholder here; 5_launch.py PUTs the real compressed
    # window at launch time. A campaign with no schedule cannot be resumed.
    schedule = {d: (d in camp["send_days"]) for d in
                ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")}
    schedule.update({"start_time": "09:00", "end_time": "17:00",
                     "timezone": cfg["timezone"], "save_as_template": False})

    built = []
    for p in plan:
        status, resp = bison("POST", "/campaigns", {"name": p["name"], "type": "outbound"})
        if status not in (200, 201):
            print(f"  CREATE FAILED {p['name']}: {status} {resp.get('__error')}")
            continue
        cid = resp["data"]["id"]

        # Both cap fields must go in the same PATCH or Bison validates the
        # missing one against 0 and 422s.
        bison("PATCH", f"/campaigns/{cid}/update", {
            "plain_text": camp["plain_text"],
            "open_tracking": camp["open_tracking"],
            "include_auto_replies_in_stats": False,
            "sequence_prioritization": "new_leads",
            "max_emails_per_day": camp["max_emails_per_day"],
            "max_new_leads_per_day": seeds,
        })
        # Outer key is sequence_steps (not steps); top-level title is required;
        # wait_in_days must be >= 1 even though step 1 fires on launch.
        seq_status, _ = bison("POST", f"/campaigns/v1.1/{cid}/sequence-steps", {
            "title": p["name"],
            "sequence_steps": [{
                "email_subject": copy["subject"], "email_body": copy["body"],
                "order": 1, "wait_in_days": 1, "thread_reply": False, "variant": False,
            }],
        })
        sch_status, _ = bison("POST", f"/campaigns/{cid}/schedule", schedule)
        att_status, _ = bison("POST", f"/campaigns/{cid}/attach-sender-emails",
                              {"sender_email_ids": [str(s) for s in p["senders"]]})

        p["campaign_id"] = cid
        built.append(p)
        print(f"  created #{cid}  {p['name']}  seq={seq_status} sched={sch_status} attach={att_status}")

    save_state({
        "built_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "seed_count": seeds,
        "campaigns": built,
    })
    print(f"\nsaved .placement_state.json ({len(built)} campaigns)")
    print("If a run was interrupted, list the workspace's placement campaigns and "
          "DELETE any stray partial duplicates before continuing.")


if __name__ == "__main__":
    main()
