"""Offline release-stamp tests; no published HTML or PDF is modified."""

import contextlib
import io
import pathlib
import shutil
import sys
import types
import unittest
import uuid
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from maintenance import sync_dates  # noqa: E402
import postprocess_pdfs as pdfs  # noqa: E402
import update_html_metadata as metadata  # noqa: E402
import build_sitemap as sitemap  # noqa: E402


class ReleaseMetadataTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(__file__).resolve().parent / (
            ".self-test-release-" + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "scripts").mkdir()
        self.ledger = self.root / "release.txt"
        for name, value in (("ROOT", self.root), ("LEDGER_PAGE", self.ledger),
                            ("COPIES", ())):
            context = patch.object(sync_dates, name, value)
            context.start()
            self.addCleanup(context.stop)
        self.set_release("19 August 2026")

    def set_release(self, date):
        self.ledger.write_text(
            f"<td>Current release</td><td>Example release — {date}</td>\n"
            + sync_dates.build_ledger([], self.root),
            encoding="utf-8",
        )

    def test_pdf_subject_follows_the_release_row(self):
        for date in ("19 August 2026", "7 January 2031"):
            self.set_release(date)
            self.assertEqual(sync_dates.current_release_date(), date)
            self.assertEqual(
                pdfs.pdf_subject(),
                "Independent Microsoft 365 Copilot Analytics implementation guidance; "
                f"validated {date}",
            )

    def test_pdf_process_uses_the_shared_subject_without_writing_a_pdf(self):
        document = Mock()
        document.docinfo = {}
        document.Root = types.SimpleNamespace()
        manager = Mock()
        manager.__enter__ = Mock(return_value=document)
        manager.__exit__ = Mock(return_value=False)
        library = types.SimpleNamespace(Pdf=types.SimpleNamespace(
            open=Mock(return_value=manager)))
        path = Mock(spec=pathlib.Path)
        with patch.dict(sys.modules, {"pikepdf": library}), \
                contextlib.redirect_stdout(io.StringIO()):
            pdfs.process(path)
        self.assertEqual(document.docinfo["/Subject"], pdfs.pdf_subject())
        self.assertEqual(document.Root.Lang, "en-AU")
        document.save.assert_called_once_with(path.with_suffix.return_value)
        path.with_suffix.return_value.replace.assert_called_once_with(path)

    def test_missing_release_row_fails_instead_of_guessing(self):
        self.ledger.write_text("No release row", encoding="utf-8")
        with self.assertRaises(SystemExit):
            pdfs.pdf_subject()

    def test_unknown_page_description_has_no_validation_claim(self):
        updated = metadata.upsert_head(
            "<html><head><title>Example &amp; scope — Copilot Analytics</title>"
            "</head></html>", "4-reference/future-guide.html")
        self.assertIn("guidance: Example &amp; scope.", updated)
        self.assertNotIn("Last validated", updated)
        self.assertIn(metadata.SITE + "4-reference/future-guide.html", updated)

    def test_known_page_description_is_preserved(self):
        updated = metadata.upsert_head(
            "<html><head><title>Example</title></head></html>", "index.html")
        self.assertIn(metadata.DESCRIPTIONS["index.html"], updated)

    def test_metadata_writer_leaves_redirect_stubs_byte_identical(self):
        page = self.root / "redirect.html"
        original = (
            '<html><head><meta http-equiv="refresh" content="0;url=/">\r\n'
            '<meta name="description" content="Original redirect description">'
            '<link rel="canonical" href="https://example.org/original">'
            '</head></html>\r\n'
        ).encode("utf-8")
        page.write_bytes(original)
        with patch.object(metadata, "REPO", self.root), \
                patch.object(metadata, "public_pages", return_value=[page]), \
                contextlib.redirect_stdout(io.StringIO()):
            metadata.main()
        self.assertEqual(page.read_bytes(), original)

    def test_sitemap_includes_new_guides_and_uses_the_release_row(self):
        self.set_release("7 January 2031")
        directory = self.root / "3-operate"
        directory.mkdir()
        page = directory / "cowork-dashboard.html"
        page.write_text("<html><head><title>Cowork</title></head></html>")
        redirect = directory / "index.html"
        redirect.write_text('<meta http-equiv="refresh" content="0;url=/">')
        with patch.object(sitemap, "REPO", self.root), \
                patch.object(sitemap, "ROOT_PAGES", ()), \
                patch.object(sitemap, "CONTENT_DIRS", ("3-operate",)), \
                contextlib.redirect_stdout(io.StringIO()):
            sitemap.main()
        root = ET.parse(self.root / "sitemap.xml").getroot()
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        self.assertEqual(
            [node.text for node in root.findall("s:url/s:loc", namespace)],
            [sitemap.SITE + "3-operate/cowork-dashboard.html"],
        )
        self.assertEqual(
            [node.text for node in root.findall("s:url/s:lastmod", namespace)],
            ["2031-01-07"],
        )

    def test_guard_catches_labelled_and_named_dates_even_if_current(self):
        (self.root / "scripts" / "future.py").write_text(
            'subject = "Guidance; validated 19 August 2026"\n'
            'RELEASE_DATE = "2026-08-19"\n'
            'VALIDATION_DATE = "2031-01-07"\n', encoding="utf-8")
        (self.root / "scripts" / "future.sh").write_text(
            'VALIDATED_DATE="19 August 2026"\n', encoding="utf-8")
        drift = sync_dates.script_date_drift()
        self.assertEqual(len(drift), 4)
        self.assertTrue(all("hard-coded release/validation date" in item for item in drift))

    def test_guard_allows_dynamic_dates_citations_and_test_fixtures(self):
        (self.root / "scripts" / "future.py").write_text(
            'from maintenance.sync_dates import current_release_date\n'
            'subject = f"Guidance; validated {current_release_date()}"\n'
            'citation_date = "19 August 2026"\n', encoding="utf-8")
        (self.root / "scripts" / "test_fixture.py").write_text(
            'subject = "Guidance; validated 19 August 2026"\n', encoding="utf-8")
        self.assertEqual(sync_dates.script_date_drift(), [])

    def test_check_and_write_modes_block_literals_without_changing_files(self):
        generator = self.root / "scripts" / "future.py"
        generator.write_text('subject = "Validated 19 August 2026"\n', encoding="utf-8")
        originals = {p: p.read_bytes() for p in (generator, self.ledger)}
        for args in (["sync_dates.py", "--check"], ["sync_dates.py"]):
            with patch.object(sys, "argv", args), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(sync_dates.main(), 1)
            self.assertEqual({p: p.read_bytes() for p in originals}, originals)


if __name__ == "__main__":
    unittest.main()
