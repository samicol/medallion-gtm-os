#!/usr/bin/env python3
"""Step 8.5 - end-to-end pre-launch QA. Only launch on all-green.

A total_leads and sender-count check is not enough. This sweeps copy/spintax
integrity, tag correctness and cross-contamination, seeds, settings, sender
pools, and OAuth token liveness across every campaign, then prints a PASS/FAIL
table.

    python scripts/4_qa_preflight.py
"""
import sys, os, re, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bison_api import bison, bison_paginate, load_config, load_state  # noqa: E402

KNOWN_VARS = {"FIRST_NAME", "LAST_NAME", "COMPANY", "SENDER_EMAIL_SIGNATURE"}
INNERMOST = re.compile(r"\{([^{}]*)\}")
OAUTH_TYPES = ("google_workspace_oauth", "microsoft_oauth")


def render(text, rng):
    """Resolve spintax innermost-first. Variables survive as {NAME}; anything
    unrecognised comes back as {?...} so it shows up in the rendered output."""
    out = text
    for _ in range(500):
        m = INNERMOST.search(out)
        if not m:
            break
        inner = m.group(1)
        if "|" in inner:
            repl = rng.choice(inner.split("|"))
        elif inner.strip() in KNOWN_VARS:
            repl = "\x00" + inner.strip() + "\x01"
        else:
            repl = "\x00?" + inner + "\x01"
        out = out[:m.start()] + repl + out[m.end():]
    return out.replace("\x00", "{").replace("\x01", "}")


def check_copy(subject, body):
    problems = []
    for label, text in (("subject", subject), ("body", body)):
        if text.count("{") != text.count("}"):
            problems.append(f"{label}: unbalanced braces ({text.count('{')} open, {text.count('}')} close)")
        for bad in ("||", "{|", "|}"):
            if bad in text:
                problems.append(f"{label}: empty spintax option '{bad}'")
        for group in INNERMOST.findall(text):
            if "|" not in group and group.strip() not in KNOWN_VARS:
                problems.append(f"{label}: unknown token {{{group}}}")

    rng = random.Random(7)
    for i in range(5):
        for label, text in (("subject", subject), ("body", body)):
            out = render(text, rng)
            if "{?" in out:
                problems.append(f"{label}: unresolved token in variant {i + 1}")
            if "  " in out.replace("\n", " ").replace("\n\n", " "):
                problems.append(f"{label}: double space in variant {i + 1}")
            if re.search(r"\s[,.!?]|,,|\.\.(?!\.)", out):
                problems.append(f"{label}: orphan punctuation in variant {i + 1}")
    return sorted(set(problems))


def main():
    cfg, state = load_config(), load_state()
    camps = state["campaigns"]
    seeds_expected = state.get("seed_count", 30)
    tags = {c["campaign_id"]: c.get("tag", "") for c in camps}
    all_tags = [t for t in tags.values() if t]

    by_id = {r["id"]: r for r in bison_paginate("/sender-emails")}
    seen_senders, results = {}, []

    for c in camps:
        cid = c["campaign_id"]
        row = {"pool": c["pool"], "cid": cid}
        _, camp = bison("GET", f"/campaigns/{cid}")
        data = camp.get("data") or {}
        _, steps_resp = bison("GET", f"/campaigns/{cid}/sequence-steps")
        steps = steps_resp.get("data") or steps_resp
        step = steps[0] if steps else {}
        subject, body = step.get("email_subject", ""), step.get("email_body", "")

        copy_problems = check_copy(subject, body)
        row["copy"] = ("PASS", "") if not copy_problems else ("FAIL", "; ".join(copy_problems[:3]))

        own = tags[cid]
        foreign = [t for t in all_tags if t != own and t in body]
        tag_problems = []
        if not own:
            tag_problems.append("no tag armed")
        elif body.count(own) != 1:
            tag_problems.append(f"own tag appears {body.count(own)}x")
        if foreign:
            tag_problems.append(f"FOREIGN TAG present: {foreign}")
        if len(set(all_tags)) != len(all_tags):
            tag_problems.append("duplicate tags across campaigns")
        row["tags"] = ("PASS", "") if not tag_problems else ("FAIL", "; ".join(tag_problems))

        leads = list(bison_paginate(f"/campaigns/{cid}/leads"))
        emails = [(l.get("email") or "").lower() for l in leads]
        seed_problems = []
        if len(leads) != seeds_expected:
            seed_problems.append(f"{len(leads)} leads, expected {seeds_expected}")
        if len(set(emails)) != len(emails):
            seed_problems.append("duplicate seed emails")
        blanks = sum(1 for l in leads if not (l.get("first_name") or "").strip())
        if blanks:
            seed_problems.append(f"{blanks} blank first names")
        if state.get("seed_emails") and set(emails) != {e.lower() for e in state["seed_emails"]}:
            seed_problems.append("seed set differs from the loaded set")
        row["seeds"] = ("PASS", "") if not seed_problems else ("FAIL", "; ".join(seed_problems))

        want = {"plain_text": True, "open_tracking": False,
                "include_auto_replies_in_stats": False,
                "sequence_prioritization": "new_leads",
                "max_new_leads_per_day": seeds_expected}
        wrong = [f"{k}={data.get(k)!r} want {v!r}" for k, v in want.items()
                 if k in data and data.get(k) != v]
        if (data.get("status") or "").lower() not in ("draft", ""):
            wrong.append(f"status={data.get('status')} (expected draft)")
        row["settings"] = ("PASS", "") if not wrong else ("FAIL", "; ".join(wrong))

        attached = [s["id"] for s in bison_paginate(f"/campaigns/{cid}/sender-emails")]
        pool_problems = []
        if len(attached) != len(c["senders"]):
            pool_problems.append(f"{len(attached)} attached, config says {len(c['senders'])}")
        for sid in attached:
            if sid in seen_senders and seen_senders[sid] != cid:
                pool_problems.append(f"inbox {sid} also in campaign #{seen_senders[sid]}")
            seen_senders[sid] = cid
        row["pool"] = c["pool"]
        row["senders"] = ("PASS", "") if not pool_problems else ("FAIL", "; ".join(pool_problems))

        dead = []
        for sid in attached:
            if (by_id.get(sid) or {}).get("type") in OAUTH_TYPES:
                st, _ = bison("GET", f"/sender-emails/{sid}/oauth-access-token")
                if st != 200:
                    dead.append(sid)
        row["tokens"] = ("PASS", "") if not dead else ("FAIL", f"dead: {dead}")
        results.append(row)

    cols = ["copy", "tags", "seeds", "settings", "senders", "tokens"]
    print(f"\n{'pool':24s} {'c#':>6s} " + " ".join(f"{c:>9s}" for c in cols))
    print("-" * (24 + 7 + 10 * len(cols)))
    failed = False
    for r in results:
        print(f"{r['pool']:24s} {r['cid']:>6} " + " ".join(f"{r[c][0]:>9s}" for c in cols))
        for c in cols:
            if r[c][0] == "FAIL":
                failed = True
                print(f"    {c}: {r[c][1]}")

    if failed:
        print("\nNOT READY. Fix every FAIL above before the launch gate.")
        raise SystemExit(2)
    print("\nAll green. Present the review table to the operator, then 5_launch.py.")


if __name__ == "__main__":
    main()
