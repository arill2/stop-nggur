#!/usr/bin/env python3
"""Build the send queue: drop anything already contacted, and cap per company.

This is the step that stops duplicate applications. It reads the targets list,
subtracts every address in the suppression list and every address already in
the sent log, then keeps at most --per-domain addresses per company.

Usage:
    python3 scripts/dedupe.py [--per-domain 1] [--limit 50]
Output:
    data/queue.json
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def load_targets() -> list[dict]:
    if not C.TARGETS_FILE.exists():
        C.die(f"{C.TARGETS_FILE} not found — run verify.py first")
    with C.TARGETS_FILE.open(newline="") as fh:
        return list(csv.DictReader(fh))


def preference(email: str) -> int:
    """Lower is better. Prefer application inboxes over support desks."""
    local = email.split("@")[0].lower()
    if any(k in local for k in ("career", "job", "recruit", "karir", "rekrut",
                                "hiring", "talent", "hr")):
        return 0
    if any(k in local for k in ("security", "cyber", "pentest", "infosec")):
        return 1
    if local in {"hello", "hi", "info", "contact", "office", "general",
                 "enquiry", "enquiries", "inquiry", "halo", "kontak"}:
        return 2
    if any(k in local for k in ("admin", "team", "business", "bd", "sales")):
        return 3
    return 4


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a de-duplicated send queue.")
    ap.add_argument("--per-domain", type=int, default=1,
                    help="max addresses per company domain (default 1)")
    ap.add_argument("--limit", type=int, default=50,
                    help="max addresses in the queue (default 50)")
    ap.add_argument("--input", default=str(C.TARGETS_FILE))
    args = ap.parse_args()

    rows = load_targets() if args.input == str(C.TARGETS_FILE) else C.load_json(Path(args.input), [])
    # best inbox first, so the per-domain cap keeps the right one
    rows = sorted(rows, key=lambda r: preference(str(r.get("email", "")).lower()))
    blocked = C.load_suppression()
    C.info(f"suppression list: {len(blocked)} address(es)")

    seen_email: set[str] = set()
    per_domain: dict[str, int] = {}
    queue: list[dict] = []
    skipped_dup = skipped_cap = 0

    for row in rows:
        email = str(row.get("email", "")).strip().lower()
        if "@" not in email:
            continue
        if email in blocked or email in seen_email:
            skipped_dup += 1
            continue
        domain = email.split("@")[-1]
        if per_domain.get(domain, 0) >= args.per_domain:
            skipped_cap += 1
            continue
        per_domain[domain] = per_domain.get(domain, 0) + 1
        seen_email.add(email)
        queue.append({
            "company": row.get("company") or domain,
            "email": email,
            "domain": domain,
        })
        if len(queue) >= args.limit:
            break

    C.save_json(C.QUEUE_FILE, queue)
    C.info(f"skipped: {skipped_dup} duplicate/already-sent, {skipped_cap} over per-domain cap")
    C.info(f"\nqueue: {len(queue)} address(es) across {len(per_domain)} domain(s)")
    for i, r in enumerate(queue[:10], 1):
        C.info(f"  {i:2d}. {r['company'][:34]:34s} {r['email']}")
    if len(queue) > 10:
        C.info(f"  ... and {len(queue) - 10} more")
    C.info(f"-> {C.QUEUE_FILE}")


if __name__ == "__main__":
    main()
