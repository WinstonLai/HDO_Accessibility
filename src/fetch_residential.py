"""Build the residential locations table:

1. HDB blocks: download data.gov.sg's "HDB Property Information" dataset
   (block + street, no coordinates), then geocode each unique address via
   OneMap's Search API to get postal_code + lat/lon. Geocoding results are
   cached to disk so re-runs don't re-hit the API for addresses already
   resolved.
2. Private residential / condo: only if config.RESIDENTIAL_THEME_QUERYNAME
   has been set to a confirmed OneMap theme queryName (see discover_themes.py).
   If left as None, this step is skipped and logged.

Both are merged into a single residential_locations.csv with a `source`
column so downstream consumers can tell HDB rows from condo rows.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.fetch_dining import fetch_theme_points
from src.onemap_client import OneMapClient

POLL_DOWNLOAD_URL = config.DATA_GOV_SG_POLL_DOWNLOAD_URL.format(
    dataset_id=config.HDB_PROPERTY_INFO_DATASET_ID
)


def download_hdb_property_info() -> pd.DataFrame:
    resp = requests.get(POLL_DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    csv_url = payload["data"]["url"]
    df = pd.read_csv(csv_url)
    df.columns = [c.strip().lower() for c in df.columns]
    if "residential" in df.columns:
        df = df[df["residential"].astype(str).str.upper() == "Y"]
    return df[["blk_no", "street"]].drop_duplicates().reset_index(drop=True)


def _load_geocode_cache() -> dict[str, dict]:
    if config.GEOCODE_CACHE_PATH.exists():
        cached = pd.read_csv(config.GEOCODE_CACHE_PATH)
        return {row["query"]: row.to_dict() for _, row in cached.iterrows()}
    return {}


def _save_geocode_cache(cache: dict[str, dict]) -> None:
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cache.values()).to_csv(config.GEOCODE_CACHE_PATH, index=False)


def geocode_hdb_blocks(client: OneMapClient, blocks: pd.DataFrame, flush_every: int = 200) -> pd.DataFrame:
    cache = _load_geocode_cache()
    queries = (blocks["blk_no"].astype(str) + " " + blocks["street"].astype(str)).tolist()
    to_resolve = [q for q in queries if q not in cache]
    print(f"{len(queries) - len(to_resolve)}/{len(queries)} addresses already cached; "
          f"resolving {len(to_resolve)} remaining.")

    for i, query in enumerate(tqdm(to_resolve, desc="Geocoding HDB blocks")):
        try:
            payload = client.get(
                "/api/common/elastic/search",
                params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
            )
            results = payload.get("results", [])
            # Prefer the first result with a real postal code - OneMap sometimes
            # returns a same-address facility (e.g. a community centre sharing
            # the block/street) with POSTAL "NIL" ahead of the residential block.
            match = next((r for r in results if r.get("POSTAL") not in (None, "", "NIL")), None)
            cache[query] = {
                "query": query,
                "postal_code": match.get("POSTAL") if match else None,
                "address": match.get("ADDRESS") if match else None,
                "lat": float(match["LATITUDE"]) if match and match.get("LATITUDE") else None,
                "lon": float(match["LONGITUDE"]) if match and match.get("LONGITUDE") else None,
            }
        except Exception as exc:  # noqa: BLE001 - keep going, log the failure per-address
            cache[query] = {"query": query, "postal_code": None, "address": None, "lat": None, "lon": None}
            print(f"  geocode failed for {query!r}: {exc}")

        if (i + 1) % flush_every == 0:
            _save_geocode_cache(cache)

    _save_geocode_cache(cache)

    rows = [cache[q] for q in queries]
    df = pd.DataFrame(rows)
    before = len(df)
    df = df.dropna(subset=["lat", "lon", "postal_code"])
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped}/{before} HDB blocks that failed to geocode.")
    df["source"] = "hdb"
    return df[["postal_code", "address", "lat", "lon", "source"]].drop_duplicates(subset=["postal_code"])


def fetch_condo_locations(client: OneMapClient) -> pd.DataFrame:
    if not config.RESIDENTIAL_THEME_QUERYNAME:
        print("config.RESIDENTIAL_THEME_QUERYNAME is not set - skipping private residential/condo "
              "theme; residential coverage will be HDB-only. Run `python main.py discover` to check "
              "whether OneMap exposes a usable theme, then set it in config.py.")
        return pd.DataFrame(columns=["postal_code", "address", "lat", "lon", "source"])

    df = fetch_theme_points(client, config.RESIDENTIAL_THEME_QUERYNAME)
    df = df.rename(columns={"name": "building_name"})
    df["source"] = "condo"
    df = df.dropna(subset=["postal_code"])
    return df[["postal_code", "address", "lat", "lon", "source"]].drop_duplicates(subset=["postal_code"])


def main() -> None:
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = OneMapClient()

    print("Downloading HDB Property Information from data.gov.sg...")
    blocks = download_hdb_property_info()
    print(f"{len(blocks)} unique residential HDB blocks to geocode.")

    hdb_df = geocode_hdb_blocks(client, blocks)
    condo_df = fetch_condo_locations(client)

    combined = pd.concat([hdb_df, condo_df], ignore_index=True)
    combined = combined.drop_duplicates(subset=["postal_code"]).reset_index(drop=True)
    combined.to_csv(config.RESIDENTIAL_OUTPUT_PATH, index=False)
    print(
        f"Wrote {len(combined)} residential locations "
        f"({(combined['source'] == 'hdb').sum()} HDB, {(combined['source'] == 'condo').sum()} condo) "
        f"to {config.RESIDENTIAL_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
