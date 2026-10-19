"""Shared helpers: paths, env loading, suppression list, logging.

No credentials are ever hardcoded here. Everything sensitive comes from the
environment or from a local .env file that is gitignored.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMPLATES = ROOT / "templates"

LOG_FILE = DATA / "sent_log.csv"
SUPPRESSION_FILE = DATA / "suppression.txt"
QUEUE_FILE = DATA / "queue.json"
CANDIDATES_FILE = DATA / "candidates.json"
TARGETS_FILE = DATA / "targets.csv"

LOG_FIELDS = ["ts", "company", "email", "subject", "status", "detail"]


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from .env without pulling in a dependency."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(key: str) -> str:
    value = os.environ.get(key, "").strip()
    if not value:
        sys.exit(
            f"error: {key} is not set.\n"
            f"       Copy .env.example to .env and fill it in, or export {key}."
        )
    return value


def env_or(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip() or default


def load_suppression() -> set[str]:
    """Every address we must never contact again (sent, bounced, opted out)."""
    blocked: set[str] = set()
    if SUPPRESSION_FILE.exists():
        for line in SUPPRESSION_FILE.read_text().splitlines():
            line = line.strip().lower()
            if line and not line.startswith("#"):
                blocked.add(line)
    if LOG_FILE.exists():
        with LOG_FILE.open(newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("status") in {"sent", "unsubscribed", "bounced"}:
                    blocked.add(row["email"].strip().lower())
    return blocked


def add_suppression(email: str, reason: str = "") -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    email = email.strip().lower()
    if not email:
        return
    with SUPPRESSION_FILE.open("a") as fh:
        stamp = datetime.now().isoformat(timespec="seconds")
        fh.write(f"{email}  # {reason} {stamp}\n")


def append_log(company: str, email: str, subject: str, status: str, detail: str = "") -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    new = not LOG_FILE.exists()
    with LOG_FILE.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=LOG_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(
            {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "company": company,
                "email": email,
                "subject": subject,
                "status": status,
                "detail": str(detail)[:300],
            }
        )


def sent_today() -> int:
    if not LOG_FILE.exists():
        return 0
    today = date.today().isoformat()
    count = 0
    with LOG_FILE.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("status") == "sent" and str(row.get("ts", "")).startswith(today):
                count += 1
    return count


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"error: {path} is not valid JSON ({exc})")


def save_json(path: Path, payload) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))


def die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def info(msg: str) -> None:
    print(msg, flush=True)
