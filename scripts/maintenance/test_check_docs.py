#!/usr/bin/env python3
"""
Self-test for check_docs.py — proves each check fires on known-bad input and
stays quiet on known-good input. Uses only synthetic repo-local fixtures, so it never
touches the real repo. Run: python3 scripts/maintenance/test_check_docs.py
"""
import json
import os
import shutil
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_docs as cd  # noqa: E402
import learn_sources as ls  # noqa: E402


@contextmanager
def workspace():
    path = Path(__file__).resolve().parent / (".self-test-" + uuid.uuid4().hex)
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path)


def run_checks(tmp):

    # good target page (provides an anchor id="ok")
    (tmp / "target.html").write_text(
        '<html><head><title>T</title></head><body>'
        '<h1 id="ok">Ok</h1></body></html>')

    # page with several planted defects
    (tmp / "bad.html").write_text(
        '<html><head><title></title></head><body>'          # empty <title>
        '<a href="missing.html">a</a>'                        # broken internal link
        '<a href="target.html#nope">b</a>'                   # anchor absent in target
        '<a href="#dup">c</a>'                                # same-page anchor (exists)
        '<div id="dup"></div><div id="dup"></div>'           # duplicate id
        '</body></html>')

    # page whose only "link" is JavaScript string-building (must NOT be flagged)
    (tmp / "js.html").write_text(
        '<html><head><title>J</title></head><body>'
        '<a href="' + "' + m.url + '" + '">x</a></body></html>')

    (tmp / "tables.html").write_text(
        '<html><head><title>Tables</title></head><body>'
        '<table><th scope="col"ead><tr><th>Name</th></tr></thead>'
        '<tbody><tr><td>Example</td></tbody></table></body></html>')

    pages = [tmp / "target.html", tmp / "bad.html", tmp / "js.html", tmp / "tables.html"]

    f = cd.Findings()
    cd.check_internal_links(f, pages)
    cd.check_structure(f, pages)
    msgs = [i["message"] for i in f.items]

    checks = {
        "broken internal link": any("missing.html" in m for m in msgs),
        "missing anchor": any("#nope" in m for m in msgs),
        "duplicate id": any('duplicate id="dup"' in m for m in msgs),
        "empty <title>": any("<title>" in m for m in msgs),
        "no false positive on JS href": not any("m.url" in m for m in msgs),
        "malformed thead detected": any("malformed <thead>" in m for m in msgs),
        "unbalanced table row detected": any("unbalanced <tr>" in m for m in msgs),
    }

    # secret detection — build the token at runtime so THIS file never contains it
    secret = "ghp_" + "b" * 36
    (tmp / "leak.txt").write_text("GH_TOKEN=" + secret + "\n")
    fs = cd.Findings()
    cd.check_secrets(fs, [tmp / "leak.txt"])
    checks["secret detected"] = any("GitHub PAT" in i["message"] for i in fs.items)

    # redirect detection
    checks["redirect detected"] = cd.is_redirect(
        '<meta http-equiv="refresh" content="0; url=/x">')
    checks["non-redirect ignored"] = not cd.is_redirect("<h1>hello</h1>")

    hints = tmp / "hints.html"
    stylesheet = "https://fonts.googleapis.com/css2?family=Example"
    hints.write_text(
        '<link rel="PRECONNECT dns-prefetch" href="https://fonts.googleapis.com">\n'
        '<link href="https://fonts.gstatic.com" rel="preload">\n'
        '<link rel="dns-prefetch" href="https://example.org">\n'
        '<link rel="canonical" href="https://example.org/unpublished-page">\n'
        '<link href="' + stylesheet + '" rel="stylesheet">\n'
        '<a href="https://example.org/real">real</a>\n')
    urls = cd.collect_external([hints])
    checks["resource hints and canonical metadata skipped, real links kept"] = set(urls) == {
        stylesheet, "https://example.org/real",
    }
    with patch.object(cd, "CACHE_FILE", tmp / "hints-cache.json"), \
            patch.object(ls, "fetch_url", return_value={
                "code": 404, "final_url": stylesheet,
            }):
        findings = cd.Findings()
        cd.check_external(findings, [hints])
        checks["stylesheet still checked for breakage"] = any(
            item["url"] == stylesheet and item["severity"] == cd.ERROR
            for item in findings.items)

    # Local page fixture: no network is used by any external-link test.
    fixture = tmp / "learn-page.txt"
    fixture.write_text(
        '<meta content="2026-09-30T00:00:00Z" name="ms.date">'
        '<meta name="updated_at" content="2026-10-01T10:00:00Z">'
        '<h2 id="present">Present</h2><p id=\'encoded id\'>Encoded</p>')
    raw = fixture.read_text()
    redirects = tmp / "redirects.html"
    redirects.write_text(
        '<a href="https://learn.microsoft.com/viva/old#present">moved</a>\n'
        '<a href="https://learn.microsoft.com/VIVA/STABLE/?view=o365-worldwide">'
        'stable</a>\n'
        '<a href="https://learn.microsoft.com/viva/stable#present">stable</a>\n')

    def response_for(url, **kwargs):
        target = "new" if ls.article_path(url) == "/viva/old" else "stable"
        return {
            "code": 200, "html": raw,
            "final_url": f"https://learn.microsoft.com/en-us/VIVA/{target.upper()}/"
                         "?view=o365-worldwide",
        }

    redirect_cache = tmp / "redirect-cache.json"
    with patch.object(cd, "CACHE_FILE", redirect_cache), \
            patch.object(ls, "fetch_url", side_effect=response_for) as fetch:
        findings = cd.Findings()
        cd.check_external(findings, [redirects])
        warnings = findings.by_severity(cd.WARN)
        checks["different Learn article redirects warn"] = len(warnings) == 1 \
            and warnings[0].get("issue") == "redirect"
        checks["locale, case, slash and query redirects ignored"] = not any(
            "stable" in item.get("url", "").lower() for item in warnings)
        checks["each Learn article fetched once per run"] = fetch.call_count == 2
    cached = json.loads(redirect_cache.read_text())
    checks["final URL and all three Learn dates cached"] = all(
        entry.get("final_url") and entry.get("html") == raw
        and entry.get("ms_date") == "2026-09-30T00:00:00Z"
        and entry.get("updated_at") == "2026-10-01T10:00:00Z"
        and entry.get("visible_date") == "2026-09-30"
        for entry in cached.values())

    anchors = tmp / "anchors.html"
    base = "https://learn.microsoft.com/viva/fixture"
    anchors.write_text(
        f'<a href="{base}#present">present</a>\n'
        f'<a href="{base}#missing">missing</a>\n'
        f'<a href="{base}#encoded%20id">encoded</a>\n')
    anchor_cache = tmp / "anchor-cache.json"
    anchor_cache.write_text(json.dumps({base: {
        "code": 200, "checked": time.time(),
    }}))
    with patch.object(cd, "CACHE_FILE", anchor_cache), \
            patch.object(ls, "fetch_url", return_value={
                "code": 200, "html": raw, "final_url": base,
            }) as fetch:
        findings = cd.Findings()
        cd.check_external(findings, [anchors])
        cd.check_external(cd.Findings(), [anchors])
        warnings = findings.by_severity(cd.WARN)
        checks["missing Learn anchor warns from local fixture"] = len(warnings) == 1 \
            and warnings[0].get("issue") == "anchor" \
            and warnings[0]["url"] == base + "#missing"
        checks["present and URL-encoded anchors pass"] = len(findings.items) == 1
        checks["old cache refreshed and page HTML reused within TTL"] = fetch.call_count == 1
    expired = json.loads(anchor_cache.read_text())
    expired[base]["checked"] = time.time() - cd.CACHE_TTL - 1
    anchor_cache.write_text(json.dumps(expired))
    with patch.object(cd, "CACHE_FILE", anchor_cache), \
            patch.object(ls, "fetch_url", return_value={
                "code": 200, "html": raw, "final_url": base,
            }) as fetch:
        cd.check_external(cd.Findings(), [anchors])
        checks["page HTML refreshed after the same cache TTL"] = fetch.call_count == 1

    status_page = tmp / "status.html"
    status_page.write_text(f'<a href="{base}">status</a>')
    for code in (0, 400, 403, 404, 410, 429, 451, 500):
        with patch.object(cd, "CACHE_FILE", tmp / f"status-{code}.json"), \
                patch.object(ls, "fetch_url", return_value={
                    "code": code, "html": "", "final_url": base,
                }):
            findings = cd.Findings()
            cd.check_external(findings, [status_page])
            checks[f"HTTP {code} has correct broken/unknown severity"] = (
                len(findings.by_severity(cd.ERROR)) == (1 if code in (404, 410, 451) else 0)
                and len(findings.by_severity(cd.INFO)) == (0 if code in (404, 410, 451) else 1)
            )

    with patch.object(ls.time, "sleep") as sleep, \
            patch.object(ls.subprocess, "run", return_value=Mock(
                returncode=0, stdout=raw + f"\n200\t{base}\ttext/html",
            )) as run:
        response = ls.fetch_url(base, include_html=True)
        command = run.call_args.args[0]
        checks["request has a total 30-second deadline"] = (
            command[command.index("--max-time") + 1] == "30"
            and run.call_args.kwargs["timeout"] == 32
            and response["html"] == raw
        )
        checks["requests delayed at least one second"] = all(
            call.args[0] >= 1 for call in sleep.call_args_list)

    old_org_data = "https://learn.microsoft.com/viva/organizational-data"
    moved_org_data = (
        "https://learn.microsoft.com/en-us/microsoft-365-apps/"
        "org-data-service/organizational-data"
    )

    def mocked_opener(command, **kwargs):
        final = (old_org_data.replace("/viva/", "/en-us/viva/")
                 if "--head" in command else moved_org_data)
        return Mock(returncode=0, stdout=f"\n200\t{final}\ttext/html")

    get_cache = tmp / "get-redirect-cache.json"
    with patch.object(ls.time, "sleep"), \
            patch.object(ls.subprocess, "run", side_effect=mocked_opener) as opener:
        cache = ls.PageCache(get_cache)
        response = cache.get(old_org_data)
        cache.save()
        reused = ls.PageCache(get_cache).get(old_org_data)
        checks["Learn redirects use GET even without page HTML"] = (
            "--head" not in opener.call_args.args[0]
            and opener.call_count == 1
        )
        checks["Learn GET reveals moves hidden by HEAD"] = (
            response["final_url"] == moved_org_data and "html" not in response
        )
        checks["Learn GET redirect response remains cached"] = (
            reused == response and opener.call_count == 1
        )

    with patch.object(ls.time, "sleep"), \
            patch.object(ls.subprocess, "run", return_value=Mock(
                returncode=0, stdout="\n200\thttps://example.org\ttext/html",
            )) as opener:
        ls.fetch_url("https://example.org")
        checks["non-Learn link probes retain HEAD"] = (
            "--head" in opener.call_args.args[0] and opener.call_count == 1
        )

    return checks


def test_check_docs():
    with workspace() as tmp:
        checks = run_checks(tmp)
    assert all(checks.values()), [name for name, passed in checks.items() if not passed]


def main():
    with workspace() as tmp:
        checks = run_checks(tmp)
    print("=" * 50)
    ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=" * 50)
    if ok:
        print("ALL TESTS PASSED")
        return 0
    print("TESTS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
