#!/usr/bin/env python3
"""Send the rendered outbox through Composio's Gmail tool.

DRY RUN BY DEFAULT. Nothing leaves your machine unless you pass --send.

Safety rails:
  * --send is required to actually transmit
  * hard daily cap (--daily-cap, default 20) counted from the sent log
  * random delay between sends (--min-delay/--max-delay)
  * re-checks the suppression list at send time, so a race cannot double-send
  * API key comes from COMPOSIO_API_KEY in the environment, never from source

Prerequisites:
    pip install composio   # or: curl -fsSL https://composio.dev/install | bash
    composio login         # or export COMPOSIO_API_KEY=...
    composio add gmail

Usage:
    python3 scripts/send.py                          # dry run
    python3 scripts/send.py --send --limit 10        # send 10
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def composio_bin() -> str:
    path = shutil.which("composio")
    if not path:
        C.die(
            "composio CLI not found.\n"
            "       Install: curl -fsSL https://composio.dev/install | bash\n"
            "       Then:    composio login && composio add gmail"
        )
    return path


def send_one(row: dict, attachment: Path | None) -> tuple[bool, str]:
    payload = json.dumps({
        "recipient_email": row["email"],
        "subject": row["subject"],
        "body": row["body"],
        "is_html": False,
        "user_id": "me",
    })
    cmd = [composio_bin(), "execute", "GMAIL_SEND_EMAIL", "-d", payload]
    if attachment:
        cmd += ["--file", str(attachment)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    try:
        result = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        result = {}
    if result.get("successful"):
        return True, (result.get("data") or {}).get("id", "")
    return False, str(result.get("error") or proc.stderr or proc.stdout)[:250]


def main() -> None:
    ap = argparse.ArgumentParser(description="Send application emails via Composio.")
    ap.add_argument("--send", action="store_true", help="actually transmit (default is dry run)")
    ap.add_argument("--limit", type=int, default=10, help="max emails this run")
    ap.add_argument("--daily-cap", type=int, default=20, help="max emails per calendar day")
    ap.add_argument("--min-delay", type=int, default=45)
    ap.add_argument("--max-delay", type=int, default=90)
    ap.add_argument("--attachment", default="", help="path to CV/PDF to attach")
    ap.add_argument("--outbox", default=str(C.DATA / "outbox.json"))
    args = ap.parse_args()

    C.load_env()
    outbox = C.load_json(Path(args.outbox), [])
    if not outbox:
        C.die(f"outbox empty — run compose.py first ({args.outbox})")

    attachment = None
    if args.attachment:
        attachment = Path(args.attachment).expanduser()
        if not attachment.exists():
            C.die(f"attachment not found: {attachment}")

    already_today = C.sent_today()
    budget = max(0, args.daily_cap - already_today)
    if budget == 0:
        C.die(f"daily cap reached ({already_today}/{args.daily_cap}). Try tomorrow.")
    limit = min(args.limit, budget)
    C.info(f"daily usage {already_today}/{args.daily_cap} — sending up to {limit} this run")

    if not args.send:
        C.info("\nDRY RUN — no email will be sent. Re-run with --send to transmit.\n")
        for i, row in enumerate(outbox[:limit], 1):
            C.info(f"  {i:2d}. {row['email']:42s} {row['company'][:30]}")
        C.info(f"\n{len(outbox)} queued, {limit} would be sent.")
        return

    blocked = C.load_suppression()
    sent_now = 0
    for row in outbox:
        if sent_now >= limit:
            break
        email = row["email"].lower()
        if email in blocked:
            C.info(f"skip {email} (suppression list)")
            continue
        ok, info = send_one(row, attachment)
        sent_now += 1
        status = "OK " if ok else "ERR"
        C.info(f"[{sent_now}/{limit}] {status} {email} {'' if ok else info[:90]}")
        if ok:
            C.append_log(row["company"], email, row["subject"], "sent", info)
        else:
            C.append_log(row["company"], email, row["subject"], "failed", info)
        if sent_now < limit:
            time.sleep(random.randint(args.min_delay, args.max_delay))

    C.info(f"\ndone: {sent_now} processed")


if __name__ == "__main__":
    main()
