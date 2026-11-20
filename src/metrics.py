"""
Step 3 of the pipeline: turn clean counts into analytical measures.

prepare.py gave us tidy daily numbers. This file answers the actual
questions, and it is where the dashboard earns its keep. Every public
chokepoint tracker shows raw daily transits. None of them answers
"is this number normal for this time of year?" -- which is the question
an analyst actually has.

The four measures built here:

  1. SMOOTHED SERIES. Daily counts are jumpy (weekends, weather, a
     convoy arriving a day late). A 7-day centred average removes that
     noise without shifting the timing of real events.

  2. SEASONAL BASELINE. For each chokepoint and each calendar day, what
     was normal before the crisis? Comparing 3 March against previous
     3 Marches, not against a flat yearly average, is the difference
     between "traffic is down 12%" and "traffic is down 12% *for March*".

  3. DEVIATION FROM BASELINE. Each day as a percentage above or below
     its own seasonal normal. This is what the map colours by.

  4. SUBSTITUTION RATIO. Suez's share of Suez-plus-the-detour. One
     number that captures rerouting: if ships moved to the Cape, this
     falls, even if total world traffic changed too.

----------------------------------------------------------------------
WHY THE REFERENCE WINDOW STARTS IN 2022
----------------------------------------------------------------------
We define "normal" as 1 January 2022 to 6 October 2023, and we exclude
everything before it. Three reasons, all defensible out loud:

  - 2020 was distorted by the pandemic collapse in trade.
  - 2021 held both the post-pandemic shipping boom and the Ever Given
    grounding, which shut the canal for six days in March 2021. Averaging
    that in would make "normal" meaningless.
  - 6 October 2023 is the day before the regional conflict began, so it
    is the last clean day.

The World Bank's own Red Sea study drew the line in the same place, for
the same reason. Being able to explain *why* you excluded two years of
available data is a better answer than having used all of it.

----------------------------------------------------------------------
A HONEST LIMITATION, WORTH STATING IN YOUR DEFENCE
----------------------------------------------------------------------
The reference window is 1 year and 9 months long, not a round 2 years.
So calendar days from 1 January to 6 October appear in it twice (2022 and
2023), but days from 7 October to 31 December appear only once (2022).
The baseline for that late-year stretch therefore rests on a single
observation per day and is noisier.

We do two things about it rather than hiding it: we smooth the baseline
across neighbouring calendar days (so one odd day cannot distort it), and
we record the observation count per day in the output, so the dashboard
can show where the baseline is thin.

Usage
-----
    python src/metrics.py
    python src/metrics.py --summary
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# --- the reference window that defines "normal" (see note above) ---
REFERENCE_START = "2022-01-01"
REFERENCE_END = "2023-10-06"

# --- columns we build measures for ---
VALUE_COLUMNS = ["n_total", "n_cargo", "n_tanker", "capacity", "mean_vessel_size"]

# --- dates worth drawing a line on in the time series ---
EVENTS: dict[str, str] = {
    "Ever Given blocks the canal": "2021-03-23",
    "Regional conflict begins": "2023-10-07",
    "Red Sea diversions begin": "2023-11-17",
}

# --- periods for the comparison table. None = "up to the last day of data" ---
PERIODS: dict[str, tuple[str, str | None]] = {
    "Baseline (2022-01 to 2023-10)": (REFERENCE_START, REFERENCE_END),
    "Conflict onset": ("2023-10-07", "2023-11-16"),
    "Acute crisis": ("2023-11-17", "2024-06-30"),
    "Since mid-2024": ("2024-07-01", None),
}

SMOOTH_WINDOW = 7  # days, centred: one full week removes the weekday cycle
BASELINE_SMOOTH_DAYS = 15  # +/- days of calendar smoothing on the baseline


# --------------------------------------------------------------------------
# 1. Smoothing
# --------------------------------------------------------------------------


def add_smoothed(df: pd.DataFrame, columns: list[str] | None = None, window: int = SMOOTH_WINDOW) -> pd.DataFrame:
    """
    Add a 7-day centred rolling average of each value column.

    `center=True` matters: a trailing average would push every event a few
    days later than it really happened, which would be a lie on a chart
    with event markers on it. `min_periods` lets the first and last few
    days still get a value instead of becoming blank.
    """
    columns = columns or VALUE_COLUMNS
    df = df.sort_values(["portname", "date"]).copy()

    for column in columns:
        df[f"{column}_smooth"] = df.groupby("portname", observed=True)[column].transform(
            lambda s: s.rolling(window, center=True, min_periods=window // 2).mean()
        )
    return df


# --------------------------------------------------------------------------
# 2. Seasonal baseline
# --------------------------------------------------------------------------


def _smooth_around_the_year(frame: pd.DataFrame, columns: list[str], days: int) -> pd.DataFrame:
    """
    Average each calendar day with its neighbours, wrapping at New Year.

    The trick is to stack three copies of the year and roll across the
    middle one. That way 1 January is smoothed using late December as
    well as early January, instead of having nothing on its left.
    """
    frame = frame.sort_index()  # index is the month-day string, which sorts correctly
    size = len(frame)
    out = frame.copy()

    for column in columns:
        tripled = pd.concat([frame[column]] * 3, ignore_index=True)
        rolled = tripled.rolling(2 * days + 1, center=True, min_periods=1).mean()
        out[column] = rolled.iloc[size : 2 * size].to_numpy()
    return out


def seasonal_baseline(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    start: str = REFERENCE_START,
    end: str = REFERENCE_END,
    smooth_days: int = BASELINE_SMOOTH_DAYS,
) -> pd.DataFrame:
    """
    Build the "what is normal for this date" table.

    Returns one row per chokepoint per calendar day (month-day), holding
    the expected value of each column plus `baseline_n_years`, the number
    of observations that day's figure rests on.
    """
    columns = columns or VALUE_COLUMNS
    window = df[(df["date"] >= start) & (df["date"] <= end)]
    if window.empty:
        raise ValueError(f"no rows between {start} and {end}; check the date range")

    # Every calendar day that appears anywhere in the data, so that 29
    # February gets a row even though the reference window has no leap day.
    all_md = sorted(df["md"].unique())

    pieces = []
    for portname, group in window.groupby("portname", observed=True):
        by_day = group.groupby("md", observed=True)[columns].mean()
        counts = group.groupby("md", observed=True)[columns[0]].size().rename("baseline_n_years")

        # Reindex onto the full calendar. Missing days (29 Feb) become NaN
        # and are then filled by the neighbour smoothing below.
        by_day = by_day.reindex(all_md)
        by_day = _smooth_around_the_year(by_day, columns, smooth_days)

        by_day["baseline_n_years"] = counts.reindex(all_md).fillna(0).astype("int16")
        by_day["portname"] = portname
        pieces.append(by_day.rename_axis("md").reset_index())

    baseline = pd.concat(pieces, ignore_index=True)
    return baseline.rename(columns={c: f"{c}_ref" for c in columns})


def add_deviation(df: pd.DataFrame, baseline: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """
    Join the baseline on (chokepoint, calendar day) and express each day as
    a percentage above or below its seasonal normal.

    We deviate from the *smoothed* series, not the raw one, so a single
    quiet Sunday does not read as a crisis.
    """
    columns = columns or VALUE_COLUMNS
    merged = df.merge(baseline, on=["portname", "md"], how="left", validate="m:1")

    for column in columns:
        reference = merged[f"{column}_ref"]
        actual = merged.get(f"{column}_smooth", merged[column])
        # Guard the division: a baseline of zero would give infinity.
        merged[f"{column}_pct_change"] = ((actual - reference) / reference).where(reference > 0)
        merged[f"{column}_index"] = (actual / reference).where(reference > 0) * 100

    return merged


# --------------------------------------------------------------------------
# 3. Substitution ratio
# --------------------------------------------------------------------------


def substitution_ratio(
    df: pd.DataFrame,
    route: str = "Suez Canal",
    alternative: str = "Cape of Good Hope",
    column: str = "n_total_smooth",
) -> pd.DataFrame:
    """
    Suez's share of (Suez + the long way round), per day.

    This is the cleanest single measure of rerouting. A fall means traffic
    moved to the detour, and because it is a share it is not confused by
    world trade growing or shrinking overall.
    """
    pair = df[df["portname"].isin([route, alternative])]
    wide = pair.pivot_table(index="date", columns="portname", values=column, aggfunc="mean")
    if route not in wide or alternative not in wide:
        raise KeyError(f"need both {route!r} and {alternative!r} in the data")

    total = wide[route] + wide[alternative]
    result = pd.DataFrame(
        {
            "date": wide.index,
            route: wide[route].to_numpy(),
            alternative: wide[alternative].to_numpy(),
            "suez_share": (wide[route] / total).where(total > 0).to_numpy(),
        }
    )
    return result.reset_index(drop=True)


# --------------------------------------------------------------------------
# 4. Period comparison table
# --------------------------------------------------------------------------


def period_table(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    periods: dict[str, tuple[str, str | None]] | None = None,
    chokepoints: list[str] | None = None,
) -> pd.DataFrame:
    """
    Average each column over each named period, and express every later
    period as a percentage change from the first one.

    This is the table behind the dashboard's comparison heatmap, and it is
    also the clearest thing to put on a slide.
    """
    columns = columns or ["n_total", "capacity", "mean_vessel_size"]
    periods = periods or PERIODS
    data = df if chokepoints is None else df[df["portname"].isin(chokepoints)]
    last_day = data["date"].max()

    rows = []
    for label, (start, end) in periods.items():
        stop = pd.Timestamp(end) if end else last_day
        window = data[(data["date"] >= pd.Timestamp(start)) & (data["date"] <= stop)]
        means = window.groupby("portname", observed=True)[columns].mean()
        means = means.assign(period=label, days=window.groupby("portname", observed=True).size())
        rows.append(means.reset_index())

    table = pd.concat(rows, ignore_index=True)

    # percentage change against the first period listed
    first_label = next(iter(periods))
    reference = table[table["period"] == first_label].set_index("portname")[columns]
    for column in columns:
        table[f"{column}_vs_baseline"] = (
            table[column] / table["portname"].map(reference[column]) - 1
        )

    ordered = list(periods)
    table["period"] = pd.Categorical(table["period"], categories=ordered, ordered=True)
    return table.sort_values(["portname", "period"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# 5. Canal versus Egypt's ports  (RQ3)
# --------------------------------------------------------------------------


def port_change_table(
    ports: pd.DataFrame,
    baseline: tuple[str, str] = (REFERENCE_START, REFERENCE_END),
    since: str = "2024-07-01",
    active_only: bool = True,
) -> pd.DataFrame:
    """
    Per Egyptian port: average activity before the crisis, average since, and
    the change between them -- in both ship calls and tonnage.

    Both measures, because they can disagree and the disagreement is the
    finding. A port can take fewer ships while moving more cargo, which says
    the ships calling there got bigger, not that the port got quieter.
    """
    data = ports[ports["is_active"]] if active_only else ports
    before = data[(data["date"] >= baseline[0]) & (data["date"] <= baseline[1])]
    after = data[data["date"] >= pd.Timestamp(since)]

    rows = []
    for name, group in data.groupby("portname", observed=True):
        b = before[before["portname"] == name]
        a = after[after["portname"] == name]
        if b.empty or a.empty:
            continue
        calls_b, calls_a = b["portcalls"].mean(), a["portcalls"].mean()
        trade_b, trade_a = b["trade"].mean(), a["trade"].mean()
        rows.append(
            {
                "portname": name,
                "role": group["role"].iloc[0],
                "calls_before": calls_b,
                "calls_after": calls_a,
                "calls_change": (calls_a / calls_b - 1) if calls_b else float("nan"),
                "trade_before": trade_b,
                "trade_after": trade_a,
                "trade_change": (trade_a / trade_b - 1) if trade_b else float("nan"),
            }
        )
    table = pd.DataFrame(rows)
    return table.sort_values("calls_change").reset_index(drop=True)


def canal_vs_ports(
    metrics: pd.DataFrame,
    ports: pd.DataFrame,
    route: str = "Suez Canal",
    baseline: tuple[str, str] = (REFERENCE_START, REFERENCE_END),
    active_only: bool = True,
) -> pd.DataFrame:
    """
    Three monthly series on one scale: canal transits, Egyptian port calls,
    and Egyptian seaborne tonnage -- each indexed so that its own pre-crisis
    average equals 100.

    Indexing is what makes this one chart instead of three. Transits, calls
    and tonnes have nothing in common as units, and putting them on separate
    y-axes would invite the reader to read the crossings as meaningful when
    they would be an artefact of axis placement. Rebased to a common 100,
    they are directly comparable and a single axis is honest.
    """
    canal = metrics[metrics["portname"] == route]
    active = ports[ports["is_active"]] if active_only else ports

    monthly = {
        "Canal transits": canal.set_index("date")["n_total"].resample("MS").mean(),
        "Egyptian port calls": active.groupby("date")["portcalls"].sum().resample("MS").mean(),
        "Egyptian trade (tonnes)": active.groupby("date")["trade"].sum().resample("MS").mean(),
    }

    frames = []
    start, end = pd.Timestamp(baseline[0]), pd.Timestamp(baseline[1])
    for label, series in monthly.items():
        reference = series[(series.index >= start) & (series.index <= end)].mean()
        if not reference:
            continue
        frames.append(
            pd.DataFrame(
                {
                    "date": series.index,
                    "series": label,
                    "value": series.to_numpy(),
                    "index": series.to_numpy() / reference * 100,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


# --------------------------------------------------------------------------
# Build everything
# --------------------------------------------------------------------------


def build(verbose: bool = True) -> pd.DataFrame:
    """Run the whole chain and save data/processed/chokepoints_metrics.parquet."""
    source = PROCESSED_DIR / "chokepoints_daily.parquet"
    if not source.exists():
        raise FileNotFoundError(f"{source} not found. Run:  python src/prepare.py")

    df = pd.read_parquet(source)
    if verbose:
        print(f"loaded {len(df):,} rows, {df['portname'].nunique()} chokepoints")

    df = add_smoothed(df)
    baseline = seasonal_baseline(df)
    if verbose:
        thin = int((baseline["baseline_n_years"] < 2).sum())
        print(f"baseline built: {len(baseline):,} chokepoint-days "
              f"({thin:,} rest on fewer than 2 observations)")

    df = add_deviation(df, baseline)
    df = df.sort_values(["portname", "date"]).reset_index(drop=True)

    out = PROCESSED_DIR / "chokepoints_metrics.parquet"
    df.to_parquet(out, index=False)
    if verbose:
        print(f"saved {out.name} ({len(df):,} rows, {len(df.columns)} columns)")

    ratio = substitution_ratio(df)
    ratio_out = PROCESSED_DIR / "suez_substitution.parquet"
    ratio.to_parquet(ratio_out, index=False)
    if verbose:
        print(f"saved {ratio_out.name} ({len(ratio):,} rows)")

    # ---- RQ3: the canal against Egypt's own ports ----
    ports_path = PROCESSED_DIR / "ports_daily.parquet"
    if ports_path.exists():
        ports = pd.read_parquet(ports_path)

        changes = port_change_table(ports)
        changes_out = PROCESSED_DIR / "port_changes.parquet"
        changes.to_parquet(changes_out, index=False)

        divergence = canal_vs_ports(df, ports)
        divergence_out = PROCESSED_DIR / "canal_vs_ports.parquet"
        divergence.to_parquet(divergence_out, index=False)

        if verbose:
            print(f"saved {changes_out.name} ({len(changes)} active ports)")
            print(f"saved {divergence_out.name} ({len(divergence):,} rows)")
    elif verbose:
        print("ports_daily.parquet not found - skipping RQ3 measures")

    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Build analytical measures from the clean data.")
    parser.add_argument("--summary", action="store_true", help="also print the period comparison table")
    args = parser.parse_args()

    df = build()

    if args.summary:
        focus = ["Suez Canal", "Bab el-Mandeb Strait", "Cape of Good Hope"]
        table = period_table(df, chokepoints=focus)
        pd.set_option("display.width", 200)
        print("\n--- average ships per day, and change from baseline ---")
        view = table.pivot(index="period", columns="portname", values="n_total").round(1)
        print(view.to_string())
        print("\n--- as % of baseline ---")
        pct = table.pivot(index="period", columns="portname", values="n_total_vs_baseline")
        print((pct * 100).round(1).to_string())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
