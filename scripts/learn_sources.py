"""Shared, polite Learn fetching and metadata parsing (Python 3.9+).

Evidence policy: the reader's Last updated date is the UTC calendar date of the
calculated local-time badge, not either metadata date by assumption. If that
badge is absent, fall back to ms.date, then updated_at; retain both separately.
The response cache is separate from the fact-check snapshots. Refreshing it never
acknowledges content drift or overwrites a snapshot baseline.
"""

import datetime
import json
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urlsplit, urlunsplit

CACHE_TTL = 14 * 86400
BROKEN_CODES = {404, 410, 451}
FETCH_TIMEOUT = 30
FETCH_DELAY = 1.0
CACHE_FILE = Path(__file__).resolve().parent / "maintenance" / "link-cache.json"
USER_AGENT = ("CopilotAnalyticsHub-DocHealth/1.0 "
              "(github.com/sumitsadhu1/copilot-analytics-public)")
_LOCALE = re.compile(r"^/[a-z]{2}(?:-[a-z0-9]{2,8})*/", re.IGNORECASE)


def is_learn_url(url):
    return urlsplit(url).hostname == "learn.microsoft.com"


def article_path(url):
    """Compare article paths, not locale, case, slash, query or fragment."""
    return _LOCALE.sub("/", urlsplit(url).path).rstrip("/").lower()


def normalise_learn_url(url):
    return urlunsplit(("https", "learn.microsoft.com", article_path(url), "", ""))


def utc_calendar_date(value):
    """Normalise an ISO timestamp/date or legacy ms.date to a UTC date."""
    if not value:
        return None
    value = value.strip()
    try:
        stamp = datetime.datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=datetime.timezone.utc)
        return stamp.astimezone(datetime.timezone.utc).date().isoformat()
    except ValueError:
        try:
            return datetime.datetime.strptime(value, "%m/%d/%Y").date().isoformat()
        except ValueError:
            return None


class _Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates = {"ms_date": None, "updated_at": None}
        self.ids = set()
        self.stack = []
        self.last_updated_depth = None
        self.badge_seen = False
        self.badge_datetime = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id") is not None:
            self.ids.add(attrs["id"])
        if tag == "meta":
            name = (attrs.get("name") or "").lower()
            key = {"ms.date": "ms_date", "updated_at": "updated_at"}.get(name)
            if key:
                self.dates[key] = attrs.get("content") or None
        if tag == "local-time" and self.last_updated_depth is not None \
                and attrs.get("data-article-date-source") == "calculated":
            self.badge_seen = True
            self.badge_datetime = attrs.get("datetime")
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, "badge" in (attrs.get("class") or "").split()))

    def handle_data(self, data):
        if self.stack and re.search(r"\bLast updated on\b", data, re.I):
            badges = [i + 1 for i, (_, badge) in enumerate(self.stack) if badge]
            self.last_updated_depth = badges[-1] if badges else len(self.stack)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if self.last_updated_depth is not None \
                and len(self.stack) < self.last_updated_depth:
            self.last_updated_depth = None

    def visible_date(self):
        if self.badge_seen:
            return utc_calendar_date(self.badge_datetime)
        return utc_calendar_date(self.dates["ms_date"]) \
            or utc_calendar_date(self.dates["updated_at"])


def extract_dates(html):
    parser = _Metadata()
    parser.feed(html)
    return {**parser.dates, "visible_date": parser.visible_date()}


def extract_visible_date(html):
    """UTC date of the Last updated badge; metadata fallback only if absent."""
    return extract_dates(html)["visible_date"]


def extract_ids(html):
    parser = _Metadata()
    parser.feed(html)
    return parser.ids


def fetch_url(url, include_html=False, delay=FETCH_DELAY):
    """Return status, final URL and optionally HTML; curl bounds total time.

    urllib's socket timeout is not a total deadline across redirects/body reads.
    curl's --max-time enforces the 30-second deadline without scratch files.
    Learn's HEAD responses can hide article moves, so resolve them with GET.
    """
    url = urldefrag(url)[0]
    result = {"code": 0, "final_url": url}
    if include_html:
        result["html"] = ""
    methods = ("GET",) if include_html or is_learn_url(url) else ("HEAD", "GET")
    for method in methods:
        time.sleep(max(FETCH_DELAY, delay))
        command = [
            "curl", "--silent", "--show-error", "--location",
            "--max-time", str(FETCH_TIMEOUT), "--user-agent", USER_AGENT,
            "--write-out", "\n%{http_code}\t%{url_effective}\t%{content_type}",
        ]
        if method == "HEAD":
            command.append("--head")
        command.extend(["--url", url])
        try:
            response = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=FETCH_TIMEOUT + 2,
            )
        except (OSError, subprocess.SubprocessError):
            response = None
        if response is not None and response.returncode == 0:
            body, _, metadata = response.stdout.rpartition("\n")
            fields = metadata.split("\t", 2)
            if len(fields) == 3 and fields[0].isdigit():
                code = int(fields[0])
                result.update(code=code, final_url=fields[1] or url)
                if include_html and 200 <= code < 300 \
                        and "html" in fields[2].lower():
                    result["html"] = body
                if method == "HEAD" and code in (403, 405, 429):
                    continue
                return result
        if method == "GET":
            return result
    return result


class PageCache:
    """One response per article per run, with a shared 14-day disk cache."""

    def __init__(self, path=CACHE_FILE):
        self.path = Path(path)
        self.entries = {}
        self.fetched = set()
        if self.path.exists():
            try:
                entries = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(entries, dict):
                    self.entries = entries
            except (OSError, ValueError) as exc:
                print(f"Cannot read page cache {self.path}: {exc}", file=sys.stderr)

    def get(self, url, refresh=False, include_html=False):
        key = normalise_learn_url(url) if is_learn_url(url) else urldefrag(url)[0]
        cached = self.entries.get(key)
        if key in self.fetched:
            return cached
        if not refresh and isinstance(cached, dict) \
                and cached.get("code", 0) not in BROKEN_CODES \
                and cached.get("final_url") \
                and (not include_html or "html" in cached) \
                and time.time() - cached.get("checked", 0) < CACHE_TTL:
            return cached
        response = fetch_url(url, include_html=include_html)
        response["checked"] = time.time()
        if include_html:
            response.update(extract_dates(response.get("html", "")))
        self.entries[key] = response
        self.fetched.add(key)
        return response

    def save(self):
        try:
            self.path.write_text(
                json.dumps(self.entries, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Cannot save page cache {self.path}: {exc}", file=sys.stderr)
