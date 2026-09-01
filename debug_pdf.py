"""Diagnostic: run against a real flash report PDF to see why extraction is empty
or to check whether a new report format still matches app.py's TABLES config.

Usage: python debug_pdf.py "path/to/FlashReport.pdf"
"""
import sys

import pdfplumber

from app import TABLES, extract_table, report_month_from_pdf

if len(sys.argv) != 2:
    print("Usage: python debug_pdf.py <path-to-pdf>")
    sys.exit(1)

path = sys.argv[1]
settings = {"vertical_strategy": "lines", "horizontal_strategy": "lines"}

with pdfplumber.open(path) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    print(f"Detected report_month: {report_month_from_pdf(pdf, path)}\n")

    for key, cfg in TABLES.items():
        marker_re = cfg["marker_re"]
        print(f"--- {key} (marker: {marker_re.pattern!r}) ---")

        hits = [i for i, page in enumerate(pdf.pages) if marker_re.search(page.extract_text() or "")]

        if not hits:
            print("  No page matches this title regex.")
            print("  Nearby table-of-contents lines (page 1, if present):")
            if len(pdf.pages) > 1:
                for line in (pdf.pages[1].extract_text() or "").split("\n"):
                    if "table" in line.lower() or "project list" in line.lower():
                        print(f"    {line}")
            print()
            continue

        print(f"  Marker matches pages: {hits[:5]}{' ...' if len(hits) > 5 else ''} ({len(hits)} total)")

        first = pdf.pages[hits[0]]
        raw_table = first.extract_table(settings)
        if raw_table is None:
            print(f"  page {hits[0]}: extract_table() with 'lines' strategy returned None")
        else:
            widths = sorted({len(r) for r in raw_table})
            print(f"  page {hits[0]}: extract_table() found {len(raw_table)} raw rows, "
                  f"col widths on this page: {widths}")
            for row in raw_table[:3]:
                cells = [(c or "").strip() for c in row]
                print(f"    {len(cells)} cells: {cells}")

        df = extract_table(pdf, key)
        print(f"  Parsed result: {len(df)} rows")
        print()
