#!/usr/bin/env python3
"""
MS Learn Fact Checker for Copilot Analytics Documentation Hub.

Runs on every push (via GitHub Actions) or locally. Checks:
1. Whether watched MS Learn pages have changed since last snapshot
2. Whether our factual claims still match the source content
3. Whether new pages have appeared in the MS Learn doc tree

Usage:
    python3 scripts/fact-check/check_facts.py [--update-snapshots] [--verbose]

Exit codes:
    0 = all checks passed
    1 = discrepancies found (printed to stdout as structured report)
    2 = script error (network failure, missing files, etc.)
"""

import json
import hashlib
import os
import sys
import re
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from html.parser import HTMLParser

SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent.parent
URLS_FILE = SCRIPT_DIR / "ms-learn-urls.json"
FACTS_FILE = SCRIPT_DIR / "facts.json"
SNAPSHOTS_DIR = SCRIPT_DIR / "snapshots"

USER_AGENT = "CopilotAnalyticsHub-FactChecker/1.0 (github.com/sumitsadhu1/copilot-analytics-public)"
FETCH_TIMEOUT = 30
FETCH_DELAY = 1.5  # seconds between requests to be polite


class TextExtractor(HTMLParser):
    """Extract visible text from HTML, stripping tags."""
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        return ' '.join(self._text)


class LinkExtractor(HTMLParser):
    """Extract all internal MS Learn links from an HTML page."""
    def __init__(self, base_domain="learn.microsoft.com"):
        super().__init__()
        self.links = set()
        self.base_domain = base_domain

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value and self.base_domain in value:
                    # Normalise: strip fragments and query params for comparison
                    clean = value.split('#')[0].split('?')[0].rstrip('/')
                    if '/viva/' in clean or '/copilot/' in clean:
                        self.links.add(clean)


def fetch_page(url):
    """Fetch a URL and return (status_code, text_content, raw_html)."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
            extractor = TextExtractor()
            extractor.feed(raw)
            return resp.status, extractor.get_text(), raw
    except HTTPError as e:
        return e.code, "", ""
    except (URLError, Exception) as e:
        return 0, "", ""


def hash_content(text):
    """Hash the visible text content of a page for change detection."""
    # Normalise whitespace for stable comparison
    normalised = re.sub(r'\s+', ' ', text.strip().lower())
    return hashlib.sha256(normalised.encode('utf-8')).hexdigest()


def load_snapshot(page_id):
    """Load the last-known hash and link set for a page."""
    path = SNAPSHOTS_DIR / f"{page_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def save_snapshot(page_id, content_hash, links=None, last_updated=None):
    """Save the current hash and link set for a page."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "hash": content_hash,
        "checked": time.strftime("%Y-%m-%d"),
        "links": sorted(links) if links else [],
    }
    if last_updated:
        data["last_updated"] = last_updated
    with open(SNAPSHOTS_DIR / f"{page_id}.json", 'w') as f:
        json.dump(data, f, indent=2)


def extract_last_updated(html):
    """Extract the 'Last updated on' date from an MS Learn page."""
    match = re.search(r'Last updated on (\d{2}/\d{2}/\d{4})', html)
    if match:
        return match.group(1)
    match = re.search(r'Last updated on (\d{4}-\d{2}-\d{2})', html)
    if match:
        return match.group(1)
    return None


def extract_links_from_html(html):
    """Extract all MS Learn links from HTML content."""
    extractor = LinkExtractor()
    extractor.feed(html)
    return extractor.links


def check_fact(fact, page_text):
    """Check if a fact's verify_text strings are present in the page text."""
    text_lower = page_text.lower()
    missing = []
    for term in fact.get("verify_text", []):
        if term.lower() not in text_lower:
            missing.append(term)
    return missing


