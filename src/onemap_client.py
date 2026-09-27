"""Authentication and a retrying HTTP wrapper for the OneMap API."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

import config

load_dotenv()

BASE_URL = "https://www.onemap.gov.sg"
TOKEN_URL = f"{BASE_URL}/api/auth/post/getToken"


class OneMapAuthError(RuntimeError):
    pass


class RetryableHTTPError(RuntimeError):
    """Raised for 429/5xx responses so tenacity knows to retry."""


def _load_credentials() -> tuple[str, str]:
    import os

    email = os.environ.get("ONEMAP_EMAIL")
    password = os.environ.get("ONEMAP_PASSWORD")
    if not email or not password:
        raise OneMapAuthError(
            "ONEMAP_EMAIL / ONEMAP_PASSWORD not set. Copy .env.example to .env "
            "and fill in your OneMap account credentials."
        )
    return email, password


def _fetch_new_token() -> dict[str, Any]:
    email, password = _load_credentials()
    resp = requests.post(TOKEN_URL, json={"email": email, "password": password}, timeout=30)
    if resp.status_code != 200:
        raise OneMapAuthError(f"getToken failed ({resp.status_code}): {resp.text[:500]}")
    payload = resp.json()
    if "access_token" not in payload:
        raise OneMapAuthError(f"getToken response missing access_token: {payload}")
    return payload


def _is_expiring_soon(expiry_timestamp: Any, buffer_seconds: int = 3600) -> bool:
    try:
        expiry = float(expiry_timestamp)
    except (TypeError, ValueError):
        return True
    now = datetime.now(timezone.utc).timestamp()
    return (expiry - now) < buffer_seconds


_token_lock = threading.Lock()


def get_token(force_refresh: bool = False) -> str:
    """Return a valid OneMap bearer token, refreshing and caching as needed.

    Guarded by a lock so concurrent worker threads don't all race to refresh
    the token (and clobber the cache file) at once when it's near expiry.
    """
    cache_path: Path = config.TOKEN_CACHE_PATH
    with _token_lock:
        if not force_refresh and cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text())
                if not _is_expiring_soon(cached.get("expiry_timestamp")):
                    return cached["access_token"]
            except (json.JSONDecodeError, KeyError):
                pass

        payload = _fetch_new_token()
        cache_path.write_text(json.dumps(payload))
        return payload["access_token"]


class OneMapClient:
    """Thin wrapper around requests with auth, throttling, and retries."""

    def __init__(self) -> None:
        # A single requests.Session is safe to share across threads for
        # simple GET calls. Throttle state (_throttle_lock/_last_request_time)
        # is shared across all threads, not per-thread - OneMap's ~5 req/s
        # ceiling is a server-side aggregate limit, so per-thread throttling
        # would let N concurrent workers each independently run at 5 req/s,
        # multiplying aggregate throughput by N over the real ceiling.
        self._session = requests.Session()
        self._throttle_lock = threading.Lock()
        self._last_request_time = 0.0

    def _headers(self) -> dict[str, str]:
        return {"Authorization": get_token()}

    def _throttle(self) -> None:
        with self._throttle_lock:
            elapsed = time.monotonic() - self._last_request_time
            wait = config.MIN_REQUEST_INTERVAL_SECONDS - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_request_time = time.monotonic()

    @retry(
        retry=retry_if_exception_type(RetryableHTTPError),
        stop=stop_after_attempt(config.MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        reraise=True,
    )
    def get(self, path: str, params: dict[str, Any] | None = None, *, base_url: str = BASE_URL) -> Any:
        self._throttle()
        url = f"{base_url}{path}"
        resp = self._session.get(url, params=params, headers=self._headers(), timeout=30)

        if resp.status_code == 401:
            # Token likely expired/invalid mid-run: force a refresh and retry once.
            get_token(force_refresh=True)
            raise RetryableHTTPError(f"401 from {path}, refreshed token and retrying")
        if resp.status_code == 429 or resp.status_code >= 500:
            raise RetryableHTTPError(f"{resp.status_code} from {path}: {resp.text[:200]}")
        resp.raise_for_status()
        return resp.json()
