"""
The report template, defined as data.

This module is the single source of truth for *what a report contains*. The
Jinja template renders whatever is in `ReportModel`; the LLM is asked to fill
in whatever is in `ReportModel`. To add a field, a table row or a whole new
section, add it here and it flows through both sides.

Every field is optional. A report generated from a thin source document is a
valid report -- it just has blanks. See `Missing` in render.py for how empty
values are drawn.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# small building blocks
# --------------------------------------------------------------------------


class Rating(str, Enum):
    """Geojit's five-point recommendation scale (see page 4 of the sample)."""

    BUY = "BUY"
    ACCUMULATE = "ACCUMULATE"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    NOT_RATED = "NOT RATED"


Direction = Literal["up", "down", "none"]
"""Drives the triangle glyphs in the Key Changes strip: green up, orange down."""


class LabelValue(BaseModel):
    """A single row in a two-column key/value table (e.g. Company Data)."""

    label: str
    value: str | None = None


class TableRow(BaseModel):
    """
    One row of a generic financial table.

    `values` is positional and lines up with the parent table's `columns`. A
    short row is padded, a long row is truncated, so a partial extraction still
    renders rather than blowing up the layout.
    """

    label: str
    values: list[str | None] = Field(default_factory=list)
    bold: bool = False
    italic: bool = False
    indent: bool = False
    section: bool = False
    """A section divider inside a table, e.g. 'Profitab. & Return' in Ratios."""


class GroupHeaderCell(BaseModel):
    """One cell of an optional spanning header row above `columns`."""

    label: str
    span: int = 1


class FinancialTable(BaseModel):
    """
    A generic column/row table. Used for every tabular block in the report --
    Profit & Loss, Balance Sheet, Cashflow, Ratios, Quarterly Financials and
    Change in Estimates -- so there is exactly one table renderer to maintain.
    """

    title: str | None = None
    corner: str | None = None
    """Text for the top-left header cell, e.g. 'Y.E March (Rs. Cr)'."""
    columns: list[str] = Field(default_factory=list)
    rows: list[TableRow] = Field(default_factory=list)
    group_header: list[GroupHeaderCell] = Field(default_factory=list)
    """Spanning header above `columns`, e.g. Old estimates / New estimates / Change."""


class ChartSeries(BaseModel):
    """
    A combo chart: teal bars on the left axis, orange line on the right axis.
    This is the only chart shape the sample uses for its metric panels
    (Revenue / GOV / EBITDA / PAT), so one spec covers all four.
    """

    title: str
    categories: list[str] = Field(default_factory=list)
    bar_label: str = ""
    bar_values: list[float | None] = Field(default_factory=list)
    line_label: str = ""
    line_values: list[float | None] = Field(default_factory=list)
    line_suffix: str = "%"
    """Unit appended to the point labels drawn along the line."""


class PriceHistory(BaseModel):
    """Series behind the price-vs-index chart in the left rail of page 1."""

    labels: list[str] = Field(default_factory=list)
    stock: list[float | None] = Field(default_factory=list)
    index: list[float | None] = Field(default_factory=list)
    stock_label: str = ""
    index_label: str = "Sensex Rebased"


class RatingHistoryRow(BaseModel):
    """One line of the Recommendation Summary table on page 4."""

    date: str | None = None
    rating: str | None = None
    target: str | None = None


# --------------------------------------------------------------------------
# page 1 -- header and left rail
# --------------------------------------------------------------------------


class Header(BaseModel):
    company_name: str | None = None
    sector: str | None = None
    report_kind: str = "Result Update"
    """Vertical tab text on the right edge, e.g. 'Q2FY26 Result Update'."""
    period: str | None = None
    """The quarter being reported, e.g. 'Q2FY26'."""
    date: str | None = None
    data_as_of: str | None = None
    rating: Rating | None = None
    target_price: str | None = None
    cmp: str | None = None
    expected_return: str | None = None
    currency: str = "Rs."


class KeyChanges(BaseModel):
    """The Target / Rating / Earnings arrow strip under the header."""

    target: Direction = "none"
    rating: Direction = "none"
    earnings: Direction = "none"


class StockIdentity(BaseModel):
    """The Stock Type / Bloomberg / Sensex / NSE / BSE / Time Frame strip."""

    stock_type: str | None = None
    bloomberg_code: str | None = None
    index_name: str = "Sensex"
    index_value: str | None = None
    nse_code: str | None = None
    bse_code: str | None = None
    time_frame: str = "12 Months"


# --------------------------------------------------------------------------
# page 1 -- narrative
# --------------------------------------------------------------------------


class Narrative(BaseModel):
    headline: str | None = None
    """The teal one-line thesis, e.g. 'Blinkit propels growth; valuation limits upside'."""
    company_blurb: str | None = None
    """Bold intro paragraph describing what the company does."""
    result_bullets: list[str] = Field(default_factory=list)
    outlook_valuation: str | None = None
    key_highlights: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------
# the whole report
# --------------------------------------------------------------------------


