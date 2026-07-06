#!/usr/bin/env python3
"""Focused hygiene check — AI-tell detection + render-correctness only.

Goal (per Ryan, 2026-05-06): the hygiene check should answer one main
question — does this article look obviously AI-written? The classic LLM
giveaway is the em dash. The canonical `article-hygiene-check` skill also
flags hyphen overuse, hyphen density, and compound creep, which fire on
legitimate financial-domain terms ("first-time-buyer",
"WHEDA-participating-lender", "down-payment-assistance"). Those rules
produced 46 warnings on this draft — too noisy for client review and not
indicative of AI generation.

This script keeps the useful parts and drops the noise:

KEEPS
- Em dash detection (the AI-tell)
- En dash detection (smaller AI-tell)
- A small set of common AI-phrase tells ("delve into", "it's important to
  note", "in conclusion", "I'd be happy to")
- Spelling check via pyspellchecker + custom dictionary
- Markdown integrity (broken link targets, missing image alt)
- HTML render with transforms + verification (external links get
  rel="nofollow" target="_blank", tables get class="table", image alt
  preserved)

DROPS
- Hyphen overuse (per sentence + density)
- Compound creep
- Quote consistency NITs
- Whitespace NITs

Usage:
  python3 focused-hygiene-check.py \
    --article <path-to-article.md> \
    --credit-union-domain heartlandcu.org \
    --dictionary <path-to-dictionary.txt> \
    --output-html <path-to-rendered.html>

Output: writes <article>.hygiene-check.md next to the source.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from markdown_it import MarkdownIt
except ImportError:
    print("ERROR: markdown-it-py not installed. Install with:\n"
          "  pip3 install markdown-it-py", file=sys.stderr)
    sys.exit(1)

try:
    from spellchecker import SpellChecker
except ImportError:
    SpellChecker = None  # type: ignore

EM_DASH = "—"
EN_DASH = "–"

AI_PHRASE_PATTERNS = [
    (r"\bdelve\s+into\b",                              "delve into"),
    (r"\bit'?s\s+important\s+to\s+note\b",             "it's important to note"),
    (r"\bit'?s\s+worth\s+noting\b",                    "it's worth noting"),
    (r"\bin\s+conclusion\b",                           "in conclusion"),
    (r"\bI'?d\s+be\s+happy\s+to\b",                    "I'd be happy to"),
    (r"\bI\s+hope\s+this\s+helps\b",                   "I hope this helps"),
    (r"\blet\s+me\s+know\s+if\b",                      "let me know if"),
    (r"\bin\s+the\s+ever[- ]evolving\b",               "in the ever-evolving"),
    (r"\bnavigating\s+the\s+complexities\b",           "navigating the complexities"),
    (r"\bit\s+goes\s+without\s+saying\b",              "it goes without saying"),
    (r"\bwhen\s+it\s+comes\s+to\b",                    "when it comes to"),
    (r"\bin\s+today'?s\s+(fast[- ]paced|digital)\b",   "in today's fast-paced / digital"),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--article", required=True, help="Path to the article markdown file")
    p.add_argument("--credit-union-domain", required=True, help="Owned domain (e.g. heartlandcu.org)")
    p.add_argument("--dictionary", help="Optional custom dictionary path")
    p.add_argument("--output-html", help="Where to write rendered HTML (default: alongside source)")
    p.add_argument("--output-report", help="Where to write the hygiene report (default: alongside source)")
    p.add_argument("--em-dash-tolerance", type=int, default=0,
                   help="Number of em dashes allowed before flagging (default: 0)")
    return p.parse_args()


def load_dictionary(custom_path: Optional[str]) -> set[str]:
    """Build a custom-words set: bundled credit-union seed terms + any custom file."""
    base = {
        "heartland", "ncua", "ncua's", "wheda", "wheda's", "fhlbank",
        "downpayment", "uwcu", "fha", "usda", "va", "wb-11", "sps", "dsps",
        "eretr", "hmda", "homeready", "homepossible", "preapproval",
        "preapproved", "underwritten", "fthb", "covid-19",
    }
    if custom_path and Path(custom_path).exists():
        for line in Path(custom_path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                base.add(line.lower())
    return base


def strip_code_and_attrs(md_source: str) -> str:
    """Return md_source with fenced code blocks, inline code, and link targets removed.

    We don't want spelling/AI-tell checks firing on code identifiers, URLs, or
    image-alt-attribute targets.
    """
    s = re.sub(r"```.*?```", " ", md_source, flags=re.DOTALL)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", s)  # images
    s = re.sub(r"\]\([^)]*\)", "] ", s)             # link targets (keep label)
    return s


# ------------- Findings --------------

class Finding:
    def __init__(self, severity: str, rule: str, title: str, location: str, passage: str, suggestion: str = ""):
        self.severity = severity
        self.rule = rule
        self.title = title
        self.location = location
        self.passage = passage
        self.suggestion = suggestion


def find_em_dashes(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if EM_DASH in line:
            count = line.count(EM_DASH)
            findings.append(Finding(
                severity="BLOCK",
                rule="AI-1",
                title=f"Em dash present ({count}× on this line)",
                location=f"line {i}",
                passage=line.strip()[:160],
                suggestion="Em dashes are a classic LLM tell. Replace with a comma, parentheses, a colon, or a sentence break."
            ))
    return findings


def find_en_dashes(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if EN_DASH in line:
            findings.append(Finding(
                severity="WARN",
                rule="AI-2",
                title="En dash present",
                location=f"line {i}",
                passage=line.strip()[:160],
                suggestion="En dashes are uncommon in human-written marketing copy. Replace with 'to' (for ranges) or a regular hyphen."
            ))
    return findings


def find_ai_phrases(text: str) -> List[Finding]:
    findings: List[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line_lower = line.lower()
        for pattern, label in AI_PHRASE_PATTERNS:
            for m in re.finditer(pattern, line_lower):
                findings.append(Finding(
                    severity="WARN",
                    rule="AI-3",
                    title=f"AI-typical phrase: \"{label}\"",
                    location=f"line {i}",
                    passage=line.strip()[:160],
                    suggestion=f"\"{label}\" appears frequently in LLM output. Consider rephrasing or removing."
                ))
    return findings


def find_spelling(text: str, dictionary: set[str]) -> List[Finding]:
    if SpellChecker is None:
        return []
    spell = SpellChecker()
    spell.word_frequency.load_words(dictionary)
    findings: List[Finding] = []
    seen: set[str] = set()
    # Strip an apostrophe-s suffix (Heartland's -> Heartland) but NOT bare s.
    poss_re = re.compile(r"['’]s?$")
    for i, line in enumerate(text.splitlines(), start=1):
        words = re.findall(r"[A-Za-z][A-Za-z'’]*", line)
        for w in words:
            wl = poss_re.sub("", w.lower())
            if not wl or wl in seen or len(wl) < 4:
                continue
            if wl in dictionary:
                continue
            if spell.unknown([wl]):
                seen.add(wl)
                cands = spell.candidates(wl) or set()
                cand = next(iter(cands)) if cands else ""
                if cand and cand != wl:
                    findings.append(Finding(
                        severity="WARN",
                        rule="SPELL",
                        title=f"Possible misspelling: \"{w}\"",
                        location=f"line {i}",
                        passage=line.strip()[:160],
                        suggestion=f"Did you mean: {cand}?"
                    ))
    return findings


def find_md_integrity(md_source: str) -> List[Finding]:
    """Markdown integrity: broken markdown structures we can detect cheaply."""
    findings: List[Finding] = []
    for i, line in enumerate(md_source.splitlines(), start=1):
        # Image without alt: ![](url)
        m = re.search(r"!\[\s*\]\([^)]+\)", line)
        if m:
            findings.append(Finding(
                severity="WARN",
                rule="MD-1",
                title="Image with empty alt text",
                location=f"line {i}",
                passage=line.strip()[:160],
                suggestion="Add descriptive alt text inside the brackets: ![Description](url)"
            ))
        # Link with empty text: [](url)
        m = re.search(r"(?<!\!)\[\s*\]\([^)]+\)", line)
        if m:
            findings.append(Finding(
                severity="BLOCK",
                rule="MD-2",
                title="Link with empty anchor text",
                location=f"line {i}",
                passage=line.strip()[:160],
                suggestion="Provide descriptive link text: [text](url)"
            ))
    return findings


# ------------- HTML render + attribute verification --------------

def render_html(md_source: str, owned_domain: str) -> tuple[str, Dict[str, int]]:
    md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table").enable("strikethrough")
    rendered = md.render(md_source)

    transforms = {"external_links": 0, "internal_links": 0, "tables": 0, "images_with_alt": 0}

    # External links: add rel + target. Internal links untouched.
    def link_replace(m: re.Match) -> str:
        attrs = m.group(1)
        href_m = re.search(r'href="([^"]+)"', attrs)
        if not href_m:
            return m.group(0)
        href = href_m.group(1)
        is_external = bool(re.match(r"https?://", href)) and owned_domain not in href.lower()
        if is_external:
            transforms["external_links"] += 1
            new_attrs = attrs
            if 'rel=' not in new_attrs:
                new_attrs += ' rel="nofollow"'
            else:
                new_attrs = re.sub(r'rel="([^"]*)"', lambda mm: f'rel="{mm.group(1)} nofollow"' if "nofollow" not in mm.group(1) else mm.group(0), new_attrs)
            if 'target=' not in new_attrs:
                new_attrs += ' target="_blank"'
            return f"<a{new_attrs}>"
        else:
            transforms["internal_links"] += 1
            return m.group(0)

    rendered = re.sub(r"<a([^>]*)>", link_replace, rendered)

    # Tables: add class="table"
    def table_replace(m: re.Match) -> str:
        transforms["tables"] += 1
        return m.group(0).replace("<table>", '<table class="table">')

    rendered = re.sub(r"<table[^>]*>", lambda m: '<table class="table">' if 'class=' not in m.group(0) else m.group(0), rendered)
    transforms["tables"] = rendered.count('<table class="table">')

    # Count images with alt
    transforms["images_with_alt"] = len(re.findall(r'<img\s+[^>]*alt="[^"]*"', rendered))

    return rendered, transforms


# ------------- Report writer --------------

def render_report(article_path: Path, html_path: Path, findings: List[Finding], transforms: Dict[str, int],
                  em_dash_tolerance: int, ai_tell_count: int) -> str:
    severity_counts = {"BLOCK": 0, "WARN": 0, "NIT": 0}
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1

    em_dashes = sum(1 for f in findings if f.rule == "AI-1")
    en_dashes = sum(1 for f in findings if f.rule == "AI-2")
    ai_phrases = sum(1 for f in findings if f.rule == "AI-3")
    spelling = sum(1 for f in findings if f.rule == "SPELL")
    md_issues = sum(1 for f in findings if f.rule.startswith("MD-"))

    if severity_counts["BLOCK"] > 0:
        rec = "Address BLOCK items before publish — these are AI-tells or broken markdown."
    elif severity_counts["WARN"] > 0:
        rec = "Review WARN items as judgment calls. The article reads cleanly enough to advance to compliance review."
    else:
        rec = "Clean. Advance to compliance review."

    now = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    out: List[str] = []
    out.append(f"# Article hygiene check — {article_path.stem}")
    out.append("")
    out.append(f"**Reviewed:** {now}")
    out.append(f"**Article path:** {article_path}")
    out.append(f"**Skill version:** focused-1.0 (AI-tell detection)")
    out.append(f"**Rendered HTML:** {html_path}")
    out.append("")
    out.append("> Focused on AI-tell detection: em dashes are the classic LLM giveaway, with en dashes and a small set of AI-typical phrases as secondary signals. Hyphen-density and compound-creep rules from the canonical skill are intentionally omitted — they fire on legitimate financial-domain compound terms (\"first-time-buyer\", \"WHEDA-participating-lender\", \"down-payment-assistance\") and produce noise without indicating AI generation.")
    out.append("")
    out.append("## Summary")
    out.append("")
    out.append(f"- **Em dashes:** {em_dashes}" + (f" (tolerance {em_dash_tolerance})" if em_dash_tolerance else ""))
    out.append(f"- **En dashes:** {en_dashes}")
    out.append(f"- **AI-typical phrases:** {ai_phrases}")
    out.append(f"- **Possible spelling issues:** {spelling}")
    out.append(f"- **Markdown integrity issues:** {md_issues}")
    out.append("")
    out.append(f"- **BLOCK:** {severity_counts['BLOCK']}")
    out.append(f"- **WARN:** {severity_counts['WARN']}")
    out.append(f"- **NIT:** {severity_counts['NIT']}")
    out.append("")
    out.append(f"**Recommendation:** {rec}")
    out.append("")

    if findings:
        out.append("## Issues")
        out.append("")
        for sev in ["BLOCK", "WARN", "NIT"]:
            issues = [f for f in findings if f.severity == sev]
            if not issues:
                continue
            for n, f in enumerate(issues, start=1):
                out.append(f"### {sev} {n}: {f.title}")
                out.append("")
                out.append(f"- **Location:** {f.location}")
                out.append(f"- **Rule:** {f.rule}")
                out.append(f"- **Passage:** {f.passage}")
                if f.suggestion:
                    out.append(f"- **Suggestion:** {f.suggestion}")
                out.append("")
    else:
        out.append("_No issues found._")
        out.append("")

    out.append("## Renderer transforms applied")
    out.append("")
    out.append(f"- External links rewritten with `rel=\"nofollow\" target=\"_blank\"`: **{transforms['external_links']}**")
    out.append(f"- Internal links left untouched: **{transforms['internal_links']}**")
    out.append(f"- Tables given `class=\"table\"`: **{transforms['tables']}**")
    out.append(f"- Images with `alt` preserved: **{transforms['images_with_alt']}**")
    out.append("")
    out.append("## Sign-off")
    out.append("")
    out.append("- [ ] BLOCK items resolved (or none reported).")
    out.append("- [ ] WARN items reviewed and dispositioned.")
    out.append("- [ ] Rendered HTML matches publish-time expectations.")
    out.append("")
    return "\n".join(out)


def main() -> int:
    args = parse_args()
    article_path = Path(args.article).resolve()
    if not article_path.exists():
        print(f"ERROR: article not found: {article_path}", file=sys.stderr)
        return 2

    output_html = Path(args.output_html).resolve() if args.output_html else article_path.with_suffix(".html")
    output_report = Path(args.output_report).resolve() if args.output_report else article_path.with_suffix(".hygiene-check.md")

    md_source = article_path.read_text(encoding="utf-8")
    text_for_checks = strip_code_and_attrs(md_source)
    dictionary = load_dictionary(args.dictionary)

    findings: List[Finding] = []
    findings.extend(find_em_dashes(text_for_checks))
    findings.extend(find_en_dashes(text_for_checks))
    findings.extend(find_ai_phrases(text_for_checks))
    findings.extend(find_spelling(text_for_checks, dictionary))
    findings.extend(find_md_integrity(md_source))

    rendered_html, transforms = render_html(md_source, args.credit_union_domain.lower())
    output_html.write_text(rendered_html, encoding="utf-8")

    em_dashes_count = sum(1 for f in findings if f.rule == "AI-1")
    report_md = render_report(article_path, output_html, findings, transforms,
                              em_dash_tolerance=args.em_dash_tolerance, ai_tell_count=em_dashes_count)
    output_report.write_text(report_md, encoding="utf-8")

    block = sum(1 for f in findings if f.severity == "BLOCK")
    warn = sum(1 for f in findings if f.severity == "WARN")
    print(f"Wrote {output_report}")
    print(f"Wrote {output_html}")
    print(f"Findings: BLOCK {block} · WARN {warn} · NIT {sum(1 for f in findings if f.severity == 'NIT')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
