# Chokepoint Lens

**Visualization and Visual Analytics — project work**
**Author:** Elfadel Mohamed  
**Date:** November 2026


An interactive dashboard for reading daily ship traffic through the world's
maritime chokepoints against a **seasonal baseline** — what was normal for that
waterway on that calendar day — with the Suez Canal as its subject.

---

## The problem

Every public chokepoint tracker shows raw daily transit counts. None of them
answers the question an analyst actually has, which is *"is this number normal
for this time of year?"* A quiet week in Suez in August and a quiet week in
March mean different things, and a dashboard that cannot tell them apart cannot
support a decision.

**Target user.** An analyst at the Suez Canal Authority or Egypt's Ministry of
Finance who needs to know whether canal traffic is recovering, which vessel
segments returned first, and whether a given week's dip is a real signal or
ordinary seasonal noise.

## Research questions

- **RQ1** — How did traffic redistribute between the Suez Canal and its
  alternatives during the Red Sea crisis, and how complete is the recovery
  relative to a seasonally adjusted pre-crisis baseline?
- **RQ2** — Which vessel segments and cargo types abandoned the canal first, and
  which returned first?
- **RQ3** — Does canal transit volume translate into activity at Egyptian ports,
  or do the two decouple?

---

## Data source

**IMF PortWatch** — International Monetary Fund / University of Oxford, derived
from UN Global Platform AIS satellite tracking.
<https://portwatch.imf.org/>

Four layers are used, all from the ArcGIS REST service at
`https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services`:

| Layer | Contents | Rows |
|---|---|---:|
| `Daily_Chokepoints_Data` | daily transits, 28 chokepoints, 2019-01-01 onward | 80,528 |
| `PortWatch_chokepoints_database` | chokepoint names and coordinates | 28 |
| `Daily_Ports_Data` | daily port calls and trade, filtered to Egypt | 37,362 |
| `PortWatch_ports_database` | port names, countries, coordinates | 2,071 |

**Exact retrieval dates and filters are recorded in
`data/raw/_manifest.json`** and copied into `docs/data_quality.md` on every
run. This is not bookkeeping for its own sake: PortWatch revises its most
recent days every week, so a figure is only reproducible if you know when it
was downloaded.

> Two notes for anyone following published guides to this API. The widely cited
> `Daily_Trade_Data` layer **no longer exists** — it answers with error 499 and
> has been renamed `Daily_Ports_Data`. And the `date` field is now an ISO string,
> not the epoch-milliseconds integer the documentation describes. Both were found
> by querying the live service rather than trusting the docs; `fetch.py --discover`
> exists for exactly this reason.

Basemap tiles are © Esri, HERE, Garmin, OpenStreetMap contributors.

---

## Running it

