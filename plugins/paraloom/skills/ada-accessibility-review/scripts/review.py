#!/usr/bin/env python3
"""Entrypoint: review a markdown article for ADA / WCAG 2.1 AA compliance.

Usage:
    python review.py <article-path> [--target-grade N] [--audience "..."]

Writes the report next to the article as <basename>.accessibility-review.md.
Exit code is 0 even when issues are found — this is an advisory tool, not a
gate. Pipelines that want to block on BLOCK issues can grep the report or
parse the JSON sidecar (--json).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Make sibling modules importable when invoked as `python review.py`.
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from markdown_audit import audit, Issue  # noqa: E402
from reading_level import compute_metrics, hardest_sentences, suggest_simplification  # noqa: E402
from wcag_checks import deferred_checks, run_all_checks  # noqa: E402


SKILL_VERSION = "1.0.0"


def _shorten(text: str, n: int = 80) -> str:
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _article_title(headings, fallback: str) -> str:
    h1s = [h for h in headings if h.level == 1]
    if h1s:
        return h1s[0].text.strip() or fallback
    return fallback


def _render_report(article_path: Path, audit_result, metrics, issues: List[Issue],
                   target_grade: int, audience: str) -> str:
    title = _article_title(audit_result.headings, fallback=article_path.stem)

    by_sev = {"BLOCK": [], "WARN": [], "DEFER": [], "NIT": []}
    for i in issues:
        by_sev.setdefault(i.severity, []).append(i)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    grades = (metrics.flesch_kincaid_grade,
              metrics.smog_index,
              metrics.gunning_fog)
    pass_status = "PASS" if max(grades) <= target_grade else "FLAGGED"

    lines: List[str] = []
    a = lines.append

    a(f"# Accessibility Review — {title}")
    a("")
    a(f"**Reviewed:** {timestamp}")
    a(f"**Article path:** {article_path}")
    a(f"**Audience:** {audience}")
    a("**Standard:** WCAG 2.1 AA (with AAA reading-level checks for general audience)")
    a(f"**Skill version:** {SKILL_VERSION}")
    a("")
    a("## Summary")
    a("")
    a(f"- BLOCK issues: {len(by_sev['BLOCK'])}")
    a(f"- WARN issues: {len(by_sev['WARN'])}")
    a(f"- DEFER (page-level): {len(by_sev['DEFER'])}")
    a(f"- NIT issues: {len(by_sev['NIT'])}")
    a("")
    a("**Reading level:**")
    a("")
    a(f"- Flesch-Kincaid Grade: {metrics.flesch_kincaid_grade}")
    a(f"- SMOG Index: {metrics.smog_index}")
    a(f"- Gunning Fog: {metrics.gunning_fog}")
    a(f"- Target: grade ≤ {target_grade}")
    a(f"- Status: {pass_status}")
    a("")
    a("> ⚠️ This is a content-level audit. A rendered-page audit (color "
      "contrast, keyboard navigation, screen reader compatibility) using axe "
      "DevTools, Lighthouse, or WAVE is still required before publication.")
    a("")
    a("## Issues")
    a("")
    a("Issues are listed in this order: BLOCK first (must fix), then WARN, "
      "then DEFER (page-level checks for downstream auditing), then NIT.")
    a("")

    def _emit_issues(severity: str):
        items = by_sev.get(severity, [])
        if not items:
            a(f"_No {severity} issues._")
            a("")
            return
        for idx, issue in enumerate(items, start=1):
            a(f"### {severity} {idx}: {issue.title}")
            a("")
            a(f"**Location:** {issue.location}")
            a(f"**WCAG criterion:** {issue.wcag}")
            a(f"**Issue:** {issue.detail}")
            a(f"**Fix:** {issue.fix}")
            a("")

    _emit_issues("BLOCK")
    _emit_issues("WARN")
    _emit_issues("DEFER")
    _emit_issues("NIT")

    a("## Reading-level breakdown")
    a("")
    a(f"- Sentence count: {metrics.sentence_count}")
    a(f"- Word count: {metrics.word_count}")
    a(f"- Average words per sentence: {metrics.avg_words_per_sentence}")
    a(f"- Average syllables per word: {metrics.avg_syllables_per_word}")
    a(f"- Complex words (3+ syllables, non-proper): {metrics.complex_word_count}")
    a("")
    a("Most-difficult passages (top 3 by sentence-level Flesch-Kincaid):")
    a("")
    for i, (sent, grade) in enumerate(hardest_sentences(metrics, n=3), start=1):
        a(f"  {i}. \"{_shorten(sent, 160)}\" — grade {grade}.")
        a(f"     Suggested simplification: {suggest_simplification(sent)}")
    a("")
    a("## Reviewer sign-off")
    a("")
    a("- [ ] All BLOCK items resolved")
    a("- [ ] WARN items reviewed")
    a("- [ ] Reading level meets target OR exceptions documented")
    a("- [ ] Rendered-page audit scheduled (note: not part of this skill)")
    a("- [ ] Final review by: __________________ (name)")
    a("- [ ] Sign-off date: __________________")
    a("")

    return "\n".join(lines)


def review_article(article_path: Path, target_grade: int = 9,
                   audience: str = "general consumer") -> dict:
    text = article_path.read_text(encoding="utf-8")

    audit_result = audit(text)
    metrics = compute_metrics(audit_result.body_text or text)
    issues = run_all_checks(audit_result, metrics, target_grade, audience)
    issues.extend(deferred_checks())

    report = _render_report(article_path, audit_result, metrics, issues,
                            target_grade, audience)
    out_path = article_path.with_name(article_path.stem + ".accessibility-review.md")
    out_path.write_text(report, encoding="utf-8")

    counts = {"BLOCK": 0, "WARN": 0, "DEFER": 0, "NIT": 0}
    for i in issues:
        counts[i.severity] = counts.get(i.severity, 0) + 1
    return {
        "report_path": str(out_path),
        "counts": counts,
        "metrics": {
            "flesch_kincaid_grade": metrics.flesch_kincaid_grade,
            "smog_index": metrics.smog_index,
            "gunning_fog": metrics.gunning_fog,
            "target_grade": target_grade,
            "pass": max(metrics.flesch_kincaid_grade,
                        metrics.smog_index,
                        metrics.gunning_fog) <= target_grade,
        },
        "issues": [
            {
                "severity": i.severity,
                "title": i.title,
                "wcag": i.wcag,
                "location": i.location,
            }
            for i in issues
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Review a markdown article for WCAG 2.1 AA accessibility (content-level)."
    )
    p.add_argument("article_path", help="Path to the markdown article")
    p.add_argument("--target-grade", type=int, default=9,
                   help="Reading-level target grade (default 9)")
    p.add_argument("--audience", default="general consumer",
                   help="Audience descriptor used in the report")
    p.add_argument("--json", action="store_true",
                   help="Emit a JSON summary to stdout (the markdown report is "
                        "still written next to the article)")
    args = p.parse_args(argv)

    article = Path(args.article_path)
    if not article.is_file():
        print(f"error: not a file: {article}", file=sys.stderr)
        return 2

    result = review_article(article, target_grade=args.target_grade,
                            audience=args.audience)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        c = result["counts"]
        print(
            f"Wrote {result['report_path']}\n"
            f"  BLOCK: {c['BLOCK']}  WARN: {c['WARN']}  DEFER: {c['DEFER']}  NIT: {c['NIT']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
