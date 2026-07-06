#!/usr/bin/env python3
"""Wrap DataForSEO /keywords_data/google_ads/keywords_for_keywords/live.

Given a seed keyword (or seeds), return related keywords with monthly volume
and competition. Useful for expanding a Paraloom prompt into adjacent queries.

Usage:
  python -m scripts.keywords_for_keywords --seeds "cd rates wisconsin" \
      --location "Wisconsin,United States" --language "English"

Stdout: JSON array of related-keyword rows.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import _dfs

ENDPOINT = "keywords_data/google_ads/keywords_for_keywords/live"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", required=True, help="Comma-separated seed keywords")
    p.add_argument("--location", default="United States")
    p.add_argument("--language", default="English")
    p.add_argument("--limit", type=int, default=200, help="Max related keywords to return")
    p.add_argument("--no-cache", action="store_true")
    return p.parse_args()


def fetch(seeds: List[str], location: str, language: str, *,
          limit: int = 200, use_cache: bool = True) -> List[Dict[str, Any]]:
    payload = {
        "keywords": seeds,
        "location_name": location,
        "language_name": language,
        "limit": limit,
    }
    data = _dfs.post(ENDPOINT, payload, use_cache=use_cache)
    rows: List[Dict[str, Any]] = []
    for task in data.get("tasks") or []:
        for result in task.get("result") or []:
            items = result.get("items") or [result]
            for item in items:
                rows.append({
                    "keyword": item.get("keyword"),
                    "search_volume": item.get("search_volume") or 0,
                    "competition": item.get("competition"),
                    "competition_index": item.get("competition_index"),
                    "cpc": item.get("cpc"),
                    "monthly_searches": item.get("monthly_searches") or [],
                })
    return rows


def main() -> int:
    args = parse_args()
    seeds = [s.strip() for s in args.seeds.split(",") if s.strip()]
    if not seeds:
        print("ERROR: pass at least one seed via --seeds", file=sys.stderr)
        return 2
    rows = fetch(seeds, args.location, args.language, limit=args.limit,
                 use_cache=not args.no_cache)
    json.dump(rows, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
