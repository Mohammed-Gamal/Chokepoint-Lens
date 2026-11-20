"""
The designs that did NOT ship, rendered so they can be argued with.

    python src/design_alternatives.py     ->  docs/mockups/alternatives.html

A finished dashboard is evidence of a design. It is not evidence of a design
*process*: it shows where you arrived, not what you rejected to get there, and
a reader cannot tell a considered choice from an accident.

So rather than describe the alternatives in prose, this file rebuilds them
from the real data and puts each one next to what replaced it. They are not
mockups -- every chart here is live and can be re-rendered, which means the
comparison can be checked rather than taken on trust.

Three decisions are documented, each one a place where the obvious design was
tried first and found to be wrong:

  A. What counts as "normal"      -- a flat average, or a seasonal baseline?
  B. Showing the gap vs normal    -- every route at once, or one at a time?
  C. Two measures, two units      -- share an axis, or rebase to an index?

The written argument lives in docs/design-rationale.md. This file supplies
the pictures it refers to.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MOCKUP_DIR = PROJECT_ROOT / "docs" / "mockups"

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
from metrics import EVENTS, REFERENCE_END, REFERENCE_START  # noqa: E402

hv.extension("bokeh")

WIDTH = 760
HEIGHT = 260
FOCUS = "Suez Canal"
TRIO = ["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope"]


def _events(data: pd.DataFrame) -> list:
    """Dotted vertical markers, shared by every panel here."""
    out = []
    for when in EVENTS.values():
        moment = pd.Timestamp(when)
        if data["date"].min() <= moment <= data["date"].max():
            out.append(
                hv.VLine(moment).opts(
                    color=charts.INK_MUTED, line_dash="dotted", line_width=1.5
                )
            )
    return out


# --------------------------------------------------------------------------
# A. What counts as "normal"
# --------------------------------------------------------------------------


def a_rejected_flat_baseline(metrics: pd.DataFrame):
    """
    REJECTED: compare every day against one flat pre-crisis average.

    This is the obvious first move and it is wrong in a specific, testable
    way. Suez traffic has a real annual rhythm, so a flat line sits above
    the quiet months and below the busy ones all year round. The chart then
    reports a deficit every winter and a surplus every summer, in years when
    nothing whatsoever was happening.
    """
    one = metrics[metrics["portname"] == FOCUS].sort_values("date")
    window = one[(one["date"] >= REFERENCE_START) & (one["date"] <= REFERENCE_END)]
    flat = window["n_total"].mean()

    frame = one.assign(flat=flat)
    band = hv.Area(frame, "date", ["n_total_smooth", "flat"]).opts(
        color=charts.INK_MUTED, alpha=0.18, line_width=0
    )
    level = hv.HLine(flat).opts(color=charts.SERIES[7], line_dash="dashed", line_width=1.5)
    line = hv.Curve(frame, "date", "n_total_smooth", label=FOCUS).opts(
        color=charts.SERIES[0], line_width=2
    )
    return hv.Overlay([band, level, line] + _events(frame)).opts(
        width=WIDTH, height=HEIGHT, show_grid=True, shared_axes=False,
        title="REJECTED — one flat average as 'normal'",
        ylabel="ships per day", xlabel="", legend_position="right",
    )


def a_chosen_seasonal_baseline(metrics: pd.DataFrame):
    """CHOSEN: compare each day against the same calendar day in past years."""
    return charts.transit_timeline(
        metrics, chokepoints=[FOCUS], width=WIDTH, height=HEIGHT
    ).opts(title="CHOSEN — a seasonal baseline, per calendar day")


# --------------------------------------------------------------------------
# B. Showing the gap against normal
# --------------------------------------------------------------------------


def b_rejected_all_baselines(metrics: pd.DataFrame):
    """
    REJECTED: draw the baseline band behind every route at once.

    It seems strictly more informative -- three routes, three baselines, all
    comparable on one frame. On screen it is six lines and three overlapping
    grey bands, and the one thing the chart was built to show, the gap
    between actual and normal, becomes the hardest thing in it to see.
    """
    layers = []
    for name in TRIO:
        one = metrics[metrics["portname"] == name].sort_values("date")
        layers.append(
            hv.Area(one, "date", ["n_total_smooth", "n_total_ref"]).opts(
                color=charts.colour_for(name), alpha=0.15, line_width=0
            )
        )
        layers.append(
            hv.Curve(one, "date", "n_total_ref").opts(
                color=charts.colour_for(name), line_dash="dashed", line_width=1
            )
        )
        layers.append(
            hv.Curve(one, "date", "n_total_smooth", label=name).opts(
                color=charts.colour_for(name), line_width=2
            )
        )
    return hv.Overlay(layers).opts(
        width=WIDTH, height=HEIGHT, show_grid=True, shared_axes=False,
        title="REJECTED — a baseline band behind all three routes",
        ylabel="ships per day", xlabel="", legend_position="right",
    )


def b_chosen_split(metrics: pd.DataFrame):
    """CHOSEN: compare routes bare; show the band only on the focused route."""
    return charts.transit_timeline(
        metrics, chokepoints=TRIO, width=WIDTH, height=HEIGHT
    ).opts(title="CHOSEN — comparison view stays bare; the band moves to its own panel")


# --------------------------------------------------------------------------
# C. Two measures on two different units
# --------------------------------------------------------------------------


def c_rejected_shared_axis(metrics: pd.DataFrame, ports: pd.DataFrame):
    """
    REJECTED: canal transits and Egyptian tonnage on one raw axis.

    Tonnes outnumber ships by five orders of magnitude, so the canal line is
    flattened onto the x-axis and the chart answers nothing.

    The usual fix is a second y-axis, which we rejected as well and did not
    bother to draw. It makes both lines visible but invents a relationship:
    where the two cross, and which appears to lead the other, depend entirely
    on the scales chosen, and a reader has no way to know that. Rebasing both
    to an index keeps one honest axis.
    """
    canal = metrics[metrics["portname"] == FOCUS].set_index("date")["n_total"].resample("MS").mean()
    tonnes = ports[ports["is_active"]].groupby("date")["trade"].sum().resample("MS").mean()

    frame_c = pd.DataFrame({"date": canal.index, "value": canal.to_numpy()})
    frame_t = pd.DataFrame({"date": tonnes.index, "value": tonnes.to_numpy()})

    return hv.Overlay(
        [
            hv.Curve(frame_t, "date", "value", label="Egyptian trade (tonnes)").opts(
                color=charts.SERIES[2], line_width=2
            ),
            hv.Curve(frame_c, "date", "value", label="Canal transits (ships)").opts(
                color=charts.SERIES[0], line_width=2
            ),
        ]
    ).opts(
        width=WIDTH, height=HEIGHT, show_grid=True, shared_axes=False,
        title="REJECTED — raw values sharing one axis",
        ylabel="mixed units", xlabel="", legend_position="right",
    )


def c_chosen_indexed(divergence: pd.DataFrame):
    """CHOSEN: rebase each series so its own pre-crisis average is 100."""
    return charts.canal_vs_ports_chart(divergence, width=WIDTH, height=HEIGHT).opts(
        title="CHOSEN — each series indexed to its own pre-crisis normal"
    )


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------


def build() -> Path:
    charts.apply_theme()
    metrics = charts.load("chokepoints_metrics")

    panels = [
        a_rejected_flat_baseline(metrics),
        a_chosen_seasonal_baseline(metrics),
        b_rejected_all_baselines(metrics),
        b_chosen_split(metrics),
    ]

    try:
        ports = charts.load("ports_daily")
        divergence = charts.load("canal_vs_ports")
        panels += [c_rejected_shared_axis(metrics, ports), c_chosen_indexed(divergence)]
    except FileNotFoundError:
        print("ports tables missing - skipping comparison C")

    MOCKUP_DIR.mkdir(parents=True, exist_ok=True)
    layout = hv.Layout(panels).cols(1).opts(hv.opts.Layout(shared_axes=False))
    out = MOCKUP_DIR / "alternatives.html"
    hv.save(layout, out, backend="bokeh", resources="inline")
    return out


if __name__ == "__main__":
    print(f"wrote {build()}")
