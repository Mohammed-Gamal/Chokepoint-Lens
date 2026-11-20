# Data quality report

Generated automatically by `src/prepare.py`. Do not edit by hand.

## Provenance

- Source: IMF PortWatch (International Monetary Fund / University of Oxford), derived from UN Global Platform AIS satellite data. https://portwatch.imf.org/
- Service endpoint: `https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services`

| Layer | Filter | Rows | Retrieved (UTC) |
|---|---|---:|---|
| `Daily_Chokepoints_Data/FeatureServer/0` | `1=1` | 80,528 | 2026-11-20 21:27:34Z |
| `PortWatch_chokepoints_database/FeatureServer/0` | `1=1` | 28 | 2026-11-20 21:26:54Z |
| `Daily_Ports_Data/FeatureServer/0` | `country='Egypt'` | 37,362 | 2026-11-20 21:28:58Z |
| `PortWatch_ports_database/FeatureServer/0` | `1=1` | 2,071 | 2026-11-20 21:27:35Z |

- Rows after cleaning: 80,528
- Chokepoints: 28
- Date range: 2019-01-01 to 2026-11-15

## Checks performed

- Metadata: 28 chokepoints with coordinates.
- Downloaded 80,528 raw daily rows.
- Date format: ISO date strings.
- Date check: parsed dates agree with the independent year/month/day columns on every row.
- Identity holds: n_cargo = sum of 4 cargo types (worst gap 0.0, tolerance 0).
- Identity holds: n_total = n_cargo + n_tanker (worst gap 0.0, tolerance 0).
- Identity holds: capacity_cargo = sum of 4 cargo capacities (worst gap 3.0, tolerance 10).
- Identity holds: capacity = capacity_cargo + capacity_tanker (worst gap 1.0, tolerance 10).
- No duplicate portid+date rows.
- No missing values anywhere.
- Outliers: 142 days beyond 4 standard deviations of their own chokepoint's mean, across 20 chokepoints. Flagged, not removed.
  - lowest: Korea Strait on 2022-09-05 with 1 ships
  - lowest: Korea Strait on 2023-08-09 with 1 ships
  - lowest: Korea Strait on 2020-09-02 with 2 ships
- Saved wide table: chokepoints_daily.parquet (80,528 rows, 28 columns).
- Saved long table: chokepoints_long.parquet (402,640 rows).
- Ports: 37,362 raw daily rows for Egypt.
- Date format: ISO date strings.
- Date check: parsed dates agree with the independent year/month/day columns on every row.
- Identity holds (ports): portcalls_cargo = sum of 4 cargo types (worst gap 0.0, tolerance 0).
- Identity holds (ports): portcalls = portcalls_cargo + portcalls_tanker (worst gap 0.0, tolerance 0).
- Identity holds (ports): import_cargo = sum of 4 cargo types (worst gap 3.0, tolerance 10).
- Identity holds (ports): import = import_cargo + import_tanker (worst gap 1.0, tolerance 10).
- Identity holds (ports): export_cargo = sum of 4 cargo types (worst gap 3.0, tolerance 10).
- Identity holds (ports): export = export_cargo + export_tanker (worst gap 1.0, tolerance 10).
- Ports: no duplicate portid+date rows.
- Ports: 2 with NO recorded calls in the whole period (Ras Gharib, Ras Shukheir). Kept but marked inactive.
- Ports: 2 below 0.1 calls/day (Egyptian LNG Terminal, Zeit Bay). Marked inactive: percentage changes on numbers this small are not meaningful.
- Ports: 9 of 13 ports carry enough traffic to analyse.
- Saved ports table: ports_daily.parquet (37,362 rows, 31 columns).
