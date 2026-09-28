"""Data loading and enrichment for the accessibility dashboard.

Kept separate from app.py so the Streamlit-caching layer wraps pure
pandas logic that's easy to reason about independent of UI code.
"""

from __future__ import annotations

import sys
from pathlib import Path

import h3
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from dashboard.districts import SECTOR_TO_DISTRICT, sector_to_label  # noqa: E402

COUNT_COL = "num_dining_options_within_1km_walk"


@st.cache_data
def load_accessibility_data() -> pd.DataFrame:
    """Load the pipeline's final CSV.

    dtype={"postal_code": str} is required here -- without it pandas infers
    postal_code as float64 and leading-zero codes round-trip incorrectly
    (see CLAUDE.md's cache-loading gotcha; the same bug class applies to any
    read of this column).
    """
    df = pd.read_csv(config.ACCESSIBILITY_OUTPUT_PATH, dtype={"postal_code": str})
    df["postal_sector"] = df["postal_code"].str[:2]
    df["district_number"] = df["postal_sector"].map(
        lambda s: SECTOR_TO_DISTRICT.get(s, (None, None))[0]
    )
    df["district_label"] = df["postal_sector"].map(sector_to_label)
    return df


@st.cache_data
def assign_h3_hex(df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    """Add an H3 cell id per point at the given resolution."""
    out = df.copy()
    out["h3_cell"] = [
        h3.latlng_to_cell(lat, lon, resolution)
        for lat, lon in zip(out["lat"], out["lon"])
    ]
    return out


def hex_aggregate(df: pd.DataFrame, resolution: int) -> pd.DataFrame:
    """Mean/count of dining options per H3 hex, with hex boundary for pydeck."""
    hexed = assign_h3_hex(df, resolution)
    agg = (
        hexed.groupby("h3_cell")[COUNT_COL]
        .agg(mean_options="mean", num_addresses="count")
        .reset_index()
    )
    return agg


def district_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """Mean/median dining options per postal district, sorted ascending by mean."""
    agg = (
        df.dropna(subset=["district_number"])
        .groupby(["district_number", "district_label"])[COUNT_COL]
        .agg(mean_options="mean", median_options="median", num_addresses="count")
        .reset_index()
        .sort_values("mean_options")
    )
    return agg
