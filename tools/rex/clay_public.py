"""
Clay Public API Client: Search
Official, documented API (https://developers.clay.com). Auth via personal API key,
NOT the claysession cookie. Read/search layer; table writes stay in clay_client.py.

Setup:
    Create a key in the Clay app (Settings → Account) and add to the repo .env:
        CLAY_API_KEY=...

Usage:
    from clay_public import ClayPublicClient
    clay = ClayPublicClient()

    fields = clay.search_fields("people")          # discover valid filter names
    people = clay.search("people", {
        "job_title_keywords": ["software engineer"],
        "location_cities_include": ["New York"],
    }, max_results=200)

CLI:
    .venv/bin/python clay_public.py fields people
    .venv/bin/python clay_public.py search people '{"job_title_keywords": ["cfo"]}' \
        --max 100 --csv out.csv
"""

import csv
import json
import os
import random
import sys
import time
from typing import Any, Iterator

import requests

BASE = "https://api.clay.com/public/v0"
PAGE_SIZE_MAX = 500  # NextSearchResultsBody limit cap
MAX_RETRIES = 5


def _load_api_key(client: str = None) -> str:
    """Resolve the Clay Public API key.

    Order (CLIENT-KEY-FIRST): an explicit suffix (CLAY_API_KEY_<CLIENT>, e.g.
    CLAY_API_KEY_ACME), then the shared CLAY_API_KEY. Env vars win over the repo
    .env. Set CLAY_CLIENT=ACME to pick a suffixed key without passing one in code.
    """
    client = client or os.environ.get("CLAY_CLIENT")
    names = ([f"CLAY_API_KEY_{client.upper()}"] if client else []) + ["CLAY_API_KEY"]
    for n in names:
        key = os.environ.get(n)
        if key:
            return key
    # Fall back to the repo root .env (tools/rex/ → repo root is two levels up)
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                for n in names:
                    if line.startswith(n + "="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
    raise RuntimeError(
        f"No Clay Public API key found (looked for: {', '.join(names)}). Create a key in "
        "the Clay app (Settings → Account → API keys) and fill it into the repo .env."
    )


class ClayPublicClient:
    def __init__(self, api_key: str = None, client: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            "clay-api-key": api_key or _load_api_key(client),
            "content-type": "application/json",
        })
        me = self.me()
        print(f"[clay-public] authenticated as {me.get('email', me)}")

    def _request(self, method: str, path: str, **kwargs) -> Any:
        """Request with 429 backoff (honors Retry-After, else exponential + jitter)."""
        for attempt in range(MAX_RETRIES):
            r = self.session.request(method, f"{BASE}{path}", **kwargs)
            if r.status_code != 429:
                if not r.ok:
                    raise requests.HTTPError(
                        f"{r.status_code} on {method} {path}: {r.text[:500]}", response=r
                    )
                return r.json()
            wait = float(r.headers.get("Retry-After") or 2 ** attempt + random.random())
            print(f"[clay-public] 429 rate limited, retrying in {wait:.1f}s")
            time.sleep(wait)
        raise requests.HTTPError(f"rate limited after {MAX_RETRIES} retries on {path}")

    def get(self, path: str, **kwargs) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, body: dict = None, **kwargs) -> Any:
        return self._request("POST", path, json=body, **kwargs)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def me(self) -> dict:
        return self.get("/me")

    # ── Search ────────────────────────────────────────────────────────────────

    def search_fields(self, source_type: str) -> dict:
        """Filter-field catalog for 'people' or 'companies'. Returns
        {source_type, fields: [{name, type, description, ...}], guidance}."""
        return self.get("/search/filters-mode/fields", params={"source_type": source_type})

    def create_search(self, source_type: str, filters: dict) -> str:
        """Start a filter-mode search. Returns search_id."""
        res = self.post("/search/filters-mode", {"source_type": source_type, "filters": filters})
        return res["search_id"]

    def search_page(self, search_id: str, limit: int = PAGE_SIZE_MAX) -> dict:
        """One page of results: {data: [...], has_more: bool}. The iterator is
        stateful server-side, repeated calls advance through the result set."""
        return self.post(f"/search/filters-mode/{search_id}/run", {"limit": limit})

    def search_iter(self, source_type: str, filters: dict,
                    page_size: int = PAGE_SIZE_MAX) -> Iterator[dict]:
        """Create a search and yield records until exhausted."""
        search_id = self.create_search(source_type, filters)
        page_num = 0
        while True:
            page = self.search_page(search_id, limit=page_size)
            page_num += 1
            records = page.get("data", [])
            print(f"[clay-public] page {page_num}: {len(records)} records"
                  f"{'' if page.get('has_more') else ' (end)'}")
            yield from records
            if not page.get("has_more") or not records:
                return

    def search(self, source_type: str, filters: dict, max_results: int = None) -> list[dict]:
        """Create a search and return up to max_results records (all if None)."""
        results = []
        page_size = min(max_results, PAGE_SIZE_MAX) if max_results else PAGE_SIZE_MAX
        for rec in self.search_iter(source_type, filters, page_size=page_size):
            results.append(rec)
            if max_results and len(results) >= max_results:
                return results[:max_results]
        return results


# ── CSV helper ─────────────────────────────────────────────────────────────────


def flatten(record: dict, prefix: str = "") -> dict:
    """Flatten nested dicts to dotted keys; JSON-encode lists of objects."""
    out = {}
    for k, v in record.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, prefix=f"{key}."))
        elif isinstance(v, list):
            out[key] = json.dumps(v) if v and isinstance(v[0], dict) else "; ".join(map(str, v))
        else:
            out[key] = v
    return out


def to_csv(records: list[dict], path: str) -> str:
    rows = [flatten(r) for r in records]
    headers: list[str] = []
    for r in rows:
        headers.extend(k for k in r if k not in headers)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[clay-public] wrote {len(rows)} rows → {path}")
    return path


# ── CLI ────────────────────────────────────────────────────────────────────────

USAGE = """\
Usage:
  clay_public.py fields <people|companies>
  clay_public.py search <people|companies> '<filters-json>' [--max N] [--csv path]
"""


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("fields", "search"):
        print(USAGE)
        sys.exit(1)

    clay = ClayPublicClient()

    if args[0] == "fields":
        if len(args) < 2:
            sys.exit(USAGE)
        print(json.dumps(clay.search_fields(args[1]), indent=2))
        return

    if len(args) < 3:
        sys.exit(USAGE)
    source_type, filters = args[1], json.loads(args[2])
    max_results = None
    csv_path = None
    if "--max" in args:
        max_results = int(args[args.index("--max") + 1])
    if "--csv" in args:
        csv_path = args[args.index("--csv") + 1]

    records = clay.search(source_type, filters, max_results=max_results)
    print(f"[clay-public] {len(records)} total records")
    if csv_path:
        to_csv(records, csv_path)
    else:
        print(json.dumps(records[:5], indent=2))
        if len(records) > 5:
            print(f"... and {len(records) - 5} more (use --csv to save all)")


if __name__ == "__main__":
    main()
