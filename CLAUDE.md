# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A pipeline that answers one business question: **how many HPB Healthier Dining Programme options are within 1 km true walking distance of each HDB residential postal code in Singapore?** It sources both datasets through the OneMap API (Singapore's national map platform) and computes true walking-route distance (not straight-line) via OneMap's Routing API.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ONEMAP_EMAIL / ONEMAP_PASSWORD (register at onemap.gov.sg/apidocs/register)
git config core.hooksPath githooks   # enables the pre-commit postal_code check below
```

OneMap has no static API key — auth is email+password exchanged for a JWT (`POST /api/auth/post/getToken`, ~3 day TTL), handled automatically by `src/onemap_client.py` and cached in the gitignored `.token_cache.json`.

## Commands

Pipeline stages, run via `main.py` (each also runnable directly, e.g. `python -m src.fetch_dining`):

```bash
python main.py discover                  # dump OneMap's theme catalog - run this FIRST after any OneMap catalog change
python main.py dining                    # fetch healthier dining locations -> data/raw/healthier_dining_options.csv
python main.py residential                # fetch HDB residential postal codes -> data/raw/residential_locations.csv
python main.py accessibility [--limit N]  # compute walking-distance access -> data/processed/accessibility_by_postal_code.csv
python main.py all [--limit N]           # dining -> residential -> accessibility
```

`--limit N` truncates to the first N residential points — always use it to validate on a small sample before a full run (the full `accessibility` run makes on the order of 10^5 routing API calls; see Performance below).

No test suite, linter, or build step exists in this repo.

## Architecture

**Config-driven theme names, not hardcoded assumptions.** `config.py` holds the OneMap theme `queryName`s (`DINING_THEME_QUERYNAME`, `RESIDENTIAL_THEME_QUERYNAME`). These are NOT guessable from the theme's display name — e.g. "Healthier Eateries" has `queryName=healthierdining`. Always confirm/update them via `python main.py discover` (writes `data/raw/themes_catalog.csv`) after any change, rather than assuming a name. As of the last discovery pass, OneMap has no private-residential/condo theme, so residential coverage is HDB-only (`RESIDENTIAL_THEME_QUERYNAME = None`); `fetch_residential.py` logs this limitation rather than silently under-covering.

**Data flow:**
1. `src/fetch_dining.py` — pulls the dining theme via OneMap's `retrieveTheme`.
2. `src/fetch_residential.py` — two sources merged: (a) data.gov.sg's "HDB Property Information" dataset (block/street only, no coordinates) geocoded block-by-block through OneMap's Search API, with results cached to `data/raw/hdb_geocode_cache.csv` so re-runs don't re-geocode resolved addresses; (b) an optional condo/private-residential theme if `config.RESIDENTIAL_THEME_QUERYNAME` is set.
3. `src/compute_accessibility.py` — the core algorithm, see below.

**Two-stage distance computation (`compute_accessibility.compute`):**
1. Haversine pre-filter via a `BallTree` (`src/geo_utils.py`) narrows each residential point to dining candidates within `STRAIGHT_LINE_PREFILTER_RADIUS_M`. This **must equal** `WALK_DISTANCE_THRESHOLD_M` (1000m) — a walking route can never be shorter than straight-line distance, so a larger buffer only wastes routing calls that can never pass the filter. Don't reintroduce a bigger buffer.
2. OneMap's Routing API (`routeType=walk`) resolves true walking distance for each surviving candidate pair, via a `ThreadPoolExecutor` (`config.ROUTING_MAX_WORKERS`, default 6). Results are cached to `data/raw/walk_route_cache.csv` keyed by `(postal_code, dining_idx)` so interrupted/resumed runs don't re-fetch resolved pairs.

**Cache-loading gotcha (already fixed, don't regress it):** when reading `walk_route_cache.csv` back, `postal_code` must be loaded with `dtype={"postal_code": str}`. Without it, `pd.read_csv` silently infers the column as float64 (e.g. `"190001"` round-trips to `"190001.0"`), which then never matches the plain-string keys built elsewhere from the residential DataFrame — causing 100% cache misses and full re-computation on every resumed run (this happened once and cost a wasted ~12-hour re-run before being caught). See the comment in `_load_route_cache` for the full explanation.

The same class of bug (missing `dtype={"postal_code": str}` on a `pd.read_csv`) previously stripped leading zeros from ~1% of postal codes in three separate places — `fetch_residential.py`'s geocode cache, and both the residential and dining reads in `compute_accessibility.py`. Any new `pd.read_csv` on a file with a `postal_code` column must set that dtype explicitly. A git pre-commit hook (`githooks/pre-commit`, run via `scripts/validate_postal_codes.py`) blocks committing `data/processed/accessibility_by_postal_code.csv` if any postal code isn't a well-formed 6-digit string — enable it once per clone with `git config core.hooksPath githooks` (see Setup).

**OneMap rate limits are undocumented and real.** Empirically the sustained ceiling is ~5 requests/sec regardless of concurrency; going above it produces `429`s that get retried (`tenacity`, exponential backoff, `config.MAX_ATTEMPTS`) rather than help. `src/onemap_client.py`'s `OneMapClient` shares one `requests.Session` *and* a single lock-guarded throttle timestamp across all worker threads (not per-thread) so the ~5 req/s ceiling is enforced in aggregate — per-thread throttling would let N concurrent workers each independently run at the limit, multiplying real throughput by N. A lock-guarded token refresh (`get_token`) similarly avoids races when multiple worker threads see an expiring token simultaneously. A full `accessibility` run over all residential postal codes is on the order of hours, not minutes — always sanity-check with `--limit` first, and expect to run the full pass in the background.

**Failed routing pairs are left uncached, not cached as `None`.** A pair that raises an exception (e.g. exhausted retries) is intentionally NOT written to the cache, so a subsequent run retries it automatically. Only a genuine successful API response with no route (`route_summary` missing) is cached as `None`. Don't "fix" this by caching exceptions — that was the original bug.

## Data files

- `.env`, `.token_cache.json`, `.venv/`, `data/raw/` are gitignored (secrets, regenerable caches/intermediates).
- `data/processed/accessibility_by_postal_code.csv` is the one tracked deliverable — the final answer to the business question, committed intentionally so it's reviewable without re-running the whole pipeline.

## Dashboard

`dashboard/app.py` is a Streamlit app that browses `data/processed/accessibility_by_postal_code.csv` without needing to open the raw CSV. Run locally with `streamlit run dashboard/app.py`.

- **Sidebar filters** (postal district multiselect, dining-options-within-1km range slider, address/postal-code search) narrow the working DataFrame; every tab below reacts to the same filtered set.
- **KPI row**: addresses shown, mean/median options, % of addresses with 0 options, max options.
- **Individual Addresses** tab: a pydeck `ScatterplotLayer` map, one point per postal code, colored red→green by option count (scale capped at the 95th percentile so outliers don't wash out the gradient) with radius also scaled to option count.
- **Hex Density (H3)** tab: `dashboard/data.py`'s `hex_aggregate` buckets points into H3 cells (user-adjustable resolution 7–10) and renders a pydeck `H3HexagonLayer` colored by mean options per cell.
- **District Comparison** tab: `dashboard/data.py`'s `district_aggregate` groups by postal district (via `dashboard/districts.py`'s static `SECTOR_TO_DISTRICT` lookup — URA's 28-district postal-sector table, hardcoded since it's stable public reference data, not something OneMap exposes) into a Plotly horizontal bar chart plus best/worst-5 tables.
- **Distribution** tab: Plotly histogram of option counts across filtered addresses.
- **Data Table** tab: filtered rows with a CSV download button.

`dashboard/data.py`'s `load_accessibility_data` reads the CSV with `dtype={"postal_code": str}` — same leading-zero gotcha as elsewhere in this repo (see above); don't drop it.

**Deployed** on Streamlit Community Cloud at https://hdoaccessibility-efgzng32zrdwamfydfpjgb.streamlit.app/, tracking `main` / `dashboard/app.py`. The repo is public, so Community Cloud auto-redeploys on every push to `main` — no manual republish step needed after merging dashboard changes.
