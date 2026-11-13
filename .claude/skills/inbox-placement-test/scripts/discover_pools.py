#!/usr/bin/env python3
"""Helper - enumerate this workspace's sender inboxes and draft a config.

Groups every sender email by auth type and sending domain so you can see what
pools actually exist before defining them. A pool = inboxes sharing a vendor and
auth type that serve the SAME recipient segment in production.

    python scripts/discover_pools.py                 # inspect
    python scripts/discover_pools.py --emit          # write a config.json skeleton

--emit groups by auth type as a starting point. You still have to do two things
by hand, because no API knows them:

  1. Split or merge groups to match your real vendor pools (a workspace often
     has two vendors under one auth type, and they place very differently).
  2. Set each pool's "segment" - GW if it sends to Google recipients in
     production, M365 if it sends to Microsoft recipients. Verify this from your
     live campaigns rather than guessing: count sender types attached to each
     recipient-segment variant. Getting it wrong inverts the verdict.
"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison_paginate, CONFIG_PATH, die  # noqa: E402

TYPE_LABEL = {
    "custom": ("Custom SMTP", "M365"),
    "google_workspace_oauth": ("Google Workspace OAuth", "GW"),
    "microsoft_oauth": ("Microsoft OAuth", "M365"),
}


def main():
    rows = list(bison_paginate("/sender-emails"))
    if not rows:
        die("No sender emails returned. Check EMAILBISON_API_KEY and _BASE_URL.")

    by_type = collections.defaultdict(list)
    for r in rows:
        by_type[r.get("type") or "unknown"].append(r)

    print(f"{len(rows)} sender inboxes in this workspace\n")
    for typ, items in sorted(by_type.items()):
        label = TYPE_LABEL.get(typ, (typ, "?"))[0]
        domains = collections.Counter((i.get("email") or "@?").split("@")[-1] for i in items)
        print(f"{label}  ({typ})  -  {len(items)} inboxes, {len(domains)} domains")
        for dom, n in domains.most_common():
            print(f"    {n:>4}  {dom}")
        print()

    print("Domains usually map to vendors. If one auth type spans two vendors, split it into\n"
          "two pools - vendors place differently and a blended pool hides which one is dead.\n")

    if "--emit" not in sys.argv:
        print("[inspect only] pass --emit to write a config.json skeleton.")
        return

    if os.path.exists(CONFIG_PATH):
        die(f"{CONFIG_PATH} already exists. Move it aside first; this will not overwrite it.")

    pools = []
    for typ, items in sorted(by_type.items()):
        label, seg = TYPE_LABEL.get(typ, (typ, "GW"))
        pools.append({
            "key": typ.replace("_", "-"),
            "name": label,
            "auth": label,
            "segment": seg,
            "sender_email_ids": sorted(i["id"] for i in items),
            "tag": "",
            "_TODO": "rename to the vendor, split if this type spans vendors, and VERIFY segment",
        })

    cfg = {
        "date_label": "<Mon DD YYYY>",
        "timezone": "America/New_York",
        "seed_csv": "~/Downloads/mailreach_spamchecker_emails.csv",
        "campaign": {
            "name_template": "Inbox Placement Test - {date} - {pool}",
            "max_emails_per_day": 1000,
            "plain_text": True,
            "open_tracking": False,
            "send_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        },
        "copy": {"subject": "<subject spintax>", "body": "<body spintax, {FIRST_NAME} only>"},
        "pools": pools,
        "sheet": {"spreadsheet_id": "", "tab": "MailReach Tests", "sheet_id": 0,
                  "start_row": 1, "round_label": "Round 1"},
    }
    with open(CONFIG_PATH, "w") as fh:
        json.dump(cfg, fh, indent=1)
    print(f"wrote {CONFIG_PATH} with {len(pools)} draft pools.")
    print("Now: rename pools to vendors, split any type that spans vendors, set every\n"
          "segment, drop the _TODO keys, and paste in the copy.")


if __name__ == "__main__":
    main()
