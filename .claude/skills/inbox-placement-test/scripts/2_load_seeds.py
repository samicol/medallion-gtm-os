#!/usr/bin/env python3
"""Step 7 - load this run's fresh MailReach seeds into every campaign.

Never recycle seed addresses from a prior run: MailReach's seed set changes
between tests and stale seeds silently reduce the scanned count.

Two traps handled here:
  - Bison 422s on a blank first_name, and personal Gmail/Outlook seeds often
    arrive with both names blank. Backfill from the email prefix, digits stripped.
  - allow_parallel_sending must be on the ATTACH call, not just lead-create.
    Without it the first campaign claims the seeds and every later attach 422s.

    python scripts/2_load_seeds.py           # dry run, prints the parsed seeds
    python scripts/2_load_seeds.py --load
"""
import sys, os, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, load_config, load_state, save_state, die, confirm_flag  # noqa: E402


def clean_name(part, fallback):
    """Truncate at the first digit: seeds arrive as rita.johnson2r@... and the
    trailing disambiguator is not part of the name (-> Rita Johnson)."""
    cut = next((i for i, ch in enumerate(part) if ch.isdigit()), len(part))
    name = part[:cut].strip()
    return name.capitalize() if name else fallback


def parse_seeds(path):
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        die(f"seed CSV not found: {path}")
    seeds, seen = [], set()
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            email = (row.get("Email") or "").strip()
            if not email or email.lower() in seen:
                continue
            seen.add(email.lower())
            prefix = email.split("@")[0]
            parts = [p for p in prefix.replace(".", " ").replace("_", " ").split() if p]
            first = (row.get("First name") or "").strip()
            last = (row.get("Last name") or "").strip()
            if not first:
                first = clean_name(parts[0] if parts else "", "Seed")
            if not last:
                last = clean_name(parts[1] if len(parts) > 1 else "", "Seed")
            seeds.append({"email": email, "first_name": first, "last_name": last})
    return seeds


def main():
    cfg, state = load_config(), load_state()
    seeds = parse_seeds(cfg["seed_csv"])
    print(f"parsed {len(seeds)} unique seeds from {cfg['seed_csv']}")
    for s in seeds:
        print(f"  {s['email']:44s} {s['first_name']} {s['last_name']}")
    blank = [s for s in seeds if not s["first_name"]]
    if blank:
        die(f"{len(blank)} seeds still have a blank first name; Bison will 422.")
    if not confirm_flag("--load", "create and attach these seeds"):
        return

    status, resp = bison("POST", "/leads/create-or-update/multiple",
                         {"existing_lead_behavior": "patch", "leads": seeds})
    if status not in (200, 201):
        die(f"lead create failed ({status}): {resp.get('__error')}")

    data = resp.get("data")
    rows = data if isinstance(data, list) else (data or {}).get("leads") or []
    email_to_id = {r["email"].strip().lower(): r["id"] for r in rows if r.get("email")}
    lead_ids = [email_to_id[s["email"].lower()] for s in seeds if s["email"].lower() in email_to_id]
    print(f"\ncreated/updated {len(lead_ids)} seed leads")
    if len(lead_ids) != len(seeds):
        print(f"WARNING: {len(seeds) - len(lead_ids)} seeds did not come back with an id.")

    for c in state["campaigns"]:
        cid = c["campaign_id"]
        att_status, _ = bison("POST", f"/campaigns/{cid}/leads/attach-leads",
                              {"lead_ids": lead_ids, "allow_parallel_sending": True})
        # A re-attach 422s harmlessly, so trust the lead count, not the response.
        _, listing = bison("GET", f"/campaigns/{cid}/leads?per_page=1&page=1")
        total = (listing.get("meta") or {}).get("total")
        c["total_leads"] = total
        ok = "ok" if total == len(seeds) else f"EXPECTED {len(seeds)}"
        print(f"  #{cid} {c['pool']:22s} attach={att_status} total_leads={total} {ok}")

    state["seed_count"] = len(seeds)
    state["seed_emails"] = [s["email"] for s in seeds]
    save_state(state)
    print("\nDONE. Re-run 1_build's cap settings if the seed count changed from the "
          "config default: max_new_leads_per_day must equal the actual seed count.")


if __name__ == "__main__":
    main()
