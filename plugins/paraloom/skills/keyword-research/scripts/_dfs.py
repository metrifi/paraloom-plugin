"""Shared helpers for DataForSEO endpoint scripts.

Responsibilities:
  - Read DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD from env, build HTTP Basic auth.
  - Cache POST responses for 24h under ~/.cache/keyword-research/<endpoint>/<hash>.json.
  - Provide a uniform `post(endpoint, payload)` that handles auth + cache + errors.
  - Never log or echo credentials.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    print("ERROR: 'requests' is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(2)

API_BASE = "https://api.dataforseo.com"
CACHE_ROOT = Path(os.path.expanduser("~/.cache/keyword-research"))
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24h

# Per-endpoint approximate cost in USD per call. Used only for the cost preview
# in research.py — these are conservative public-list-price estimates and the
# real bill is whatever DataForSEO invoices. Update if pricing changes.
ENDPOINT_COST_USD = {
    "keywords_data/google_ads/search_volume/live": 0.05,
    "keywords_data/google_ads/keywords_for_keywords/live": 0.05,
    "dataforseo_labs/google/keyword_ideas/live": 0.01,
    "serp/google/ai_mode/live/advanced": 0.005,
    "serp/google/organic/live/advanced": 0.002,
}


def _load_env_file(path: Path) -> None:
    """Best-effort .env loader: KEY=value per line, # comments allowed.

    Existing environment values win — explicit env always overrides the file.
    Quietly returns on any read/parse error; the caller's auth check will
    still fire if creds aren't set.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def _autoload_credentials() -> None:
    """Look for a .dataforseo.env file in a few sensible places and load it.

    Search order (first hit wins, but env vars already set are never overwritten):
      1. $DATAFORSEO_ENV (explicit override)
      2. .dataforseo.env in the current working directory
      3. .dataforseo.env walking up from CWD (so running from any subfolder works)
      4. ~/.dataforseo.env
    """
    explicit = os.environ.get("DATAFORSEO_ENV")
    if explicit:
        _load_env_file(Path(explicit))
        return

    cwd = Path.cwd()
    candidates = [cwd / ".dataforseo.env"]
    for parent in cwd.parents:
        candidates.append(parent / ".dataforseo.env")
    candidates.append(Path.home() / ".dataforseo.env")

    for c in candidates:
        if c.is_file():
            _load_env_file(c)
            return


def _auth_header() -> str:
    if not os.environ.get("DATAFORSEO_LOGIN") or not os.environ.get("DATAFORSEO_PASSWORD"):
        _autoload_credentials()
    login = os.environ.get("DATAFORSEO_LOGIN")
    password = os.environ.get("DATAFORSEO_PASSWORD")
    if not login or not password or login.startswith("replace-with-"):
        print(
            "ERROR: DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are not set. "
            "Either edit .dataforseo.env in your project folder with real "
            "credentials, export them inline, or fall back to the browser "
            "path (see references/browser_fallback.md).",
            file=sys.stderr,
        )
        sys.exit(3)
    token = base64.b64encode(f"{login}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _cache_path(endpoint: str, payload: Any) -> Path:
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(payload_bytes).hexdigest()[:32]
    safe_endpoint = endpoint.strip("/").replace("/", "__")
    return CACHE_ROOT / safe_endpoint / f"{digest}.json"


def _cache_read(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > CACHE_TTL_SECONDS:
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _cache_write(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh)
    except OSError:
        # Cache write failures are non-fatal — better to lose the cache than to
        # crash the lookup.
        pass


def post(endpoint: str, payload: Any, *, use_cache: bool = True, timeout: int = 60) -> Dict[str, Any]:
    """POST to a DataForSEO endpoint, with optional 24h caching.

    `endpoint` is the path after /v3/, e.g. "keywords_data/google_ads/search_volume/live".
    `payload` is the request body — DataForSEO expects an array of task objects, but
    callers may pass a single dict for convenience; we wrap it in a list automatically.
    """
    if isinstance(payload, dict):
        body = [payload]
    else:
        body = payload

    cache_path = _cache_path(endpoint, body)
    if use_cache:
        cached = _cache_read(cache_path)
        if cached is not None:
            cached["_cached"] = True
            return cached

    url = f"{API_BASE}/v3/{endpoint.strip('/')}"
    headers = {"Authorization": _auth_header(), "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=timeout)

    # Try to parse JSON regardless of status — DataForSEO often returns a JSON
    # error body that's more useful than the HTTP status alone.
    try:
        data = resp.json()
    except ValueError:
        print(f"ERROR: non-JSON response from {endpoint} (HTTP {resp.status_code})", file=sys.stderr)
        sys.exit(4)

    if resp.status_code != 200:
        msg = data.get("status_message") if isinstance(data, dict) else str(data)[:200]
        print(f"ERROR: DataForSEO {endpoint} returned HTTP {resp.status_code}: {msg}", file=sys.stderr)
        sys.exit(5)

    if isinstance(data, dict) and data.get("status_code") not in (20000, None):
        msg = data.get("status_message", "unknown error")
        print(f"ERROR: DataForSEO {endpoint} status {data.get('status_code')}: {msg}", file=sys.stderr)
        sys.exit(6)

    data["_cached"] = False
    if use_cache:
        _cache_write(cache_path, data)
    return data


def estimate_cost_usd(endpoint: str, n_calls: int) -> float:
    rate = ENDPOINT_COST_USD.get(endpoint.strip("/"), 0.05)
    return round(rate * n_calls, 4)
