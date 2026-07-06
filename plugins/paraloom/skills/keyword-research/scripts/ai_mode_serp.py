#!/usr/bin/env python3
"""Wrap DataForSEO /serp/google/ai_mode/live/advanced.

Captures Google's AI Mode answer for a query along with the citations Google's
AI pulls from. This is the AI-search-demand piece — it tells us what Google's
AI is currently saying about a topic and which sources are getting cited.

Usage:
  python -m scripts.ai_mode_serp --query "best cd rates wisconsin retirees" \
      --location "Wisconsin,United States" --language "English"

Stdout JSON shape:
  {
    "query": "...",
    "ai_answer": "Full AI-Mode answer text concatenated from blocks.",
    "citations": [ { "domain": "...", "url": "...", "title": "..." }, ... ],
    "raw": { ... }   # full SERP item, for advanced consumers
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from . import _dfs

ENDPOINT = "serp/google/ai_mode/live/advanced"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", required=True)
    p.add_argument("--location", default="United States")
    p.add_argument("--language", default="English")
    p.add_argument("--no-cache", action="store_true")
    return p.parse_args()


def _domain_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        host = urlparse(url).hostname
        return host.lstrip("www.") if host else None
    except ValueError:
        return None


def _collect_citations(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Walk the AI Mode item shape and pull every cited link.

    DataForSEO's AI Mode response varies; citations show up under several keys:
    `references`, `links`, or inline inside `items` of nested blocks. We walk
    the structure defensively rather than assume one shape.
    """
    found: List[Dict[str, Any]] = []
    seen = set()

    def add(url: Optional[str], title: Optional[str]) -> None:
        if not url or url in seen:
            return
        seen.add(url)
        found.append({"domain": _domain_of(url), "url": url, "title": title})

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            url = node.get("url") or node.get("link")
            if url and isinstance(url, str) and url.startswith("http"):
                add(url, node.get("title") or node.get("text"))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(item)
    return found


def _collect_answer_text(item: Dict[str, Any]) -> str:
    """Pull AI Mode answer text from blocks/components/items, in reading order."""
    parts: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            # Common text-bearing keys in DataForSEO AI Mode responses.
            for key in ("text", "answer", "content", "description"):
                val = node.get(key)
                if isinstance(val, str) and val.strip() and val not in parts:
                    parts.append(val.strip())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(item)
    return "\n\n".join(parts)


def fetch(query: str, location: str, language: str, *, use_cache: bool = True) -> Dict[str, Any]:
    payload = {
        "keyword": query,
        "location_name": location,
        "language_name": language,
    }
    data = _dfs.post(ENDPOINT, payload, use_cache=use_cache)
    item: Dict[str, Any] = {}
    for task in data.get("tasks") or []:
        for result in task.get("result") or []:
            items = result.get("items") or []
            if items:
                item = items[0]
                break
            # Some responses inline the AI Mode block at the result level.
            if "ai_mode" in result or "ai_overview" in result:
                item = result
                break
        if item:
            break
    return {
        "query": query,
        "ai_answer": _collect_answer_text(item),
        "citations": _collect_citations(item),
        "raw": item,
    }


def main() -> int:
    args = parse_args()
    out = fetch(args.query, args.location, args.language, use_cache=not args.no_cache)
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
