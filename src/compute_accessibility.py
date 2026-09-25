"""Answer: how many healthier dining options are within 1 KM walking distance
of each residential postal code?

Two-stage approach:
1. Haversine pre-filter (BallTree radius query) narrows each residential
   point down to dining candidates within STRAIGHT_LINE_PREFILTER_RADIUS_M -
   this keeps the number of expensive routing calls tractable instead of a
   full cross join.
2. OneMap's walking Routing API gives the true walk distance for each
   surviving candidate pair. Results are cached to disk keyed by
   (postal_code, dining index) so an interrupted run can resume without
   re-querying pairs already resolved.
"""

from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from src.geo_utils import build_ball_tree, radius_candidates
from src.onemap_client import OneMapClient


def _load_route_cache() -> dict[tuple[str, int], float | None]:
    if config.ROUTE_CACHE_PATH.exists():
        # dtype=str on postal_code is load-bearing: without it, a pure-digit
        # text column round-trips through CSV as float64 (e.g. "190001" ->
        # 190001.0 -> "190001.0"), which then never matches the plain string
        # keys used everywhere else in this module - silently breaking the
        # cache (100% miss on every resumed run). zip() over columns instead
        # of iterrows() also avoids per-row Series overhead on ~200k+ rows.
        cached = pd.read_csv(config.ROUTE_CACHE_PATH, dtype={"postal_code": str})
        return {
            (pc, int(idx)): (None if pd.isna(dist) else float(dist))
            for pc, idx, dist in zip(cached["postal_code"], cached["dining_idx"], cached["walk_distance_m"])
        }
    return {}


def _save_route_cache(cache: dict[tuple[str, int], float | None]) -> None:
    config.DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    rows = [
        {"postal_code": pc, "dining_idx": idx, "walk_distance_m": dist}
        for (pc, idx), dist in cache.items()
    ]
    pd.DataFrame(rows).to_csv(config.ROUTE_CACHE_PATH, index=False)


def walk_distance_m(client: OneMapClient, start: tuple[float, float], end: tuple[float, float]) -> float | None:
    payload = client.get(
        "/api/public/routingsvc/route",
        params={
            "start": f"{start[0]},{start[1]}",
            "end": f"{end[0]},{end[1]}",
            "routeType": "walk",
        },
    )
    summary = payload.get("route_summary")
    if not summary or "total_distance" not in summary:
        return None
    return float(summary["total_distance"])


def compute(
    residential: pd.DataFrame,
    dining: pd.DataFrame,
    client: OneMapClient,
    flush_every: int = 500,
    max_workers: int = config.ROUTING_MAX_WORKERS,
) -> pd.DataFrame:
    tree = build_ball_tree(dining["lat"], dining["lon"])
    candidate_indices = radius_candidates(
        tree, residential["lat"], residential["lon"], radius_m=config.STRAIGHT_LINE_PREFILTER_RADIUS_M
    )

    cache = _load_route_cache()
    postal_codes = residential["postal_code"].astype(str).tolist()
    # Plain numpy arrays instead of repeated .iloc[] lookups - .iloc is slow
    # enough per-call that doing it ~200k+ times in a loop dominates runtime.
    res_lat, res_lon = residential["lat"].to_numpy(), residential["lon"].to_numpy()
    dine_lat, dine_lon = dining["lat"].to_numpy(), dining["lon"].to_numpy()

    # Build the flat list of (postal_code, dining_idx) pairs not yet resolved.
    pending: list[tuple[str, int, tuple[float, float], tuple[float, float]]] = []
    seen: set[tuple[str, int]] = set()
    for row_i, dining_idxs in enumerate(candidate_indices):
        postal_code = postal_codes[row_i]
        start = (res_lat[row_i], res_lon[row_i])
        for dining_idx in dining_idxs:
            dining_idx = int(dining_idx)
            key = (postal_code, dining_idx)
            if key in cache or key in seen:
                continue
            seen.add(key)
            pending.append((postal_code, dining_idx, start, (dine_lat[dining_idx], dine_lon[dining_idx])))

    total_pairs = sum(len(idxs) for idxs in candidate_indices)
    print(
        f"{total_pairs} candidate pairs within {config.STRAIGHT_LINE_PREFILTER_RADIUS_M}m straight-line "
        f"radius ({total_pairs - len(pending)} already cached, {len(pending)} to resolve via routing API "
        f"with {max_workers} concurrent workers)."
    )

    cache_lock = threading.Lock()
    completed = 0

    def _resolve(item: tuple[str, int, tuple[float, float], tuple[float, float]]) -> None:
        nonlocal completed
        postal_code, dining_idx, start, end = item
        try:
            dist = walk_distance_m(client, start, end)
        except Exception as exc:  # noqa: BLE001 - leave uncached so a resumed run retries it, keep going
            print(f"  routing failed for postal_code={postal_code} dining_idx={dining_idx}: {exc}")
            with cache_lock:
                completed += 1
            return
        with cache_lock:
            cache[(postal_code, dining_idx)] = dist
            completed += 1
            if completed % flush_every == 0:
                _save_route_cache(cache)

    if pending:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_resolve, item) for item in pending]
            for _ in tqdm(as_completed(futures), total=len(futures), desc="Routing calls"):
                pass

    _save_route_cache(cache)

    counts = []
    for row_i, dining_idxs in enumerate(candidate_indices):
        postal_code = postal_codes[row_i]
        within_1km = sum(
            1
            for dining_idx in dining_idxs
            if (dist := cache.get((postal_code, int(dining_idx)))) is not None
            and dist <= config.WALK_DISTANCE_THRESHOLD_M
        )
        counts.append(within_1km)

    out = residential.copy()
    out["num_dining_options_within_1km_walk"] = counts
    return out


def run(limit: int | None = None) -> pd.DataFrame:
    residential = pd.read_csv(config.RESIDENTIAL_OUTPUT_PATH)
    dining = pd.read_csv(config.DINING_OUTPUT_PATH)
    if limit:
        residential = residential.head(limit)

    client = OneMapClient()
    result = compute(residential, dining, client)

    config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(config.ACCESSIBILITY_OUTPUT_PATH, index=False)
    print(f"Wrote {len(result)} rows to {config.ACCESSIBILITY_OUTPUT_PATH}")

    print("\nSummary:")
    print(result["num_dining_options_within_1km_walk"].describe())
    zero_access = (result["num_dining_options_within_1km_walk"] == 0).mean() * 100
    print(f"{zero_access:.1f}% of residential postal codes have 0 healthier dining options within 1km walk.")

    top = result.sort_values("num_dining_options_within_1km_walk", ascending=False).head(10)
    print("\nTop 10 best-served postal codes:")
    print(top[["postal_code", "address", "num_dining_options_within_1km_walk"]].to_string(index=False))

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N residential points (for testing).")
    args = parser.parse_args()
    run(args.limit)


if __name__ == "__main__":
    main()
