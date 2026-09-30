"""Central configuration for the OneMap healthier-dining accessibility pipeline."""

from pathlib import Path

# --- Paths -------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
TOKEN_CACHE_PATH = ROOT_DIR / ".token_cache.json"
GEOCODE_CACHE_PATH = DATA_RAW_DIR / "hdb_geocode_cache.csv"
ROUTE_CACHE_PATH = DATA_RAW_DIR / "walk_route_cache.csv"

THEMES_CATALOG_PATH = DATA_RAW_DIR / "themes_catalog.csv"
DINING_OUTPUT_PATH = DATA_RAW_DIR / "healthier_dining_options.csv"
RESIDENTIAL_OUTPUT_PATH = DATA_RAW_DIR / "residential_locations.csv"
ACCESSIBILITY_OUTPUT_PATH = DATA_PROCESSED_DIR / "accessibility_by_postal_code.csv"

# --- OneMap theme query names -------------------------------------------
# Confirmed via `python main.py discover` against data/raw/themes_catalog.csv
# (165 themes as of 2026-09-24):
#   "Healthier Eateries" (HEALTH PROMOTION BOARD) -> queryName "healthierdining"
DINING_THEME_QUERYNAME = "healthierdining"

# No private-residential/condo theme exists in OneMap's catalog (checked
# keywords: residen*, condo, apartment, landed, private, building, ura,
# property, town, planning - only HDB-owned themes and unrelated URA/NParks
# building themes came up). Residential coverage is therefore HDB-only via
# data.gov.sg + OneMap geocoding (see fetch_residential.py); this constant
# stays None and fetch_residential.py logs the HDB-only limitation.
RESIDENTIAL_THEME_QUERYNAME = None

# --- Singapore bounding box (used for theme extents) ---------------------
SG_EXTENTS = "1.144,103.535,1.494,104.502"  # minLat,minLon,maxLat,maxLon

# --- data.gov.sg dataset ids ---------------------------------------------
HDB_PROPERTY_INFO_DATASET_ID = "d_17f5382f26140b1fdae0ba2ef6239d2f"
DATA_GOV_SG_POLL_DOWNLOAD_URL = (
    "https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download"
)

# --- Accessibility computation --------------------------------------------
WALK_DISTANCE_THRESHOLD_M = 1000  # the "1 KM walking distance" business rule
# A walking route can never be shorter than the straight-line (haversine)
# distance between two points, so no pair with straight-line distance above
# the threshold can ever have walk_distance <= threshold. The prefilter
# radius must therefore equal (never exceed) WALK_DISTANCE_THRESHOLD_M - a
# larger buffer would only add routing calls that can never pass the filter.
STRAIGHT_LINE_PREFILTER_RADIUS_M = WALK_DISTANCE_THRESHOLD_M
EARTH_RADIUS_M = 6_371_000

# --- Rate limiting / HTTP behaviour ---------------------------------------
# OneMap's documented limit is 250 requests/minute (~4.167 req/s) - matches
# the ~5 req/s empirical ceiling. 0.24s keeps the shared throttle at/under
# the documented rate instead of slightly over it, since a 429 costs a much
# more expensive exponential backoff (starts at 1s) than the interval saved
# by pacing tighter than the documented limit.
MIN_REQUEST_INTERVAL_SECONDS = 0.24  # shared client-side throttle across all threads
MAX_ATTEMPTS = 5  # total attempts per call (tenacity's stop_after_attempt counts the initial try, so this is 4 retries)
# The shared throttle (not this count) gates the real aggregate dispatch
# rate, so this only needs to be high enough that a free worker is always
# available when the throttle timer allows the next request - it does not
# multiply throughput past the ~5 req/s ceiling.
ROUTING_MAX_WORKERS = 10

# --- Geocoding -------------------------------------------------------------
# Cap on how many Search API result pages geocode_hdb_blocks will page
# through looking for a non-NIL postal match, so one ambiguous/ high-result
# query can't issue dozens of sequential, throttled requests unbounded.
GEOCODE_SEARCH_MAX_PAGES = 5
