#!/usr/bin/env python3
"""Report how closely each page follows the hub's voice rules (CONTRIBUTING.md).

The hub explains how to operate Microsoft products; it shouldn't retell
Microsoft Learn. This report-only check measures the symptoms of a page that
narrates its sources instead of guiding the reader:

  narration   sentences that carry a fact with "Microsoft states/says…" or
              "The article says…"
  quotes      verbatim quotations in the visible text (per 1,000 words)
  sentence    average sentence length in words
  conflicts   mentions of Microsoft sources disagreeing (informational; consolidate
              these in one "Known Gaps and Conflicts" section)

Usage:
    python3 scripts/maintenance/check_voice.py [page.html ...] [--strict]

With no paths, every published HTML page is checked (redirect stubs skipped).
Exit codes: 0 report produced; 1 with --strict when any page needs review.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

NARRATION = re.compile(
    r"\bMicrosoft(?:’s|'s)?\s+(?:states|says|said|notes|cautions)\b"
    r"|\b[Tt]he (?:article|page|FAQ|doc(?:ument)?) (?:says|states)\b"
)
QUOTE = re.compile(r"“[^”]{3,}”|\"[^\"]{3,}\"")
CONFLICT = re.compile(
    r"(?i)(?:articles|sources|documentation) (?:disagree|differ|(?:is|are) inconsistent)"
)

# Advisory limits from CONTRIBUTING.md "Voice and evidence".
MAX_NARRATION = 0
MAX_QUOTES_PER_1K = 3.0
MAX_AVG_SENTENCE = 22.0


def visible_text(source: str) -> str:
    source = re.sub(r"<(script|style|pre|code)\b.*?</\1>", " ", source, flags=re.S | re.I)
    source = re.sub(r"<!--.*?-->", " ", source, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", source))
    return re.sub(r"\s+", " ", text).strip()


def measure(text: str) -> dict:
    words = len(text.split()) or 1
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text) if len(s.split()) > 3]
    avg = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0.0
    result = {
        "words": words,
        "narration": len(NARRATION.findall(text)),
        "quotes": len(QUOTE.findall(text)),
        "conflicts": len(CONFLICT.findall(text)),
        "avg_sentence": round(avg, 1),
    }
    result["quotes_per_1k"] = round(result["quotes"] * 1000 / words, 1)
    reasons = []
    if result["narration"] > MAX_NARRATION:
        reasons.append("narration")
    if result["quotes_per_1k"] > MAX_QUOTES_PER_1K:
        reasons.append("quotes")
    if result["avg_sentence"] > MAX_AVG_SENTENCE:
        reasons.append("long sentences")
    result["review"] = reasons
    return result


def default_pages() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "*.html"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    pages = []
    for name in out:
        path = ROOT / name
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"http-equiv\s*=\s*[\"']?refresh", text, re.I):
            continue
        pages.append(path)
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pages", nargs="*", help="HTML pages to check (default: all)")
    parser.add_argument("--strict", action="store_true", help="exit 1 if any page needs review")
    args = parser.parse_args()

    pages = [Path(p).resolve() for p in args.pages] or default_pages()
    rows = []
    for path in pages:
        result = measure(visible_text(path.read_text(encoding="utf-8", errors="replace")))
        try:
            name = path.relative_to(ROOT).as_posix()
        except ValueError:
            name = str(path)
        rows.append((name, result))
    rows.sort(key=lambda r: (-len(r[1]["review"]), -r[1]["narration"], -r[1]["quotes_per_1k"]))

    print(f"{'page':58} {'words':>6} {'narr':>5} {'quotes/1k':>9} {'avg sent':>8} {'conflicts':>9}  review")
    for name, r in rows:
        print(f"{name[:58]:58} {r['words']:>6} {r['narration']:>5} {r['quotes_per_1k']:>9} "
              f"{r['avg_sentence']:>8} {r['conflicts']:>9}  {', '.join(r['review']) or '-'}")
    flagged = sum(1 for _, r in rows if r["review"])
    print(f"\n{flagged} of {len(rows)} page(s) need a voice review "
          f"(limits: narration {MAX_NARRATION}, quotes/1k {MAX_QUOTES_PER_1K}, "
          f"avg sentence {MAX_AVG_SENTENCE}).")
    return 1 if args.strict and flagged else 0


if __name__ == "__main__":
    sys.exit(main())
