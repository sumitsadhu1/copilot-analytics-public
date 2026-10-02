#!/usr/bin/env python3
"""Add metadata without rebuilding the tagged PDF object graph."""

from pathlib import Path

from maintenance.sync_dates import current_release_date


REPO = Path(__file__).resolve().parent.parent
PDF_ROOT = REPO / "artifacts" / "pdfs"


def pdf_subject():
    """Single-source the validation stamp from the hub's Current release row."""
    return ("Independent Microsoft 365 Copilot Analytics implementation guidance; "
            f"validated {current_release_date()}")


def process(path):
    import pikepdf

    temporary = path.with_suffix(".tmp.pdf")
    with pikepdf.Pdf.open(path) as pdf:
        pdf.docinfo["/Author"] = "Sumit Sadhu"
        pdf.docinfo["/Subject"] = pdf_subject()
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