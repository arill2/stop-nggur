#!/usr/bin/env python3
"""Verify that a domain can receive mail, and optionally that a mailbox exists.

Default behaviour is DNS-only (MX lookup): safe, fast, no contact with the
target's mail server.

SMTP RCPT probing is opt-in behind --probe. Read references/compliance.md
before using it. Many providers treat bulk RCPT probing as abuse, and it can
get your sending IP or account blocked.

Usage:
    python3 scripts/verify.py                      # MX only
    python3 scripts/verify.py --probe              # MX + RCPT (opt-in)
    python3 scripts/verify.py --probe --max-probes 100
Output:
    data/targets.csv   [company,email,mx,catch_all,verified]
"""
from __future__ import annotations

import argparse
import random
import smtplib
import socket
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

try:
    import dns.resolver
except ImportError:
    C.die("dnspython is required: pip install dnspython")


def get_mx(domain: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=6)
    except Exception:
        return []
    ordered = sorted(answers, key=lambda r: r.preference)
    return [str(r.exchange).rstrip(".") for r in ordered if str(r.exchange).rstrip(".")]


def rcpt(mx_hosts: list[str], address: str, timeout: int = 6) -> int | None:
    """Return the SMTP code for RCPT TO, or None if unreachable."""
    for host in mx_hosts:
        try:
            server = smtplib.SMTP(timeout=timeout)
            server.connect(host, 25)
            try:
                server.ehlo("localhost")
            except smtplib.SMTPException:
                pass
            code, _ = server.mail("probe@example.com")
            if code != 250:
                server.quit()
                continue
            code, _ = server.rcpt(address)
            try:
                server.quit()
            except smtplib.SMTPException:
                pass
            if code is not None:
                return code
        except (smtplib.SMTPException, socket.error, OSError):
            continue
    return None


def is_catch_all(mx_hosts: list[str], domain: str) -> bool:
    tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return rcpt(mx_hosts, f"{tag}@{domain}") == 250


def verify_one(row: dict, probe: bool) -> dict:
    email = row["email"]
    domain = email.split("@")[-1]
    mx = get_mx(domain)
    company = row.get("company") or domain.split(".")[0].replace("-", " ").title()
    row = {**row, "company": company, "mx": "ok" if mx else "no_mx",
           "catch_all": "", "verified": ""}
    if not mx or not probe:
        return row
    if is_catch_all(mx, domain):
        row["catch_all"] = "yes"
        row["verified"] = "unknown"  # domain accepts anything
        return row
    code = rcpt(mx, email)
    row["verified"] = "yes" if code == 250 else "no"
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify mail domains / mailboxes.")
    ap.add_argument("--probe", action="store_true",
                    help="also probe mailboxes via SMTP RCPT (read compliance.md first)")
    ap.add_argument("--max-probes", type=int, default=200,
                    help="hard cap on SMTP probes per run")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--input", default=str(C.CANDIDATES_FILE))
    args = ap.parse_args()

    rows = C.load_json(Path(args.input), [])
    if not rows:
        C.die(f"no candidates in {args.input} — run discover.py first")

    blocked = C.load_suppression()
    rows = [r for r in rows if r["email"] not in blocked]
    if args.probe:
        rows = rows[: args.max_probes]
        C.info(f"probing {len(rows)} mailboxes (cap {args.max_probes}) — be polite")

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(verify_one, r, args.probe): r for r in rows}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                results.append(fut.result())
            except Exception as exc:  # noqa: BLE001 - keep the batch alive
                row = futures[fut]
                results.append({**row, "mx": "error", "catch_all": "", "verified": "",
                                "detail": str(exc)[:120]})
            if i % 25 == 0:
                C.info(f"  verified {i}/{len(rows)}")
            if args.probe:
                time.sleep(0.2)  # do not hammer mail servers

    order = {"yes": 0, "unknown": 1, "": 2, "no": 3}
    results.sort(key=lambda r: (r.get("mx") != "ok", order.get(r.get("verified", ""), 4)))
    usable = [r for r in results if r.get("mx") == "ok" and r.get("verified") != "no"]

    fields = ["company", "email", "mx", "catch_all", "verified", "source_url"]
    C.DATA.mkdir(parents=True, exist_ok=True)
    import csv
    with C.TARGETS_FILE.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(usable)

    C.info(f"\nmx ok: {sum(1 for r in results if r.get('mx') == 'ok')}/{len(results)}")
    C.info(f"usable: {len(usable)}  -> {C.TARGETS_FILE}")


if __name__ == "__main__":
    main()
