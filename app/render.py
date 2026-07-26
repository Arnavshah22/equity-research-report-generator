"""
ReportModel -> HTML -> PDF.

Charts are rendered to data URIs, the Jinja template is filled, and headless
Chromium prints the result. Chromium is used rather than WeasyPrint because it
needs no system libraries on Windows/macOS/Linux -- `playwright install
chromium` is the only setup step.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from .branding import load_brand
from .charts import combo_chart, price_chart
from .schema import ReportModel

TEMPLATE_DIR = Path(__file__).parent / "templates"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def build_charts(report: ReportModel) -> dict:
    """Render every chart the report has data for, skipping empty ones."""
    combos = []
    for series in report.charts[:4]:
        uri = combo_chart(series)
        if uri:
            combos.append({"title": series.title, "uri": uri})

    history = report.price_history
    return {
        "combos": combos,
        "price": price_chart(history) if history else None,
        "price_wide": price_chart(history, wide=True) if history else None,
    }


def render_html(report: ReportModel) -> str:
    """
    Fill the template and inline the stylesheet.

    The <link> is replaced with a <style> block so the HTML is a single
    self-contained document -- it can be written to a temp file anywhere, or
    opened directly in a browser, without a sibling CSS file.
    """
    template = _env.get_template("report.html")
    html = template.render(
        report=report,
        brand=load_brand(),
        charts=build_charts(report),
    )
    css = (TEMPLATE_DIR / "report.css").read_text(encoding="utf-8")
    html = html.replace(
        '<link rel="stylesheet" href="report.css">',
        f"<style>\n{css}\n</style>",
    )
    return f"<!doctype html>\n<html><head><meta charset='utf-8'>{html}</html>"


def render_pdf(report: ReportModel, out_path: Path) -> Path:
    """Print the report to `out_path` and return it."""
    html = render_html(report)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            browser.close()

    return out_path
