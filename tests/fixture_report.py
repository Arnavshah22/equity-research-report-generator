"""
A fully-populated ReportModel used to exercise the template.

The company is fictional on purpose: this fixture renders a complete,
real-looking research note, and using an invented issuer means the output
can never be mistaken for a genuine note on a listed company. It covers
every construct the template supports -- group headers, section rows, bold
and italic rows, charts, and deliberately missing cells.

    python -m tests.fixture_report          # writes output/_fixture.pdf
"""

from __future__ import annotations

from pathlib import Path

from app.schema import (
    ChartSeries,
    FinancialTable,
    GroupHeaderCell,
    Header,
    KeyChanges,
    LabelValue,
    Narrative,
    PriceHistory,
    Rating,
    RatingHistoryRow,
    ReportModel,
    StockIdentity,
    TableRow,
)

FY = ["FY23A", "FY24A", "FY25A", "FY26E", "FY27E"]


def _t(label, *values, bold=False, italic=False, section=False, indent=False):
    return TableRow(
        label=label,
        values=list(values),
        bold=bold,
        italic=italic,
        section=section,
        indent=indent,
    )


def build() -> ReportModel:
    return ReportModel(
        header=Header(
            company_name="Meridian Industrial Ltd.",
            sector="Industrial Engineering",
            report_kind="Result Update",
            period="Q2FY26",
            date="17th October, 2025",
            data_as_of="16-October-2025, 16:20hrs",
            rating=Rating.ACCUMULATE,
            target_price="Rs. 1,485",
            cmp="Rs. 1,310",
            expected_return="+13%",
        ),
        key_changes=KeyChanges(target="up", rating="none", earnings="up"),
        identity=StockIdentity(
            stock_type="Mid Cap",
            bloomberg_code="MRDN:IN",
            index_value="82,140",
            nse_code="MERIDIAN",
            bse_code="532961",
        ),
        company_data=[
            LabelValue(label="Market Cap (Rs.cr)", value="41,880"),
            LabelValue(label="52 Week High — Low (Rs.)", value="1,486 - 902"),
            LabelValue(label="Enterprise Value (Rs. cr)", value="40,215"),
            LabelValue(label="Outstanding Shares (cr)", value="32.0"),
            LabelValue(label="Free Float (%)", value="46.2"),
            LabelValue(label="Dividend Yield (%)", value="1.4"),
            LabelValue(label="6m average volume (cr)", value="0.4"),
            LabelValue(label="Beta", value="1.1"),
            LabelValue(label="Face value (Rs. )", value="2.0"),
        ],
        shareholding=FinancialTable(
            corner="Shareholding (%)",
            columns=["Q4FY25", "Q1FY26", "Q2FY26"],
            rows=[
                _t("Promoters", "53.8", "53.8", "53.8"),
                _t("FII's", "18.2", "19.0", "20.1"),
                _t("MFs/Institutions", "16.4", "16.1", "15.6"),
                _t("Public", "8.9", "8.5", "8.0"),
                _t("Others", "2.7", "2.6", "2.5"),
                _t("Total", "100.0", "100.0", "100.0", bold=True),
                _t("Promoter Pledge", "Nil", "Nil", "Nil"),
            ],
        ),
        price_performance=FinancialTable(
            corner="Price Performance",
            columns=["3 Month", "6 Month", "1 Year"],
            rows=[
                _t("Absolute Return", "11.4", "24.8", "38.2"),
                _t("Absolute Sensex", "3.1", "7.4", "9.8"),
                _t("Relative Return", "8.3", "17.4", "28.4"),
            ],
        ),
        price_history=PriceHistory(
            labels=["Oct-24", "Jan-25", "Apr-25", "Jul-25", "Oct-25"],
            stock=[948, 1032, 1145, 1268, 1310],
            index=[948, 972, 1004, 1028, 1041],
            stock_label="MERIDIAN",
        ),
        estimates_summary=FinancialTable(
            corner="Y.E March (cr)",
            columns=["FY25A", "FY26E", "FY27E"],
            rows=[
                _t("Sales", "11,240", "13,180", "15,420"),
                _t("Growth (%)", "14.2", "17.3", "17.0", italic=True),
                _t("EBITDA", "1,910", "2,320", "2,810"),
                _t("EBITDA Margin (%)", "17.0", "17.6", "18.2", italic=True),
                _t("PAT Adjusted", "1,142", "1,395", "1,708"),
                _t("Growth (%)", "18.6", "22.2", "22.4", italic=True),
                _t("Adjusted EPS", "35.7", "43.6", "53.4"),
                _t("Growth (%)", "18.6", "22.2", "22.4", italic=True),
                _t("P/E", "36.7", "30.0", "24.5"),
                _t("P/B", "6.8", "5.9", "5.0"),
                _t("EV/EBITDA", "21.1", "17.3", "14.3"),
                _t("ROE (%)", "19.8", "21.1", "22.0", italic=True),
                _t("D/E", "0.2", "0.2", "0.1"),
            ],
        ),
        narrative=Narrative(
            headline="Order book at record high; margin recovery underway",
            company_blurb=(
                "Meridian Industrial Limited manufactures precision flow-control "
                "equipment for the energy, water and process industries. It operates "
                "five plants across India and derives roughly a third of revenue from "
                "exports, principally to the Middle East and South-East Asia."
            ),
            result_bullets=[
                "Consolidated revenue rose 16.8% YoY to Rs. 3,142cr in Q2FY26, ahead of "
                "our estimate of Rs. 3,020cr, on faster execution in the energy segment.",
                "EBITDA grew 24.1% YoY to Rs. 561cr; EBITDA margin expanded 100bps YoY to "
                "17.9% as commodity costs eased and the export mix improved.",
                "Order inflow of Rs. 4,010cr took the closing order book to a record "
                "Rs. 18,600cr, representing 1.7x trailing twelve-month revenue.",
                "Reported PAT increased 27.4% YoY to Rs. 372cr; adjusted PAT of Rs. 368cr "
                "excludes a one-time Rs. 4cr provision write-back.",
                "Export revenue grew 29.2% YoY and now contributes 34.1% of the mix, up "
                "from 30.8% a year ago.",
                "Net debt fell to Rs. 1,665cr from Rs. 2,140cr in Q2FY25, taking net "
                "debt/equity to 0.2x.",
            ],
            outlook_valuation=(
                "We expect the record order book to support 17% revenue CAGR over "
                "FY25-27E, with execution weighted towards the second half of each year. "
                "Margin recovery should continue as legacy fixed-price contracts run off "
                "and the higher-margin export mix builds. Balance sheet deleveraging and "
                "improving working capital give further comfort. We raise our FY26E and "
                "FY27E earnings by 4.2% and 6.1% respectively and roll forward our "
                "valuation, arriving at a revised target price of Rs. 1,485 based on 28x "
                "FY27E earnings. We maintain our ACCUMULATE rating."
            ),
            key_highlights=[
                "The energy segment drove the beat, growing 22.4% YoY as three large "
                "orders moved into peak execution. Management expects this segment to "
                "hold above 20% growth through FY26 before normalising to mid-teens.",
                "Gross margin improved 140bps YoY to 38.2%, of which roughly 90bps came "
                "from softer alloy steel prices and the balance from mix. Management "
                "guided to holding gross margin near current levels, noting that input "
                "costs have stabilised rather than continuing to fall.",
                "Working capital days reduced to 84 from 97 a year ago, largely on faster "
                "collections in the domestic water business, where receivable days fell "
                "from 118 to 92.",
                "Capacity utilisation stands at 78%. The Rs. 900cr brownfield expansion "
                "announced in FY25 remains on schedule for commissioning in Q4FY26 and is "
                "expected to add roughly 20% to installed capacity.",
                "Management reiterated FY26 revenue guidance of Rs. 13,000-13,400cr and "
                "raised the EBITDA margin guidance band to 17.5-18.0% from 17.0-17.5%.",
            ],
        ),
        quarterly=FinancialTable(
            corner="Rs.cr",
            columns=["Q2FY26", "Q2FY25", "YoY Growth (%)", "Q1FY26", "QoQ Growth (%)"],
            rows=[
                _t("Sales", "3,142", "2,690", "16.8", "2,980", "5.4"),
                _t("EBITDA", "561", "452", "24.1", "521", "7.7"),
                _t("Margin (%)", "17.9", "16.8", "110bps", "17.5", "40bps", italic=True),
                _t("EBIT", "486", "384", "26.6", "448", "8.5"),
                _t("PBT", "498", "392", "27.0", "455", "9.5"),
                _t("Rep. PAT", "372", "292", "27.4", "340", "9.4"),
                _t("Adj PAT", "368", "292", "26.0", "340", "8.2"),
                _t("Adj. EPS (Rs)", "11.5", "9.1", "26.0", "10.6", "8.2"),
            ],
        ),
        charts=[
            ChartSeries(
                title="Revenue",
                categories=["Q2FY25", "Q3FY25", "Q4FY25", "Q1FY26", "Q2FY26"],
                bar_label="Revenue (Rs.cr)",
                bar_values=[2690, 2810, 3020, 2980, 3142],
                line_label="Growth (YoY)",
                line_values=[12.4, 13.1, 15.6, 15.9, 16.8],
            ),
            ChartSeries(
                title="EBITDA",
                categories=["Q2FY25", "Q3FY25", "Q4FY25", "Q1FY26", "Q2FY26"],
                bar_label="EBITDA (Rs.cr)",
                bar_values=[452, 481, 528, 521, 561],
                line_label="Margin",
                line_values=[16.8, 17.1, 17.5, 17.5, 17.9],
            ),
            ChartSeries(
                title="PAT",
                categories=["Q2FY25", "Q3FY25", "Q4FY25", "Q1FY26", "Q2FY26"],
                bar_label="PAT (Rs.cr)",
                bar_values=[292, 310, 348, 340, 368],
                line_label="Margin",
                line_values=[10.9, 11.0, 11.5, 11.4, 11.7],
            ),
            ChartSeries(
                title="Order Book",
                categories=["Q2FY25", "Q3FY25", "Q4FY25", "Q1FY26", "Q2FY26"],
                bar_label="Order Book (Rs.cr)",
                bar_values=[14200, 15100, 16400, 17300, 18600],
                line_label="Growth (YoY)",
                line_values=[18.2, 20.1, 24.6, 28.0, 31.0],
            ),
        ],
        change_in_estimates=FinancialTable(
            group_header=[
                GroupHeaderCell(label="Old estimates", span=2),
                GroupHeaderCell(label="New estimates", span=2),
                GroupHeaderCell(label="Change (%)", span=2),
            ],
            corner="Year / Rs cr",
            columns=["FY26E", "FY27E", "FY26E", "FY27E", "FY26E", "FY27E"],
            rows=[
                _t("Revenue", "12,850", "14,780", "13,180", "15,420", "2.6", "4.3"),
                _t("EBITDA", "2,215", "2,610", "2,320", "2,810", "4.7", "7.7"),
                _t("Margins (%)", "17.2", "17.7", "17.6", "18.2", "40bps", "50bps", italic=True),
                _t("Adj. PAT", "1,339", "1,610", "1,395", "1,708", "4.2", "6.1"),
                _t("EPS", "41.8", "50.3", "43.6", "53.4", "4.3", "6.2"),
            ],
        ),
        profit_loss=FinancialTable(
            corner="Y.E March (Rs. Cr)",
            columns=FY,
            rows=[
                _t("Sales", "8,640", "9,842", "11,240", "13,180", "15,420", bold=True),
                _t("% change", "18.4", "13.9", "14.2", "17.3", "17.0", italic=True),
                _t("EBITDA", "1,340", "1,588", "1,910", "2,320", "2,810", bold=True),
                _t("% change", "21.2", "18.5", "20.3", "21.5", "21.1", italic=True),
                _t("Depreciation", "268", "292", "318", "356", "402"),
                _t("EBIT", "1,072", "1,296", "1,592", "1,964", "2,408", bold=True),
                _t("Interest", "184", "171", "148", "132", "118"),
                _t("Other Income", "96", "112", "138", "156", "174"),
                _t("PBT", "984", "1,237", "1,582", "1,988", "2,464", bold=True),
                _t("% change", "24.1", "25.7", "27.9", "25.7", "23.9", italic=True),
                _t("Tax", "172", "274", "440", "593", "756"),
                _t("Tax Rate (%)", "17.5", "22.2", "27.8", "29.8", "30.7", italic=True),
                _t("Reported PAT", "812", "963", "1,142", "1,395", "1,708", bold=True),
                _t("PAT att. to common shareholders", "812", "963", "1,142", "1,395", "1,708"),
                _t("Adj.*", None, None, None, None, None),
                _t("Adj. PAT", "812", "963", "1,142", "1,395", "1,708", bold=True),
                _t("% change", "26.4", "18.6", "18.6", "22.2", "22.4", italic=True),
                _t("No. of shares (cr)", "32.0", "32.0", "32.0", "32.0", "32.0"),
                _t("Adj EPS (Rs.)", "25.4", "30.1", "35.7", "43.6", "53.4", bold=True),
                _t("% change", "26.4", "18.6", "18.6", "22.2", "22.4", italic=True),
                _t("DPS (Rs.)", "12.0", "14.0", "18.0", "21.0", "25.0"),
            ],
        ),
        balance_sheet=FinancialTable(
            corner="Y.E March (Rs. Cr)",
            columns=FY,
            rows=[
                _t("Cash", "620", "748", "1,012", "1,340", "1,780"),
                _t("Accts. Receivable", "2,480", "2,610", "2,840", "3,180", "3,620"),
                _t("Inventories", "1,940", "2,080", "2,210", "2,480", "2,810"),
                _t("Other Cur. Assets", "740", "812", "902", "1,010", "1,140"),
                _t("Investments", "310", "364", "420", "480", "545"),
                _t("Gross Fixed Assets", "4,120", "4,480", "5,010", "5,940", "6,720"),
                _t("Net Fixed Assets", "2,610", "2,742", "2,986", "3,560", "3,978"),
                _t("CWIP", "180", "240", "410", "620", "380"),
                _t("Intangible Assets", "96", "104", "112", "120", "128"),
                _t("Def. Tax -Net", None, None, None, None, None),
                _t("Other Assets", "412", "448", "492", "540", "596"),
                _t("Total Assets", "9,388", "10,148", "11,384", "13,330", "14,977", bold=True),
                _t("Current Liabilities", "2,410", "2,580", "2,810", "3,180", "3,540"),
                _t("Provisions", "180", "196", "214", "238", "264"),
                _t("Debt Funds", "2,120", "1,940", "1,760", "1,620", "1,480"),
                _t("Other Liabilities", "268", "284", "302", "324", "348"),
                _t("Equity Capital", "64", "64", "64", "64", "64"),
                _t("Res. & Surplus", "4,346", "5,084", "6,234", "7,904", "9,281"),
                _t("Shareholder Funds", "4,410", "5,148", "6,298", "7,968", "9,345", bold=True),
                _t("Minority Interest", None, None, None, None, None),
                _t("Total Liabilities", "9,388", "10,148", "11,384", "13,330", "14,977", bold=True),
                _t("BVPS", "138", "161", "197", "249", "292"),
            ],
        ),
        cashflow=FinancialTable(
            corner="Y.E March",
            columns=FY,
            rows=[
                _t("Net inc. + Depn.", "1,080", "1,255", "1,460", "1,751", "2,110"),
                _t("Non-cash adj.", "-64", "-78", "-92", "-104", "-118"),
                _t("Other adjustments", None, None, None, None, None),
                _t("Changes in W.C", "-386", "-241", "-198", "-412", "-486"),
                _t("C.F. Operation", "630", "936", "1,170", "1,235", "1,506", bold=True),
                _t("Capital exp.", "-412", "-420", "-700", "-1,140", "-820"),
                _t("Change in inv.", "-48", "-54", "-56", "-60", "-65", indent=True),
                _t("Other invest.CF", "62", "74", "88", "96", "108"),
                _t("C.F - Investment", "-398", "-400", "-668", "-1,104", "-777", bold=True),
                _t("Issue of equity", None, None, None, None, None),
                _t("Issue/repay debt", "-140", "-180", "-180", "-140", "-140", indent=True),
                _t("Dividends paid", "-384", "-448", "-576", "-672", "-800"),
                _t("Other finance.CF", "-92", "-84", "-72", "-64", "-58", indent=True),
                _t("C.F - Finance", "-616", "-712", "-828", "-876", "-998", bold=True),
                _t("Chg. in cash", "-384", "-176", "-326", "-745", "-269"),
                _t("Closing Cash", "620", "748", "1,012", "1,340", "1,780", bold=True),
            ],
        ),
        ratios=FinancialTable(
            corner="Y.E March",
            columns=FY,
            rows=[
                _t("Profitab. & Return", section=True),
                _t("EBITDA margin (%)", "15.5", "16.1", "17.0", "17.6", "18.2"),
                _t("EBIT margin (%)", "12.4", "13.2", "14.2", "14.9", "15.6"),
                _t("Net profit mgn.(%)", "9.4", "9.8", "10.2", "10.6", "11.1"),
                _t("ROE (%)", "19.2", "20.1", "19.8", "21.1", "22.0"),
                _t("ROCE (%)", "17.4", "18.6", "19.4", "20.6", "21.8"),
                _t("W.C & Liquidity", section=True),
                _t("Receivables (days)", "104.8", "96.8", "92.2", "88.1", "85.7"),
                _t("Inventory (days)", "82.0", "77.1", "71.8", "68.7", "66.5"),
                _t("Payables (days)", "101.8", "95.7", "91.3", "88.1", "83.8"),
                _t("Current ratio (x)", "2.4", "2.5", "2.6", "2.6", "2.7"),
                _t("Quick ratio (x)", "1.6", "1.7", "1.8", "1.8", "1.9"),
                _t("Turnover &Leverage", section=True),
                _t("Gross asset T.O (x)", "2.1", "2.2", "2.2", "2.2", "2.3"),
                _t("Total asset T.O (x)", "0.9", "1.0", "1.0", "1.0", "1.0"),
                _t("Int. covge. ratio (x)", "5.8", "7.6", "10.8", "14.9", "20.4"),
                _t("Adj. debt/equity (x)", "0.3", "0.2", "0.2", "0.2", "0.1"),
                _t("Valuation", section=True),
                _t("EV/Sales (x)", "4.8", "4.2", "3.6", "3.1", "2.6"),
                _t("EV/EBITDA (x)", "31.0", "26.1", "21.1", "17.3", "14.3"),
                _t("P/E (x)", "51.6", "43.5", "36.7", "30.0", "24.5"),
                _t("P/BV (x)", "9.5", "8.1", "6.8", "5.9", "5.0"),
            ],
        ),
        rating_history=[
            RatingHistoryRow(date="12-Aug-24", rating="BUY", target="1,050"),
            RatingHistoryRow(date="09-Nov-24", rating="BUY", target="1,140"),
            RatingHistoryRow(date="14-Feb-25", rating="ACCUMULATE", target="1,220"),
            RatingHistoryRow(date="16-May-25", rating="ACCUMULATE", target="1,305"),
            RatingHistoryRow(date="08-Aug-25", rating="ACCUMULATE", target="1,420"),
            RatingHistoryRow(date="17-Oct-25", rating="ACCUMULATE", target="1,485"),
        ],
        source_note="Rendering fixture - fictional issuer, not a real research note",
    )


if __name__ == "__main__":
    from app.render import render_html, render_pdf

    report = build()
    out = Path("output/_fixture.pdf")
    Path("output/_fixture.html").write_text(render_html(report), encoding="utf-8")
    render_pdf(report, out)
    print(f"Wrote {out}")
