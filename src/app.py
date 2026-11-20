"""
Step 5: the dashboard. Run it with

    panel serve src/app.py --show --autoreload

----------------------------------------------------------------------
WHAT THE INTERACTION IS FOR
----------------------------------------------------------------------
The brief asks for interactive features that "support data analysis", and
warns that variety is not a goal in itself. So every control here exists to
answer one of the three research questions, and none of them is decoration:

  FILTER   Date range, route picker, and measure picker. Changing the
           measure from ships to mean vessel size is what turns RQ1 into
           RQ2 -- same chart, different question.

  SELECT   Drag across the timeline to define your own comparison period.
           The summary underneath recomputes against the seasonal baseline
           for exactly the days you selected. This is the most useful
           control on the page: the preset periods are my guesses about
           where the interesting boundaries are, and this lets the analyst
           disagree with me.

  LINK     The focus route drives three views at once -- the baseline band,
           the vessel composition, and the table. Picking a route is a
           single act that changes the whole page, instead of three
           separate dropdowns that have to be kept in sync by hand.

  SEARCH   The table at the bottom has per-column filters, so a specific
           date or value can be found without scrolling 80,000 rows.

  HOVER    Every chart carries tooltips with the underlying numbers, so
           nothing on screen is a shape you cannot interrogate.

  ZOOM     Bokeh's wheel-zoom and pan are on for every time series.

Each block also states, in writing on the page, which question it answers.
That costs a line of text and makes the dashboard explain itself to anyone
who opens it without you standing next to them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import pandas as pd
import panel as pn

sys.path.insert(0, str(Path(__file__).resolve().parent))

import charts  # noqa: E402
from metrics import PERIODS, REFERENCE_END, REFERENCE_START  # noqa: E402

pn.extension("tabulator", sizing_mode="stretch_width")
hv.extension("bokeh")
charts.apply_theme()

ACCENT = charts.SERIES[0]


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


@pn.cache
def load_everything() -> dict[str, pd.DataFrame]:
    """
    Read the processed tables once and keep them in memory.

    @pn.cache matters here: without it every widget change would re-read
    80,528 rows from disk, and the dashboard would feel sluggish for no
    reason. With it, interaction is instant.
    """
    tables = {
        "metrics": charts.load("chokepoints_metrics"),
        "meta": charts.load("chokepoints_meta"),
        "long": charts.load("chokepoints_long"),
        "ratio": charts.load("suez_substitution"),
    }
    # RQ3 tables are optional: the dashboard still works without them, it
    # just hides that section rather than crashing on a missing file.
    for name in ("ports_daily", "port_changes", "canal_vs_ports"):
        try:
            tables[name] = charts.load(name)
        except FileNotFoundError:
            tables[name] = None
    return tables


DATA = load_everything()
METRICS = DATA["metrics"]
META = DATA["meta"]
LONG = DATA["long"]
RATIO = DATA["ratio"]
PORTS = DATA["ports_daily"]
PORT_CHANGES = DATA["port_changes"]
DIVERGENCE = DATA["canal_vs_ports"]
HAS_PORTS = PORT_CHANGES is not None and DIVERGENCE is not None

ALL_ROUTES = sorted(METRICS["portname"].unique())
FIRST_DAY = METRICS["date"].min().to_pydatetime()
LAST_DAY = METRICS["date"].max().to_pydatetime()

MEASURES = {
    "Ships per day": "n_total",
    "Cargo ships per day": "n_cargo",
    "Tankers per day": "n_tanker",
    "Total capacity": "capacity",
    "Mean vessel size": "mean_vessel_size",
}


# --------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------

focus_route = pn.widgets.Select(
    name="Focus route",
    value="Suez Canal",
    options=ALL_ROUTES,
    description="Drives the baseline band, the vessel mix, and the table.",
)

compare_routes = pn.widgets.MultiChoice(
    name="Routes to compare",
    value=["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope"],
    options=ALL_ROUTES,
    max_items=8,
    description="Up to 8. Each keeps its own colour however many are shown.",
)

measure = pn.widgets.Select(name="Measure", options=MEASURES, value="n_total")

date_range = pn.widgets.DateRangeSlider(
    name="Date range",
    start=FIRST_DAY,
    end=LAST_DAY,
    value=(FIRST_DAY, LAST_DAY),
    step=24 * 60 * 60 * 1000,
)

map_day = pn.widgets.DateSlider(
    name="Map shows this day",
    start=FIRST_DAY,
    end=LAST_DAY,
    value=LAST_DAY,
)

normalise = pn.widgets.Checkbox(name="Vessel mix as shares (not counts)", value=True)


def _window(df: pd.DataFrame, span) -> pd.DataFrame:
    """Slice a frame to the selected date range."""
    start, end = pd.Timestamp(span[0]), pd.Timestamp(span[1])
    return df[(df["date"] >= start) & (df["date"] <= end)]


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------


def view_map(day):
    try:
        return charts.chokepoint_map(METRICS, META, as_of=day, height=360)
    except Exception as exc:  # noqa: BLE001
        return pn.pane.Alert(f"Map unavailable: {exc}", alert_type="warning")


def view_heatmap(routes):
    if not routes:
        return pn.pane.Alert("Pick at least one route.", alert_type="light")
    return charts.period_heatmap(METRICS, chokepoints=list(routes), height=360)


def view_timeline(routes, column, span):
    if not routes:
        return pn.pane.Alert("Pick at least one route.", alert_type="light")
    data = _window(METRICS, span)
    if data.empty:
        return pn.pane.Alert("No data in that date range.", alert_type="light")
    return charts.transit_timeline(
        data, chokepoints=list(routes), value=column, height=330
    )


def view_focus(route, column, span):
    """The focus route on its own, with its seasonal normal drawn behind it."""
    data = _window(METRICS, span)
    if data.empty or route not in set(data["portname"]):
        return pn.pane.Alert("No data for that route in this range.", alert_type="light")
    return charts.transit_timeline(
        data, chokepoints=[route], value=column, height=300
    )


def view_composition(route, span, as_shares):
    data = _window(LONG, span)
    if data.empty:
        return pn.pane.Alert("No data in that date range.", alert_type="light")
    return charts.composition_area(
        data, chokepoint=route, normalise=as_shares, height=320
    )


def view_substitution(span):
    data = _window(RATIO, span)
    if data.empty:
        return pn.pane.Alert("No data in that date range.", alert_type="light")
    return charts.substitution_curve(data, height=320)


def view_divergence(span):
    """RQ3: canal and ports on one indexed scale."""
    data = _window(DIVERGENCE, span)
    if data.empty:
        return pn.pane.Alert("No data in that date range.", alert_type="light")
    return charts.canal_vs_ports_chart(data, height=330)


def view_port_changes():
    """
    RQ3: each Egyptian port against the canal's own change.

    Not filtered by the date slider on purpose. This chart compares two
    fixed windows -- the pre-crisis baseline and everything since mid-2024 --
    and letting the slider cut into either of them would quietly change what
    the percentages mean while leaving the title saying otherwise.
    """
    return charts.port_change_dumbbell(
        PORT_CHANGES,
        canal_change=charts.canal_change_vs_baseline(METRICS),
        height=360,
    )


def view_table(route, span):
    """
    The searchable table. Also the accessibility fallback: three of the
    palette hues sit below the 3:1 contrast threshold, and an exact-values
    table is the required relief so nothing is readable only by colour.
    """
    data = _window(METRICS, span)
    data = data[data["portname"] == route]
    view = data[
        ["date", "portname", "n_total", "n_total_ref", "n_total_pct_change",
         "mean_vessel_size", "is_outlier"]
    ].copy()
    view["date"] = view["date"].dt.strftime("%Y-%m-%d")
    view["n_total_ref"] = view["n_total_ref"].round(1)
    view["n_total_pct_change"] = (view["n_total_pct_change"] * 100).round(1)
    view["mean_vessel_size"] = view["mean_vessel_size"].round(0)
    view = view.rename(
        columns={
            "date": "Date",
            "portname": "Route",
            "n_total": "Ships",
            "n_total_ref": "Normal",
            "n_total_pct_change": "% vs normal",
            "mean_vessel_size": "Mean vessel size",
            "is_outlier": "Flagged",
        }
    )
    return pn.widgets.Tabulator(
        view.sort_values("Date", ascending=False),
        pagination="remote",
        page_size=12,
        header_filters=True,
        show_index=False,
        sizing_mode="stretch_width",
        height=430,
    )


# --------------------------------------------------------------------------
# The brush: select a period on the timeline, get it scored
# --------------------------------------------------------------------------

brush_summary = pn.pane.Markdown(
    "**Drag left-to-right across the timeline above** to score your own period "
    "against the seasonal baseline.",
    styles={"font-size": "14px"},
)

timeline_dmap = hv.DynamicMap(
    pn.bind(view_timeline, compare_routes, measure, date_range)
)
brush = hv.streams.BoundsX(source=timeline_dmap, boundsx=None)


def score_window(boundsx) -> str:
    """Recompute the headline numbers for whatever the user dragged over."""
    if not boundsx:
        return (
            "**Drag left-to-right across the timeline above** to score your own "
            "period against the seasonal baseline."
        )

    start, end = (pd.Timestamp(b) for b in sorted(boundsx))
    column = measure.value
    picked = METRICS[
        METRICS["portname"].isin(compare_routes.value)
        & (METRICS["date"] >= start)
        & (METRICS["date"] <= end)
    ]
    if picked.empty:
        return "_Nothing in that window._"

    lines = [
        f"### Your selected period: {start:%d %b %Y} to {end:%d %b %Y}  "
        f"({(end - start).days + 1} days)",
        "",
        "| Route | Average | Seasonal normal | Difference |",
        "|---|---:|---:|---:|",
    ]
    for route in [r for r in charts.CHOKEPOINT_COLOURS if r in compare_routes.value]:
        one = picked[picked["portname"] == route]
        if one.empty:
            continue
        actual = one[column].mean()
        normal = one[f"{column}_ref"].mean()
        change = (actual / normal - 1) * 100 if normal else float("nan")
        lines.append(
            f"| {route} | {actual:,.1f} | {normal:,.1f} | **{change:+.1f}%** |"
        )
    lines += [
        "",
        f"_Baseline = the same calendar days averaged over "
        f"{REFERENCE_START} to {REFERENCE_END}._",
    ]
    return "\n".join(lines)


def _on_brush(boundsx):
    brush_summary.object = score_window(boundsx)


brush.add_subscriber(_on_brush)
# Re-score when the measure or the route list changes, so the panel never
# shows numbers that belong to a different measure than the chart above it.
measure.param.watch(lambda _: _on_brush(brush.boundsx), "value")
compare_routes.param.watch(lambda _: _on_brush(brush.boundsx), "value")


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------


def heading(text: str, question: str) -> pn.pane.Markdown:
    """A section title plus the research question it answers."""
    return pn.pane.Markdown(
        f"### {text}\n<span style='color:{charts.INK_MUTED}'>{question}</span>",
        styles={"margin-bottom": "0"},
    )


intro = pn.pane.Markdown(
    f"""
