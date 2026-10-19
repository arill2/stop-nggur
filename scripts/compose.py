#!/usr/bin/env python3
"""Render application emails from a template plus your profile.

Identity lives in data/profile.md (gitignored). Templates in templates/ carry
NO personal data — they are skeletons with placeholders. Copy
profile.example.md to data/profile.md and fill it in.

The agent is expected to write each body itself when it has a reason to vary
it. This script is the deterministic fallback: same template, profile values
substituted, opt-out enforced.

Usage:
    python3 scripts/compose.py --template templates/en_penetration_tester.txt
    python3 scripts/compose.py --from-outbox   # validate agent-written bodies
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

PROFILE_FILE = C.DATA / "profile.md"

# A template is only acceptable if it lets the recipient say no.
OPT_OUT_RE = re.compile(
    r"(unsubscribe|opt[- ]out|do not wish to receive|no longer wish"
    r"|reply\s+stop|balas\s+stop|tidak akan menghubungi|berhenti)",
    re.I,
)


def parse_profile(path: Path) -> dict:
    """Minimal front-matter parser: `key: value` plus `key:` followed by `- item`."""
    if not path.exists():
        C.die(
            f"{path} not found.\n"
            f"       cp profile.example.md data/profile.md and fill it in.\n"
            f"       data/ is gitignored, so your details stay local."
        )
    data: dict = {}
    current_key = None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(line.lstrip()[2:].strip())
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            current_key = key
            data[key] = value if value else []
    return data


def bullets(items: list[str], prefix: str = "- ") -> str:
    return "\n".join(f"{prefix}{i}" for i in items) if items else ""


def build_values(profile: dict, company: str, position: str) -> dict:
    disclosure = profile.get("disclosure", "").strip()
    availability = profile.get("availability", "").strip().rstrip(".")
    disclosure_line = ""
    if disclosure:
        disclosure_line = disclosure.rstrip(".")
        if availability:
            disclosure_line += f", so I can only work {availability[0].lower() + availability[1:]}"
        disclosure_line += "."
    first_step = profile.get("first_step", "").strip()
    return {
        "company": company,
        "position": position,
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "linkedin": profile.get("linkedin", ""),
        "headline": profile.get("headline", ""),
        "availability": profile.get("availability", ""),
        "disclosure": disclosure,
        "disclosure_line": disclosure_line,
        "capability_bullets": bullets(profile.get("capabilities", [])),
        "highlight_bullets": bullets(profile.get("highlights", [])),
        "first_step_line": f"{first_step.rstrip('.')}." if first_step else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Render application emails.")
    ap.add_argument("--template", default="templates/en_penetration_tester.txt")
    ap.add_argument("--position", default="",
                    help="override the {position} placeholder")
    ap.add_argument("--profile", default=str(PROFILE_FILE))
    ap.add_argument("--from-outbox", action="store_true",
                    help="validate bodies already in data/outbox.json (agent-written)")
    ap.add_argument("--allow-no-optout", action="store_true",
                    help="override the opt-out requirement (not recommended)")
    args = ap.parse_args()

    profile = parse_profile(Path(args.profile))
    missing = [k for k in ("name", "email") if not profile.get(k)]
    if missing:
        C.die(f"profile is missing: {', '.join(missing)}")

    queue = C.load_json(C.QUEUE_FILE, [])
    if not queue:
        C.die(f"queue is empty — run dedupe.py first ({C.QUEUE_FILE})")

    position = args.position or profile.get("headline", "") or \
        "Penetration Tester / Freelance Bug Bounty Hunter"

    # Agent-written path: check bodies, do not overwrite them.
    if args.from_outbox:
        outbox = C.load_json(C.DATA / "outbox.json", [])
        if not outbox:
            C.die("no data/outbox.json to validate")
        bad = [r["email"] for r in outbox if not OPT_OUT_RE.search(r.get("body", ""))]
        if bad and not args.allow_no_optout:
            C.die(f"{len(bad)} body/bodies have no opt-out line: {', '.join(bad[:5])}")
        C.info(f"validated {len(outbox)} agent-written body/bodies — all have an opt-out")
        return

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

    outbox = []
    for row in queue:
        values = build_values(profile, row["company"], position)
        try:
            body = template.format(**values)
        except KeyError as exc:
            C.die(f"template references unknown placeholder {exc}")
        subject = f"Application for {position} — {values['name']}"
        outbox.append({**row, "subject": subject, "body": body})

    C.save_json(C.DATA / "outbox.json", outbox)
    C.info(f"rendered {len(outbox)} email(s) -> {C.DATA / 'outbox.json'}")
    C.info("\n--- preview ---")
    C.info(outbox[0]["body"][:900])


if __name__ == "__main__":
    main()
