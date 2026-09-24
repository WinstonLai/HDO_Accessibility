"""One-off utility: dump OneMap's full theme catalog so we can confirm the
exact queryName values for the healthier-dining theme and any private
residential / condo theme, instead of guessing.

Run this BEFORE fetch_dining.py / fetch_residential.py and update
config.DINING_THEME_QUERYNAME / config.RESIDENTIAL_THEME_QUERYNAME with
whatever this prints.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.onemap_client import OneMapClient

KEYWORDS = [
    "health",
    "dining",
    "eatery",
    "eateries",
    "hawker",
    "hdb",
    "residential",
    "condo",
    "housing",
    "private",
]


def fetch_theme_catalog(client: OneMapClient) -> pd.DataFrame:
    payload = client.get(
        "/api/public/themesvc/getAllThemesInfo",
        params={"moreInfo": "Y"},
    )
    themes = payload.get("Theme_Names") or payload.get("themeNames") or payload
    if isinstance(themes, dict):
        # some responses nest the list under a key; fall back to first list value found
        for value in themes.values():
            if isinstance(value, list):
                themes = value
                break
    df = pd.DataFrame(themes)
    return df


def main() -> None:
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    client = OneMapClient()
    df = fetch_theme_catalog(client)
    df.to_csv(config.THEMES_CATALOG_PATH, index=False)
    print(f"Wrote {len(df)} themes to {config.THEMES_CATALOG_PATH}")

    text_cols = [c for c in df.columns if df[c].dtype == object]
    if text_cols:
        mask = pd.Series(False, index=df.index)
        for col in text_cols:
            lower = df[col].astype(str).str.lower()
            for kw in KEYWORDS:
                mask |= lower.str.contains(kw, na=False)
        matches = df[mask]
        print(f"\n{len(matches)} theme(s) matching keywords {KEYWORDS}:\n")
        with pd.option_context("display.max_colwidth", 80, "display.width", 200):
            print(matches.to_string(index=False))
    else:
        print("Could not identify text columns to keyword-match; inspect the CSV manually.")


if __name__ == "__main__":
    main()
