"""
Turn extracted document text into a filled `ReportModel`.

One model call with structured outputs does the whole extraction: the schema
in schema.py is handed to the model as the output format, so the response is
already a valid ReportModel and there is no JSON repair or field mapping here.

Which vendor serves that call is a deployment detail -- see providers.py. This
module owns the prompt and the fallback, not the transport.

Without any API key the module falls back to a deterministic stub so the app
stays runnable and demoable offline -- see `_offline_report`.
"""

from __future__ import annotations

import re

from dotenv import load_dotenv

from .providers import Backend, ExtractionError, complete, resolve
from .schema import (
    BALANCE_SHEET_ROWS,
    CASHFLOW_ROWS,
    COMPANY_DATA_FIELDS,
    ESTIMATES_SUMMARY_ROWS,
    PRICE_PERFORMANCE_ROWS,
    PROFIT_LOSS_ROWS,
    RATIO_ROWS,
    SHAREHOLDING_ROWS,
    Header,
    LabelValue,
    Narrative,
    ReportModel,
)

load_dotenv()

__all__ = ["ExtractionError", "extract_report", "has_api_key", "backend_label"]


def _rows(names) -> str:
    """Render a canonical row list for the prompt."""
    out = []
    for n in names:
        out.append(n[0] if isinstance(n, tuple) else n)
    return ", ".join(out)


SYSTEM_PROMPT = f"""\
You are an equity research analyst at a retail brokerage. You read a company's \
filings, press releases and investor presentations, and you produce the \
structured content for a four-page "Result Update" research note.

Fill every field of the report schema you can support from the source document. \
The house format expects these canonical rows -- use these exact labels so the \
report is comparable across companies:

- Company Data: {_rows(COMPANY_DATA_FIELDS)}
- Shareholding: {_rows(SHAREHOLDING_ROWS)}
- Price Performance: {_rows(PRICE_PERFORMANCE_ROWS)}
- Y.E March summary: {_rows(ESTIMATES_SUMMARY_ROWS)}
- Profit & Loss: {_rows(PROFIT_LOSS_ROWS)}
- Balance Sheet: {_rows(BALANCE_SHEET_ROWS)}
- Cashflow: {_rows(CASHFLOW_ROWS)}
- Ratios: {_rows(RATIO_ROWS)}

Rules:

1. NEVER invent a number. If the source does not support a figure, leave that
   cell null. A blank cell is correct; a plausible-looking guess is not. The
   renderer prints null cells as a dash, which is the expected house style for
   undisclosed data.
2. Numbers are strings, formatted for print: thousands separators ("20,243"),
   one decimal for percentages and ratios ("70.4", "3.6"), a leading minus for
   negatives ("-199"). Do not include units in cells -- units belong in the
   column or row label.
3. Derive what is genuinely derivable (growth %, margin %, per-share figures)
   from figures in the document, and say so nowhere -- just compute it. Do not
   derive a forward estimate that the document does not state.
4. `rows[].values` must line up positionally with the table's `columns`. Emit
   one value per column, using null for gaps, so rows never shift.
5. Mark subtotal and total rows (Sales, EBITDA, PBT, Adj. PAT, Total Assets,
   Total Liabilities, C.F. Operation, ...) with bold=true, and growth/margin/
   percentage rows with italic=true, matching the sample's typography.
6. Charts: emit up to four combo charts covering the metrics the document
   actually reports over time -- typically revenue, EBITDA, PAT, plus one
   business-specific metric. bar_values are absolute amounts; line_values are
   the matching growth or margin percentages. Only include quarters the
   document reports; equal-length categories/bar_values/line_values.
7. Narrative: `headline` is a punchy one-line thesis. `company_blurb` is 2-3
   sentences on what the company does. `result_bullets` are 4-6 quarter
   highlights, each with a concrete number. `outlook_valuation` is one
   paragraph on outlook and the rating rationale. `key_highlights` are 4-6
   longer analytical points for page 2.
8. If the document does not state a rating, target price or CMP, leave them
   null rather than inventing a recommendation.
9. `quarterly` is the centrepiece of page 1 and is REQUIRED whenever the
   document reports a quarter's results -- build it from the P&L down to EPS,
   with one column per reported quarter plus QoQ and YoY change columns. Fill
   `profit_loss`, `balance_sheet`, `cashflow` and `ratios` too wherever the
   document gives you the lines, even if only one or two periods are covered.
   Omitting a table entirely is only correct when the document says nothing
   about it; a table with some null cells is always better than no table.

Write in the clipped, factual register of a sell-side note: "Revenue grew
15.8% YoY to Rs. 2,980cr", not "The company had a good quarter".
"""


