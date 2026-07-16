#!/usr/bin/env python3
"""Apply canonical URLs, descriptions, and table-header semantics to public HTML."""

from html import escape, unescape
from pathlib import Path
import re


REPO = Path(__file__).resolve().parent.parent
SITE = "https://sumitsadhu1.github.io/copilot-analytics-public/"
CONTENT_DIRS = (
    "1-strategy", "2-setup", "3-operate", "4-reference",
    "artifacts", "decide", "docs", "explain", "tools",
)
ROOT_PAGES = ("index.html", "browse.html", "404.html")
REDIRECTS = {
    "1-strategy/index.html": "index.html",
    "1-strategy/multi-agency-decision.html": "decide/architecture.html",
    "2-setup/index.html": "index.html",
    "3-operate/index.html": "index.html",
    "4-reference/index.html": "index.html",
    "docs/core/Copilot_Analytics_Implementation_Guide.html": "index.html",
    "docs/core/Copilot_Analytics_Setup_Companion_Guide.html": "2-setup/admin-setup.html",
    "docs/playbooks/Advanced_Viva_Insights_Collaboration_Guide.html": "3-operate/collaboration-analysis.html",
    "docs/playbooks/Copilot_Lifecycle_Billing_Playbook.html": "3-operate/billing-operations.html",
    "artifacts/Copilot_Analytics_FAQ.html": "4-reference/faq.html",
}
DESCRIPTIONS = {
    "index.html": "Independent, role-based implementation guidance for Microsoft 365 Copilot Analytics, Viva Insights reporting, privacy, and operations.",
    "browse.html": "Browse Microsoft 365 Copilot Analytics guides by role, task, and reporting capability.",
    "3-operate/consumption-dashboard.html": "Operate the Consumption Dashboard for Copilot Credits, covered services, usage concentration, and spending-policy limits.",
    "tools/index.html": "Choose Copilot Analytics reporting paths and open organizational-data and Entra hierarchy utilities.",
    "4-reference/change-history.html": "Change history, evidence snapshot, ownership, and review cadence for the Copilot Analytics documentation hub.",
    "404.html": "The requested Copilot Analytics documentation page could not be found.",
}


def public_pages():
    pages = [REPO / page for page in ROOT_PAGES if (REPO / page).exists()]
    for directory in CONTENT_DIRS:
        pages.extend(sorted((REPO / directory).rglob("*.html")))
    return pages


def plain_title(text):
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if not match:
        return "Copilot Analytics documentation"
    title = unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    title = re.sub(r"\s+[—|-]\s+Copilot Analytics.*$", "", title, flags=re.I)
    return title or "Copilot Analytics documentation"


def upsert_head(text, relative):
    text = re.sub(r"\n?<meta\s+name=[\"']description[\"'][^>]*>", "", text, flags=re.I)
    text = re.sub(r"\n?<link\s+rel=[\"']canonical[\"'][^>]*>", "", text, flags=re.I)
    text = re.sub(r"\n?<meta\s+name=[\"']viewport[\"'][^>]*>", "", text, flags=re.I)
    canonical_relative = REDIRECTS.get(relative, relative)
    canonical = SITE + canonical_relative
    description = DESCRIPTIONS.get(
        relative,
        f"Independent Microsoft 365 Copilot Analytics guidance: {plain_title(text)}. Last validated 16 July 2026.",
    )
    additions = (
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f'<meta name="description" content="{escape(description, quote=True)}">\n'
        f'<link rel="canonical" href="{canonical}">'
    )
    head = re.search(r"<head\b[^>]*>", text, re.I)
    head_end = re.search(r"</head>", text, re.I)
    charset = re.search(r"<meta\s+charset=[\"'][^\"']+[\"'][^>]*>", text, re.I)
    if charset and head and head_end and head.end() <= charset.start() < head_end.start():
        updated = text[:charset.end()] + "\n" + additions + text[charset.end():]
    elif head:
        updated = text[:head.end()] + "\n" + additions + text[head.end():]
    else:
        updated = text
    return re.sub(r'\n[ \t]+\n', '\n\n', updated)


def add_table_scopes(text):
    return re.sub(r"<th\b(?![^>]*\bscope=)([^>]*)>", r'<th scope="col"\1>', text, flags=re.I)


def main():
    for path in public_pages():
        relative = path.relative_to(REPO).as_posix()
        original = path.read_text(encoding="utf-8")
        updated = add_table_scopes(upsert_head(original, relative))
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            print(f"Updated {relative}")


if __name__ == "__main__":
    main()