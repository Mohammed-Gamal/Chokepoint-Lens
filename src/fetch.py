"""
Step 1 of the pipeline: download raw data from IMF PortWatch.

PortWatch publishes its data through an ArcGIS REST service. Every layer
answers the same kind of URL:

    <base>/<LayerPath>/query?where=...&outFields=*&f=json

Two things make this trickier than a plain CSV download:

  1. The server returns at most ~1000 records per request, so we have to
     page through the results using `resultOffset`.
  2. Dates come back as epoch milliseconds (1546300800000), not text.
     We leave them alone here and convert in prepare.py -- this file's
     only job is to get the bytes onto disk, unchanged.

Everything we download is cached as JSON in data/raw/. PortWatch revises
recent days, so caching means your numbers stay stable while you work
instead of quietly shifting between runs.

Usage
-----
    python src/fetch.py --list                 # show available layers
    python src/fetch.py chokepoints_meta       # small: the 24 chokepoints
    python src/fetch.py chokepoints_daily      # big: ~70k daily rows
    python src/fetch.py ports_meta
    python src/fetch.py ports_daily --country Egypt
    python src/fetch.py all                    # everything we need

Source: IMF PortWatch (https://portwatch.imf.org/), a joint IMF /
University of Oxford platform built on UN Global Platform AIS data.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"

# Friendly name -> ArcGIS layer path.
#
# All four confirmed against the live service (run --discover to re-check;
# the account publishes 208 services and the names do change).
#
# Note for the write-up: published guides to this API, including the World
# Bank's teaching notebook, name the daily port layer `Daily_Trade_Data`.
# That service no longer exists -- it now answers with error 499, "Item
# does not exist or is inaccessible". The live name is `Daily_Ports_Data`.
# Finding that out is why --discover exists rather than trusting the docs.
LAYERS: dict[str, str] = {
    "chokepoints_daily": "Daily_Chokepoints_Data/FeatureServer/0",
    "chokepoints_meta": "PortWatch_chokepoints_database/FeatureServer/0",
    "ports_daily": "Daily_Ports_Data/FeatureServer/0",
    "ports_meta": "PortWatch_ports_database/FeatureServer/0",
    # Extras spotted on the service that we may want later:
    #   Global_Shipping_Routes          - shipping lane geometry for the map
    #   portwatch_disruptions_database  - disaster / geopolitical event feed
    #   PortWatch_countries_database    - country-level trade shares
}

PAGE_SIZE = 1000  # the server's own limit
TIMEOUT = 90  # seconds per request
RETRIES = 3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
MANIFEST = RAW_DIR / "_manifest.json"

SOURCE_CREDIT = (
    "IMF PortWatch (International Monetary Fund / University of Oxford), "
    "derived from UN Global Platform AIS satellite data. https://portwatch.imf.org/"
)


# --------------------------------------------------------------------------
# The paginated client
# --------------------------------------------------------------------------


def _get(url: str, params: dict) -> dict:
    """One GET request, with a couple of retries for flaky connections."""
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            # ArcGIS reports its own errors inside a 200 OK response.
            if "error" in payload:
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            return payload
        except Exception as exc:  # noqa: BLE001 - we want to retry anything
            last_error = exc
            if attempt < RETRIES:
                wait = 2**attempt
                print(f"    request failed ({exc}); retrying in {wait}s", file=sys.stderr)
                time.sleep(wait)
    raise RuntimeError(f"giving up after {RETRIES} attempts: {last_error}")


def query_layer(
    layer: str,
    where: str = "1=1",
    out_fields: str = "*",
    order_by: str = "ObjectId ASC",
) -> list[dict]:
    """
    Download every record from one PortWatch layer.

    `where` is plain SQL, e.g. "portid='chokepoint1'" or "country='Egypt'".
    We sort by ObjectId so that paging is stable: without an explicit sort
    the server may return rows in a different order between pages and you
    can silently lose or duplicate records.
    """
    if layer not in LAYERS:
        raise KeyError(f"unknown layer {layer!r}; choose from {sorted(LAYERS)}")

    url = f"{BASE}/{LAYERS[layer]}/query"
    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "false",
            "outSR": 4326,
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
            "orderByFields": order_by,
        }
        payload = _get(url, params)
        features = payload.get("features", [])
        records.extend(feature["attributes"] for feature in features)

        print(f"    fetched {len(records):,} rows", end="\r", flush=True)

        # Stop when the server says there is nothing more, or when it hands
        # back a short page (which also means we reached the end).
        if not features or not payload.get("exceededTransferLimit"):
            break
        offset += len(features)

    print(f"    fetched {len(records):,} rows")
    return records


def discover() -> None:
    """
    Ask the server what it actually publishes.

    Layer names change. Rather than guessing from documentation that may
    be out of date, this prints the live list so you can copy the exact
    path into LAYERS above.
    """
    payload = _get(BASE, {"f": "json"})
    services = payload.get("services", [])
    print(f"{len(services)} services published at\n  {BASE}\n")
    for service in sorted(services, key=lambda s: str(s.get("name", ""))):
        print(f"  {service.get('name'):<45} ({service.get('type')})")
    folders = payload.get("folders", [])
    if folders:
        print(f"\nfolders: {', '.join(folders)}")
    print(
        "\nTo use one, the layer path is:  <ServiceName>/FeatureServer/0"
        "\n(append ?f=json to a layer URL in a browser to see its field list)"
    )


def record_provenance(layer: str, where: str, records: list[dict], path: Path) -> None:
    """
    Write down what was downloaded, from exactly where, and when.

    The assignment requires the data source to be clearly indicated, and
    naming "IMF PortWatch" is not sufficient on its own. This service
    revises its most recent days every week and has already renamed one of
    its layers out from under the published documentation, so the retrieval
    timestamp and the exact layer path are part of the source, not trivia.

    prepare.py reads this file and copies it into the data quality report,
    so the provenance travels with the cleaned data rather than living only
    in someone's memory of when they ran the script.
    """
    manifest: dict = {}
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}  # corrupt file: start again rather than crash

    manifest["source"] = SOURCE_CREDIT
    manifest["service"] = BASE
    manifest.setdefault("layers", {})
    manifest["layers"][layer] = {
        "layer_path": LAYERS[layer],
        "where": where,
        "rows": len(records),
        "file": path.name,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
    }

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"    provenance recorded in {MANIFEST.name}")


def save_raw(layer: str, records: list[dict], suffix: str = "") -> Path:
    """Write the records to data/raw/<layer><suffix>.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{layer}{suffix}.json"
    path.write_text(json.dumps(records, indent=None), encoding="utf-8")
    size_mb = path.stat().st_size / 1_000_000
    print(f"    saved {path.relative_to(PROJECT_ROOT)} ({size_mb:.1f} MB)")
    return path


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "layer",
        nargs="?",
        help="layer to fetch, or 'all' for everything the dashboard needs",
    )
    parser.add_argument("--list", action="store_true", help="list the layers configured in this file")
    parser.add_argument("--discover", action="store_true", help="ask the server what layers really exist")
    parser.add_argument("--where", default=None, help="SQL filter, e.g. \"portid='chokepoint1'\"")
    parser.add_argument("--country", default=None, help="shorthand for --where \"country='<name>'\"")
    args = parser.parse_args()

    if args.discover:
        discover()
        return 0

    if args.list or not args.layer:
        print("Available layers:")
        for name, path in LAYERS.items():
            print(f"  {name:20s} {BASE}/{path}")
        return 0

    where = args.where
    suffix = ""
    if args.country:
        where = f"country='{args.country}'"
        suffix = f"_{args.country.lower().replace(' ', '_')}"

    if args.layer == "all":
        jobs = [
            ("chokepoints_meta", "1=1", ""),
            ("chokepoints_daily", "1=1", ""),
            ("ports_meta", "1=1", ""),
            ("ports_daily", "country='Egypt'", "_egypt"),
        ]
    else:
        jobs = [(args.layer, where or "1=1", suffix)]

    for layer, layer_where, layer_suffix in jobs:
        print(f"\n{layer}  (where: {layer_where})")
        try:
            records = query_layer(layer, where=layer_where)
        except Exception as exc:  # noqa: BLE001
            print(f"    FAILED: {exc}", file=sys.stderr)
            continue
        if records:
            path = save_raw(layer, records, layer_suffix)
            record_provenance(layer, layer_where, records, path)
        else:
            print("    no records returned")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
