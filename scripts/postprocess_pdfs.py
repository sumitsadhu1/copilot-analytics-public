#!/usr/bin/env python3
"""Add metadata without rebuilding the tagged PDF object graph."""

from pathlib import Path

import pikepdf


REPO = Path(__file__).resolve().parent.parent
PDF_ROOT = REPO / "artifacts" / "pdfs"


def process(path):
    temporary = path.with_suffix(".tmp.pdf")
    with pikepdf.Pdf.open(path) as pdf:
        pdf.docinfo["/Author"] = "Sumit Sadhu"
        pdf.docinfo["/Subject"] = "Independent Microsoft 365 Copilot Analytics implementation guidance; validated 16 July 2026"
        pdf.docinfo["/Keywords"] = "Microsoft 365 Copilot, Copilot Analytics, Viva Insights, implementation guidance"
        pdf.Root.Lang = "en-AU"
        pdf.save(temporary)
    temporary.replace(path)
    print(f"Post-processed {path.relative_to(REPO)}")


def main():
    for path in sorted(PDF_ROOT.rglob("*.pdf")):
        process(path)
    duplicate = REPO / "artifacts" / "Copilot_Analytics_Setup_Companion_Guide.pdf"
    if duplicate.exists():
        process(duplicate)


if __name__ == "__main__":
    main()