"""Pull healthier-dining-option locations from OneMap's Theme API.

Requires config.DINING_THEME_QUERYNAME to be the confirmed queryName from
`python main.py discover` (see discover_themes.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.onemap_client import OneMapClient

LAT_KEYS = ("LATITUDE", "LAT", "Y")
LON_KEYS = ("LONGITUDE", "LON", "LNG", "X")


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    # theme responses are inconsistently cased across datasets, so normalize
    # once and fall through to the next candidate key whenever a match is
    # missing or empty - don't stop at the first case-insensitive hit if its
    # value is blank.
    normalized = {k.upper(): v for k, v in row.items()}
    for k in keys:
        v = normalized.get(k)
        if v not in (None, ""):
            return v
    return None


def _parse_latlng(row: dict[str, Any]) -> tuple[float | None, float | None]:
    for key in row:
        if key.upper() in ("LATLNG", "LAT_LNG"):
            value = row[key]
            if isinstance(value, str) and "," in value:
                lat_str, lon_str = value.split(",", 1)
                try:
                    return float(lat_str.strip()), float(lon_str.strip())
                except ValueError:
                    return None, None
    lat = _first_present(row, LAT_KEYS)
    lon = _first_present(row, LON_KEYS)
    try:
        return (float(lat) if lat is not None else None), (float(lon) if lon is not None else None)
    except (TypeError, ValueError):
        return None, None


def fetch_theme_points(client: OneMapClient, query_name: str) -> pd.DataFrame:
    payload = client.get(
        "/api/public/themesvc/retrieveTheme",
        params={"queryName": query_name, "extents": config.SG_EXTENTS},
    )
    results = payload.get("SrchResults", payload if isinstance(payload, list) else [])
    records = [r for r in results if isinstance(r, dict) and "FeatureCount" not in r]

    rows = []
    for r in records:
        lat, lon = _parse_latlng(r)
        rows.append(
            {
                "name": r.get("NAME") or r.get("Name") or r.get("name"),
                "postal_code": r.get("ADDRESSPOSTALCODE") or r.get("POSTAL") or r.get("postal_code"),
                "address": r.get("ADDRESS") or r.get("address"),
                "lat": lat,
                "lon": lon,
                "description": r.get("DESCRIPTION") or r.get("description"),
            }
        )

    df = pd.DataFrame(rows)
    before = len(df)
    df = df.dropna(subset=["lat", "lon"])
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped}/{before} dining rows with no parseable coordinates.")
    return df.reset_index(drop=True)


def main() -> None:
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = OneMapClient()
    df = fetch_theme_points(client, config.DINING_THEME_QUERYNAME)
    df.to_csv(config.DINING_OUTPUT_PATH, index=False)
    print(f"Wrote {len(df)} healthier dining options to {config.DINING_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
