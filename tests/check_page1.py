"""
Guard page 1 against silent overflow.

Page 1 is a fixed-height A4 sheet with `overflow: hidden`, so a quarterly table
that runs long doesn't wrap or spill -- it just loses its last rows, and the
PDF still looks plausible. The template steps the table's density down as the
row count grows; this checks that those steps actually hold, by rendering real
PDFs and measuring where the ink stops.

    python -m tests.check_page1
"""

from __future__ import annotations

import pathlib
import tempfile

import pypdfium2 as pdfium

from app.render import render_pdf
from tests.fixture_report import build

PAGE_MM = 297.0
FOOTER_TOP_MM = PAGE_MM - 10.8  # top edge of the teal band
ROW_COUNTS = (8, 14, 18, 20, 22, 24, 28)


def lowest_ink_mm(img) -> float:
    """Lowest content row above the footer band, in mm from the page top."""
    w, h = img.size
    px = img.convert("RGB")
    limit = int(FOOTER_TOP_MM / PAGE_MM * h) - 2
    for y in range(limit, -1, -1):
        if any(sum(px.getpixel((x, y))) < 690 for x in range(40, w - 60, 3)):
            return y * PAGE_MM / h
    return 0.0


def measure(rows: int) -> float:
    report = build()
    base = list(report.quarterly.rows)
    report.quarterly.rows = [base[i % len(base)].model_copy() for i in range(rows)]

    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "page1.pdf"
        render_pdf(report, out)
        doc = pdfium.PdfDocument(out)
        try:
            img = doc[0].render(scale=2.0).to_pil()
        finally:
            doc.close()
    return lowest_ink_mm(img)


def main() -> int:
    print(f"footer band starts at {FOOTER_TOP_MM:.1f}mm\n")
    failures = 0
    seen: dict[float, int] = {}

    for n in ROW_COUNTS:
        y = measure(n)
        clipped = y >= FOOTER_TOP_MM - 0.6
        # Two different row counts bottoming out at the identical depth is the
        # signature of clipping even when the value is under the band.
        twin = seen.get(round(y, 1))
        seen[round(y, 1)] = n

        status = "ok"
        if clipped:
            status, failures = "CLIPPED", failures + 1
        elif twin is not None and y > FOOTER_TOP_MM - 8:
            status, failures = f"SUSPECT (same depth as {twin} rows)", failures + 1

        print(f"  quarterly rows={n:3}  lowest ink {y:6.1f}mm   {status}")

    if failures:
        print(f"\n{failures} row count(s) overflow page 1 -- add a density step "
              "in report.html / report.css.")
        return 1

    print("\nPage 1 holds its content at every tested row count.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
