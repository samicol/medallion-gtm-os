"""Shared helpers: config/state/env loading, Bison + MailReach HTTP, pagination.

Stdlib only. Every script in this folder imports from here.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# Where this run's config, state, and results live. Defaults to the folder above
# scripts/, which is right for a standalone checkout. Set PLACEMENT_RUN_DIR to
# keep a run's files somewhere else - required when these scripts are installed
# read-only (e.g. vendored inside a skill) and when running several fleets.
ROOT = os.environ.get("PLACEMENT_RUN_DIR") or os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.expanduser(ROOT))
os.makedirs(ROOT, exist_ok=True)

CONFIG_PATH = os.path.join(ROOT, "config.json")
STATE_PATH = os.path.join(ROOT, ".placement_state.json")
ENV_PATH = os.path.join(ROOT, ".env")

# MailReach sits behind Cloudflare and 1010s any request without a browser UA.
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# MailReach `desc` values -> the four scoring buckets. Anything unmapped is
# reported as "unknown" rather than silently dropped.
# MailReach is inconsistent about case and about the "smart features" suffix:
# a single run returned "Office 365" AND "office 365", plus "Google Workspace
# without smart features". Lookups are normalised to lowercase (see
# _bucket_of) so a case variant cannot silently drop seeds out of the
# denominator. That drop is not cosmetic: on one real run it
# hid all 8 Office 365 seeds from one pool, turning a real result into a
# bogus "8/8 KEEP".
DESC_BUCKETS = {
    "google workspace": "gw",
    "google workspace with smart features": "gw",
    "google workspace without smart features": "gw",
    "gmail account with smart features": "gmail",
    "gmail account": "gmail",
    "office 365": "m365",
    "hotmail account": "outlook",
    "outlook account": "outlook",
}
WORK_BUCKETS = ("gw", "m365")


# --------------------------------------------------------------------------
# env / config / state
# --------------------------------------------------------------------------
def load_env():
    """Read .env into os.environ without clobbering real environment vars.
    Checks the run dir first, then the install dir."""
    path = ENV_PATH if os.path.exists(ENV_PATH) else os.path.join(os.path.dirname(HERE), ".env")
    if not os.path.exists(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def env(name, required=True):
    load_env()
    val = os.environ.get(name, "").strip()
    if required and not val:
        die(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return val


def load_config():
    if not os.path.exists(CONFIG_PATH):
        die("config.json not found. Copy config.example.json to config.json and edit it.")
    with open(CONFIG_PATH) as fh:
        cfg = json.load(fh)
    pools = cfg.get("pools") or []
    if not pools:
        die("config.json has no pools.")
    keys = [p["key"] for p in pools]
    if len(set(keys)) != len(keys):
        die("config.json pool keys must be unique.")
    for pool in pools:
        if pool.get("segment") not in ("GW", "M365"):
            die(f"pool '{pool['key']}': segment must be \"GW\" or \"M365\" (the recipient "
                "segment this pool actually serves in production).")
        if not pool.get("sender_email_ids"):
            die(f"pool '{pool['key']}': sender_email_ids is empty.")
    return cfg


def load_state():
    if not os.path.exists(STATE_PATH):
        die("No .placement_state.json yet. Run 1_build.py first.")
    with open(STATE_PATH) as fh:
        return json.load(fh)


def save_state(state):
    with open(STATE_PATH, "w") as fh:
        json.dump(state, fh, indent=1)


def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(1)


def confirm_flag(flag, what):
    """Every mutating script is dry-run by default. Returns True if armed."""
    if flag in sys.argv:
        return True
    print(f"\n[DRY RUN] nothing was changed. Pass {flag} to {what}.")
    return False


# --------------------------------------------------------------------------
# Bison
# --------------------------------------------------------------------------
def _request(url, method, headers, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            detail = exc.read().decode("utf-8", "replace")[:400]
            return exc.code, {"__error": detail}
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            return 0, {"__error": str(exc)}
    return 0, {"__error": "exhausted retries"}


def bison(method, path, body=None):
    """Call the Bison API. `path` is relative to EMAILBISON_BASE_URL, e.g. "/campaigns"."""
    base = env("EMAILBISON_BASE_URL").rstrip("/")
    key = env("EMAILBISON_API_KEY")
    return _request(
        base + path,
        method,
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        body,
    )


def bison_paginate(path, per_page=15):
    """Yield every row across all pages. Bison caps sender-emails at 15/page, so
    reading only page 1 silently under-counts any pool larger than 15."""
    page = 1
    sep = "&" if "?" in path else "?"
    while True:
        status, payload = bison("GET", f"{path}{sep}page={page}&per_page={per_page}")
        if status != 200:
            die(f"GET {path} page {page} failed ({status}): {payload.get('__error')}")
        rows = payload.get("data") or []
        for row in rows:
            yield row
        last = (payload.get("meta") or {}).get("last_page") or 1
        if page >= last or not rows:
            return
        page += 1


# --------------------------------------------------------------------------
# MailReach
# --------------------------------------------------------------------------
def bare_public_id(value):
    """The API wants the bare public_id; the mlrch- prefixed form returns
    "public_id is invalid"."""
    return (value or "").strip().removeprefix("mlrch-")


def mailreach_test(public_id):
    key = env("MAILREACH_API_KEY")
    url = f"https://api.mailreach.co/api/v1/spam_tests/{bare_public_id(public_id)}"
    status, payload = _request(
        url, "GET", {"X-Api-Key": f"Bearer {key}", "User-Agent": BROWSER_UA}
    )
    if status != 200:
        die(f"MailReach {public_id} failed ({status}): {payload.get('__error')}")
    return payload


def bucket_counts(test_json):
    """Collapse results[] into the 4-way split. Only received_in == INBOX counts
    as inbox; PROMOTION is not inbox."""
    counts = {b: {"inbox": 0, "spam": 0, "other": 0, "total": 0}
              for b in ("gw", "gmail", "m365", "outlook", "unknown")}
    for row in test_json.get("results") or []:
        bucket = DESC_BUCKETS.get((row.get("desc") or "").strip().lower(), "unknown")
        placement = (row.get("received_in") or "").strip().upper()
        counts[bucket]["total"] += 1
        if placement == "INBOX":
            counts[bucket]["inbox"] += 1
        elif placement == "SPAM":
            counts[bucket]["spam"] += 1
        else:
            counts[bucket]["other"] += 1
    return counts


def verdict(in_segment_inbox, in_segment_total):
    """Segment-aware verdict. Thresholds are expressed against a /8 work segment
    and scaled if MailReach's seed mix shifts."""
    if not in_segment_total:
        return "NO DATA"
    ratio = in_segment_inbox / in_segment_total
    if ratio >= 0.80:
        return "KEEP"
    if ratio >= 0.50:
        return "MARGINAL"
    return "KILL"