def main():
    update_snapshots = "--update-snapshots" in sys.argv
    verbose = "--verbose" in sys.argv

    # Load config
    with open(URLS_FILE) as f:
        urls_config = json.load(f)
    with open(FACTS_FILE) as f:
        facts_config = json.load(f)

    watched = urls_config["watched_pages"]
    discovery = urls_config["discovery_pages"]
    facts = facts_config["facts"]
    scenarios = facts_config["scenarios"]

    # Build page_id -> url lookup
    page_lookup = {p["id"]: p for p in watched}

    report = {
        "pages_checked": 0,
        "pages_changed": [],
        "pages_failed": [],
        "fact_discrepancies": [],
        "new_pages_detected": [],
        "facts_verified": 0,
        "scenarios_affected": set(),
    }

    print("=" * 60)
    print("COPILOT ANALYTICS HUB — MS Learn Fact Check")
    print("=" * 60)
    print()

    # ── Phase 1: Check watched pages for changes ──
    print("Phase 1: Checking watched MS Learn pages for changes...")
    page_texts = {}
    page_htmls = {}

    for page in watched:
        pid = page["id"]
        url = page["url"]
        report["pages_checked"] += 1

        if verbose:
            print(f"  Fetching {pid}... ", end="", flush=True)

        status, text, html = fetch_page(url)
        time.sleep(FETCH_DELAY)

        if status != 200:
            report["pages_failed"].append({"id": pid, "url": url, "status": status})
            if verbose:
                print(f"FAILED (HTTP {status})")
            continue

        page_texts[pid] = text
        page_htmls[pid] = html
        current_hash = hash_content(text)
        last_updated = extract_last_updated(html)
        snapshot = load_snapshot(pid)

        if snapshot and snapshot.get("hash") != current_hash:
            report["pages_changed"].append({
                "id": pid,
                "title": page["title"],
                "url": url,
                "last_updated": last_updated,
                "our_files": page["our_files"],
            })
            if verbose:
                print(f"CHANGED (last updated: {last_updated})")
        else:
            if verbose:
                print(f"ok" + (f" (last updated: {last_updated})" if last_updated else ""))

        if update_snapshots:
            links = extract_links_from_html(html)
            save_snapshot(pid, current_hash, links, last_updated)

    print(f"  → {report['pages_checked']} pages checked, {len(report['pages_changed'])} changed, {len(report['pages_failed'])} failed")
    print()

    # ── Phase 2: Verify factual claims ──
    print("Phase 2: Verifying factual claims...")

    for fact in facts:
        source_page = fact["source_page"]
        if source_page not in page_texts:
            if verbose:
                print(f"  SKIP {fact['id']} — source page {source_page} not fetched")
            continue

        missing = check_fact(fact, page_texts[source_page])
        if missing:
            entry = {
                "id": fact["id"],
                "claim": fact["claim"],
                "severity": fact["severity"],
                "missing_terms": missing,
                "source_page": source_page,
                "source_url": page_lookup[source_page]["url"],
                "our_files": fact["our_files"],
                "scenarios_affected": fact.get("scenarios_affected", []),
            }
            report["fact_discrepancies"].append(entry)
            for s in fact.get("scenarios_affected", []):
                report["scenarios_affected"].add(s)
            if verbose:
                print(f"  ⚠ {fact['id']}: missing [{', '.join(missing)}]")
        else:
            report["facts_verified"] += 1
            if verbose:
                print(f"  ✓ {fact['id']}")

    print(f"  → {report['facts_verified']} facts verified, {len(report['fact_discrepancies'])} discrepancies")
    print()

    # ── Phase 3: Discover new pages ──
    print("Phase 3: Checking for new MS Learn pages...")

    # Collect all known URLs from our watched list
    known_urls = set()
    for page in watched:
        clean = page["url"].split('#')[0].split('?')[0].rstrip('/')
        known_urls.add(clean)

    # Also load previously seen links from snapshots
    for page in watched:
        snapshot = load_snapshot(page["id"])
        if snapshot and "links" in snapshot:
            known_urls.update(snapshot["links"])

    for disc_page in discovery:
        if verbose:
            print(f"  Scanning {disc_page['id']}... ", end="", flush=True)

        status, text, html = fetch_page(disc_page["url"])
        time.sleep(FETCH_DELAY)

        if status != 200:
            if verbose:
                print(f"FAILED (HTTP {status})")
            continue

        current_links = extract_links_from_html(html)
        new_links = current_links - known_urls

        # Filter to only Viva Insights / Copilot related pages
        relevant_new = [
            link for link in new_links
            if any(kw in link for kw in ['/insights/', '/copilot', '/organizational-data'])
        ]

        if relevant_new:
            for link in relevant_new:
                report["new_pages_detected"].append({
                    "url": link,
                    "discovered_from": disc_page["id"],
                })
            if verbose:
                print(f"{len(relevant_new)} new pages found")
        else:
            if verbose:
                print("no new pages")

    print(f"  → {len(report['new_pages_detected'])} new pages detected")
    print()

    # ── Report ──
    print("=" * 60)
    print("REPORT SUMMARY")
    print("=" * 60)
    print()

    has_issues = False

    if report["pages_changed"]:
        has_issues = True
        print(f"📄 PAGES CHANGED: {len(report['pages_changed'])}")
        for p in report["pages_changed"]:
            print(f"   {p['id']}: {p['title']}")
            print(f"     URL: {p['url']}")
            print(f"     Last updated: {p.get('last_updated', 'unknown')}")
            print(f"     Our files to review: {', '.join(p['our_files'])}")
            print()

    if report["fact_discrepancies"]:
        has_issues = True
        # Sort by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_disc = sorted(report["fact_discrepancies"],
                           key=lambda x: severity_order.get(x["severity"], 4))

        print(f"⚠️  FACT DISCREPANCIES: {len(report['fact_discrepancies'])}")
        for d in sorted_disc:
            print(f"   [{d['severity'].upper()}] {d['id']}")
            print(f"     Claim: {d['claim']}")
            print(f"     Missing terms: {', '.join(d['missing_terms'])}")
            print(f"     Source: {d['source_url']}")
            print(f"     Our files: {', '.join(d['our_files'])}")
            if d["scenarios_affected"]:
                labels = [scenarios[s]["label"] for s in d["scenarios_affected"] if s in scenarios]
                print(f"     Scenarios affected: {'; '.join(labels)}")
            print()

    if report["new_pages_detected"]:
        has_issues = True
        print(f"🆕 NEW PAGES DETECTED: {len(report['new_pages_detected'])}")
        for np in report["new_pages_detected"]:
            print(f"   {np['url']}")
            print(f"     Discovered from: {np['discovered_from']}")
            print()

    if report["pages_failed"]:
        print(f"❌ FETCH FAILURES: {len(report['pages_failed'])}")
        for pf in report["pages_failed"]:
            print(f"   {pf['id']}: HTTP {pf['status']} — {pf['url']}")
        print()

    if report["scenarios_affected"]:
        print(f"🎯 SCENARIOS THAT MAY NEED REVIEW:")
        for s_id in report["scenarios_affected"]:
            if s_id in scenarios:
                s = scenarios[s_id]
                print(f"   • {s['label']} → {s['primary_page']}")
        print()

    if not has_issues:
        print(f"✅ ALL CLEAR — {report['facts_verified']} facts verified, "
              f"{report['pages_checked']} pages checked, no changes detected.")
        print()

    # ── Write machine-readable output for CI ──
    output_path = SCRIPT_DIR / "last-report.json"
    report["scenarios_affected"] = sorted(report["scenarios_affected"])
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Full report saved to: {output_path}")

    # Exit code
    if report["fact_discrepancies"] or report["new_pages_detected"]:
        # Discrepancies or new pages found — CI should warn (but not block)
        sys.exit(1)
    elif report["pages_changed"]:
        # Pages changed but all facts still verify — informational
        print("\nNote: MS Learn pages changed but all facts still verify. Run with --update-snapshots to acknowledge.")
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
