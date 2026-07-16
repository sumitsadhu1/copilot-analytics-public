#!/usr/bin/env python3
"""
Documentation Health Check for the Copilot Analytics Hub.

Complements scripts/fact-check/check_facts.py (which watches *upstream* MS Learn
pages for content/fact drift). This checker validates the *internal health* of
our own repository — the things a doc-repo maintainer has to keep true on every
change but that no human reliably re-verifies by hand.

Six checks (each independently reported, with severity + file + line):

  1. links        Internal <a>/<link>/<script>/<img> targets resolve to real
                  files, and every "#anchor" points at a real id="" on the
                  destination page. Catches dead cross-links and stale anchors.
  2. pdfs         Every pdf-btn download links to a PDF the generator actually
                  produces; every generated PDF exists and is NEWER than its
                  source HTML (stale-PDF detection); generator inputs exist.
  3. index        assets/search-index.json parses, every entry points at a real
                  file + anchor, and every published doc is covered (or flagged).
  4. structure    Each page has a non-empty <title> and NO duplicate id="" values
                  (duplicate ids silently break anchor navigation).
  5. secrets      No committed file leaks a credential (GitHub PAT, user:pass@
                  URL, AWS key, Slack token). The repo bans embedded PATs.
  6. external     (--external) Outbound http(s) links still resolve. Definitive
                  404/410/451 = broken; bot-blocks/timeouts = unknown (non-fatal).
                  Results cached to avoid hammering hosts on every run.

Usage:
    python3 scripts/maintenance/check_docs.py [--external] [--strict] [--verbose]

Exit codes:
    0  clean (no ERRORs; WARN/INFO allowed unless --strict)
    1  one or more ERRORs (or any WARN when --strict)
    2  script error (bad config, unreadable files, etc.)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
PDF_DIR = REPO / "artifacts" / "pdfs"
SEARCH_INDEX = REPO / "assets" / "search-index.json"
PDF_SCRIPT = REPO / "scripts" / "generate_all_pdfs.sh"
INDEX_SCRIPT = REPO / "scripts" / "build_search_index.py"
CACHE_FILE = SCRIPT_DIR / "link-cache.json"
REPORT_FILE = SCRIPT_DIR / "last-report.json"

# Directories whose *.html are published documentation pages.
CONTENT_DIRS = ("1-strategy", "2-setup", "3-operate", "4-reference",
                "decide", "explain", "artifacts", "docs", "tools")
# Root-level published pages.
ROOT_PAGES = ("index.html", "browse.html")

TEXT_EXTS = {".html", ".css", ".js", ".py", ".sh", ".json", ".md",
             ".yml", ".yaml", ".csv", ".txt", ".jsonl"}
MAX_SCAN_BYTES = 2_000_000  # skip files larger than this for the secret scan

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


class Findings:
    def __init__(self):
        self.items = []

    def add(self, severity, check, message, file=None, line=None):
        rel = None
        if file is not None:
            try:
                rel = str(Path(file).resolve().relative_to(REPO))
            except ValueError:
                rel = str(file)
        self.items.append({
            "severity": severity, "check": check, "message": message,
            "file": rel, "line": line,
        })

    def by_severity(self, severity):
        return [i for i in self.items if i["severity"] == severity]


# ── shared helpers ────────────────────────────────────────────────────────────

def run_git(*args):
    try:
        out = subprocess.run(["git", "-C", str(REPO), *args],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def tracked_files():
    """Tracked and untracked non-ignored files (falls back to a filesystem walk)."""
    out = run_git("ls-files", "--cached", "--others", "--exclude-standard")
    if out is not None:
        return [REPO / line for line in out.splitlines() if line.strip()]
    files = []
    skip = {".git", ".venv", "node_modules", "__pycache__"}
    for root, dirs, names in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in skip]
        for n in names:
            files.append(Path(root) / n)
    return files


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def git_commit_time(path):
    """Unix time of the last commit touching *path* (None if untracked/no git)."""
    out = run_git("log", "-1", "--format=%ct", "--", str(path))
    try:
        return int(out.strip()) if out and out.strip() else None
    except ValueError:
        return None


def line_at(text, pos):
    return text.count("\n", 0, pos) + 1


def html_pages():
    """All published HTML pages on disk (works pre-commit for new pages)."""
    pages = []
    for name in ROOT_PAGES:
        p = REPO / name
        if p.exists():
            pages.append(p)
    for d in CONTENT_DIRS:
        base = REPO / d
        if base.exists():
            pages.extend(sorted(base.rglob("*.html")))
    return pages


def collect_ids(html):
    return re.findall(r'\bid\s*=\s*"([^"]+)"', html)


def is_redirect(html):
    """True if the page is a redirect stub (meta refresh or JS location change)."""
    return bool(
        re.search(r"http-equiv\s*=\s*[\"']?\s*refresh", html, re.IGNORECASE)
        or re.search(r"window\.location|location\.(href|assign|replace)",
                     html, re.IGNORECASE)
    )


# ── check 1: internal links + anchors ─────────────────────────────────────────

_ATTR_RE = re.compile(
    r'<(a|link|script|img)\b[^>]*?\b(?:href|src)\s*=\s*"([^"]*)"',
    re.IGNORECASE,
)
EXTERNAL_PREFIXES = ("http://", "https://", "//", "mailto:", "tel:",
                     "javascript:", "data:")


def check_internal_links(f, pages):
    id_cache = {}

    def ids_for(path):
        if path not in id_cache:
            try:
                id_cache[path] = set(collect_ids(read_text(path)))
            except OSError:
                id_cache[path] = set()
        return id_cache[path]

    for page in pages:
        html = read_text(page)
        own_ids = set(collect_ids(html))
        for m in _ATTR_RE.finditer(html):
            raw = m.group(2).strip()
            if not raw or raw == "#" or raw.lower().startswith(EXTERNAL_PREFIXES):
                continue
            # Skip JS/template-constructed hrefs, e.g. "' + m.url + '", "${x}", "{{y}}".
            if raw.startswith("'") or any(c in raw for c in "+{}<>"):
                continue
            line = line_at(html, m.start())
            path_part, _, anchor = raw.partition("#")
            path_part = path_part.split("?")[0]

            if path_part == "":  # same-page anchor
                if anchor and anchor not in own_ids:
                    f.add(ERROR, "links",
                          f'anchor "#{anchor}" has no matching id on this page',
                          page, line)
                continue

            target = (page.parent / path_part).resolve()
            if target.is_dir():
                idx = target / "index.html"
                if idx.exists():
                    target = idx
                else:
                    continue
            if not target.exists():
                f.add(ERROR, "links", f'link target not found: "{raw}"', page, line)
                continue
            if anchor and target.suffix.lower() == ".html":
                if anchor not in ids_for(target):
                    f.add(ERROR, "links",
                          f'anchor "#{anchor}" missing in {os.path.basename(target)} '
                          f'(link "{raw}")', page, line)


# ── check 2: PDF generation / staleness / button drift ────────────────────────

_PDF_PAIR_RE = re.compile(r'"([^"|]+\.html)\|([^"|]+\.pdf)"')
_PDF_BTN_RE = re.compile(
    r'href\s*=\s*"([^"]*?/)?([^"/]+\.pdf)"[^>]*class="pdf-btn"', re.IGNORECASE)


def parse_pdf_map():
    if not PDF_SCRIPT.exists():
        return []
    return _PDF_PAIR_RE.findall(read_text(PDF_SCRIPT))


def check_pdfs(f, pages, git_time=False):
    def freshness(p):
        if git_time:
            t = git_commit_time(p)
            if t is not None:
                return t
        return p.stat().st_mtime

    pairs = parse_pdf_map()
    produced = set()
    for src, out in pairs:
        produced.add(os.path.basename(out))
        src_path = REPO / src
        out_path = PDF_DIR / out
        if not src_path.exists():
            f.add(WARN, "pdfs", f"generator input missing on disk: {src}", PDF_SCRIPT)
            continue
        if not out_path.exists():
            f.add(WARN, "pdfs", f"PDF never generated: {out} (source {src})", src_path)
            continue
        if freshness(out_path) < freshness(src_path):
            f.add(WARN, "pdfs",
                  f"PDF is STALE — {out} older than its source HTML; regenerate",
                  src_path)

    # Every pdf-btn must point at a PDF the generator actually produces + that exists.
    for page in pages:
        html = read_text(page)
        for m in _PDF_BTN_RE.finditer(html):
            pdf_name = m.group(2)
            line = line_at(html, m.start())
            if pdf_name not in produced:
                f.add(WARN, "pdfs",
                      f'pdf-btn links "{pdf_name}" which the generator does not '
                      f"produce (config drift)", page, line)


# ── check 3: search index health + coverage ───────────────────────────────────

def indexed_files_from_script():
    if not INDEX_SCRIPT.exists():
        return set()
    src = read_text(INDEX_SCRIPT)
    return {m for m in re.findall(r'\(\s*"([^"]+\.html)"\s*,', src)}


def check_search_index(f, pages):
    if not SEARCH_INDEX.exists():
        f.add(ERROR, "index", "assets/search-index.json is missing", SEARCH_INDEX)
        return
    try:
        entries = json.loads(read_text(SEARCH_INDEX))
    except json.JSONDecodeError as e:
        f.add(ERROR, "index", f"search-index.json does not parse: {e}", SEARCH_INDEX)
        return

    id_cache = {}
    bad_files = set()
    for entry in entries:
        url = entry.get("url", "")
        path_part, _, anchor = url.partition("#")
        target = REPO / path_part
        if not target.exists():
            bad_files.add(path_part)
            continue
        if anchor:
            if target not in id_cache:
                id_cache[target] = set(collect_ids(read_text(target)))
            if anchor not in id_cache[target]:
                f.add(WARN, "index",
                      f'index entry anchor "#{anchor}" missing in {path_part}',
                      SEARCH_INDEX)
    for bf in sorted(bad_files):
        f.add(ERROR, "index", f"index references non-existent file: {bf}", SEARCH_INDEX)

    # Config drift: files listed in build_search_index.py that no longer exist.
    for rel in sorted(indexed_files_from_script()):
        if not (REPO / rel).exists():
            f.add(WARN, "index",
                  f"build_search_index.py lists missing file: {rel}", INDEX_SCRIPT)

    # Coverage: published pages absent from the index (info — some are intentional).
    indexed = {(REPO / e.get("url", "").split("#")[0]).resolve() for e in entries}
    for page in pages:
        if page.name in ("index.html", "browse.html"):
            continue  # landing/browse pages are navigational, not indexed content
        if is_redirect(read_text(page)):
            continue  # redirect stubs are not content and shouldn't be indexed
        if page.resolve() not in indexed:
            f.add(INFO, "index", "published page not in search index", page)


# ── check 4: HTML structure ───────────────────────────────────────────────────

def check_structure(f, pages):
    for page in pages:
        html = read_text(page)
        title = re.search(r"<title\b[^>]*>(.*?)</title>", html,
                          re.IGNORECASE | re.DOTALL)
        if not title or not title.group(1).strip():
            f.add(WARN, "structure", "missing or empty <title>", page)

        if not re.search(r'<html\b[^>]*\blang="[^"]+"', html, re.IGNORECASE):
            f.add(WARN, "structure", "missing html lang attribute", page)

        if not is_redirect(html):
            if not re.search(r'<meta\s+name="description"\s+content="[^"]+"', html, re.IGNORECASE):
                f.add(WARN, "structure", "missing meta description", page)
            if not re.search(r'<link\s+rel="canonical"\s+href="https://sumitsadhu1\.github\.io/copilot-analytics-public/[^"]*"', html, re.IGNORECASE):
                f.add(WARN, "structure", "missing or non-public canonical URL", page)
            for match in re.finditer(r'<th\b(?![^>]*\bscope=)[^>]*>', html, re.IGNORECASE):
                f.add(WARN, "structure", "table header missing scope attribute", page, line_at(html, match.start()))
                break

        malformed_thead = re.search(r'<th\s+scope=["\']col["\']ead\b', html, re.IGNORECASE)
        if malformed_thead:
            f.add(ERROR, "structure", 'malformed <thead> token: <th scope="col"ead>',
                  page, line_at(html, malformed_thead.start()))

        for tag in ("table", "thead", "tbody", "tr"):
            opens = len(re.findall(rf'<{tag}\b[^>]*>', html, re.IGNORECASE))
            closes = len(re.findall(rf'</{tag}\s*>', html, re.IGNORECASE))
            if opens != closes:
                f.add(ERROR, "structure",
                      f"unbalanced <{tag}> elements: {opens} opening, {closes} closing",
                      page)

        seen, dupes = set(), set()
        for i in collect_ids(html):
            (dupes if i in seen else seen).add(i)
        for d in sorted(dupes):
            f.add(ERROR, "structure",
                  f'duplicate id="{d}" (breaks anchor navigation)', page)

    repo_pages = []
    for page in pages:
        try:
            page.resolve().relative_to(REPO.resolve())
            repo_pages.append(page)
        except ValueError:
            pass

    if len(repo_pages) == len(pages):
        for required in ("404.html", "robots.txt", "sitemap.xml"):
            if not (REPO / required).exists():
                f.add(WARN, "structure", f"public web control missing: {required}", REPO / required)

        sitemap = REPO / "sitemap.xml"
        if sitemap.exists():
            try:
                root = ET.parse(sitemap).getroot()
                urls = {node.text for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
                expected = set()
                site = "https://sumitsadhu1.github.io/copilot-analytics-public/"
                for page in repo_pages:
                    if page.name == "404.html" or is_redirect(read_text(page)):
                        continue
                    expected.add(site + page.relative_to(REPO).as_posix())
                for missing in sorted(expected - urls):
                    f.add(WARN, "structure", f"canonical page missing from sitemap: {missing}", sitemap)
                for extra in sorted(urls - expected):
                    f.add(WARN, "structure", f"non-canonical or missing page in sitemap: {extra}", sitemap)
            except (ET.ParseError, OSError) as exc:
                f.add(ERROR, "structure", f"sitemap.xml does not parse: {exc}", sitemap)


# ── check 5: secret / credential leakage ──────────────────────────────────────

SECRET_PATTERNS = [
    ("GitHub PAT (classic)", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("GitHub PAT (fine-grained)", re.compile(r"github_pat_[A-Za-z0-9_]{50,}")),
    ("GitHub OAuth/refresh token", re.compile(r"gh[orsu]_[A-Za-z0-9]{36}")),
    ("credential in URL", re.compile(r"https?://[^/\s:@\"']+:[^/\s@\"']+@")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
]
# Obvious placeholders that must not trip the credential-in-URL rule.
PLACEHOLDER = re.compile(
    r"(TOKEN|PAT_HERE|PAT|YOUR[_-]?\w+|EXAMPLE|USER|PASS(WORD)?|xx+|\.\.\.|<[^>]+>)",
    re.IGNORECASE)


def check_secrets(f, files):
    for path in files:
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            text = read_text(path)
        except OSError:
            continue
        for label, pat in SECRET_PATTERNS:
            for m in pat.finditer(text):
                hit = m.group(0)
                if label == "credential in URL" and PLACEHOLDER.search(hit):
                    continue
                f.add(ERROR, "secrets",
                      f"possible {label} in committed file: {hit[:60]}",
                      path, line_at(text, m.start()))


# ── check 6: external link reachability (opt-in) ──────────────────────────────

_HREF_RE = re.compile(r'href\s*=\s*"(https?://[^"]+)"', re.IGNORECASE)
CACHE_TTL = 14 * 86400  # re-verify a previously-OK URL at most every 14 days
BROKEN_CODES = {400, 404, 410, 451}
USER_AGENT = ("CopilotAnalyticsHub-DocHealth/1.0 "
              "(github.com/sumitsadhu1/copilot-analytics-public)")


def collect_external(pages):
    urls = {}
    for page in pages:
        html = read_text(page)
        for m in _HREF_RE.finditer(html):
            url = m.group(1).split("#")[0]
            urls.setdefault(url, []).append((page, line_at(html, m.start())))
    return urls


def probe(url):
    """Return an HTTP-ish status code, or 0 for network/unknown failures."""
    for method in ("HEAD", "GET"):
        try:
            req = Request(url, method=method, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=20) as resp:
                return resp.status
        except HTTPError as e:
            if e.code in (403, 405, 429) and method == "HEAD":
                continue  # some hosts refuse HEAD — retry with GET
            return e.code
        except (URLError, OSError, ValueError):
            if method == "GET":
                return 0
    return 0


def check_external(f, pages):
    cache = {}
    if CACHE_FILE.exists():
        try:
            cache = json.loads(read_text(CACHE_FILE))
        except json.JSONDecodeError:
            cache = {}
    now = time.time()
    occurrences = collect_external(pages)
    for url in sorted(occurrences):
        cached = cache.get(url)
        if cached and cached.get("code", 0) not in BROKEN_CODES \
                and now - cached.get("checked", 0) < CACHE_TTL:
            code = cached["code"]
        else:
            code = probe(url)
            time.sleep(0.4)
            cache[url] = {"code": code, "checked": now}
        for page, line in occurrences[url]:
            if code in BROKEN_CODES:
                f.add(ERROR, "external", f"broken link (HTTP {code}): {url}", page, line)
            elif code == 0:
                f.add(INFO, "external", f"unverified (network/bot-block): {url}", page, line)
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except OSError:
        pass


# ── orchestration ─────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Copilot Analytics Hub doc-health check")
    ap.add_argument("--external", action="store_true",
                    help="also probe outbound http(s) links (network, slower)")
    ap.add_argument("--ci", action="store_true",
                    help="CI mode: use git commit times for PDF staleness "
                         "(file mtimes are unreliable after a fresh checkout)")
    ap.add_argument("--strict", action="store_true",
                    help="treat WARN as failure (exit 1)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    f = Findings()
    pages = html_pages()
    files = tracked_files()

    print("=" * 64)
    print("COPILOT ANALYTICS HUB — Documentation Health Check")
    print("=" * 64)
    print(f"Pages: {len(pages)}   Tracked files: {len(files)}\n")

    checks = [
        ("links", lambda: check_internal_links(f, pages)),
        ("pdfs", lambda: check_pdfs(f, pages, git_time=args.ci)),
        ("index", lambda: check_search_index(f, pages)),
        ("structure", lambda: check_structure(f, pages)),
        ("secrets", lambda: check_secrets(f, files)),
    ]
    if args.external:
        checks.append(("external", lambda: check_external(f, pages)))

    for name, fn in checks:
        before = len(f.items)
        try:
            fn()
        except Exception as e:  # a check crashing must not kill the run
            f.add(ERROR, name, f"check crashed: {e}")
        found = len(f.items) - before
        print(f"  {name:10s} … {found} finding(s)")
    print()

    order = {ERROR: 0, WARN: 1, INFO: 2}
    icon = {ERROR: "❌", WARN: "⚠️ ", INFO: "ℹ️ "}
    for sev in (ERROR, WARN, INFO):
        items = f.by_severity(sev)
        if not items:
            continue
        print(f"{icon[sev]}{sev} ({len(items)})")
        for i in sorted(items, key=lambda x: (x["check"], x["file"] or "")):
            loc = i["file"] or "(repo)"
            if i["line"]:
                loc += f":{i['line']}"
            print(f"   [{i['check']}] {loc} — {i['message']}")
        print()

    summary = {s: len(f.by_severity(s)) for s in (ERROR, WARN, INFO)}
    REPORT_FILE.write_text(json.dumps(
        {"summary": summary, "findings": f.items}, indent=2))

    print("-" * 64)
    print(f"ERRORS: {summary[ERROR]}   WARNINGS: {summary[WARN]}   "
          f"INFO: {summary[INFO]}")
    print(f"Report: {REPORT_FILE.relative_to(REPO)}")

    if summary[ERROR] or (args.strict and summary[WARN]):
        sys.exit(1)
    if not any(summary.values()):
        print("✅ ALL CLEAR")
    sys.exit(0)


if __name__ == "__main__":
    main()