class ReportModel(BaseModel):
    """
    A complete equity research note. This is what the LLM fills, what the
    template consumes, and what gets cached to disk next to the output PDF.
    """

    header: Header = Field(default_factory=Header)
    key_changes: KeyChanges = Field(default_factory=KeyChanges)
    identity: StockIdentity = Field(default_factory=StockIdentity)

    company_data: list[LabelValue] = Field(default_factory=list)
    shareholding: FinancialTable | None = None
    price_performance: FinancialTable | None = None
    price_history: PriceHistory | None = None
    estimates_summary: FinancialTable | None = None
    """The Y.E March valuation snapshot in the left rail (Sales -> D/E)."""

    narrative: Narrative = Field(default_factory=Narrative)
    quarterly: FinancialTable | None = None

    charts: list[ChartSeries] = Field(default_factory=list)
    change_in_estimates: FinancialTable | None = None

    profit_loss: FinancialTable | None = None
    balance_sheet: FinancialTable | None = None
    cashflow: FinancialTable | None = None
    ratios: FinancialTable | None = None

    rating_history: list[RatingHistoryRow] = Field(default_factory=list)
    analyst_name: str | None = None
    source_note: str | None = None
    """Provenance line printed in the footer, e.g. which file this came from."""


# --------------------------------------------------------------------------
# canonical row labels
# --------------------------------------------------------------------------
#
# These drive the LLM prompt and give the generated reports a stable shape
# across companies. They are deliberately data, not hardcoded template markup:
# adding a metric here makes it appear in the prompt and in the output.

COMPANY_DATA_FIELDS = [
    "Market Cap (Rs.cr)",
    "52 Week High — Low (Rs.)",
    "Enterprise Value (Rs. cr)",
    "Outstanding Shares (cr)",
    "Free Float (%)",
    "Dividend Yield (%)",
    "6m average volume (cr)",
    "Beta",
    "Face value (Rs. )",
]

SHAREHOLDING_ROWS = [
    "Promoters",
    "FII's",
    "MFs/Institutions",
    "Public",
    "Others",
    "Total",
    "Promoter Pledge",
]

PRICE_PERFORMANCE_ROWS = [
    "Absolute Return",
    "Absolute Sensex",
    "Relative Return",
]

ESTIMATES_SUMMARY_ROWS = [
    ("Sales", False),
    ("Growth (%)", True),
    ("EBITDA", False),
    ("EBITDA Margin (%)", True),
    ("PAT Adjusted", False),
    ("Growth (%)", True),
    ("Adjusted EPS", False),
    ("Growth (%)", True),
    ("P/E", False),
    ("P/B", False),
    ("EV/EBITDA", False),
    ("ROE (%)", True),
    ("D/E", False),
]

PROFIT_LOSS_ROWS = [
    "Sales", "% change", "EBITDA", "% change", "Depreciation", "EBIT",
    "Interest", "Other Income", "PBT", "% change", "Tax", "Tax Rate (%)",
    "Reported PAT", "PAT att. to common shareholders", "Adj.*", "Adj. PAT",
    "% change", "No. of shares (cr)", "Adj EPS (Rs.)", "% change", "DPS (Rs.)",
]

BALANCE_SHEET_ROWS = [
    "Cash", "Accts. Receivable", "Inventories", "Other Cur. Assets",
    "Investments", "Gross Fixed Assets", "Net Fixed Assets", "CWIP",
    "Intangible Assets", "Def. Tax -Net", "Other Assets", "Total Assets",
    "Current Liabilities", "Provisions", "Debt Funds", "Other Liabilities",
    "Equity Capital", "Res. & Surplus", "Shareholder Funds", "Minority Interest",
    "Total Liabilities", "BVPS",
]

CASHFLOW_ROWS = [
    "Net inc. + Depn.", "Non-cash adj.", "Other adjustments", "Changes in W.C",
    "C.F. Operation", "Capital exp.", "Change in inv.", "Other invest.CF",
    "C.F - Investment", "Issue of equity", "Issue/repay debt", "Dividends paid",
    "Other finance.CF", "C.F - Finance", "Chg. in cash", "Closing Cash",
]

RATIO_ROWS = [
    ("Profitab. & Return", True),
    ("EBITDA margin (%)", False),
    ("EBIT margin (%)", False),
    ("Net profit mgn.(%)", False),
    ("ROE (%)", False),
    ("ROCE (%)", False),
    ("W.C & Liquidity", True),
    ("Receivables (days)", False),
    ("Inventory (days)", False),
    ("Payables (days)", False),
    ("Current ratio (x)", False),
    ("Quick ratio (x)", False),
    ("Turnover &Leverage", True),
    ("Gross asset T.O (x)", False),
    ("Total asset T.O (x)", False),
    ("Int. covge. ratio (x)", False),
    ("Adj. debt/equity (x)", False),
    ("Valuation", True),
    ("EV/Sales (x)", False),
    ("EV/EBITDA (x)", False),
    ("P/E (x)", False),
    ("P/BV (x)", False),
]
