"""Shared geospatial helpers: haversine distance and radius-neighbour queries."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

import config


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * config.EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def build_ball_tree(lat: pd.Series, lon: pd.Series) -> BallTree:
    coords_rad = np.radians(np.column_stack([lat.to_numpy(), lon.to_numpy()]))
    return BallTree(coords_rad, metric="haversine")


def radius_candidates(
    tree: BallTree,
    query_lat: pd.Series,
    query_lon: pd.Series,
    radius_m: float = config.STRAIGHT_LINE_PREFILTER_RADIUS_M,
) -> list[np.ndarray]:
    """For each query point, return indices into the tree's points within radius_m."""
    query_rad = np.radians(np.column_stack([query_lat.to_numpy(), query_lon.to_numpy()]))
    radius_rad = radius_m / config.EARTH_RADIUS_M
    indices = tree.query_radius(query_rad, r=radius_rad)
    return indices
