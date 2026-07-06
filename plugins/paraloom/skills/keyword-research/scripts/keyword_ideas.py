#!/usr/bin/env python3
"""Wrap DataForSEO /dataforseo_labs/google/keyword_ideas/live.

Returns keyword ideas with monthly volume, competition, and search intent
classification (informational / commercial / transactional / navigational).

Usage:
  python -m scripts.keyword_ideas --seeds "cd rates wisconsin" \
      --location "Wisconsin,United States" --language "English"

Stdout: JSON array of keyword-idea rows including `search_intent`.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from . import _dfs

ENDPOINT = "dataforseo_labs/google/keyword_ideas/live"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", required=True, help="Comma-separated seed keywords")
    p.add_argument("--location", default="United States")
    p.add_argument("--language", default="English")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--no-cache", action="store_true")
    return p.parse_args()


def fetch(seeds: List[str], location: str, language: str, *,
          limit: int = 200, use_cache: bool = True) -> List[Dict[str, Any]]:
    payload = {
        "keywords": seeds,
        "location_name": location,
        "language_name": language,
        "limit": limit,
        "include_serp_info": False,
    }
    data = _dfs.post(ENDPOINT, payload, use_cache=use_cache)
    rows: List[Dict[str, Any]] = []
    for task in data.get("tasks") or []:
        for result in task.get("result") or []:
            for item in result.get("items") or []:
                kinfo = item.get("keyword_info") or {}
                intent = (item.get("search_intent_info") or {}).get("main_intent")
                rows.append({
                    "keyword": item.get("keyword"),
                    "search_volume": kinfo.get("search_volume") or 0,
                    "competition": kinfo.get("competition_level") or kinfo.get("competition"),
                    "competition_index": kinfo.get("competition_index"),
                    "cpc": kinfo.get("cpc"),
                    "search_intent": intent,
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
