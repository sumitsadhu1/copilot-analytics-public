#!/usr/bin/env python3
"""Structural PDF accessibility preflight; does not claim PDF/UA conformance."""

from pathlib import Path
import sys

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


REPO = Path(__file__).resolve().parent.parent.parent
FILES = sorted((REPO / "artifacts" / "pdfs").rglob("*.pdf"))
duplicate = REPO / "artifacts" / "Copilot_Analytics_Setup_Companion_Guide.pdf"
if duplicate.exists():
    FILES.append(duplicate)


def main():
    failures = []
    for path in FILES:
        reader = PdfReader(str(path))
        root = reader.trailer["/Root"]
        metadata = reader.metadata or {}
        checks = {
            "extractable text": any((page.extract_text() or "").strip() for page in reader.pages),
            "title": bool(metadata.get("/Title")),
            "author": bool(metadata.get("/Author")),
            "language": bool(root.get("/Lang")),
            "marked content": bool(root.get("/MarkInfo")),
            "structure tree": bool(root.get("/StructTreeRoot")),
        }
        missing = [name for name, passed in checks.items() if not passed]
        if missing:
            failures.append(f"{path.relative_to(REPO)}: missing {', '.join(missing)}")
    if failures:
        print("PDF structural preflight failed:")
        print("\n".join(f"  - {item}" for item in failures))
        return 1
    print(f"PDF structural preflight passed for {len(FILES)} files.")
    print("Manual screen-reader, reading-order, table, alt-text, and reflow testing is still required for PDF/UA assurance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())