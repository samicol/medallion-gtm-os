#!/usr/bin/env python3
"""Step 0 - pre-flight OAuth token audit.

`GET /sender-emails` returning status "Connected" does NOT prove the OAuth token
is alive; an entire pool can read Connected with dead tokens and silently send
nothing. Sweep the token endpoint instead: 200 = alive, 400 = dead.

Custom-SMTP inboxes (e.g. Winnr) cannot be token-checked. The send is the proof.

    python scripts/0_token_audit.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, bison_paginate, load_config  # noqa: E402

OAUTH_TYPES = ("google_workspace_oauth", "microsoft_oauth")


def main():
    cfg = load_config()
    by_id = {}
    for row in bison_paginate("/sender-emails"):
        by_id[row["id"]] = row

    any_dead = False
    for pool in cfg["pools"]:
        alive, dead, skipped, missing = [], [], [], []
        for sid in pool["sender_email_ids"]:
            row = by_id.get(sid)
            if row is None:
                missing.append(sid)
                continue
            email = row.get("email") or row.get("name") or sid
            if row.get("type") not in OAUTH_TYPES:
                skipped.append(email)
                continue
            status, _ = bison("GET", f"/sender-emails/{sid}/oauth-access-token")
            (alive if status == 200 else dead).append(email)

        flag = "DEAD TOKENS" if dead else ("MISSING IDS" if missing else "ok")
        if dead or missing:
            any_dead = True
        print(f"\n{pool['name']}  [{flag}]")
        print(f"  alive       {len(alive)}")
        print(f"  dead        {len(dead)}" + (f"  -> {', '.join(map(str, dead))}" if dead else ""))
        print(f"  custom SMTP {len(skipped)} (not token-checkable)")
        if missing:
            print(f"  NOT FOUND in this workspace: {missing}")

    if any_dead:
        print("\nExclude dead pools from the test and flag them for manual browser "
              "re-auth in the Bison UI. There is no API fix.")
        raise SystemExit(2)
    print("\nAll OAuth tokens alive. Safe to build.")


if __name__ == "__main__":
    main()
