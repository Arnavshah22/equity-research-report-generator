#!/usr/bin/env python
"""
Command-line report generation -- the same pipeline the web UI uses.

    python generate.py "L&T Technology Services" "docs/LTTS Q2FY26.pdf"
    python generate.py "JSW Energy" data.csv -o output/jsw.pdf --offline

Useful for producing example PDFs in bulk and for debugging the extraction
step without the browser in the loop (--html writes the intermediate HTML).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.extract import UnsupportedDocument, extract_text
from app.llm import ExtractionError, backend_label, extract_report, has_api_key
from app.render import render_html, render_pdf


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate an equity research PDF.")
    ap.add_argument("company", help="Company name as it should appear on the report")
    ap.add_argument("document", type=Path, help="Source document (PDF/CSV/TXT/JSON/XLSX)")
    ap.add_argument("-o", "--out", type=Path, help="Output PDF path")
    ap.add_argument("--offline", action="store_true", help="Skip the LLM call")
    ap.add_argument("--html", type=Path, help="Also write the intermediate HTML here")
    args = ap.parse_args()

    if not args.document.is_file():
        print(f"No such file: {args.document}", file=sys.stderr)
        return 1

    if args.offline:
        print("Backend: offline (--offline)")
    elif not has_api_key():
        print(
            "warning: no LLM API key found -- falling back to offline mode "
            "(layout only, no figures). Set GEMINI_API_KEY in .env.",
            file=sys.stderr,
        )
    else:
        print(f"Backend: {backend_label()}")

    try:
        text = extract_text(args.document.name, args.document.read_bytes())
    except UnsupportedDocument as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Extracted {len(text):,} characters from {args.document.name}")

    try:
        report, used_llm = extract_report(
            args.company, text, args.document.name, offline=args.offline
        )
    except ExtractionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print("Extraction:", "live" if used_llm else "offline stub (no figures)")

    out = args.out or Path("output") / f"{args.company.replace(' ', '_')}.pdf"
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(report), encoding="utf-8")
        print(f"HTML  -> {args.html}")

    render_pdf(report, out)
    print(f"PDF   -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
