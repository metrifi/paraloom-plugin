#!/usr/bin/env python3
"""End-to-end orchestrator: prompt list -> evidence-shaped markdown report.

Inputs (one of):
  --prompts-file PATH      A markdown file. Each '-' or '*' bullet, or each
                           non-empty line, is one Paraloom prompt.
  --prompts-stdin          Read the same shape from stdin.
  --keywords-per-prompt PATH
                           Optional JSON file: {"<prompt-text>": ["kw1", "kw2", ...]}.
                           If provided, the keyword phrases come from here
                           instead of being heuristically derived.

Other options:
  --location "Wisconsin,United States"   default: "United States"
  --language "English"                   default: "English"
  --topic "<title>"                      report title; default derived from prompts
  --format markdown|json                 default: markdown
  --owned-domains a.com,b.com            tag AI Mode citations as owned
  --competitor-domains x.com,y.com       tag AI Mode citations as competitor
  --skip-ai-mode                         skip the AI Mode SERP calls (faster, cheaper)
  --no-cache                             bypass the 24h cache
  --confirm-cost                         skip the >50-keyword cost confirmation prompt
  --output PATH                          write to file instead of stdout

Exit codes:
  0   success
  2   bad CLI args
  3   missing DATAFORSEO_LOGIN/PASSWORD (raised from _dfs)
  5/6 DataForSEO API error (raised from _dfs)
  7   user did not confirm cost
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import _dfs, ai_mode_serp, search_volume

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "does", "for",
    "from", "have", "how", "i", "in", "is", "it", "of", "on", "or", "so", "the",
    "to", "what", "what's", "whats", "when", "where", "which", "who", "why",
    "will", "with", "you", "your", "should", "can", "could", "would", "best",
    "good",
}

PROMPT_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")


def parse_prompts(text: str) -> List[str]:
    """Parse a markdown bullet list (or one-per-line plain text) into prompts."""
    prompts: List[str] = []
    for line in text.splitlines():
        m = PROMPT_BULLET_RE.match(line)
        if m:
            prompts.append(m.group(1))
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # If we hit a non-bullet, non-blank line and we've already collected bullets,
        # treat it as ignorable prose. Otherwise treat each line as a prompt.
        if not prompts:
            prompts.append(stripped)
    # de-dupe preserving order
    seen, unique = set(), []
    for p in prompts:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def heuristic_keywords(prompt: str, *, max_phrases: int = 4) -> List[str]:
    """Cheap fallback when the caller didn't provide model-generated keywords.

    Strips stopwords, keeps content words in order, and emits 1-3 candidate
    phrases of varying tightness. The caller is strongly encouraged to provide
    its own keyword list via --keywords-per-prompt — this heuristic is just a
    floor so the skill still produces *something* without it.
    """
    cleaned = re.sub(r"[?!.,;:\"']", " ", prompt.lower())
    tokens = [t for t in cleaned.split() if t and t not in STOPWORDS]
    if not tokens:
        return [prompt.lower()]
    full = " ".join(tokens)
    candidates = [full]
    if len(tokens) >= 4:
        candidates.append(" ".join(tokens[:4]))
        candidates.append(" ".join(tokens[-4:]))
    if len(tokens) >= 6:
        candidates.append(" ".join(tokens[:3] + tokens[-2:]))
    out = []
    for c in candidates:
        if c and c not in out:
            out.append(c)
        if len(out) >= max_phrases:
            break
    return out


def load_keywords_per_prompt(path: Optional[str]) -> Dict[str, List[str]]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("--keywords-per-prompt must be a JSON object {prompt: [keywords]}")
    return {k: list(v) for k, v in data.items()}


def cost_preview(n_volume_keywords: int, n_ai_mode_calls: int) -> Dict[str, Any]:
    sv_calls = max(1, (n_volume_keywords + 999) // 1000)
    return {
        "search_volume_calls": sv_calls,
        "ai_mode_calls": n_ai_mode_calls,
        "estimated_cost_usd": (
            _dfs.estimate_cost_usd(search_volume.ENDPOINT, sv_calls)
            + _dfs.estimate_cost_usd(ai_mode_serp.ENDPOINT, n_ai_mode_calls)
        ),
    }


def classify_citation(domain: Optional[str], owned: List[str], competitors: List[str]) -> str:
    if not domain:
        return "other"
    dom = domain.lower()
    for o in owned:
        if dom == o.lower() or dom.endswith("." + o.lower()):
            return "owned"
    for c in competitors:
        if dom == c.lower() or dom.endswith("." + c.lower()):
            return "competitor"
    return "other"


def fmt_cpc(low: Optional[float], high: Optional[float]) -> str:
    if low is None and high is None:
        return "—"
    if low is None:
        return f"≤${high:.2f}"
    if high is None:
        return f"≥${low:.2f}"
    return f"${low:.2f}–${high:.2f}"


def render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Keyword research — {report['topic']}")
    lines.append("")
    lines.append(f"**Generated:** {report['generated_at']}  ")
    lines.append(f"**Source:** {report['source']}  ")
    lines.append(f"**Location:** {report['location']}  ")
    lines.append(f"**Language:** {report['language']}")
    lines.append("")
    lines.append("## Per-prompt results")
    lines.append("")
    for entry in report["prompts"]:
        lines.append(f'### Prompt: "{entry["prompt"]}"')
        lines.append("")
        lines.append("| Keyword phrase | Monthly volume | Competition | CPC range | Search intent |")
        lines.append("|----------------|----------------|-------------|-----------|---------------|")
        for kw in entry["keywords"]:
            comp = kw.get("competition") or "—"
            cpc = fmt_cpc(kw.get("low_top_of_page_bid"), kw.get("high_top_of_page_bid"))
            intent = kw.get("search_intent") or "—"
            lines.append(
                f"| {kw['keyword']} | {kw.get('search_volume') or 0:,} | {comp} | {cpc} | {intent} |"
            )
        lines.append("")
        ai = entry.get("ai_mode") or {}
        lines.append("**AI Mode SERP for this prompt:**")
        if not ai or (not ai.get("ai_answer") and not ai.get("citations")):
            lines.append("- No AI Mode answer surfaced for this query.")
        else:
            cites = ai.get("citations") or []
            if cites:
                rendered = ", ".join(
                    f"[{c.get('domain') or 'source'}]({c['url']})" for c in cites if c.get("url")
                )
                lines.append(f"- Cited sources: {rendered or '—'}")
            else:
                lines.append("- Cited sources: —")
            answer = (ai.get("ai_answer") or "").strip()
            if answer:
                # Trim to ~3 sentences for the dossier; keep full text in JSON output.
                summary = " ".join(re.split(r"(?<=[.!?])\s+", answer)[:3]).strip()
                lines.append(f"- AI answer summary: {summary}")
            lines.append(f"- Owned org appearance: {'yes' if entry.get('owned_appears') else 'no'}")
            comp_doms = entry.get("competitor_domains") or []
            lines.append(
                "- Competitor appearance: " + (", ".join(comp_doms) if comp_doms else "none")
            )
        lines.append("")
    lines.append("## Aggregate signals")
    lines.append("")
    agg = report["aggregate"]
    if agg["highest_volume"]:
        rendered = "; ".join(
            f'"{p}" ({v:,}/mo)' for p, v in agg["highest_volume"]
        )
        lines.append(f"- **Highest-volume prompts:** {rendered}")
    if agg["competitor_cited_prompts"]:
        lines.append(
            "- **Prompts where competitors are cited by AI Mode:** "
            + "; ".join(f'"{p}"' for p in agg["competitor_cited_prompts"])
        )
    if agg["no_ai_mode_prompts"]:
        lines.append(
            "- **Prompts with no AI Mode answer (first-to-publish candidates):** "
            + "; ".join(f'"{p}"' for p in agg["no_ai_mode_prompts"])
        )
    if agg["zero_volume_prompts"]:
        lines.append(
            "- **Prompts with zero search volume across all candidates "
            "(consider deprecating):** "
            + "; ".join(f'"{p}"' for p in agg["zero_volume_prompts"])
        )
    if not any(agg.values()):
        lines.append("- (No aggregate signals — empty input?)")
    lines.append("")
    return "\n".join(lines)


def build_report(
    prompts: List[str],
    *,
    keywords_per_prompt: Dict[str, List[str]],
    location: str,
    language: str,
    topic: str,
    owned: List[str],
    competitors: List[str],
    skip_ai_mode: bool,
    use_cache: bool,
) -> Dict[str, Any]:
    # Build the full keyword list (deduped) for batched volume lookup.
    prompt_to_phrases: Dict[str, List[str]] = {}
    all_phrases: List[str] = []
    seen_phrases: set = set()
    for p in prompts:
        phrases = keywords_per_prompt.get(p) or heuristic_keywords(p)
        prompt_to_phrases[p] = phrases
        for ph in phrases:
            if ph not in seen_phrases:
                seen_phrases.add(ph)
                all_phrases.append(ph)

    # Volume lookup, batched into 1000-keyword chunks.
    volume_rows: List[Dict[str, Any]] = []
    for i in range(0, len(all_phrases), 1000):
        chunk = all_phrases[i:i + 1000]
        volume_rows.extend(
            search_volume.fetch(chunk, location, language, use_cache=use_cache)
        )
    volume_by_kw: Dict[str, Dict[str, Any]] = {r["keyword"]: r for r in volume_rows if r.get("keyword")}

    # AI Mode lookups — one per original prompt (NOT per keyword phrase).
    ai_mode_by_prompt: Dict[str, Dict[str, Any]] = {}
    if not skip_ai_mode:
        for p in prompts:
            ai_mode_by_prompt[p] = ai_mode_serp.fetch(p, location, language, use_cache=use_cache)

    # Assemble per-prompt entries.
    entries = []
    for p in prompts:
        kw_entries = []
        for ph in prompt_to_phrases[p]:
            row = volume_by_kw.get(ph) or {"keyword": ph, "search_volume": 0}
            kw_entries.append(row)
        ai = ai_mode_by_prompt.get(p, {})
        cites = ai.get("citations") or []
        owned_appears = any(
            classify_citation(c.get("domain"), owned, competitors) == "owned" for c in cites
        )
        comp_domains = sorted({
            c.get("domain") for c in cites
            if classify_citation(c.get("domain"), owned, competitors) == "competitor"
            and c.get("domain")
        })
        entries.append({
            "prompt": p,
            "keywords": kw_entries,
            "ai_mode": ai,
            "owned_appears": owned_appears,
            "competitor_domains": comp_domains,
        })

    # Aggregate signals.
    prompt_volume = {
        e["prompt"]: max((k.get("search_volume") or 0) for k in e["keywords"]) if e["keywords"] else 0
        for e in entries
    }
    highest = sorted(prompt_volume.items(), key=lambda kv: -kv[1])[:3]
    highest = [(p, v) for p, v in highest if v > 0]
    competitor_cited = [e["prompt"] for e in entries if e["competitor_domains"]]
    no_ai = [e["prompt"] for e in entries if not (e["ai_mode"] or {}).get("ai_answer")]
    zero_vol = [e["prompt"] for e in entries if prompt_volume.get(e["prompt"], 0) == 0]

    return {
        "topic": topic,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "DataForSEO",
        "location": location,
        "language": language,
        "prompts": entries,
        "aggregate": {
            "highest_volume": highest,
            "competitor_cited_prompts": competitor_cited,
            "no_ai_mode_prompts": no_ai,
            "zero_volume_prompts": zero_vol,
        },
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompts-file")
    src.add_argument("--prompts-stdin", action="store_true")
    p.add_argument("--keywords-per-prompt")
    p.add_argument("--location", default="United States")
    p.add_argument("--language", default="English")
    p.add_argument("--topic", default="")
    p.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p.add_argument("--owned-domains", default="")
    p.add_argument("--competitor-domains", default="")
    p.add_argument("--skip-ai-mode", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--confirm-cost", action="store_true")
    p.add_argument("--output")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.prompts_stdin:
        text = sys.stdin.read()
    else:
        text = Path(args.prompts_file).read_text(encoding="utf-8")
    prompts = parse_prompts(text)
    if not prompts:
        print("ERROR: no prompts parsed from input.", file=sys.stderr)
        return 2

    kpp = load_keywords_per_prompt(args.keywords_per_prompt)
    # Build effective keyword list to estimate cost.
    total_kw = 0
    seen: set = set()
    for p in prompts:
        for ph in (kpp.get(p) or heuristic_keywords(p)):
            if ph not in seen:
                seen.add(ph)
                total_kw += 1
    n_ai = 0 if args.skip_ai_mode else len(prompts)

    if total_kw > 50 and not args.confirm_cost:
        preview = cost_preview(total_kw, n_ai)
        print(
            f"Cost preview: {total_kw} unique keywords across "
            f"{preview['search_volume_calls']} search_volume call(s) "
            f"+ {preview['ai_mode_calls']} AI Mode call(s). "
            f"Estimated cost: ~${preview['estimated_cost_usd']:.2f}. "
            "Re-run with --confirm-cost to proceed.",
            file=sys.stderr,
        )
        return 7

    topic = args.topic or prompts[0][:60]
    owned = [d.strip() for d in args.owned_domains.split(",") if d.strip()]
    competitors = [d.strip() for d in args.competitor_domains.split(",") if d.strip()]
    report = build_report(
        prompts,
        keywords_per_prompt=kpp,
        location=args.location,
        language=args.language,
        topic=topic,
        owned=owned,
        competitors=competitors,
        skip_ai_mode=args.skip_ai_mode,
        use_cache=not args.no_cache,
    )

    if args.format == "json":
        out = json.dumps(report, indent=2, default=str)
    else:
        out = render_markdown(report)

    if args.output:
        Path(args.output).write_text(out + ("\n" if not out.endswith("\n") else ""), encoding="utf-8")
    else:
        sys.stdout.write(out)
        if not out.endswith("\n"):
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
