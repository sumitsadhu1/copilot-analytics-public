#!/usr/bin/env python3
"""Single-source the hub release date and generate the per-guide update ledger.

Two kinds of date live in this repo and they are deliberately different:

  * The **hub release date** — one entry, in `Current release` in change-history.html.
    Everything else that shows a hub-wide date (the provenance popover, page footers)
    is a copy and is rewritten from that entry.

  * Each **guide's own Last validated date** — recorded in that guide's
    document-property table, and nowhere else. The Guide Update Ledger in
    change-history.html is generated from those rows.

Copies drift silently: shell.js sat five weeks stale because a release bump only
rewrote HTML. This script is the writer, and --check is the guard.
Generators reuse current_release_date(); literal release/validation stamps in
Python and shell scripts are reported, not automatically rewritten.

Usage:
    sync_dates.py            rewrite copies and regenerate the ledger
    sync_dates.py --check    report drift and exit 1, changing nothing
"""

from __future__ import annotations

import html
import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PAGE = ROOT / "4-reference" / "change-history.html"
START, END = "<!-- LEDGER:START -->", "<!-- LEDGER:END -->"

# The one authoritative release entry.
RELEASE_ROW = re.compile(
    r"<td>Current release</td><td>.*?(\d{1,2}\s+[A-Z][a-z]+\s+20\d\d)</td>", re.S
)
VALIDATED_ROW = re.compile(
    r"<td>Last validated</td>\s*<td>(\d{1,2}\s+[A-Z][a-z]+\s+20\d\d)</td>"
)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)

# Every place that repeats the hub-wide release date.
COPIES = (
    (Path("assets/shell.js"), re.compile(r"(var VALIDATED = ')([^']+)(')")),
    (Path("index.html"), re.compile(r"(Last validated )(\d{1,2} [A-Z][a-z]+ 20\d\d)()")),
    (Path("browse.html"), re.compile(r"(Last validated )(\d{1,2} [A-Z][a-z]+ 20\d\d)()")),
)


def release_date(text: str) -> str:
    match = RELEASE_ROW.search(text)
    if not match:
        sys.exit("could not find the 'Current release' row in change-history.html")
    return match.group(1)


def current_release_date() -> str:
    """Read the canonical Current release row using the shared parser."""
    return release_date(LEDGER_PAGE.read_text(encoding="utf-8"))


DATE_LITERAL = r"(?:\d{1,2}\s+[A-Z][a-z]+\s+20\d\d|20\d\d-\d{2}-\d{2})"
LABELLED_DATE = re.compile(
    r"\b(?:last\s+validated|validated|(?:current|hub)\s+release|release\s+date)"
    r"\s*[:=]?\s*(?:on\s+)?(" + DATE_LITERAL + r")", re.I,
)
DATE_ONLY = re.compile(DATE_LITERAL, re.I)
DATE_VARIABLE = re.compile(r"release|validated|validation", re.I)
SHELL_DATE = re.compile(
    r"^\s*(\w*(?:release|validated|validation)\w*)\s*=\s*[\"'](" + DATE_LITERAL + r")[\"']",
    re.I | re.M,
)


