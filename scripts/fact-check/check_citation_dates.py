#!/usr/bin/env python3
"""Verify or preview date-only repairs for watched Microsoft Learn citations.

Evidence policy (Release 5.2): printed Last updated dates use the visible badge's
calculated local-time datetime, interpreted as a UTC calendar date. Neither
ms.date nor updated_at is assumed to be the reader's date; both remain available
for comparison. When the badge is absent, visible falls back to ms.date, then
updated_at. Old author-date snapshots are not relabelled as visible evidence.

check_facts.py detects *content* drift on watched pages. It does not check that the
dates we print next to a link still match the page. This script closes that gap.

Snapshots are written only by check_facts.py --update-snapshots.
--compare-live --report PATH compares all three dates without writing snapshots
or HTML, refreshing live responses once per article.
--fix previews unified diffs only. --fix --write explicitly applies date-string
edits adjacent to watched citations with verified snapshot dates; it never
changes links, surrounding text, release metadata, line endings or snapshots.

Exit codes: 0 = clean/applied, 1 = stale dates or pending preview edits,
2 = unverified evidence or a blocked repair.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import html
import json
import pathlib
import re
import sys
import subprocess
from collections import Counter
from html.parser import HTMLParser

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from learn_sources import (  # noqa: E402
    PageCache, is_learn_url, normalise_learn_url, utc_calendar_date,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOTS = ROOT / "scripts" / "fact-check" / "snapshots"
URLS = ROOT / "scripts" / "fact-check" / "ms-learn-urls.json"

DATE_TEXT = re.compile(r"\d{1,2}\s+[A-Z][a-z]+\s+20\d\d")
LONG_FORM = "%d %B %Y"
DATE_LABEL = re.compile(
    r"(?:Microsoft\s+Learn,\s*)?"
    r"(?:(?:last\s+)?updated(?:\s+on)?|visible(?:\s+date)?)", re.I,
)


def date_prefix(text):
    return html.unescape(re.sub(r"<[^>]*>", "", text)).strip().strip("()—–-:;, ").strip()


def normalise(url: str) -> str:
    """Strip anchors, query strings, locale prefix and trailing slash."""
    return normalise_learn_url(url)


def source_date(value):
    return utc_calendar_date(value)


def load_live(date_source="visible") -> dict[str, str]:
    """Select snapshot evidence without mislabelling legacy author dates."""
    if not URLS.exists():
        sys.exit(f"missing {URLS.relative_to(ROOT)} — cannot resolve watched pages")
    watched = json.loads(URLS.read_text())["watched_pages"]
    live: dict[str, str] = {}
    for entry in watched:
        snapshot = SNAPSHOTS / f"{entry['id']}.json"
        if not snapshot.exists():
            continue
        data = json.loads(snapshot.read_text())
        key = "visible_date" if date_source == "visible" else date_source
        recorded = data.get(key)
        if not recorded and date_source == "ms_date" \
                and not any(k in data for k in ("ms_date", "updated_at", "visible_date")):
            recorded = data.get("last_updated")
        date = source_date(recorded)
        if date:
            for url in [entry["url"], *entry.get("url_aliases", [])]:
                live[normalise(url)] = date
    return live


def parse(text: str) -> datetime.date | None:
    for fmt in (LONG_FORM, "%d %b %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class CitationLinks(HTMLParser):
    """Read inline dates and source-table cells without matching scripts/comments."""

    def __init__(self, text=""):
        super().__init__()
        self.citations = []
        self.unhandled = []
        self.link = None
        self.in_anchor = False
        self.following = ""
        self.text = text
        self.line_offsets = [0] + [m.end() for m in re.finditer("\n", text)]

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.link = None
            self.following = ""
            self.in_anchor = True
            url = dict(attrs).get("href") or ""
            if is_learn_url(url):
                self.link = {"url": url, "line": self.getpos()[0]}

    def handle_endtag(self, tag):
        if tag == "a":
            self.in_anchor = False
            if self.link is not None and self.text:
                line, column = self.getpos()
                start = self.line_offsets[line - 1] + column
                end = self.text.find(">", start)
                self.link["_anchor_end"] = end + 1 if end != -1 else None
        elif tag in ("tr", "li", "p", "div", "table"):
            self.link = None

    def handle_data(self, data):
        if self.link is None or self.in_anchor:
            return
        self.following += data
        match = DATE_TEXT.search(self.following)
        if match:
            printed = " ".join(match.group().split())
            line, column = self.getpos()
            offset = self.line_offsets[line - 1] + column if self.text else 0
            end = self.text.find("<", offset)
            chunk = self.text[offset:end if end != -1 else len(self.text)]
            raw_date = DATE_TEXT.search(chunk)
            contiguous = raw_date and " ".join(raw_date.group().split()) == printed
            row = {
                **self.link, "printed_date": printed,
                "_date_start": offset + raw_date.start() if contiguous else None,
                "_date_end": offset + raw_date.end() if contiguous else None,
            }
            prefix = date_prefix(self.following[:match.start()])
            if not prefix or DATE_LABEL.fullmatch(prefix):
                self.citations.append(row)
            else:
                self.unhandled.append(row)
            self.link = None
        elif len(self.following) > 160:
            self.link = None


def tracked_html():
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(ROOT), "ls-files", "-z",
         "--cached", "--others", "--exclude-standard", "--", "*.html"],
        capture_output=True, check=True, timeout=30,
    )
    return [ROOT / name for name in result.stdout.decode().split("\0") if name]


# Reference tables that print the date in the cell *before* the link:
# <td>Article title (Last updated 1 July 2026)</td><td><a href="https://learn...">
PRECEDING_ROW = re.compile(
    r"<td>[^<]*?\((?:Last\s+updated\s+|updated\s+)?"
    r"(?P<date>\d{1,2}\s+[A-Z][a-z]+\s+20\d\d)\)[^<]*</td>\s*"
    r"<td>\s*<a\s[^>]*href=[\"'](?P<url>https://learn\.microsoft\.com/[^\"']+)[\"']",
    re.I,
)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def preceding_cell_citations(text):
    """Dates printed in the table cell immediately before a Learn link."""
    comments = [m.span() for m in COMMENT.finditer(text)]
    rows = []
    for match in PRECEDING_ROW.finditer(text):
        if any(start <= match.start() < end for start, end in comments):
            continue
        rows.append({
            "url": match.group("url"),
            "line": text.count("\n", 0, match.start("date")) + 1,
            "printed_date": " ".join(match.group("date").split()),
            "_date_start": match.start("date"),
            "_date_end": match.end("date"),
            "_preceding": True,
        })
    return rows


def collect_citations(pages=None, unhandled=None):
    citations = []
    for path in sorted(tracked_html() if pages is None else pages):
        text = path.read_bytes().decode("utf-8", errors="replace")
        if re.search(r"http-equiv\s*=\s*[\"']?\s*refresh", text, re.IGNORECASE):
            continue
        parser = CitationLinks(text)
        parser.feed(text)
        rel = str(path.relative_to(ROOT))
        citations.extend({"file": rel, **entry} for entry in parser.citations)
        citations.extend({"file": rel, **entry} for entry in preceding_cell_citations(text))
        if unhandled is not None:
            unhandled.extend({"file": rel, **entry} for entry in parser.unhandled)
    return citations


def classify(printed, ms_date, updated_at):
    parsed = parse(printed)
    cited = parsed.isoformat() if parsed else None
    matches_ms = cited is not None and cited == ms_date
    matches_updated = cited is not None and cited == updated_at
    if matches_ms and matches_updated:
        return "matches_both"
    if matches_ms:
        return "matches_ms_date"
    if matches_updated:
        return "matches_updated_at"
    return "neither"


def compare_live(citations, report_path):
    cache = PageCache()
    sources = {}
    for url in sorted({normalise(entry["url"]) for entry in citations}):
        print(f"  Fetching {url}", flush=True)
        sources[url] = cache.get(url, refresh=True, include_html=True)
    cache.save()
    rows = []
    for citation in citations:
        response = sources[normalise(citation["url"])]
        ms_date = source_date(response.get("ms_date"))
        updated_at = source_date(response.get("updated_at"))
        visible = source_date(response.get("visible_date"))
        parsed = parse(citation["printed_date"])
        printed = parsed.isoformat() if parsed else None
        verified = response["code"] == 200 and bool(response.get("html")) \
            and visible is not None
        rows.append({
            **{k: v for k, v in citation.items() if not k.startswith("_")},
            "ms_date": ms_date, "updated_at": updated_at, "visible_date": visible,
            "matches_visible": printed is not None and printed == visible,
            "matches_ms_date": printed is not None and printed == ms_date,
            "matches_updated_at": printed is not None and printed == updated_at,
            "classification": classify(citation["printed_date"], ms_date, updated_at),
            "final_url": response["final_url"], "http_status": response["code"],
            "verification": "verified" if verified else "unverified",
        })
    report_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    unverified = sum(row["verification"] == "unverified" for row in rows)
    print(f"Live comparison: {len(rows)} citations on {len(sources)} Learn pages")
    for category in ("matches_visible", "matches_ms_date", "matches_updated_at"):
        print(f"  {category}: {sum(row[category] for row in rows)}")
    print(f"  would_change_visible: {sum(row['verification'] == 'verified' and not row['matches_visible'] for row in rows)}")
    print(f"  unverified: {unverified}\nReport: {report_path}")
    return 2 if unverified else 0


def plan_fixes(citations, live, watched):
    """Plan precise, date-only replacements; block ambiguous/missing evidence."""
    files, edits, blocked = {}, {}, []
    for row in citations:
        url = normalise(row["url"])
        if url not in watched:
            continue
        location = f"{row['file']}:{row['line']}"
        actual = source_date(live.get(url))
        if actual is None:
            blocked.append(f"{location}: no selected snapshot date for {url}")
            continue
        desired = datetime.date.fromisoformat(actual).strftime(LONG_FORM).lstrip("0")
        path = ROOT / row["file"]
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            blocked.append(f"{location}: refusing a symlink/out-of-repository path")
            continue
        if path not in files:
            try:
                files[path] = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError) as exc:
                blocked.append(f"{location}: cannot preserve file bytes: {exc}")
                continue
        start, end = row.get("_date_start"), row.get("_date_end")
        anchor_end = row.get("_anchor_end")
        preceding = row.get("_preceding", False)
        if start is None or end is None or (anchor_end is None and not preceding):
            blocked.append(f"{location}: adjacent date is not a contiguous source string")
            continue
        if not preceding:
            prefix = date_prefix(files[path][anchor_end:start])
            if prefix and not DATE_LABEL.fullmatch(prefix):
                blocked.append(f"{location}: date is separated from the citation by prose")
                continue
        original = files[path][start:end]
        if " ".join(original.split()) != row["printed_date"]:
            blocked.append(f"{location}: citation changed since inspection")
            continue
        if original == desired:
            continue
        span = (start, end)
        replacements = edits.setdefault(path, {})
        if span in replacements and replacements[span] != desired:
            blocked.append(f"{location}: conflicting dates for the same source span")
        replacements[span] = desired
    plans = {}
    for path, replacements in edits.items():
        original = files[path]
        updated = original
        previous = len(original)
        for (start, end), desired in sorted(replacements.items(), reverse=True):
            if end > previous:
                blocked.append(f"{path.relative_to(ROOT)}: overlapping date spans")
            updated = updated[:start] + desired + updated[end:]
            previous = start
        plans[path] = (original, updated)
    return plans, blocked


def emit_fixes(plans, blocked, write=False):
    """Default preview; explicit writes require every planned file to be unchanged."""
    for path, (original, updated) in sorted(plans.items()):
        rel = path.relative_to(ROOT).as_posix()
        sys.stdout.write("".join(difflib.unified_diff(
            original.splitlines(keepends=True), updated.splitlines(keepends=True),
            fromfile=rel, tofile=rel, n=2)))
    for issue in blocked:
        print(f"  BLOCKED {issue}")
    if blocked:
        print("No files changed: repair needs verified, unambiguous evidence.")
        return 2
    if write:
        for path, (original, _) in plans.items():
            if path.is_symlink() or path.read_bytes() != original.encode("utf-8"):
                print(f"BLOCKED {path}: file changed since the diff; no files changed")
                return 2
        for path, (_, updated) in plans.items():
            path.write_bytes(updated.encode("utf-8"))
        print(f"Applied date-only edits to {len(plans)} file(s).")
        return 0
    print(f"Dry run: {len(plans)} file(s) would change; add --write only after review.")
    return 1 if plans else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date-source", choices=("visible", "ms_date", "updated_at"),
                    default="visible", help="snapshot date convention (default: visible)")
    ap.add_argument("--compare-live", action="store_true",
                    help="fetch live pages and compare all three dates; never write snapshots/HTML")
    ap.add_argument("--report", type=pathlib.Path,
                    help="JSON comparison output, required with --compare-live")
    ap.add_argument("--fix", action="store_true",
                    help="preview unified diffs of date-only watched-citation repairs")
    ap.add_argument("--write", action="store_true",
                    help="with --fix, explicitly apply the reviewed date-only edits")
    args = ap.parse_args()
    if args.write and not args.fix:
        ap.error("--write requires --fix")
    if args.compare_live and args.fix:
        ap.error("--compare-live and --fix cannot be combined")
    if args.report is not None and not args.compare_live:
        ap.error("--report requires --compare-live")
    unhandled = []
    citations = collect_citations(unhandled=unhandled)
    for row in unhandled:
        print(f"  UNHANDLED {row['file']}:{row['line']}: non-adjacent prose date "
              f"{row['printed_date']!r} left unchanged")
    if args.compare_live:
        if args.report is None:
            ap.error("--compare-live requires --report")
        return compare_live(citations, args.report)
    live = load_live(args.date_source)
    watched = {
        normalise(url)
        for row in json.loads(URLS.read_text())["watched_pages"]
        for url in [row["url"], *row.get("url_aliases", [])]
    }
    if args.fix:
        plans, blocked = plan_fixes(citations, live, watched)
        return emit_fixes(plans, blocked, write=args.write)
    if not live:
        print(f"no {args.date_source} snapshot dates found; use --compare-live for "
              "live evidence, or refresh snapshots when authorised", file=sys.stderr)
        return 2

    stale: list[tuple[str, int, str, str, str]] = []
    abbreviated: list[tuple[str, int, str]] = []
    unwatched: Counter[str] = Counter()
    missing_date: Counter[str] = Counter()
    verified = 0

    for citation in citations:
        url = normalise(citation["url"])
        cited = citation["printed_date"]
        line = citation["line"]
        rel = citation["file"]
        parsed = parse(cited)
        # "May" is both the full and abbreviated month name — not a defect.
        if parsed and cited != parsed.strftime(LONG_FORM).lstrip("0"):
            abbreviated.append((rel, line, cited))
        if url not in live:
            (missing_date if url in watched else unwatched)[url] += 1
            continue
        if parsed and parsed.isoformat() == live[url]:
            verified += 1
        else:
            stale.append((rel, line, cited, live[url], url))

    print("=" * 64)
    print(f"CITATION DATE CHECK ({args.date_source})")
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
    if missing_date:
        print(f"\n  {sum(missing_date.values())} watched citation(s) lack "
              f"{args.date_source} snapshot evidence; legacy author dates are "
              "not assumed to be visible dates.")

    print(f"\nverified: {verified}   stale: {len(stale)}   "
          f"format: {len(abbreviated)}   unwatched: {sum(unwatched.values())}   "
          f"missing evidence: {sum(missing_date.values())}")

    if missing_date:
        return 2
    if stale or abbreviated:
        return 1
    print("ALL CLEAR — every watched citation date matches its source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
