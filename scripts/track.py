#!/usr/bin/env python3
"""Inspect send history and manage the suppression list.

Agents should use --json; humans can use the default text output.

Usage:
    python3 scripts/track.py status
    python3 scripts/track.py status --json
    python3 scripts/track.py optout someone@example.com
    python3 scripts/track.py export out.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def status(as_json: bool = False) -> None:
    if not C.LOG_FILE.exists():
        payload = {"total": 0, "by_status": {}, "sent_today": 0,
                   "unique_sent": 0, "suppressed": len(C.load_suppression())}
        if as_json:
            print(json.dumps(payload, indent=1))
        else:
            C.info("no sends logged yet")
        return

    with C.LOG_FILE.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    counts = Counter(r.get("status", "?") for r in rows)
    sent = {r["email"].lower() for r in rows if r.get("status") == "sent"}
    payload = {
        "total": len(rows),
        "by_status": dict(counts),
        "sent_today": C.sent_today(),
        "unique_sent": len(sent),
        "suppressed": len(C.load_suppression()),
    }
    if as_json:
        print(json.dumps(payload, indent=1))
        return
    C.info(f"total logged : {payload['total']}")
    for k, v in counts.most_common():
        C.info(f"  {k:12s} {v}")
    C.info(f"today        : {payload['sent_today']}")
    C.info(f"unique sent  : {payload['unique_sent']}")
    C.info(f"suppressed   : {payload['suppressed']}")


def optout(email: str) -> None:
    C.add_suppression(email, "manual opt-out")
    C.info(f"{email} added to suppression list — will never be contacted again")


def export(dest: str) -> None:
    if not C.LOG_FILE.exists():
        C.die("no log to export")
    shutil.copy(C.LOG_FILE, dest)
    C.info(f"exported {C.LOG_FILE} -> {dest}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect the send log.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_status = sub.add_parser("status")
    p_status.add_argument("--json", action="store_true")
    p_opt = sub.add_parser("optout")
    p_opt.add_argument("email")
    p_exp = sub.add_parser("export")
    p_exp.add_argument("dest")
    args = ap.parse_args()

    if args.cmd == "status":
        status(as_json=args.json)
    elif args.cmd == "optout":
        optout(args.email)
    elif args.cmd == "export":
        export(args.dest)


if __name__ == "__main__":
    main()
