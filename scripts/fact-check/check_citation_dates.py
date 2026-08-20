#!/usr/bin/env python3
"""Verify every cited Microsoft Learn publication date against the fetched snapshots.

The hub cites Learn sources as "<link text> (13 August 2026)", where the date is
Microsoft's own last-updated date for that page. Those dates rot silently: the page
is updated upstream and nothing in the repo notices.

check_facts.py detects *content* drift on watched pages. It does not check that the
dates we print next to a link still match the page. This script closes that gap.

Run after check_facts.py, which populates scripts/fact-check/snapshots/.

Exit codes: 0 = clean, 1 = stale or malformed citation dates found.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "scripts" / "fact-check" / "snapshots"
URLS = ROOT / "scripts" / "fact-check" / "ms-learn-urls.json"

# A Learn link whose anchor is followed, within a short window, by a date.
CITATION = re.compile(
    r"https://learn\.microsoft\.com/([^\"\s<>]+)\"[^>]*>.{0,160}?</a>\D{0,40}?"
    r"(\d{1,2}\s+[A-Z][a-z]+\s+20\d\d)",
    re.S,
)
LONG_FORM = "%d %B %Y"


def normalise(url: str) -> str:
    """Strip anchors, query strings, locale prefix and trailing slash."""
    url = url.split("#")[0].split("?")[0].rstrip("/")
    return url.replace("/en-us/", "/")


def load_live() -> dict[str, str]:
    """Map normalised Learn URL -> the last_updated date recorded in its snapshot."""
    if not URLS.exists():
        sys.exit(f"missing {URLS.relative_to(ROOT)} — cannot resolve watched pages")
    watched = json.loads(URLS.read_text())["watched_pages"]
    live: dict[str, str] = {}
    for entry in watched:
        snapshot = SNAPSHOTS / f"{entry['id']}.json"
        if not snapshot.exists():
            continue
        recorded = json.loads(snapshot.read_text()).get("last_updated")
        if recorded:
            live[normalise(entry["url"])] = recorded[:10]
    return live


def parse(text: str) -> datetime.date | None:
    for fmt in (LONG_FORM, "%d %b %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def main() -> int:
    live = load_live()
    if not live:
        sys.exit("no snapshots found — run check_facts.py first")

    stale: list[tuple[str, int, str, str, str]] = []
    abbreviated: list[tuple[str, int, str]] = []
    unwatched: Counter[str] = Counter()
    verified = 0

    for path in sorted(ROOT.rglob("*.html")):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        offsets = [m.start() for m in re.finditer(r"\n", text)]
        for match in CITATION.finditer(text):
            url = "https://learn.microsoft.com/" + normalise(match.group(1))
            cited = match.group(2)
            line = sum(1 for o in offsets if o < match.start()) + 1
            rel = str(path.relative_to(ROOT))

            parsed = parse(cited)
            # "May" is both the full and abbreviated month name — not a defect.
            if parsed and cited != parsed.strftime(LONG_FORM).lstrip("0"):
                abbreviated.append((rel, line, cited))

            if url not in live:
                unwatched[url] += 1
                continue
            if parsed and parsed.isoformat() == live[url]:
                verified += 1
            else:
                stale.append((rel, line, cited, live[url], url))

    print("=" * 64)
    print("CITATION DATE CHECK")
    print("=" * 64)

    for rel, line, cited, actual, url in stale:
        print(f"  STALE  {rel}:{line}")
        print(f"         cited {cited!r} — page last updated {actual}")
        print(f"         {url}")
    for rel, line, cited in abbreviated:
        print(f"  FORMAT {rel}:{line} — abbreviated month {cited!r}, use long form")

    if unwatched:
        print(f"\n  {sum(unwatched.values())} dated citation(s) on "
              f"{len(unwatched)} page(s) not in the watch list:")
        for url, count in unwatched.most_common(10):
            print(f"    x{count}  {url}")
        print("  Add them to ms-learn-urls.json so their dates are checked.")

    print(f"\nverified: {verified}   stale: {len(stale)}   "
          f"format: {len(abbreviated)}   unwatched: {sum(unwatched.values())}")

    if stale or abbreviated:
        return 1
    print("ALL CLEAR — every watched citation date matches its source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
