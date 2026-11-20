# Data quality report

Generated automatically by `src/prepare.py`. Do not edit by hand.

- Source: IMF PortWatch (IMF / University of Oxford), from UN Global Platform AIS data
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