def script_date_drift() -> list[str]:
    """Flag literal publication-date copies, not factual dates/test fixtures."""
    drift = []
    for path in sorted((ROOT / "scripts").rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.suffix not in (".py", ".sh") \
                or path.name.startswith("test_") \
                or any(part.startswith(".self-test-") for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        hits = set()
        if path.suffix == ".py":
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError as exc:
                drift.append(
                    f"{relative.as_posix()}:{exc.lineno}: "
                    f"cannot inspect script dates: {exc.msg}")
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    hits.update((node.lineno, m.group(1))
                                for m in LABELLED_DATE.finditer(node.value))
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    value = node.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str) \
                            and DATE_ONLY.fullmatch(value.value) \
                            and any(isinstance(t, ast.Name) and DATE_VARIABLE.search(t.id)
                                    for t in targets):
                        hits.add((value.lineno, value.value))
        else:
            for pattern, group in ((LABELLED_DATE, 1), (SHELL_DATE, 2)):
                hits.update((text.count("\n", 0, m.start()) + 1, m.group(group))
                            for m in pattern.finditer(text))
        for line, value in sorted(hits):
            drift.append(
                f"{relative.as_posix()}:{line}: hard-coded release/validation "
                f"date {value!r}; use current_release_date() or omit the date")
    return drift


def guides() -> list[tuple[str, str, str]]:
    """(relative path, page title, last-validated date) for every guide carrying one."""
    found = []
    for path in sorted(ROOT.rglob("*.html")):
        if ".git" in path.parts or path == LEDGER_PAGE:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        stamp = VALIDATED_ROW.search(text)
        if not stamp:
            continue
        title = TITLE.search(text)
        name = html.unescape(title.group(1)).split("—")[0].strip() if title else path.stem
        found.append((str(path.relative_to(ROOT)), name, stamp.group(1)))
    return found


SECTIONS = {
    "1-strategy": "Strategy",
    "2-setup": "Setup",
    "3-operate": "Operate",
    "4-reference": "Reference",
    "artifacts": "Artifacts",
    "explain": "Explain",
    "tools": "Tools",
    "decide": "Decide",
    "docs": "Playbooks",
}


def build_ledger(rows: list[tuple[str, str, str]], base: Path) -> str:
    lines = [
        START,
        "<table>",
        '  <tr><th scope="col">Guide</th><th scope="col">Section</th>'
        '<th scope="col">Last validated</th></tr>',
    ]
    for rel, name, date in rows:
        top = rel.split("/")[0] if "/" in rel else "root"
        section = SECTIONS.get(top, top)
        href = os.path.relpath(ROOT / rel, base)
        lines.append(
            f'  <tr><td><a href="{href}">{html.escape(name)}</a></td>'
            f"<td>{html.escape(section)}</td><td>{date}</td></tr>"
        )
    lines += ["</table>", END]
    return "\n".join(lines)


def analyse() -> tuple[str, int, list[str], list[tuple[Path, str]]]:
    """Return (release date, guide count, drift messages, pending writes).

    Pure inspection — writes nothing, so check_docs.py can reuse it.
    """
    ledger_text = LEDGER_PAGE.read_text(encoding="utf-8")
    release = release_date(ledger_text)
    rows = guides()

    drift: list[str] = []
    writes: list[tuple[Path, str]] = []

    # 1) Every copy of the hub-wide release date must match the single entry.
    for rel, pattern in COPIES:
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")
        stale = [m.group(2) for m in pattern.finditer(text) if m.group(2) != release]
        if stale:
            drift += [f"{rel}: shows {v!r}, release entry is {release!r}" for v in set(stale)]
            updated = pattern.sub(lambda m: m.group(1) + release + m.group(3), text)
            writes.append((path, updated))

    # 2) The ledger must match the guides it is generated from.
    if START not in ledger_text or END not in ledger_text:
        sys.exit("ledger markers not found in change-history.html")
    current = ledger_text.split(START)[1].split(END)[0]
    fresh = build_ledger(rows, LEDGER_PAGE.parent)
    if START + current + END != fresh:
        drift.append(f"guide ledger in change-history.html is out of date ({len(rows)} guides)")
        writes.append(
            (LEDGER_PAGE, re.sub(re.escape(START) + r".*?" + re.escape(END),
                                 lambda _: fresh, ledger_text, flags=re.S))
        )

    # Code copies must be removed/single-sourced, not rewritten to another literal.
    drift.extend(script_date_drift())

    return release, len(rows), drift, writes


def main() -> int:
    check = "--check" in sys.argv
    release, count, drift, writes = analyse()

    print(f"release date (single entry): {release}")
    print(f"guides carrying a Last validated date: {count}")

    if not drift:
        print("\nALL CLEAR — every copy matches the release entry and the ledger is current.")
        return 0

    for item in drift:
        print(f"  DRIFT  {item}")

    script_drift = any(item.startswith("scripts/") for item in drift)
    if check or script_drift:
        if script_drift:
            print("\nRemove or single-source the flagged script dates; no files changed.")
        else:
            print(f"\n{len(drift)} item(s) out of sync. Run sync_dates.py to fix.")
        return 1

    for path, text in writes:
        path.write_text(text, encoding="utf-8")
        print(f"  wrote  {path.relative_to(ROOT)}")
    print(f"\nsynced {len(writes)} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
