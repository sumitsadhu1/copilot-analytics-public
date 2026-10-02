"""Offline tests for visible-date evidence, date-only repairs and snapshot safety."""

import contextlib
import io
import json
import pathlib
import shutil
import sys
import unittest
import uuid
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_citation_dates as dates  # noqa: E402
import check_facts as facts  # noqa: E402
from learn_sources import extract_dates, extract_visible_date  # noqa: E402


class CitationDateTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(__file__).resolve().parent / (
            ".self-test-" + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.url = "https://learn.microsoft.com/viva/example"
        self.raw = (
            '<meta content="2026-09-30T00:00:00Z" name="ms.date">'
            '<meta name="updated_at" content="2026-10-01T12:00:00Z">'
            '<span class="badge"><span>Last updated on </span>'
            '<local-time data-article-date-source="calculated" '
            'datetime="2026-09-29T08:00:00.000Z">29 September</local-time></span>'
        )

    def test_all_three_dates_and_visible_last_updated(self):
        metadata = extract_dates(self.raw)
        self.assertEqual(metadata["ms_date"], "2026-09-30T00:00:00Z")
        self.assertEqual(metadata["updated_at"], "2026-10-01T12:00:00Z")
        self.assertEqual(metadata["visible_date"], "2026-09-29")
        self.assertEqual(facts.extract_last_updated(self.raw), metadata["visible_date"])
        with patch.object(facts, "SNAPSHOTS_DIR", self.root):
            facts.save_snapshot("page", "hash", last_updated=metadata["ms_date"],
                                **metadata)
        saved = json.loads((self.root / "page.json").read_text())
        self.assertEqual(saved["ms_date"], metadata["ms_date"])
        self.assertEqual(saved["updated_at"], metadata["updated_at"])
        self.assertEqual(saved["visible_date"], metadata["visible_date"])
        self.assertEqual(saved["last_updated"], metadata["visible_date"])

    def test_visible_badge_utc_and_absent_badge_fallbacks(self):
        offset = self.raw.replace("2026-09-29T08:00:00.000Z",
                                  "2026-09-29T23:30:00-02:00")
        self.assertEqual(extract_visible_date(offset), "2026-09-30")
        no_badge = self.raw.split('<span class="badge">')[0]
        self.assertEqual(extract_visible_date(no_badge), "2026-09-30")
        updated_only = '<meta name="updated_at" content="2026-10-01T12:00:00Z">'
        self.assertEqual(extract_visible_date(updated_only), "2026-10-01")
        unrelated = no_badge + (
            '<p>Created on <local-time data-article-date-source="calculated" '
            'datetime="2026-10-02T12:00:00Z"></local-time></p>')
        self.assertEqual(extract_visible_date(unrelated), "2026-09-30")
        invalid_badge = self.raw.replace("2026-09-29T08:00:00.000Z", "not-a-date")
        self.assertIsNone(extract_visible_date(invalid_badge))

    def test_selected_date_and_legacy_snapshot(self):
        watch = self.root / "urls.json"
        watch.write_text(json.dumps({"watched_pages": [
            {"id": "page", "url": self.url},
        ]}))
        snapshot = self.root / "page.json"
        snapshot.write_text(json.dumps({"last_updated": "2026-09-30T00:00:00Z"}))
        with patch.object(dates, "URLS", watch), \
                patch.object(dates, "SNAPSHOTS", self.root):
            self.assertEqual(dates.load_live(), {})
            self.assertEqual(dates.load_live("ms_date"), {self.url: "2026-09-30"})
            self.assertEqual(dates.load_live("updated_at"), {})
            snapshot.write_text(json.dumps({
                "last_updated": "2026-09-29",
                "ms_date": "2026-09-30", "updated_at": "2026-10-01T12:00:00Z",
                "visible_date": "2026-09-29",
            }))
            self.assertEqual(dates.load_live(), {self.url: "2026-09-29"})
            self.assertEqual(dates.load_live("ms_date"), {self.url: "2026-09-30"})
            self.assertEqual(dates.load_live("updated_at"), {self.url: "2026-10-01"})

    def test_all_comparison_classes(self):
        self.assertEqual(dates.classify("30 September 2026", "2026-09-30", "2026-10-01"),
                         "matches_ms_date")
        self.assertEqual(dates.classify("1 October 2026", "2026-09-30", "2026-10-01"),
                         "matches_updated_at")
        self.assertEqual(dates.classify("30 September 2026", "2026-09-30", "2026-09-30"),
                         "matches_both")
        self.assertEqual(dates.classify("19 August 2026", "2026-09-30", "2026-10-01"),
                         "neither")
        self.assertEqual(dates.source_date("09/30/2026"), "2026-09-30")

    def test_moved_citation_alias_uses_the_canonical_snapshot(self):
        alias = self.url + "-old"
        watch = self.root / "urls.json"
        watch.write_text(json.dumps({"watched_pages": [{
            "id": "page", "url": self.url, "url_aliases": [alias],
        }]}))
        (self.root / "page.json").write_text(json.dumps({
            "visible_date": "2026-09-29",
        }))
        with patch.object(dates, "URLS", watch), \
                patch.object(dates, "SNAPSHOTS", self.root):
            self.assertEqual(dates.load_live(), {
                self.url: "2026-09-29", alias: "2026-09-29",
            })

    def test_comparison_reports_visible_matches_separately_from_metadata(self):
        store = Mock()
        store.get.return_value = {
            "code": 200, "html": self.raw, "final_url": self.url,
            **extract_dates(self.raw),
        }
        report = self.root / "comparison.json"
        row = {
            "file": "sources.html", "line": 1, "url": self.url,
            "printed_date": "29 September 2026", "_date_start": 0, "_date_end": 17,
        }
        with patch.object(dates, "PageCache", return_value=store), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(dates.compare_live([row], report), 0)
        result = json.loads(report.read_text())[0]
        self.assertEqual(result["visible_date"], "2026-09-29")
        self.assertTrue(result["matches_visible"])
        self.assertFalse(result["matches_ms_date"])
        self.assertFalse(result["matches_updated_at"])
        self.assertEqual(result["classification"], "neither")
        self.assertNotIn("_date_start", result)
        store.save.assert_called_once()

    def test_preceding_cell_dates_are_checked_and_repaired(self):
        page = self.root / "reference.html"
        original = (
            '<table>\n'
            '  <tr>\n'
            '    <td>Example article (Last updated 10 July 2026)</td>\n'
            f'    <td><a href="{self.url}?view=example">{self.url}</a></td>\n'
            '  </tr>\n'
            '  <tr>\n'
            '    <td>Unrelated note (10 July 2026)</td>\n'
            '    <td>No link here</td>\n'
            '  </tr>\n'
            '</table>\n'
            '<!-- <tr><td>Commented (Last updated 1 July 2026)</td>'
            f'<td><a href="{self.url}">x</a></td></tr> -->\n'
        )
        page.write_text(original, encoding="utf-8")
        with patch.object(dates, "ROOT", self.root):
            rows = dates.collect_citations([page])
            self.assertEqual([(r["printed_date"], r["line"]) for r in rows],
                             [("10 July 2026", 3)])
            plans, blocked = dates.plan_fixes(rows, {self.url: "2026-08-18"}, {self.url})
            self.assertEqual(blocked, [])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 0)
        self.assertEqual(
            page.read_text(),
            original.replace("(Last updated 10 July 2026)", "(Last updated 18 August 2026)"),
        )

    def test_inline_and_table_citations_ignore_comments_and_redirects(self):
        page = self.root / "sources.html"
        page.write_text(
            f'<p><a href="{self.url}">Inline</a> (30 September 2026)</p>\n'
            f'<tr><td><a href=\'{self.url}#anchor\'>Table</a></td>'
            '<td><strong>1 October 2026</strong></td></tr>\n'
            f'<!-- <a href="{self.url}">Comment</a> (2 October 2026) -->'
        )
        redirect = self.root / "redirect.html"
        redirect.write_text(
            '<meta http-equiv="refresh" content="0;url=/">'
            f'<a href="{self.url}">Stub</a> (2 October 2026)')
        with patch.object(dates, "ROOT", self.root):
            rows = dates.collect_citations([page, redirect])
        self.assertEqual([row["printed_date"] for row in rows],
                         ["30 September 2026", "1 October 2026"])
        self.assertEqual([row["line"] for row in rows], [1, 2])

    def test_untracked_new_guides_are_included_without_staging(self):
        page = self.root / "new-guide.html"
        page.write_text(
            f'<p><a href="{self.url}">New guide</a> (30 September 2026)</p>',
            encoding="utf-8",
        )
        with patch.object(dates, "ROOT", self.root), \
                patch.object(dates.subprocess, "run", return_value=Mock(
                    stdout=b"new-guide.html\0",
                )) as run:
            rows = dates.collect_citations()
        self.assertEqual([row["file"] for row in rows], ["new-guide.html"])
        self.assertIn("--cached", run.call_args.args[0])
        self.assertIn("--others", run.call_args.args[0])
        self.assertIn("--exclude-standard", run.call_args.args[0])

    def test_fix_defaults_to_preview_and_preserves_every_other_byte(self):
        page = self.root / "sources.html"
        original = (
            '<p>Last validated 19 August 2026; unrelated note 19 August 2026.</p>\r\n'
            f'<p><a href="{self.url}#anchor">Watch</a> (19 August 2026)</p>\r\n'
            f'<tr><td><a href="{self.url}?view=example">Watch</a></td>'
            '<td>19 August 2026</td></tr>\r\n'
            '<p><a href="https://learn.microsoft.com/viva/unwatched">Other</a>'
            ' (19 August 2026)</p>\r\n'
            f'<!-- <a href="{self.url}">Comment</a> (19 August 2026) -->\r\n'
        )
        page.write_bytes(original.encode("utf-8"))
        expected = original.replace(
            '</a> (19 August 2026)</p>\r\n<tr>', '</a> (29 September 2026)</p>\r\n<tr>',
        ).replace('<td>19 August 2026</td></tr>', '<td>29 September 2026</td></tr>')
        with patch.object(dates, "ROOT", self.root):
            rows = dates.collect_citations([page])
            plans, blocked = dates.plan_fixes(rows, {self.url: "2026-09-29"}, {self.url})
            self.assertEqual(blocked, [])
            preview = io.StringIO()
            with contextlib.redirect_stdout(preview):
                self.assertEqual(dates.emit_fixes(plans, blocked), 1)
            self.assertIn("--- sources.html", preview.getvalue())
            self.assertIn("Dry run", preview.getvalue())
            self.assertEqual(page.read_bytes(), original.encode("utf-8"))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 0)
        self.assertEqual(page.read_bytes(), expected.encode("utf-8"))

    def test_fix_blocks_missing_evidence_and_concurrent_changes(self):
        page = self.root / "sources.html"
        original = f'<p><a href="{self.url}">Watch</a> (19 August 2026)</p>\n'
        page.write_text(original, encoding="utf-8")
        with patch.object(dates, "ROOT", self.root):
            rows = dates.collect_citations([page])
            plans, blocked = dates.plan_fixes(rows, {}, {self.url})
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 2)
            self.assertEqual(page.read_text(), original)
            plans, blocked = dates.plan_fixes(rows, {self.url: "2026-09-29"}, {self.url})
            changed = original + "<p>New work</p>\n"
            page.write_text(changed, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 2)
            self.assertEqual(page.read_text(), changed)

    def test_explicit_date_labels_remain_adjacent_and_other_dates_are_preserved(self):
        page = self.root / "sources.html"
        original = "\n".join(
            f'<p><a href="{self.url}">Source</a> ({label}19 August 2026; '
            'content refreshed 1 October 2026).</p>'
            for label in ("Microsoft Learn, updated ", "visible date ", "Visible ")
        )
        page.write_text(original, encoding="utf-8")
        with patch.object(dates, "ROOT", self.root):
            rows = dates.collect_citations([page])
            self.assertEqual(len(rows), 3)
            plans, blocked = dates.plan_fixes(rows, {self.url: "2026-09-29"}, {self.url})
            self.assertEqual(blocked, [])
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 0)
        self.assertEqual(
            page.read_text(), original.replace("19 August 2026", "29 September 2026"),
        )

    def test_fix_does_not_rewrite_a_date_in_unrelated_following_prose(self):
        page = self.root / "sources.html"
        original = (
            f'<p><a href="{self.url}">Watch</a> discusses an event '
            'held on 19 August 2026.</p>\n')
        page.write_text(original, encoding="utf-8")
        with patch.object(dates, "ROOT", self.root):
            unhandled = []
            rows = dates.collect_citations([page], unhandled=unhandled)
            self.assertEqual(rows, [])
            self.assertEqual(len(unhandled), 1)
            plans, blocked = dates.plan_fixes(
                unhandled, {self.url: "2026-09-29"}, {self.url},
            )
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dates.emit_fixes(plans, blocked, write=True), 2)
        self.assertEqual(page.read_text(), original)

    def test_new_baseline_does_not_write_snapshot_without_flag(self):
        watched = self.root / "urls.json"
        watched.write_text(json.dumps({
            "watched_pages": [{
                "id": "new", "url": self.url, "title": "New", "our_files": [],
            }],
            "discovery_pages": [],
        }))
        catalog = self.root / "facts.json"
        catalog.write_text(json.dumps({"facts": [], "scenarios": {}}))
        snapshots = self.root / "snapshots"
        with patch.object(facts, "URLS_FILE", watched), \
                patch.object(facts, "FACTS_FILE", catalog), \
                patch.object(facts, "SCRIPT_DIR", self.root), \
                patch.object(facts, "SNAPSHOTS_DIR", snapshots), \
                patch.object(facts, "fetch_page", return_value=(200, "Visible", self.raw)), \
                patch.object(sys, "argv", ["check_facts.py"]), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as exit:
            facts.main()
        self.assertEqual(exit.exception.code, 0)
        self.assertFalse(snapshots.exists())
        report = json.loads((self.root / "last-report.json").read_text())
        self.assertEqual(report["pages_new_baseline"][0]["saved"], False)
        self.assertEqual(report["pages_new_baseline"][0]["updated_at"],
                         "2026-10-01T12:00:00Z")
        self.assertEqual(report["pages_new_baseline"][0]["visible_date"], "2026-09-29")


if __name__ == "__main__":
    unittest.main()
