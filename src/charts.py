"""
Step 4: the views. One function per chart, each returning a HoloViews object.

Why functions that return objects rather than code that draws things: you can
call any of these from a notebook to develop it on its own, and app.py can
call the identical function to put it in the dashboard. No copy-paste between
prototype and product.

----------------------------------------------------------------------
THE FOUR VIEWS, AND WHY EACH CHART TYPE
----------------------------------------------------------------------
Every chart here is answerable to one of your research questions, and the
*type* is chosen for the data's job, not for variety. You will be asked to
justify these, so the reasoning is written next to each one.

  1. chokepoint_map       (RQ1) - where traffic moved. Geographic position
                                  is the thing the user reasons about, and
                                  position is the strongest visual channel
                                  there is, so a map beats any ranked list.
  2. transit_timeline     (RQ1) - change over time against a seasonal
                                  normal. A line chart is right for a dense
                                  daily series; the baseline band is what no
                                  other chokepoint tracker shows.
  3. composition_area     (RQ2) - which vessel segments left and returned.
                                  A 100% stacked area reads composition
                                  change continuously across 2,876 days,
                                  where grouped bars would be unreadable.
  4. period_heatmap       (RQ1/2) - a matrix of chokepoint x period. A
                                  heatmap is the form for "many cells, each
                                  one signed", and it is the target of the
                                  brush interaction in app.py.

----------------------------------------------------------------------
COLOUR RULES THIS FILE OBEYS
----------------------------------------------------------------------
  - Colour follows the entity, not its rank. Suez is always blue, whether
    it is the only series on screen or one of eight. A filter that drops a
    chokepoint must never repaint the survivors, because the reader's memory
    of "blue = Suez" is part of the chart.
  - Categorical hues are assigned in a fixed, validated order and never
    cycled. The order below was checked for colour-vision-deficiency
    separation rather than chosen by eye.
  - Deviation is a *signed* quantity, so it gets a diverging scale: two
    opposing hues with a neutral grey at zero. Never a rainbow, and never a
    coloured midpoint -- zero has to look like nothing.
  - No chart here has two y-axes. Two measures on different scales go in
    two charts, which is why the substitution ratio is its own view.

Usage
-----
    python src/charts.py            # renders every view to docs/preview.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import holoviews as hv
import numpy as np
import pandas as pd
from holoviews import dim

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DOCS_DIR = PROJECT_ROOT / "docs"

# src/ is not an installed package, so make sibling modules importable
# whether we are run as a script or imported by app.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import EVENTS, PERIODS, period_table  # noqa: E402

hv.extension("bokeh")


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
# Validated for colour-vision deficiency and for contrast against the chart
# surface. Do not reorder casually: the ORDER is the safety mechanism, since
# neighbouring slots are the ones a reader has to tell apart.

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#6250d6",  # 7 violet
    "#e34948",  # 8 red
]

# Fixed entity -> colour map. Suez is slot 1 because it is the subject of the
# project; its two alternatives take slots 2 and 3 so the three-way comparison
# uses the trio that separates best under colour-blind simulation.
CHOKEPOINT_COLOURS: dict[str, str] = {
    "Suez Canal": SERIES[0],
    "Bab el-Mandeb Strait": SERIES[1],
    "Cape of Good Hope": SERIES[2],
    "Panama Canal": SERIES[3],
    "Strait of Hormuz": SERIES[4],
    "Malacca Strait": SERIES[5],
    "Bosporus Strait": SERIES[6],
    "Gibraltar Strait": SERIES[7],
}
OTHER_COLOUR = "#898781"  # anything outside the fixed map reads as "other"

# Vessel types, in the order they stack. Fixed, for the same reason.
VESSEL_ORDER = ["container", "dry_bulk", "general_cargo", "roro", "tanker"]
VESSEL_LABELS = {
    "container": "Container",
    "dry_bulk": "Dry bulk",
    "general_cargo": "General cargo",
    "roro": "Ro-Ro",
    "tanker": "Tanker",
}
VESSEL_COLOURS = dict(zip(VESSEL_ORDER, SERIES[:5]))

# Diverging scale for deviation-from-normal: red = below normal, grey = normal,
# blue = above normal. Equal steps per arm, neutral grey at the midpoint.
DIVERGING = [
    "#8c1d1d", "#b82f2f", "#d03b3b", "#e67a7a", "#f6c9c9",
    "#f0efec",
    "#b7d3f6", "#86b6ef", "#3987e5", "#256abf", "#104281",
]


def colour_for(chokepoint: str) -> str:
    """Stable colour for a chokepoint, whatever else is on screen."""
    return CHOKEPOINT_COLOURS.get(chokepoint, OTHER_COLOUR)


# Basemap behind the map view.
#
# This used to be CartoDB's "light_all" (geoviews' CartoLight). CartoDB has
# since put those tiles behind an API key, and an unkeyed request now returns
# a grey tile stamped "API KEY REQUIRED" -- so the map silently degrades into
# a watermark instead of failing loudly. Esri's light grey canvas is the
# closest free equivalent and is purpose-built as a neutral backdrop for
# data, which is what a basemap should be.
#
# A basemap is a third-party service and its terms can change without
# warning, so this is one named constant rather than a buried string. To see
# the alternatives:
#     python -c "import geoviews as gv; print(sorted(gv.tile_sources.tile_sources))"
# Bokeh recognises the provider from the URL and prints the required
# attribution in the corner of the map automatically.
BASEMAP = "EsriWorldLightGrayBase"


def _sizing(width: int | None, height: int) -> dict:
    """
    Fixed pixel width, or stretch to fill the container when width is None.

    The dashboard passes None so every chart fits whatever column it lands
    in; a hard-coded width silently overflows and clips the legend off the
    right-hand edge. The standalone preview passes real numbers, because a
    saved HTML file has no container to stretch into.
    """
    if width is None:
        return {"responsive": True, "height": height}
    return {"width": width, "height": height}


# --------------------------------------------------------------------------
# Shared look
# --------------------------------------------------------------------------


def apply_theme() -> None:
    """
    Set the house style once, so every chart matches without repeating opts.

    Grid and axes are deliberately recessive: they are scaffolding, and any
    ink spent on them is ink competing with the data.
    """
    # shared_axes=False everywhere: HoloViews links the axes of every plot
    # placed side by side, so without this one busy route squashes every
    # other panel into the bottom of its frame.
    hv.opts.defaults(
        hv.opts.Curve(
            line_width=2,
            shared_axes=False,
            gridstyle={"grid_line_color": GRID, "grid_line_width": 1},
            show_grid=True,
            fontsize={"title": 13, "labels": 11, "ticks": 10, "legend": 10},
            toolbar="above",
            backend_opts={
                "plot.background_fill_color": SURFACE,
                "plot.border_fill_color": SURFACE,
                "plot.outline_line_color": None,
            },
        ),
        hv.opts.Area(
            line_width=1.5,
            shared_axes=False,
            line_color=SURFACE,  # a 1.5px surface-coloured gap between fills
            fontsize={"title": 13, "labels": 11, "ticks": 10, "legend": 10},
        ),
        hv.opts.HeatMap(
            shared_axes=False,
            fontsize={"title": 13, "labels": 11, "ticks": 10},
            xrotation=25,
            colorbar=True,
            line_color=SURFACE,
            line_width=2,
        ),
        hv.opts.Points(
            shared_axes=False,
            fontsize={"title": 13, "labels": 11, "ticks": 10},
        ),
        hv.opts.Overlay(
            shared_axes=False,
            legend_position="right",
            fontsize={"title": 13, "labels": 11, "ticks": 10, "legend": 10},
        ),
    )


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load(name: str) -> pd.DataFrame:
    """Read one processed parquet file by short name."""
    path = PROCESSED_DIR / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found.\nRun:  python src/prepare.py  then  python src/metrics.py"
        )
    return pd.read_parquet(path)


# --------------------------------------------------------------------------
# View 1: the map  (RQ1)
# --------------------------------------------------------------------------


def chokepoint_map(
    metrics: pd.DataFrame,
    meta: pd.DataFrame,
    as_of: str | pd.Timestamp | None = None,
    width: int | None = None,
    height: int = 380,
):
    """
    World map of all 28 chokepoints on one day.

    Two encodings, doing two different jobs:
      - SIZE   = how much traffic (magnitude). Area-proportional, so we take
                 the square root of the value; sizing by raw diameter would
                 exaggerate big values roughly fourfold.
      - COLOUR = how far from normal (signed), on the diverging scale.

    Reading it: a big red circle is a busy route running well below its own
    seasonal normal, which is exactly the Suez story. A big blue one is a
    route absorbing diverted traffic.
    """
    import cartopy.crs as ccrs
    import geoviews as gv

    as_of = pd.Timestamp(as_of) if as_of is not None else metrics["date"].max()
    day = metrics[metrics["date"] == as_of]
    if day.empty:
        raise ValueError(f"no rows for {as_of:%Y-%m-%d}")

    frame = day.merge(meta[["portname", "lat", "lon"]], on="portname", how="inner").copy()
    frame["pct"] = frame["n_total_pct_change"] * 100
    frame["ships"] = frame["n_total_smooth"].round(1)
    frame["normal"] = frame["n_total_ref"].round(1)

    points = gv.Points(
        frame,
        kdims=["lon", "lat"],
        vdims=["portname", "ships", "normal", "pct"],
        crs=ccrs.PlateCarree(),
    ).opts(
        size=dim("ships") ** 0.5 * 2.6,
        color="pct",
        cmap=DIVERGING,
        clim=(-100, 100),
        colorbar=True,
        colorbar_opts={"title": "% vs normal"},
        line_color=SURFACE,
        line_width=1.5,
        alpha=0.9,
        tools=["hover", "tap"],
        hover_tooltips=[
            ("Chokepoint", "@portname"),
            ("Ships/day (7d)", "@ships"),
            ("Normal for this date", "@normal"),
            ("Difference", "@pct{0.0}%"),
        ],
        **_sizing(width, height),
        title=f"Traffic against its seasonal normal, {as_of:%d %B %Y}",
        xaxis=None,
        yaxis=None,
    )

    # global_extent keeps the whole world in frame. Without it the view
    # auto-fits to the points and the framing jumps around as the day
    # changes, which makes the map hard to read as an animation.
    # clone=True because the registry hands back a shared object; styling it
    # in place would quietly alter the basemap for every other caller.
    basemap = gv.tile_sources.tile_sources[BASEMAP].opts(alpha=0.7, clone=True)
    return (basemap * points).opts(global_extent=True, shared_axes=False)


# --------------------------------------------------------------------------
# View 2: the timeline  (RQ1)
# --------------------------------------------------------------------------


def transit_timeline(
    metrics: pd.DataFrame,
    chokepoints: list[str] | None = None,
    value: str = "n_total",
    show_events: bool = True,
    width: int | None = None,
    height: int = 320,
):
    """
    Daily transits over time, with event markers and -- when a single
    chokepoint is selected -- the seasonal normal drawn behind it.

    The band only appears for one chokepoint on purpose. With three series
    plus three baselines the chart becomes six lines and reads as noise; the
    comparison view and the focus view want different things on screen.

    We plot the 7-day *centred* average, not raw counts. Centred matters: a
    trailing average would shift every event later than it happened, which
    would be a lie on a chart that has event markers drawn on it.
    """
    chokepoints = chokepoints or ["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope"]
    # iterate in the fixed palette order, not the order the user clicked, so
    # the legend and colours are stable between interactions
    ordered = [c for c in CHOKEPOINT_COLOURS if c in chokepoints]
    ordered += [c for c in chokepoints if c not in CHOKEPOINT_COLOURS]

    data = metrics[metrics["portname"].isin(ordered)]
    if data.empty:
        raise ValueError(f"no rows for {chokepoints}")

    layers = []

    # the seasonal normal, as a filled band, only in single-chokepoint mode
    if len(ordered) == 1:
        one = data.sort_values("date")
        band = hv.Area(
            one, "date", [f"{value}_smooth", f"{value}_ref"], label="Gap vs normal"
        ).opts(color=INK_MUTED, alpha=0.18, line_width=0)
        normal = hv.Curve(one, "date", f"{value}_ref", label="Seasonal normal").opts(
            color=INK_MUTED, line_dash="dashed", line_width=1.5
        )
        layers += [band, normal]

    for name in ordered:
        one = data[data["portname"] == name].sort_values("date")
        layers.append(
            hv.Curve(one, "date", f"{value}_smooth", label=name).opts(
                color=colour_for(name),
                line_width=2,
                tools=["hover"],
                hover_tooltips=[("Date", "@date{%F}"), (name, f"@{value}_smooth{{0.0}}")],
                hover_formatters={"@date": "datetime"},
            )
        )

    if show_events:
        for label, when in EVENTS.items():
            moment = pd.Timestamp(when)
            if data["date"].min() <= moment <= data["date"].max():
                layers.append(
                    hv.VLine(moment).opts(color=INK_MUTED, line_dash="dotted", line_width=1.5)
                )

    subject = ordered[0] if len(ordered) == 1 else f"{len(ordered)} routes"
    overlay = hv.Overlay(layers).opts(
        **_sizing(width, height),
        show_grid=True,
        legend_position="right",
        title=f"{subject}: ships per day, 7-day average",
        ylabel="ships per day",
        xlabel="",
        # Each chart scales to its own data. Without this, HoloViews links
        # the y-axes of every plot in a layout, so a single busy route
        # squashes every other panel into the bottom third of its frame.
        shared_axes=False,
    )
    return overlay


# --------------------------------------------------------------------------
# View 3: vessel composition  (RQ2)
# --------------------------------------------------------------------------


def composition_area(
    long_df: pd.DataFrame,
    chokepoint: str = "Suez Canal",
    smooth_days: int = 28,
    normalise: bool = True,
    width: int | None = None,
    height: int = 300,
):
    """
    How the mix of vessel types changed, as a 100% stacked area.

    Normalised to shares by default, because the question for RQ2 is "which
    segments left", and a share answers that even while the total collapses.
    Set normalise=False to see absolute counts instead.

    Smoothed over 28 days rather than 7: shares of a small daily count are
    very jumpy, and the question here is about months-long shifts in the mix,
    not about individual days.
    """
    data = long_df[long_df["portname"] == chokepoint].copy()
    if data.empty:
        raise ValueError(f"no rows for {chokepoint!r}")

    if normalise:
        totals = data.groupby("date")["n_vessels"].transform("sum")
        data["value"] = (data["n_vessels"] / totals).where(totals > 0)
    else:
        data["value"] = data["n_vessels"]

    data = data.sort_values(["vessel_type", "date"])
    data["value"] = data.groupby("vessel_type", observed=True)["value"].transform(
        lambda s: s.rolling(smooth_days, center=True, min_periods=smooth_days // 2).mean()
    )

    areas = []
    for vessel in VESSEL_ORDER:
        one = data[data["vessel_type"] == vessel].sort_values("date")
        if one.empty:
            continue
        areas.append(
            hv.Area(one, "date", "value", label=VESSEL_LABELS[vessel]).opts(
                color=VESSEL_COLOURS[vessel],
                line_color=SURFACE,
                line_width=1.5,
            )
        )

    stacked = hv.Area.stack(hv.Overlay(areas)).opts(
        **_sizing(width, height),
        # legend underneath, not beside: this chart often sits in a half-width
        # column, where a side legend would eat a third of the plot area
        legend_position="bottom",
        legend_cols=3,
        title=f"{chokepoint}: what kind of ships, {smooth_days}-day average",
        ylabel="share of traffic" if normalise else "ships per day",
        xlabel="",
        shared_axes=False,
    )
    return stacked


# --------------------------------------------------------------------------
# View 4: period comparison  (RQ1 / RQ2)
# --------------------------------------------------------------------------


def period_heatmap(
    metrics: pd.DataFrame,
    chokepoints: list[str] | None = None,
    value: str = "n_total",
    width: int | None = None,
    height: int = 300,
):
    """
    Chokepoint x period matrix, coloured by change from the baseline period.

    A heatmap is the form for "many signed cells at once". The numbers are
    printed in every cell as well, which is not decoration: three of the
    palette's hues sit below the 3:1 contrast threshold against the chart
    surface, and visible labels are the required relief so the chart never
    depends on colour alone.
    """
    chokepoints = chokepoints or ["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope"]
    table = period_table(metrics, columns=[value], chokepoints=chokepoints)

    # drop the baseline row: it is zero by construction and spends a whole
    # column of the reader's attention saying nothing
    baseline_label = next(iter(PERIODS))
    table = table[table["period"] != baseline_label].copy()
    table["period"] = table["period"].astype(str)
    table["pct"] = table[f"{value}_vs_baseline"] * 100
    table["label"] = table["pct"].map(lambda v: f"{v:+.0f}%")

    # pandas 3 stores text as Arrow-backed strings, which HeatMap's gridded
    # aggregation cannot reshape. Only numeric value dimensions go on the
    # HeatMap; the text sits on the Labels layer, where no reshape happens.
    grid = table[["period", "portname", "pct"]].copy()
    grid["period"] = grid["period"].astype(object)
    grid["portname"] = grid["portname"].astype(object)

    heat = hv.HeatMap(grid, kdims=["period", "portname"], vdims=["pct"]).opts(
        cmap=DIVERGING,
        symmetric=True,
        colorbar=True,
        colorbar_opts={"title": "% vs baseline"},
        line_color=SURFACE,
        line_width=2,
        tools=["hover"],
        hover_tooltips=[
            ("Chokepoint", "@portname"),
            ("Period", "@period"),
            ("Change", "@pct{+0.0}%"),
        ],
        **_sizing(width, height),
        title="Change from the pre-crisis baseline",
        xlabel="",
        ylabel="",
    )

    text = table[["period", "portname", "label"]].copy()
    for column in text.columns:
        text[column] = text[column].astype(object)
    labels = hv.Labels(text, kdims=["period", "portname"], vdims=["label"]).opts(
        text_color=INK, text_font_size="10pt"
    )
    return (heat * labels).opts(**_sizing(width, height))


# --------------------------------------------------------------------------
# Supporting view: the substitution ratio
# --------------------------------------------------------------------------


def substitution_curve(
    ratio: pd.DataFrame,
    width: int | None = None,
    height: int = 220,
):
    """
    Suez's share of (Suez + Cape of Good Hope), as one line.

    This is a separate chart rather than a second axis on the timeline. Two
    y-scales on one frame is the most common chart mistake there is: the
    reader cannot tell which line belongs to which scale, and the apparent
    crossings are an artefact of where you happened to put the axes.
    """
    data = ratio.sort_values("date").copy()
    data["share_pct"] = data["suez_share"] * 100

    line = hv.Curve(data, "date", "share_pct", label="Suez share").opts(
        color=SERIES[0],
        line_width=2,
        tools=["hover"],
        hover_tooltips=[("Date", "@date{%F}"), ("Suez share", "@share_pct{0.0}%")],
        hover_formatters={"@date": "datetime"},
    )
    midline = hv.HLine(50).opts(color=INK_MUTED, line_dash="dotted", line_width=1)

    layers = [line, midline]
    for when in EVENTS.values():
        moment = pd.Timestamp(when)
        if data["date"].min() <= moment <= data["date"].max():
            layers.append(hv.VLine(moment).opts(color=INK_MUTED, line_dash="dotted", line_width=1.5))

    return hv.Overlay(layers).opts(
        **_sizing(width, height),
        show_grid=True,
        title="Share using the canal rather than the Cape",
        ylabel="% via Suez",
        xlabel="",
        ylim=(0, 100),
        legend_position="right",
        shared_axes=False,
    )


# --------------------------------------------------------------------------
# View 5: the canal against Egypt's own ports  (RQ3)
# --------------------------------------------------------------------------

MEASURE_COLOURS = {"calls": SERIES[0], "trade": SERIES[3]}


def canal_vs_ports_chart(
    divergence: pd.DataFrame,
    width: int | None = None,
    height: int = 320,
):
    """
    Canal transits, Egyptian port calls and Egyptian tonnage on one scale.

    Each series is rebased so its own pre-crisis average equals 100. That
    rebasing is what makes this a single chart rather than three: transits,
    port calls and tonnes share no unit, and giving them separate y-axes
    would let the reader read the crossings as meaningful when they would
    be an artefact of where the axes were placed. Indexed to a common 100,
    one axis is both honest and directly comparable.

    The 100 line is the whole point. A series above it is running ahead of
    its own pre-crisis normal; below it, behind. If the canal and the ports
    were coupled, the three lines would move together.
    """
    colours = {
        "Canal transits": SERIES[0],
        "Egyptian port calls": SERIES[1],
        "Egyptian trade (tonnes)": SERIES[2],
    }

    layers = [
        hv.HLine(100).opts(color=INK_MUTED, line_dash="dashed", line_width=1.5)
    ]
    for label, colour in colours.items():
        one = divergence[divergence["series"] == label].sort_values("date")
        if one.empty:
            continue
        layers.append(
            hv.Curve(one, "date", "index", label=label).opts(
                color=colour,
                line_width=2,
                tools=["hover"],
                hover_tooltips=[
                    ("Month", "@date{%b %Y}"),
                    (label, "@index{0.0} (100 = pre-crisis normal)"),
                ],
                hover_formatters={"@date": "datetime"},
            )
        )

    for when in EVENTS.values():
        moment = pd.Timestamp(when)
        if divergence["date"].min() <= moment <= divergence["date"].max():
            layers.append(
                hv.VLine(moment).opts(color=INK_MUTED, line_dash="dotted", line_width=1.5)
            )

    return hv.Overlay(layers).opts(
        **_sizing(width, height),
        show_grid=True,
        legend_position="right",
        title="Canal traffic vs Egypt's ports, each indexed to its own pre-crisis normal",
        ylabel="index (pre-crisis = 100)",
        xlabel="",
        shared_axes=False,
    )


def port_change_dumbbell(
    changes: pd.DataFrame,
    canal_change: float | None = None,
    width: int | None = None,
    height: int = 340,
):
    """
    One row per Egyptian port: how its ship calls and its cargo tonnage
    changed, with the canal's own change drawn as a reference line.

    A dumbbell rather than two bar charts, because the *gap* between the two
    dots is the interesting quantity. A port whose calls fell while tonnage
    rose is not getting quieter -- it is handling bigger ships. Two separate
    bar charts would hide exactly that, since the reader would have to hold
    one chart in memory while reading the other.

    The dashed canal line is what turns this from a list into an argument:
    if Egypt's ports simply followed the canal, the dots would cluster on
    it. Where they sit instead is the answer to RQ3.
    """
    table = changes.dropna(subset=["calls_change", "trade_change"]).copy()
    if table.empty:
        raise ValueError("no ports with both measures available")

    table = table.sort_values("calls_change").reset_index(drop=True)
    # Most negative at the top, so the chart reads as a ranking downwards.
    table["y"] = range(len(table) - 1, -1, -1)
    table["y2"] = table["y"]
    table["calls_pct"] = table["calls_change"] * 100
    table["trade_pct"] = table["trade_change"] * 100
    table["label"] = table["trade_pct"].map(lambda v: f"{v:+.0f}%")

    yticks = [(int(row.y), row.portname) for row in table.itertuples(index=False)]
    span = [table["calls_pct"].min(), table["trade_pct"].min(),
            table["calls_pct"].max(), table["trade_pct"].max()]
    if canal_change is not None:
        span.append(canal_change * 100)
    pad = (max(span) - min(span)) * 0.18 or 10

    connector = hv.Segments(table, ["calls_pct", "y", "trade_pct", "y2"]).opts(
        color=AXIS, line_width=3
    )
    zero = hv.VLine(0).opts(color=INK_MUTED, line_width=1.5)

    layers = [zero, connector]

    if canal_change is not None:
        canal_pct = canal_change * 100
        layers.append(
            hv.VLine(canal_pct).opts(color=SERIES[7], line_dash="dashed", line_width=2)
        )
        layers.append(
            hv.Text(
                canal_pct, len(table) - 0.4, f"  Suez Canal {canal_pct:+.0f}%",
                halign="left", fontsize=10,
            ).opts(color=SERIES[7])
        )

    layers.append(
        hv.Scatter(table, "calls_pct", ["y", "portname", "role"], label="Ship calls").opts(
            color=MEASURE_COLOURS["calls"],
            size=11,
            line_color=SURFACE,
            line_width=1.5,
            tools=["hover"],
            hover_tooltips=[("Port", "@portname"), ("Role", "@role"),
                            ("Change in calls", "@calls_pct{+0.0}%")],
        )
    )
    layers.append(
        hv.Scatter(table, "trade_pct", ["y", "portname", "role"], label="Cargo tonnes").opts(
            color=MEASURE_COLOURS["trade"],
            size=11,
            line_color=SURFACE,
            line_width=1.5,
            tools=["hover"],
            hover_tooltips=[("Port", "@portname"), ("Role", "@role"),
                            ("Change in tonnage", "@trade_pct{+0.0}%")],
        )
    )

    return hv.Overlay(layers).opts(
        **_sizing(width, height),
        yticks=yticks,
        ylim=(-0.8, len(table) - 0.2),
        xlim=(min(span) - pad, max(span) + pad),
        show_grid=True,
        legend_position="bottom",
        title="Egyptian ports since mid-2024, against the 2022–23 baseline",
        xlabel="% change",
        ylabel="",
        shared_axes=False,
    )


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------


def canal_change_vs_baseline(metrics: pd.DataFrame, route: str = "Suez Canal") -> float:
    """The canal's own change from baseline, for the dumbbell's reference line."""
    table = period_table(metrics, columns=["n_total"], chokepoints=[route])
    latest = table.iloc[-1]
    return float(latest["n_total_vs_baseline"])


def build_preview() -> Path:
    """Render every view into one HTML file so you can eyeball them together."""
    apply_theme()

    metrics = load("chokepoints_metrics")
    meta = load("chokepoints_meta")
    long_df = load("chokepoints_long")
    ratio = load("suez_substitution")

    views = [
        ("1. Chokepoint map (RQ1)", chokepoint_map(metrics, meta, width=720)),
        ("2. Timeline, three routes (RQ1)", transit_timeline(metrics, width=820)),
        ("2b. Timeline, Suez alone with its seasonal normal (RQ1)",
         transit_timeline(metrics, ["Suez Canal"], width=820)),
        ("3. Vessel composition at Suez (RQ2)",
         composition_area(long_df, "Suez Canal", width=820)),
        ("4. Period comparison (RQ1/RQ2)", period_heatmap(metrics, width=560)),
        ("5. Substitution ratio", substitution_curve(ratio, width=820)),
        ("6. Canal vs Egypt's ports (RQ3)",
         canal_vs_ports_chart(load("canal_vs_ports"), width=820)),
        ("7. Egyptian ports, port by port (RQ3)",
         port_change_dumbbell(load("port_changes"), canal_change=canal_change_vs_baseline(metrics), width=820)),
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    # shared_axes belongs on the Layout, not on the elements inside it:
    # without it HoloViews ties every panel to one y-range, so the quiet
    # charts get squashed by the busiest one.
    layout = (
        hv.Layout([v.relabel(title) for title, v in views])
        .cols(1)
        .opts(hv.opts.Layout(shared_axes=False))
    )
    out = DOCS_DIR / "preview.html"
    # resources="inline" embeds BokehJS in the file instead of loading it from
    # a CDN. The file gets bigger, but it then opens with no internet at all --
    # worth having on the day you present. (Map tiles still need a connection.)
    hv.save(layout, out, backend="bokeh", resources="inline")
    return out


if __name__ == "__main__":
    path = build_preview()
    print(f"wrote {path}")
