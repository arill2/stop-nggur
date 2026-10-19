#!/usr/bin/env python3
"""Render the application email for each queued recipient.

Identity comes from the environment (.env). Templates use {placeholders} and
must contain an opt-out line; the script refuses to render without one, because
a cold email without an opt-out is spam by most definitions.

Usage:
    python3 scripts/compose.py --template templates/en_penetration_tester.txt
Output:
    data/outbox.json   [{company,email,subject,body}]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

# A template is only acceptable if it lets the recipient say no.
OPT_OUT_RE = re.compile(
    r"(unsubscribe|opt[- ]out|do not wish to receive|no longer wish"
    r"|reply\s+stop|balas\s+stop|tidak akan menghubungi|berhenti)",
    re.I,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Render application emails.")
    ap.add_argument("--template", default="templates/en_penetration_tester.txt")
    ap.add_argument("--position", default="",
                    help="override the {position} placeholder")
    ap.add_argument("--allow-no-optout", action="store_true",
                    help="override the opt-out requirement (not recommended)")
    args = ap.parse_args()

    C.load_env()
    tpl_path = Path(args.template)
    if not tpl_path.is_absolute():
        tpl_path = C.ROOT / tpl_path
    if not tpl_path.exists():
        C.die(f"template not found: {tpl_path}")

    template = tpl_path.read_text()
    if not OPT_OUT_RE.search(template) and not args.allow_no_optout:
        C.die(
            "template has no opt-out line.\n"
            "       Add something like: 'Reply STOP and I will not contact you again.'\n"
            "       Cold email without an opt-out is unsolicited bulk mail."
        )

    identity = {
        "sender_name": C.env_or("SENDER_NAME"),
        "sender_email": C.env_or("SENDER_EMAIL"),
        "sender_phone": C.env_or("SENDER_PHONE"),
        "sender_linkedin": C.env_or("SENDER_LINKEDIN"),
    }
    missing = [k for k in ("sender_name", "sender_email") if not identity[k]]
    if missing:
        C.die(f"missing identity in .env: {', '.join(missing)}")

    position = args.position or "Penetration Tester / Freelance Bug Bounty Hunter"
    queue = C.load_json(C.QUEUE_FILE, [])
    if not queue:
        C.die(f"queue is empty — run dedupe.py first ({C.QUEUE_FILE})")

    outbox = []
    for row in queue:
        values = {**identity, "company": row["company"], "position": position,
                  "email": row["email"]}
        try:
            body = template.format(**values)
        except KeyError as exc:
            C.die(f"template references unknown placeholder {exc}")
        subject = f"Application for {position} — {identity['sender_name']}"
        outbox.append({**row, "subject": subject, "body": body})

    C.save_json(C.DATA / "outbox.json", outbox)
    C.info(f"rendered {len(outbox)} email(s) -> {C.DATA / 'outbox.json'}")
    C.info("\n--- preview ---")
    C.info(outbox[0]["body"][:900])


if __name__ == "__main__":
    main()