def _backend() -> Backend | None:
    """Resolved lazily so a .env edit takes effect without a restart."""
    try:
        return resolve()
    except ExtractionError:
        # A misconfigured provider shouldn't break /api/health; the error is
        # raised properly when a generation is actually attempted.
        return None


def has_api_key() -> bool:
    """Whether a live extraction is possible in this environment."""
    return _backend() is not None


def backend_label() -> str:
    """Human-readable backend name, for the UI banner and CLI output."""
    backend = _backend()
    return str(backend) if backend else "offline (no API key)"


# Models reach for markdown emphasis even when told to write plain prose, and
# the template escapes its input, so `**Asset quality:**` reaches the page with
# the asterisks intact. Strip the markers rather than rendering markdown --
# the note's typography is the stylesheet's job, not the model's.
_MD_EMPHASIS = re.compile(r"\*{1,3}(?=\S)(.+?)(?<=\S)\*{1,3}", re.DOTALL)
_MD_LEFTOVER = re.compile(r"^\s*[*_#>\-]+\s*|\s*\*+\s*$")


def _clean(value: str | None) -> str | None:
    if not value:
        return value
    return _MD_LEFTOVER.sub("", _MD_EMPHASIS.sub(r"\1", value)).strip()


def _fill_canonical_blocks(report: ReportModel) -> None:
    """
    Normalise what the model returned into what the template expects.

    Two fixes, both about the report reading as a finished document rather
    than as raw model output.
    """
    # A press release rarely carries market data, and a model that returns
    # nothing for those blocks leaves the page 1 rail as blank paper -- which
    # reads as a broken template rather than as absent data. Emitting the
    # canonical labels with dashes says "we looked, the document didn't have
    # it", which is the house convention everywhere else in the report.
    if not report.company_data:
        report.company_data = [LabelValue(label=f) for f in COMPANY_DATA_FIELDS]

    n = report.narrative
    n.headline = _clean(n.headline)
    n.company_blurb = _clean(n.company_blurb)
    n.outlook_valuation = _clean(n.outlook_valuation)
    n.result_bullets = [c for b in n.result_bullets if (c := _clean(b))]
    n.key_highlights = [c for h in n.key_highlights if (c := _clean(h))]


def extract_report(
    company_name: str,
    document_text: str,
    source_name: str,
    *,
    offline: bool = False,
) -> tuple[ReportModel, bool]:
    """
    Build a ReportModel from document text.

    Returns (report, used_llm). `used_llm` is False when the offline stub was
    used, so the UI can label the output honestly rather than passing a
    placeholder off as an extraction.
    """
    backend = None if offline else resolve()
    if backend is None:
        return _offline_report(company_name, document_text, source_name), False

    user_prompt = (
        f"Company: {company_name}\n"
        f"Source document: {source_name}\n\n"
        "Produce the research note content for this company from the document "
        "below.\n\n"
        "<document>\n"
        f"{document_text}\n"
        "</document>"
    )

    report = complete(backend, SYSTEM_PROMPT, user_prompt)
    _fill_canonical_blocks(report)

    # The caller's inputs win over anything the model inferred for them.
    report.header.company_name = report.header.company_name or company_name
    report.source_note = f"Generated from {source_name}"
    return report, True


# --------------------------------------------------------------------------
# offline fallback
# --------------------------------------------------------------------------


def _offline_report(company_name: str, text: str, source_name: str) -> ReportModel:
    """
    A structurally complete report with no extracted figures.

    This is not a simulation of the model -- it deliberately leaves financial
    cells blank so nobody mistakes stub output for real extraction. It exists
    so the template, charts and PDF pipeline can be exercised end to end
    without an API key.
    """
    snippet = re.sub(r"\s+", " ", text).strip()[:400]

    return ReportModel(
        header=Header(
            company_name=company_name,
            report_kind="Result Update",
            sector=None,
            rating=None,
        ),
        company_data=[LabelValue(label=f) for f in COMPANY_DATA_FIELDS],
        narrative=Narrative(
            headline="Offline mode - no financial extraction performed",
            company_blurb=(
                "This report was generated without an LLM API key, so no "
                "figures were extracted from the source document. Every "
                "financial field is intentionally blank. Set a key and "
                "regenerate for a populated report."
            ),
            result_bullets=[
                f"Source document: {source_name}",
                f"Extracted text begins: {snippet}...",
            ],
            outlook_valuation=(
                "Outlook and valuation commentary is produced by the extraction "
                "step, which did not run in offline mode."
            ),
            key_highlights=[
                "Set GEMINI_API_KEY (or another provider's key) in .env to "
                "enable extraction.",
            ],
        ),
        source_note=f"Offline placeholder generated from {source_name}",
    )
