#!/usr/bin/env python3
"""List a Bison workspace's active campaigns and their sender pools.

    python weekly/discover.py <label> <KEY_ENV_NAME> <outdir>

Reads the API key from the env var named KEY_ENV_NAME (e.g. EMAILBISON_API_KEY)
and the base URL from EMAILBISON_BASE_URL (e.g. https://your-bison-host/api).
Falls back to the .env file in PLACEMENT_RUN_DIR when a var is not set.
Read-only: it only issues GET requests.
"""
import json, os, re, sys, time, urllib.request
from collections import Counter

# Map a lowercase substring of your sender tags to a vendor label. Edit to match your fleet.
VENDORS = {"vendor-a": "Vendor A", "vendor-b": "Vendor B"}
DEFAULT_TAGS = {"Custom Mail Server", "Google", "Microsoft", "Outlook"}

if len(sys.argv) != 4:
    sys.exit(__doc__)
label, keyname, outdir = sys.argv[1:4]

env = {}
run_dir = os.environ.get("PLACEMENT_RUN_DIR")
if run_dir and os.path.exists(os.path.join(os.path.expanduser(run_dir), ".env")):
    for line in open(os.path.join(os.path.expanduser(run_dir), ".env")):
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
key = os.environ.get(keyname) or env.get(keyname)
base = (os.environ.get("EMAILBISON_BASE_URL") or env.get("EMAILBISON_BASE_URL") or "").rstrip("/")
if not key or not base:
    sys.exit(f"Missing {keyname} or EMAILBISON_BASE_URL.")
H = {"Authorization": "Bearer " + key, "Accept": "application/json", "User-Agent": "Mozilla/5.0"}


def get(path):
    err = None
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(base + path, headers=H), timeout=60))
        except Exception as e:  # retry transient errors
            time.sleep(2 * (i + 1))
            err = e
    raise err


def pages(path):
    out, p = [], 1
    while True:
        d = get(f"{path}{'&' if '?' in path else '?'}page={p}")
        out += d["data"]
        if p >= (d.get("meta") or {}).get("last_page", 1):
            return out
        p += 1


def describe(s):
    names = [t["name"] for t in s.get("tags") or []]
    vendor = next((VENDORS[k] for n in names for k in VENDORS if k in n.lower()), "?")
    prov = {"custom": "SMTP", "google_workspace_oauth": "Google", "microsoft_oauth": "Microsoft"}.get(s.get("type"), s.get("type"))
    batch = [n for n in names if re.fullmatch(r"Batch \d+", n)]
    extra = [n for n in names if n not in batch and n not in DEFAULT_TAGS and not any(k in n.lower() for k in VENDORS)]
    return [vendor, prov, batch, extra]


def slim(s):
    return {"id": s["id"], "email": s["email"], "status": s["status"], "daily_limit": s.get("daily_limit"),
            "type": s.get("type"), "vp": describe(s)}


camps = [c for c in pages("/campaigns") if c["status"] in ("active", "launching", "queued")]
res = {"campaigns": [], "senders": [slim(s) for s in pages("/sender-emails")]}
for c in camps:
    ss = pages(f"/campaigns/{c['id']}/sender-emails")
    res["campaigns"].append({"id": c["id"], "name": c["name"], "status": c["status"], "created_at": c.get("created_at"),
                             "emails_sent": c.get("emails_sent"), "total_leads": c.get("total_leads"),
                             "senders": [slim(s) for s in ss]})
os.makedirs(outdir, exist_ok=True)
json.dump(res, open(os.path.join(outdir, f"{label}-discovery.json"), "w"), indent=1)

for c in sorted(res["campaigns"], key=lambda c: -c["id"]):
    print(f"#{c['id']} {(c['created_at'] or '')[:10]} {c['status']} {c['name']}  sent {c['emails_sent']}/{c['total_leads']}")
    for k, n in sorted(Counter((s["vp"][0], s["vp"][1], tuple(s["vp"][2]), tuple(s["vp"][3])) for s in c["senders"]).items()):
        print(f"      {n:3d}  {k}")
print("== ALL SENDERS")
for k, n in sorted(Counter((s["vp"][0], s["vp"][1], tuple(s["vp"][2]), tuple(s["vp"][3]), s["status"]) for s in res["senders"]).items()):
    print(f"  {n:3d}  {k}")
