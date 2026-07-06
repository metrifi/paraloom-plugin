#!/usr/bin/env python3
"""Wrap DataForSEO /keywords_data/google_ads/search_volume/live.

Usage:
  python -m scripts.search_volume --keywords "kw1,kw2" \
      --location "Wisconsin,United States" --language "English"

  echo '["kw1","kw2"]' | python -m scripts.search_volume \
      --keywords-stdin --location "United States"

Writes the parsed result list to stdout as JSON (one entry per keyword). Each
entry has the shape:

  {
    "keyword": "...",
    "search_volume": 1900,
    "competition": "MEDIUM",            # LOW / MEDIUM / HIGH / null
    "competition_index": 47,            # 0-100 or null
    "cpc": 1.23,                        # USD or null
    "low_top_of_page_bid": 0.45,
    "high_top_of_page_bid": 2.10,
    "monthly_searches": [ { "year": 2025, "month": 4, "search_volume": 1800 }, ... ]
  }

Exits non-zero on auth or API errors.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import _dfs

ENDPOINT = "keywords_data/google_ads/search_volume/live"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--keywords", help="Comma-separated keyword list")
    p.add_argument("--keywords-stdin", action="store_true",
                   help="Read keywords as a JSON array from stdin")
    p.add_argument("--location", default="United States",
                   help='Location name, e.g. "Wisconsin,United States"')
    p.add_argument("--language", default="English", help="Language name")
    p.add_argument("--no-cache", action="store_true", help="Bypass the 24h cache")
    return p.parse_args()


def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "keyword": row.get("keyword"),
        "search_volume": row.get("search_volume") or 0,
        "competition": row.get("competition"),
        "competition_index": row.get("competition_index"),
        "cpc": row.get("cpc"),
        "low_top_of_page_bid": row.get("low_top_of_page_bid"),
        "high_top_of_page_bid": row.get("high_top_of_page_bid"),
        "monthly_searches": row.get("monthly_searches") or [],
    }


def fetch(keywords: List[str], location: str, language: str, *, use_cache: bool = True) -> List[Dict[str, Any]]:
    if not keywords:
        return []
    payload = {
        "keywords": keywords,
        "location_name": location,
        "language_name": language,
    }
    data = _dfs.post(ENDPOINT, payload, use_cache=use_cache)
    tasks = data.get("tasks") or []
    rows: List[Dict[str, Any]] = []
    for task in tasks:
        for result in task.get("result") or []:
            # search_volume/live returns one row per keyword inside the task
            # result list. The "items" key may or may not be present depending
            # on API version; handle both shapes.
            items = result.get("items")
            if items is None:
                rows.append(normalize_row(result))
            else:
                for item in items:
                    rows.append(normalize_row(item))
    # Ensure we have a row for every requested keyword, even if API skipped it.
    seen = {r["keyword"] for r in rows if r.get("keyword")}
    for kw in keywords:
        if kw not in seen:
            rows.append({
                "keyword": kw,
                "search_volume": 0,
                "competition": None,
                "competition_index": None,
                "cpc": None,
                "low_top_of_page_bid": None,
                "high_top_of_page_bid": None,
                "monthly_searches": [],
            })
    return rows


def main() -> int:
    args = parse_args()
    if args.keywords_stdin:
        keywords = json.load(sys.stdin)
        if not isinstance(keywords, list):
            print("ERROR: stdin must be a JSON array", file=sys.stderr)
            return 2
    elif args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    else:
        print("ERROR: pass --keywords or --keywords-stdin", file=sys.stderr)
        return 2

    rows = fetch(keywords, args.location, args.language, use_cache=not args.no_cache)
    json.dump(rows, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
