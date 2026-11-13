#!/usr/bin/env python3
"""Step 4 (second half) - append each pool's mlrch- tag to its campaign body.

Fill in each pool's "tag" in config.json first: the public_full_id returned by
POST /v1/spam_tests, or the code from the MailReach dashboard (manual fallback).
One unique tag per pool: a swapped or duplicated tag silently corrupts both
tests.

The update path has two requirements the create path does not:
  - PUT /campaigns/sequence-steps/{sequence_id}, and every entry must carry the
    existing step id, or 422 "The sequence_steps.0.id field is required."
  - a top-level title, or 422 "The title field is required."

    python scripts/3_arm_tags.py         # dry run
    python scripts/3_arm_tags.py --arm
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, load_config, load_state, save_state, die, confirm_flag  # noqa: E402


def main():
    cfg, state = load_config(), load_state()
    tags = {p["key"]: (p.get("tag") or "").strip() for p in cfg["pools"]}

    missing = [k for k, v in tags.items() if not v]
    if missing:
        die(f"no tag set in config.json for pools: {', '.join(missing)}")
    if not all(t.startswith("mlrch-") for t in tags.values()):
        die("every tag must be the full mlrch- prefixed code (public_full_id).")
    if len(set(tags.values())) != len(tags):
        die("duplicate mlrch- tags across pools. Each test needs its own tag.")

    for c in state["campaigns"]:
        print(f"  {c['pool']:22s} -> {tags[c['pool_key']]}")
    if not confirm_flag("--arm", "append these tags"):
        return

    for c in state["campaigns"]:
        cid, tag = c["campaign_id"], tags[c["pool_key"]]
        _, camp = bison("GET", f"/campaigns/{cid}")
        seq_id = camp["data"]["sequence_id"]
        _, steps_resp = bison("GET", f"/campaigns/{cid}/sequence-steps")
        steps = steps_resp.get("data") or steps_resp
        step = steps[0]

        if tag in step["email_body"]:
            print(f"  #{cid} {c['pool']:22s} already armed")
            c["tag"] = tag
            continue

        payload = {"title": c["name"], "sequence_steps": [{
            "id": step["id"],
            "order": step.get("order", 1),
            "email_subject": step["email_subject"],
            "email_body": step["email_body"].rstrip() + "\n\n" + tag,
            "wait_in_days": step.get("wait_in_days", 1),
            "thread_reply": step.get("thread_reply", False),
            "variant": step.get("variant", False),
        }]}
        put_status, put_resp = bison("PUT", f"/campaigns/sequence-steps/{seq_id}", payload)
        _, check = bison("GET", f"/campaigns/{cid}/sequence-steps")
        present = tag in ((check.get("data") or check)[0]["email_body"])
        c["tag"] = tag
        print(f"  #{cid} {c['pool']:22s} PUT={put_status} tag present={present}"
              + ("" if present else f"  {put_resp.get('__error')}"))

    save_state(state)
    print("\nsaved tags to .placement_state.json. Run 4_qa_preflight.py next.")


if __name__ == "__main__":
    main()