Requires [uv](https://docs.astral.sh/uv/). The code needs Python 3.12 or
later (`pyproject.toml`); `.python-version` pins the interpreter uv actually
uses to 3.14, which is what the committed `uv.lock` was resolved against.

```bash
uv sync                                 # install dependencies
uv run python src/fetch.py all          # download raw data (~60 MB, a few minutes)
uv run python src/prepare.py            # clean, validate, derive
uv run python src/metrics.py --summary  # baseline, deviation, substitution
uv run panel serve src/app.py --show    # launch the dashboard
```

To look at the charts without running the server:

```bash
uv run python src/charts.py              # writes docs/preview.html
uv run python src/design_alternatives.py # writes docs/mockups/alternatives.html
```

Both files have BokehJS embedded, so they open with no internet connection at
all. Only the map's basemap tiles need a network.

---

## Structure

```
pyproject.toml      dependencies and uv configuration (source of truth)
requirements.txt    the same list, for installing without uv
uv.lock             exact resolved versions
.python-version     interpreter pin (3.14)

src/
├── fetch.py        paginated ArcGIS client; caches raw JSON + writes the manifest
├── prepare.py      dates, type conversion, validation, derived columns, QC report
├── metrics.py      seasonal baseline, deviation, substitution ratio, period table
├── charts.py       one function per view, each returning a HoloViews object
├── app.py          Panel layout, widgets, and the linked interactions
└── design_alternatives.py   rebuilds the rejected designs for comparison

data/raw/        downloaded JSON (gitignored, except the manifest)
data/processed/  cleaned parquet tables
docs/
├── data_quality.md     auto-generated: provenance + every check performed
├── design-rationale.md why the dashboard looks the way it does
├── preview.html        all views in one standalone file
└── mockups/
    └── alternatives.html   each rejected design beside what replaced it
```

Charts are plain functions returning objects, so the same code runs in a
notebook during development and in the dashboard in production — there is no
copy-paste between prototype and product.

### What each module reads and writes

The pipeline runs top to bottom: each step consumes what the one above it
produced, so they can be re-run individually without redoing the whole chain.

| Module | Reads | Writes | Run with |
|---|---|---|---|
| `fetch.py` | the PortWatch API | `data/raw/*.json`, `data/raw/_manifest.json` | `python src/fetch.py all` |
| `prepare.py` | `data/raw/*.json` | `chokepoints_daily/_long/_meta.parquet`, `ports_daily.parquet`, `docs/data_quality.md` | `python src/prepare.py` |
| `metrics.py` | the parquet tables above | `chokepoints_metrics.parquet`, `suez_substitution.parquet`, `port_changes.parquet`, `canal_vs_ports.parquet` | `python src/metrics.py --summary` |
| `charts.py` | the processed tables | `docs/preview.html` | `python src/charts.py` |
| `app.py` | the processed tables | the running dashboard | `panel serve src/app.py --show` |
| `design_alternatives.py` | the processed tables | `docs/mockups/alternatives.html` | `python src/design_alternatives.py` |

`fetch.py` is the only step that needs a network connection. Everything below
it works offline from the cached JSON.

---

## Libraries

Declared in `pyproject.toml`, mirrored in `requirements.txt`. Every package
listed is either imported by `src/` or required at runtime by something that
is — nothing is carried "just in case".

The brief asks for at least one visualisation library listed on
[PyViz.org](https://pyviz.org/); four of the packages below are
(**holoviews**, **geoviews**, **panel**, **bokeh**), marked ✓.

| Package | PyViz | Imported by | What it does here |
|---|:---:|---|---|
| `pandas` | | every module | Every table in the project. Reshaping, grouping, rolling windows, parquet I/O. |
| `requests` | | `fetch.py` | The paginated calls to the PortWatch ArcGIS service. |
| `holoviews` | ✓ | `charts.py`, `app.py`, `design_alternatives.py` | Every chart object. `Curve`, `Area`, `HeatMap`, `Scatter`, `Segments`, plus `Area.stack` for the composition chart and the `VLine`/`HLine`/`Text` annotations. |
| `geoviews` | ✓ | `charts.py` | The world map: the basemap tile layer and the chokepoint points, projected correctly. |
| `cartopy` | | `charts.py` | One line — `ccrs.PlateCarree()`, which tells geoviews the points are plain latitude/longitude so it can project them onto web-mercator tiles. |
| `panel` | ✓ | `app.py` | The dashboard itself: template, sidebar widgets, `Tabulator` table, `@pn.cache`, and the server behind `panel serve`. |
| `pyarrow` | | *not imported* | pandas uses it as the engine behind `read_parquet` / `to_parquet`. Required, but never called by our code. |
| `bokeh` | ✓ | *not imported* | The renderer holoviews draws through, selected by `hv.extension("bokeh")`. It supplies the pan, zoom, hover and box-select tools. |

### What is deliberately *not* here

- **`hvplot`** — the usual companion to this stack, and a dependency in early
  drafts. It is a convenience wrapper for making charts straight off a
  dataframe, and every view here needs layered annotations, custom hover
  formatting and explicit colour assignment, so each one is built from
  holoviews elements directly. Carrying a dependency nothing imports would be
  the kind of inconsistency this README exists to avoid, so it was dropped.
- **`numpy`** — present transitively through pandas, but not imported. The one
  place it was used, square-rooting the map's circle sizes, is a HoloViews
  `dim` expression (`dim("ships") ** 0.5`) evaluated inside the plot.
- **`datashader`** — the standard answer to overplotting in this stack, and
  unnecessary at this size. 80,528 rows render instantly; adding it to look
  sophisticated would be an unjustified choice.

---

## Data preparation

Carried out in `prepare.py`, with the analytical measures built on top in
`metrics.py`. Every check below is written to `docs/data_quality.md` as the
pipeline runs, so the report is generated evidence rather than a claim:

- **Dates parsed in UTC and cross-checked** against the independent
  `year`/`month`/`day` columns. The naive conversion uses the local timezone and
  shifts every row to the previous day east of London; the cross-check proves
  ours does not.
- **The dataset's own arithmetic verified** — `n_total = n_cargo + n_tanker`,
  and `n_cargo` against its four components. Counts match exactly; capacity
  figures miss by at most 3 units out of millions, because PortWatch rounds
  before publishing, so that check carries an explicit tolerance.
- **Completeness** — 80,528 rows is exactly 28 chokepoints × 2,876 days. No
  duplicates, no missing values, no gaps.
- **Outliers flagged, never removed.** 142 days sit beyond 4σ of their own
  chokepoint's mean. These are real events, not errors: Suez drops to 2 ships
  on 25 March 2021 (the Ever Given blocked the canal 23–29 March), and Korea
  Strait drops to 1 ship on 5 September 2022 (Typhoon Hinnamnor). Deleting them
  would be deleting the evidence.
- **Derived variables** — mean vessel size, per-segment shares, month-day key
  for the seasonal baseline, and in `metrics.py` the baseline itself, deviation
  from it, and the Suez/Cape substitution ratio.
- **Reshaped** from one row per day into a long table of one row per
  day-per-vessel-type, which is the shape charts want.
- **Egyptian ports given the same treatment**, plus two things specific to
  them. A **role category** per port — canal gateway, Mediterranean trade, oil
  and gas terminal, Red Sea other — assigned by position relative to the canal
  and listed in `prepare.py` so it can be disputed. And an **activity flag**:
  Ras Gharib and Ras Shukheir record *no calls at all* across 2,874 days, while
  Zeit Bay and the Egyptian LNG Terminal average under 0.1 a day. All four are
  flagged inactive and excluded from the comparison, because a percentage
  change on three ships a year is noise dressed as a finding.

### Why the baseline starts in 2022

"Normal" is defined as **2022-01-01 to 2023-10-06**, and everything earlier is
deliberately excluded. 2020 was distorted by the pandemic collapse in trade;
2021 contained both the post-pandemic shipping boom and the Ever Given
grounding. 6 October 2023 is the last day before the regional conflict began.

One honest limitation, surfaced rather than hidden: that window is 1 year
9 months long, so calendar days from 7 October to 31 December appear in it only
once. Their baseline is noisier. The baseline is therefore smoothed across ±15
neighbouring calendar days — which also fills 29 February, absent from the
window entirely — and a `baseline_n_years` column records where it is thin.

---

## Findings

Against the seasonal baseline, averaged by period:

| | Suez Canal | Bab el-Mandeb | Cape of Good Hope |
|---|---:|---:|---:|
| Conflict onset (Oct–Nov 2023) | **+10.6%** | +10.6% | +7.3% |
| Acute crisis (Nov 2023–Jun 2024) | −31.5% | −41.8% | +72.6% |
| Since mid-2024 | **−43.7%** | −53.4% | **+94.1%** |

1. **Traffic rose before it fell.** The first six weeks after 7 October 2023 ran
   about 11% *above* normal. The World Bank measured +9.45% on the same window
   from the same source — an independent check that this pipeline is correct.
2. **The detour did not reverse; it settled.** Suez bottomed out in mid-2024 and
   stayed flat through 2025. 2026 shows the first real recovery: the index has
   climbed from 53 to 67 and Suez's share of the Suez/Cape route pair from 29%
   to 39% — still a third below normal.
3. **The big ships left and have not come back.** Mean vessel capacity at Suez
   fell from 45,757 in 2023 to 35,876 in 2025, a 22% drop. At the Cape it did
   not move at all (61,960 → 63,738). The Cape was already carrying large
   vessels and absorbed more of them; Suez is left with a smaller class.
4. **The canal's loss did not reach Egypt's ports — they decoupled.** This is
   the answer to RQ3, and it is the opposite of the obvious hypothesis. While
   canal transits ran at about 60% of their pre-crisis normal, Egyptian port
   calls ran at roughly 118% and seaborne tonnage at 130–165%. Only one active
   port, As Suways, fell at all (−22%); Alexandria rose 23% in calls and 49% in
   tonnage, El Sokhna 86% and 55%. Egypt's national seaborne trade went from
   157 Mt in 2023 to 189 Mt in 2024 and stayed there.

   The policy reading: the crisis cost Egypt **transit revenue**, not seaborne
   trade. Those are different line items with different remedies, and a
   dashboard that showed only canal transits would have implied otherwise.

---

## Limitations

- **Diversion is inferred, not observed.** A ship avoiding Suez appears as an
  absence, not as a labelled event. The Suez/Cape substitution ratio is a
  reasonable proxy, but it remains a proxy.
- **Capacity is estimated** from vessel characteristics, not measured cargo.
- **The last week or so is provisional** — PortWatch publishes weekly and
  revises recent days.
- **The basemap is a third-party service.** CartoDB's tiles moved behind an API
  key mid-project; the basemap is now one named constant in `charts.py` so it
  can be swapped in a single line.
