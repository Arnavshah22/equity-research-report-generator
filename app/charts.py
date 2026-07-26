"""
Chart rendering.

Every chart is returned as a base64 data URI so the HTML template stays a
single self-contained document -- no temp image files to clean up, and no
file:// path resolution for the headless browser to get wrong.

Two shapes cover the sample report:
  * combo_chart   -- teal bars on the left axis, orange trend line on the
                     right, with point labels. Used for the metric panels.
  * price_chart   -- the price-vs-index line chart in the page 1 left rail.
"""

from __future__ import annotations

import base64
import io

import matplotlib

matplotlib.use("Agg")  # no display; must be set before pyplot is imported

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from .schema import ChartSeries, PriceHistory

# Sampled from the reference report.
BAR = "#00BCB8"
LINE = "#ED7D31"
INK = "#404040"
GRID = "#D9D9D9"
STOCK = "#1F9E93"
INDEX = "#9BA7B0"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 7,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "figure.dpi": 200,
    }
)


def _to_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0.02, transparent=True)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _clean(values, length):
    """Pad/truncate to `length` and coerce to float-or-None."""
    out: list[float | None] = []
    for i in range(length):
        v = values[i] if i < len(values) else None
        try:
            out.append(None if v is None else float(v))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _axis_formatter(values):
    """
    Pick tick precision from the magnitude of the series.

    Integer ticks are right for revenue in millions and catastrophic for a
    ratio like net NPA (0.39, 0.41, 0.42), which would render as a column of
    zeros. Scale the decimals to the data instead of fixing them.
    """
    magnitudes = [abs(v) for v in values if v is not None]
    peak = max(magnitudes) if magnitudes else 0.0

    if peak < 10:
        decimals = 2
    elif peak < 100:
        decimals = 1
    else:
        decimals = 0

    def fmt(x, _pos):
        if x == 0:
            return "-"
        return f"{x:,.{decimals}f}"

    return FuncFormatter(fmt)


def combo_chart(series: ChartSeries) -> str | None:
    """
    Bars (left axis) plus a trend line (right axis), as on page 2 of the
    sample. Returns None if there is nothing plottable, so the caller can drop
    the panel rather than render an empty frame.
    """
    n = len(series.categories)
    if n == 0:
        return None

    bars = _clean(series.bar_values, n)
    line = _clean(series.line_values, n)
    if all(v is None for v in bars) and all(v is None for v in line):
        return None

    fig, ax = plt.subplots(figsize=(3.6, 1.75))
    x = range(n)

    bar_plot = ax.bar(
        x,
        [0 if v is None else v for v in bars],
        width=0.55,
        color=BAR,
        label=series.bar_label or "Value",
        zorder=2,
    )
    # Bars we have no data for are drawn at zero above; hide them so a gap
    # reads as missing rather than as an actual zero.
    for rect, v in zip(bar_plot, bars):
        if v is None:
            rect.set_visible(False)

    ax.set_xticks(list(x))
    ax.set_xticklabels(series.categories, fontsize=6)
    ax.yaxis.set_major_formatter(_axis_formatter(bars))
    ax.tick_params(axis="both", length=0, labelsize=6)
    ax.grid(axis="y", color=GRID, linewidth=0.4, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    handles = [bar_plot]
    labels = [series.bar_label or "Value"]

    if any(v is not None for v in line):
        ax2 = ax.twinx()
        xs = [i for i, v in enumerate(line) if v is not None]
        ys = [v for v in line if v is not None]
        (line_plot,) = ax2.plot(
            xs, ys, color=LINE, linewidth=1.2, marker="", zorder=3,
            label=series.line_label or "Growth",
        )
        for xi, yi in zip(xs, ys):
            ax2.annotate(
                f"{yi:,.1f}{series.line_suffix}",
                (xi, yi),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=5.5,
                color=INK,
            )
        ax2.tick_params(axis="y", length=0, labelsize=6)
        # Margin series often span a couple of points (16.8 -> 17.9); integer
        # ticks would collapse to a column of identical labels, so pick the
        # precision from the spread rather than fixing it.
        lo, hi = min(ys), max(ys)
        decimals = 1 if (hi - lo) < 5 else 0
        ax2.yaxis.set_major_formatter(
            FuncFormatter(lambda v, _p: f"{v:,.{decimals}f}{series.line_suffix}")
        )
        for spine in ("top", "right", "left", "bottom"):
            ax2.spines[spine].set_visible(False)
        # Headroom so the topmost point label isn't clipped by the axes box.
        pad = (hi - lo) * 0.25 or (abs(hi) * 0.25 or 1)
        ax2.set_ylim(lo - pad * 0.4, hi + pad)
        handles.append(line_plot)
        labels.append(series.line_label or "Growth")

    ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        frameon=False,
        fontsize=6,
        handlelength=1.4,
    )
    return _to_uri(fig)


def price_chart(history: PriceHistory, *, wide: bool = False) -> str | None:
    """
    The stock-vs-rebased-index chart.

    Two aspect ratios, because the same series appears in two very different
    slots: a 64mm column on page 1, and a ~120mm half-width panel beside the
    recommendation table on page 4. Rendering one figure and letting CSS scale
    it would either squash the rail or balloon the page 4 panel.
    """
    n = len(history.labels)
    if n == 0:
        return None

    stock = _clean(history.stock, n)
    index = _clean(history.index, n)
    if all(v is None for v in stock):
        return None

    fig, ax = plt.subplots(figsize=(6.6, 1.5) if wide else (2.9, 1.15))
    x = range(n)

    def _plot(values, color, label):
        xs = [i for i, v in enumerate(values) if v is not None]
        ys = [v for v in values if v is not None]
        if xs:
            ax.plot(xs, ys, color=color, linewidth=1.0, label=label)

    _plot(stock, STOCK, history.stock_label or "Stock")
    _plot(index, INDEX, history.index_label)

    # Label a handful of points so the axis stays readable at this size.
    step = max(1, n // 4)
    ticks = list(range(0, n, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([history.labels[i] for i in ticks], fontsize=5.5)
    ax.tick_params(axis="both", length=0, labelsize=5.5)
    ax.grid(axis="y", color=GRID, linewidth=0.4)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(GRID)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2,
              frameon=False, fontsize=5.5, handlelength=1.6)
    return _to_uri(fig)
