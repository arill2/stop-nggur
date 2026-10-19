#!/usr/bin/env python3
"""Discover PUBLISHED contact addresses for a list of domains.

Only addresses that a company has itself published are collected: /contact,
/about, /careers, and RFC 9116 security.txt. Nothing is guessed or probed here.

Usage:
    python3 scripts/discover.py domains.txt [--max-pages 6] [--delay 2]
Output:
    data/candidates.json   [{company, domain, email, source_url}]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

PATHS = ["", "/contact", "/contact-us", "/about", "/about-us",
         "/careers", "/karir", "/hubungi-kami",
         "/.well-known/security.txt", "/security.txt"]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# never keep these — they are not application inboxes
DROP_LOCAL = {
    "noreply", "no-reply", "donotreply", "postmaster", "abuse", "privacy",
    "unsubscribe", "bounce", "mailer-daemon", "webmaster", "hostmaster",
}
DROP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js",
            ".woff", ".woff2", ".ico", ".mp4", ".pdf")

UA = "Mozilla/5.0 (compatible; job-application-research/1.0)"


def fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            return ""
        ctype = resp.headers.get("Content-Type", "")
        if "text" not in ctype and "json" not in ctype:
            return ""
        return resp.read(400_000).decode("utf-8", "ignore")


def emails_from(text: str) -> set[str]:
    found = set()
    for raw in EMAIL_RE.findall(text):
        addr = raw.strip().strip(".,;:()<>[]").lower()
        local, _, domain = addr.partition("@")
        if not local or not domain:
            continue
        if local in DROP_LOCAL or domain.endswith(DROP_EXT):
            continue
        if any(domain.endswith(ext) for ext in DROP_EXT):
            continue
        if len(addr) > 254 or len(local) > 64:
            continue
        found.add(addr)
    return found


def security_txt_contacts(text: str) -> set[str]:
    """Parse Contact: lines from an RFC 9116 security.txt."""
    out = set()
    for line in text.splitlines():
        if line.lower().startswith("contact:"):
            value = line.split(":", 1)[1].strip()
            if value.lower().startswith("mailto:"):
                value = value[7:]
            if "@" in value:
                out.add(value.strip().lower())
    return out


def crawl_domain(domain: str, max_pages: int, delay: float) -> tuple[list[dict], dict]:
    """Return (hits, stats). stats records why a domain yielded nothing."""
    hits: dict[str, str] = {}
    stats = {"fetched": 0, "http_error": 0, "no_email": 0}
    base = f"https://{domain}"
    pages = 0
    for path in PATHS:
        if pages >= max_pages:
            break
        url = base + path
        try:
            text = fetch(url)
        except urllib.error.HTTPError as exc:
            stats["http_error"] += 1
            if exc.code == 404:
                continue
            continue
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        pages += 1
        time.sleep(delay)
        if not text:
            continue
        stats["fetched"] += 1
        found = security_txt_contacts(text) if path.endswith("security.txt") else set()
        found |= emails_from(text)
        # only keep addresses on the domain we are crawling
        matched = {a for a in found if a.split("@")[-1].endswith(domain)}
        if not matched:
            stats["no_email"] += 1
        for addr in matched:
            hits.setdefault(addr, url)
    return [{"domain": domain, "email": e, "source_url": u} for e, u in hits.items()], stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Collect published contact emails.")
    ap.add_argument("domains", help="file with one domain per line")
    ap.add_argument("--max-pages", type=int, default=6)
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests")
    args = ap.parse_args()

    path = Path(args.domains)
    if not path.exists():
        C.die(f"{path} not found")
    domains = [l.strip().lower() for l in path.read_text().splitlines()
               if l.strip() and not l.startswith("#")]

    blocked = C.load_suppression()
    out = []
    for i, domain in enumerate(domains, 1):
        rows, stats = crawl_domain(domain, args.max_pages, args.delay)
        rows = [r for r in rows if r["email"] not in blocked]
        out.extend(rows)
        if rows:
            C.info(f"[{i}/{len(domains)}] {domain}: {len(rows)} address(es)")
        else:
            reason = ("no page fetched" if not stats["fetched"]
                      else "pages fetched, no address published")
            C.info(f"[{i}/{len(domains)}] {domain}: 0 — {reason} "
                   f"({stats['fetched']} pages, {stats['http_error']} errors)")

    # dedupe
    seen, final = set(), []
    for r in out:
        if r["email"] in seen:
            continue
        seen.add(r["email"])
        final.append(r)
    C.save_json(C.CANDIDATES_FILE, final)
    C.info(f"\n-> {C.CANDIDATES_FILE} ({len(final)} unique published addresses)")


if __name__ == "__main__":
    main()
