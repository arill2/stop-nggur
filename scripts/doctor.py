#!/usr/bin/env python3
"""Preflight check for an AI agent. Run this FIRST, before any other stage.

Emits a single JSON object on stdout so an agent can branch on it without
parsing prose. Exit code is 0 when the pipeline can proceed, 1 otherwise.

Usage:
    python3 scripts/doctor.py            # human-readable
    python3 scripts/doctor.py --json     # machine-readable (agents use this)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def check_python() -> dict:
    ok = sys.version_info >= (3, 9)
    return {
        "check": "python_version",
        "ok": ok,
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}",
        "fix": "" if ok else "use Python 3.9 or newer",
    }


def check_dnspython() -> dict:
    ok = importlib.util.find_spec("dns") is not None
    return {
        "check": "dnspython",
        "ok": ok,
        "detail": "installed" if ok else "missing",
        "fix": "" if ok else "pip install dnspython",
    }


def check_composio() -> dict:
    path = shutil.which("composio")
    return {
        "check": "composio_cli",
        "ok": bool(path),
        "detail": path or "not found",
        "fix": "" if path else "curl -fsSL https://composio.dev/install | bash",
    }


def check_env() -> dict:
    C.load_env()
    name = C.env_or("SENDER_NAME")
    email = C.env_or("SENDER_EMAIL")
    ok = bool(name and email)
    missing = [k for k, v in (("SENDER_NAME", name), ("SENDER_EMAIL", email)) if not v]
    return {
        "check": "identity_env",
        "ok": ok,
        "detail": f"{name} <{email}>" if ok else f"missing: {', '.join(missing)}",
        "fix": "" if ok else "cp .env.example .env && edit SENDER_NAME / SENDER_EMAIL",
    }


def check_gitignore() -> dict:
    path = C.ROOT / ".gitignore"
    if not path.exists():
        return {"check": "gitignore", "ok": False, "detail": "missing",
                "fix": "create .gitignore covering .env and data/"}
    text = path.read_text()
    needs = [p for p in (".env", "data/") if p not in text]
    return {
        "check": "gitignore",
        "ok": not needs,
        "detail": "ok" if not needs else f"does not cover: {', '.join(needs)}",
        "fix": "" if not needs else f"add {', '.join(needs)} to .gitignore",
    }


def check_leaks() -> dict:
    """Fail if anything under version control looks like a credential."""
    import re
    patterns = {
        "composio_key": re.compile(r"ck_[A-Za-z0-9]{10,}"),
        "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
        "github_pat": re.compile(r"ghp_[A-Za-z0-9]{20,}"),
        "aws_key": re.compile(r"AKIA[0-9A-Z]{12,}"),
    }
    hits = []
    skip_dirs = {".git", "data", "__pycache__", ".venv", "venv"}
    for path in C.ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix not in {".py", ".md", ".txt", ".json", ".sh", ".toml", ".cfg"}:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for label, rx in patterns.items():
            if rx.search(text):
                hits.append(f"{path.relative_to(C.ROOT)}:{label}")
    return {
        "check": "credential_leak",
        "ok": not hits,
        "detail": "clean" if not hits else "; ".join(hits[:5]),
        "fix": "" if not hits else "remove the credential and rotate it immediately",
    }


def check_state() -> dict:
    counts = {
        "candidates": len(C.load_json(C.CANDIDATES_FILE, [])),
        "targets": len(C.load_json(C.TARGETS_FILE, [])) if C.TARGETS_FILE.suffix == ".json" else 0,
        "queue": len(C.load_json(C.QUEUE_FILE, [])),
        "outbox": len(C.load_json(C.DATA / "outbox.json", [])),
        "suppressed": len(C.load_suppression()),
        "sent_today": C.sent_today(),
    }
    if C.TARGETS_FILE.exists():
        import csv
        with C.TARGETS_FILE.open(newline="") as fh:
            counts["targets"] = sum(1 for _ in csv.DictReader(fh))
    return {"check": "pipeline_state", "ok": True, "detail": counts, "fix": ""}


CHECKS = [check_python, check_dnspython, check_composio, check_env,
          check_gitignore, check_leaks, check_state]


def main() -> None:
    ap = argparse.ArgumentParser(description="Preflight checks for the pipeline.")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    results = [fn() for fn in CHECKS]
    blocking = [r for r in results if not r["ok"]]

    if args.json:
        print(json.dumps({
            "ready": not blocking,
            "blocking": [r["check"] for r in blocking],
            "checks": results,
            "next": next_stage(results),
        }, indent=1))
    else:
        for r in results:
            mark = "PASS" if r["ok"] else "FAIL"
            detail = r["detail"]
            if isinstance(detail, dict):
                detail = ", ".join(f"{k}={v}" for k, v in detail.items())
            print(f"[{mark}] {r['check']:16s} {detail}")
            if not r["ok"] and r["fix"]:
                print(f"         fix: {r['fix']}")
        print()
        print("READY" if not blocking else f"BLOCKED: {', '.join(r['check'] for r in blocking)}")

    raise SystemExit(0 if not blocking else 1)


def next_stage(results: list[dict]) -> str:
    state = next((r["detail"] for r in results if r["check"] == "pipeline_state"), {})
    if not state.get("candidates"):
        return "discover"
    if not state.get("targets"):
        return "verify"
    if not state.get("queue"):
        return "dedupe"
    if not state.get("outbox"):
        return "compose"
    return "send"


if __name__ == "__main__":
    main()
