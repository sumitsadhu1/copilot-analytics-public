#!/usr/bin/env python3
"""
Self-test for check_docs.py — proves each check fires on known-bad input and
stays quiet on known-good input. Uses only synthetic temp files, so it never
touches the real repo. Run: python3 scripts/maintenance/test_check_docs.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_docs as cd  # noqa: E402


def main():
    tmp = Path(tempfile.mkdtemp())

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

    pages = [tmp / "target.html", tmp / "bad.html", tmp / "js.html"]

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

    print("=" * 50)
    ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        ok = ok and passed
    print("=" * 50)
    if ok:
        print("ALL TESTS PASSED")
        sys.exit(0)
    print("TESTS FAILED")
    sys.exit(1)


if __name__ == "__main__":
    main()