# Chokepoint Lens

Daily ship transits through 28 maritime chokepoints, 1 January 2019 to
{LAST_DAY:%d %B %Y}, measured from satellite AIS tracking.

Every number on this page is compared against a **seasonal baseline**: what was
normal for *that chokepoint on that calendar day*, averaged over
{REFERENCE_START} to {REFERENCE_END} — the last clean stretch before the
regional conflict began. 2020 and 2021 are deliberately excluded: the pandemic
collapse, the shipping boom and the Ever Given grounding would all make
"normal" meaningless.

**RQ1** How did traffic redistribute during the Red Sea crisis, and how complete
is the recovery? &nbsp;·&nbsp; **RQ2** Which vessel segments left first, and which
came back? &nbsp;·&nbsp; **RQ3** Does canal traffic reach Egypt's ports?

*Source: [IMF PortWatch](https://portwatch.imf.org/) (IMF / University of Oxford),
from UN Global Platform AIS data.*
"""
)

sidebar = pn.Column(
    pn.pane.Markdown("## Controls"),
    focus_route,
    compare_routes,
    measure,
    date_range,
    pn.layout.Divider(),
    map_day,
    normalise,
    pn.layout.Divider(),
    pn.pane.Markdown(
        f"<span style='font-size:12px;color:{charts.INK_MUTED}'>"
        "Charts share a fixed colour per route, so filtering never repaints "
        "the routes that remain.</span>"
    ),
)

main = pn.Column(
    intro,
    pn.layout.Divider(),

    heading("Where the traffic went", "RQ1 — one day across all 28 chokepoints"),
    pn.Row(
        pn.panel(pn.bind(view_map, map_day)),
        pn.panel(pn.bind(view_heatmap, compare_routes)),
    ),
    pn.layout.Divider(),

    heading("How it changed", "RQ1 — drag across the chart to score your own period"),
    pn.panel(timeline_dmap),
    brush_summary,
    pn.layout.Divider(),

    heading("The focus route against its seasonal normal", "RQ1 — the grey band is the gap"),
    pn.panel(pn.bind(view_focus, focus_route, measure, date_range)),
    pn.layout.Divider(),

    heading("What kind of ships", "RQ2 — which segments left, and which returned"),
    pn.Row(
        pn.panel(pn.bind(view_composition, focus_route, date_range, normalise)),
        pn.panel(pn.bind(view_substitution, date_range)),
    ),
    pn.layout.Divider(),

    heading("The numbers", "search and sort the underlying daily data"),
    pn.panel(pn.bind(view_table, focus_route, date_range)),
)

if HAS_PORTS:
    main.extend(
        [
            pn.layout.Divider(),
            heading(
                "Does the canal's loss reach Egypt's ports?",
                "RQ3 — 9 active Egyptian ports against the canal's own change",
            ),
            pn.pane.Markdown(
                "The three lines below are rebased so each one's own pre-crisis "
                "average equals 100, which is what lets transits, port calls and "
                "tonnes share a single axis honestly. If canal traffic drove port "
                "activity, they would move together.",
                styles={"font-size": "14px", "color": charts.INK_MUTED},
            ),
            pn.panel(pn.bind(view_divergence, date_range)),
            pn.panel(view_port_changes),
            pn.pane.Markdown(
                f"<span style='font-size:12px;color:{charts.INK_MUTED}'>"
                "Four of Egypt's 13 ports are left out: Ras Gharib and Ras Shukheir "
                "record no calls at all across the whole period, and Zeit Bay and the "
                "Egyptian LNG Terminal average under 0.1 calls a day, where one extra "
                "ship in a year reads as a triple-digit swing.</span>"
            ),
        ]
    )

template = pn.template.FastListTemplate(
    title="Chokepoint Lens — Suez Canal traffic against its seasonal normal",
    sidebar=[sidebar],
    main=[main],
    accent_base_color=ACCENT,
    header_background=ACCENT,
    sidebar_width=330,
    theme_toggle=False,  # the palette is validated for the light surface only
)

template.servable()
