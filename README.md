# Chokepoint Lens

**Visualization and Visual Analytics — project work**
**Author:** Elfadel Mohamed · **Date:** November 2026

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
  or do the two decouple? *(data downloaded; view not yet built)*

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

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                 # install dependencies
uv run python src/fetch.py all          # download raw data (~60 MB, a few minutes)
uv run python src/prepare.py            # clean, validate, derive
uv run python src/metrics.py --summary  # baseline, deviation, substitution
uv run panel serve src/app.py --show    # launch the dashboard
```

To look at the charts without running the server:

```bash
uv run python src/charts.py             # writes docs/preview.html
```

That file has BokehJS embedded, so it opens with no internet connection. Only
the map tiles need a network.

---

## Structure

```
src/
├── fetch.py     paginated ArcGIS client; caches raw JSON + writes the manifest
├── prepare.py   dates, type conversion, validation, derived columns, QC report
├── metrics.py   seasonal baseline, deviation, substitution ratio, period table
├── charts.py    one function per view, each returning a HoloViews object
└── app.py       Panel layout, widgets, and the linked interactions

data/raw/        downloaded JSON (gitignored, except the manifest)
data/processed/  cleaned parquet tables
docs/
├── data_quality.md   auto-generated: provenance + every check performed
├── preview.html      all views in one standalone file
└── mockups/          rejected design alternatives
```

Charts are plain functions returning objects, so the same code runs in a
notebook during development and in the dashboard in production — there is no
copy-paste between prototype and product.

---

## Data preparation

Carried out in `prepare.py`, with every check written to `docs/data_quality.md`:

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
