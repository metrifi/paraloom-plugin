#!/usr/bin/env python3
"""Escape hatch: POST any DataForSEO endpoint with a JSON body, get raw JSON.

Use this for endpoints not yet wrapped (e.g. the AI Overview parsing path on
serp/google/organic/live/advanced). Caching and auth still apply.

Usage:
  python -m scripts.raw_post serp/google/organic/live/advanced < payload.json
"""
from __future__ import annotations

import json
import sys

from . import _dfs


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: raw_post.py <endpoint-path> [< payload.json]", file=sys.stderr)
        return 2
    endpoint = sys.argv[1]
    payload = json.load(sys.stdin)
    use_cache = "--no-cache" not in sys.argv
    data = _dfs.post(endpoint, payload, use_cache=use_cache)
    json.dump(data, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
