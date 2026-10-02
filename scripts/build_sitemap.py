#!/usr/bin/env python3
"""Generate canonical, non-redirect URLs with the shared hub release date."""

from datetime import datetime
from pathlib import Path
import re

from maintenance.sync_dates import current_release_date


REPO = Path(__file__).resolve().parent.parent
SITE = "https://sumitsadhu1.github.io/copilot-analytics-public/"
CONTENT_DIRS = (
    "1-strategy", "2-setup", "3-operate", "4-reference",
    "artifacts", "decide", "docs", "explain", "tools",
)
ROOT_PAGES = ("index.html", "browse.html")


def pages():
    result = [REPO / name for name in ROOT_PAGES if (REPO / name).exists()]
    for directory in CONTENT_DIRS:
        result.extend(sorted((REPO / directory).rglob("*.html")))
    return result


def main():
    lastmod = datetime.strptime(current_release_date(), "%d %B %Y").date().isoformat()
    urls = []
    for path in pages():
        text = path.read_text(encoding="utf-8")
        if re.search(r'http-equiv\s*=\s*["\']refresh', text, re.IGNORECASE):
            continue
        urls.append(SITE + path.relative_to(REPO).as_posix())
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        lines.extend((
            "  <url>",
            f"    <loc>{url}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            "  </url>",
        ))
    lines.append("</urlset>")
    (REPO / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Generated sitemap.xml with {len(urls)} canonical HTML URLs")


if __name__ == "__main__":
    main()
