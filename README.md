# HDO Accessibility

How many [HPB Healthier Dining Programme](https://www.hpb.gov.sg/healthy-living/food-beverage/healthier-dining-programme) options are within 1 km true walking distance of each HDB residential postal code in Singapore?

This pipeline sources both datasets through [OneMap](https://www.onemap.gov.sg/) (Singapore's national map platform) and computes true walking-route distance — not straight-line — via OneMap's Routing API.

**[Explore the results in the live dashboard →](https://hdoaccessibility-efgzng32zrdwamfydfpjgb.streamlit.app/)**

## What it does

1. Fetches Healthier Dining Programme locations from OneMap's theme API.
2. Fetches HDB residential postal codes by geocoding data.gov.sg's HDB Property Information dataset through OneMap's Search API.
3. For each residential postal code, finds every dining option within 1 km of *true walking distance* (via OneMap's Routing API, `routeType=walk`) — not straight-line distance — and counts them.
4. Publishes the result as `data/processed/accessibility_by_postal_code.csv`, and browsable via a Streamlit dashboard (map, hex-density heatmap, district comparison, distribution).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ONEMAP_EMAIL / ONEMAP_PASSWORD (register at onemap.gov.sg/apidocs/register)
git config core.hooksPath githooks   # enables a pre-commit check that postal codes stay 6-digit strings
```

OneMap has no static API key — auth is email+password exchanged for a JWT, handled automatically and cached locally.

## Usage

```bash
python main.py discover                   # dump OneMap's theme catalog
python main.py dining                     # fetch healthier dining locations
python main.py residential                # fetch HDB residential postal codes
python main.py accessibility [--limit N]  # compute walking-distance access
python main.py all [--limit N]            # run the full pipeline end to end
```

`--limit N` truncates to the first N residential points — always validate on a small sample before a full run. The full `accessibility` run makes on the order of 10^5 routing API calls and takes hours, not minutes.

To browse the results:

```bash
streamlit run dashboard/app.py
```

## Architecture

- `src/fetch_dining.py` — pulls the dining theme via OneMap's `retrieveTheme`.
- `src/fetch_residential.py` — merges data.gov.sg's HDB Property Information dataset (geocoded block-by-block through OneMap's Search API, with caching) with an optional condo/private-residential theme if configured. Coverage is currently HDB-only, since OneMap has no private-residential theme.
- `src/compute_accessibility.py` — the core algorithm:
  1. A haversine pre-filter (BallTree) narrows each residential point to dining candidates within 1 km straight-line distance.
  2. OneMap's Routing API resolves true walking distance for each surviving candidate pair, run concurrently with a shared rate-limited client and cached to disk so interrupted runs can resume.
- `dashboard/` — a Streamlit app for browsing the final CSV (map, H3 hex-density, district comparison, distribution, filterable data table).

Full implementation details, gotchas (postal-code dtype handling, rate limits, caching semantics), and data-file conventions are documented in [CLAUDE.md](CLAUDE.md).

## Data

- `data/raw/` — intermediate fetches and caches (gitignored, regenerable).
- `data/processed/accessibility_by_postal_code.csv` — the tracked deliverable: the final answer to the business question, committed so it's reviewable without re-running the pipeline.

No test suite, linter, or build step exists in this repo.
