#!/usr/bin/env python3
"""
article-hygiene-check — pre-publish hygiene checker for credit-union markdown
articles. Implements the M1–M6 markdown rules and H1–H4 HTML rules described
in RULES.md.

Usage:
    python3 hygiene_check.py \\
        --article path/to/article.md \\
        --credit-union-domain heartlandcu.org \\
        --mode both \\
        [--dictionary path/to/extra-dict.txt] \\
        [--compound-allow path/to/compound-allow.txt] \\
        [--output-html path/to/article.html] \\
        [--severity-overrides path/to/overrides.json] \\
        [--json]                 # emit JSON summary on stdout
        [--add-to-dictionary WORD]  # append a word to the bundled dictionary

Outputs:
    <article-name>.hygiene-check.md  (the report)
    <article-name>.html              (the rendered HTML; only if mode includes html)

Exits 0 on a successful run, regardless of how many BLOCK/WARN/NIT items were
found. Exits non-zero on a real error (file missing, parse failure, etc.).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from markdown_it import MarkdownIt
from markdown_it.token import Token
from spellchecker import SpellChecker
from bs4 import BeautifulSoup

SKILL_VERSION = "0.1.0"
SKILL_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants — character classes, default thresholds.
# ---------------------------------------------------------------------------

# Dashes that M1 flags. Hyphen-minus (U+002D) is intentionally NOT here; it's
# allowed but governed by M2.
DASH_CHARS = {
    "—": ("em dash", "U+2014"),
    "–": ("en dash", "U+2013"),
    "‒": ("figure dash", "U+2012"),
    "―": ("horizontal bar", "U+2015"),
    "﹘": ("small em dash", "U+FE58"),
    "－": ("fullwidth hyphen-minus", "U+FF0D"),
}

CURLY_QUOTES = "“”‘’"  # " " ' '
STRAIGHT_QUOTES = "\"'"

# M2 thresholds — tunable later via severity_overrides if needed.
HYPHENS_PER_SENTENCE_LIMIT = 3
HYPHEN_DENSITY_LIMIT = 0.02  # 2% of words in a paragraph
COMPOUND_CREEP_INTERNAL_HYPHENS = 2

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str          # BLOCK, WARN, NIT
    rule: str              # M1, M2, ..., H4
    title: str             # short summary, e.g. "Em dash present"
    location: str          # human-readable, e.g. "line 24"
    line: int = 0
    passage: str = ""
    suggestions: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Transforms:
    external_links_rewritten: int = 0
    internal_links_untouched: int = 0
    tables_classed: int = 0
    images_alt_preserved: int = 0
    images_alt_missing: int = 0


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def load_word_list(path: Path) -> set[str]:
    """Load a word list. One token per line; '#' comments stripped."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lower())
    return out


def load_compound_allow(path: Path) -> set[str]:
    """Compound-allow has the same shape as a word list."""
    return load_word_list(path)


def is_external_url(href: str, credit_union_domain: str) -> bool | None:
    """
    Return True if href is external, False if internal, None if not really a
    web URL at all (anchor, mailto:, tel:, javascript:, data:).
    """
    if not href:
        return None
    if href.startswith("#"):
        return None
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+\-.]*):", href)
    scheme = scheme_match.group(1).lower() if scheme_match else ""
    if scheme in {"mailto", "tel", "javascript", "data"}:
        return None
    if scheme not in {"", "http", "https"}:
        # Other protocols (ftp, file, etc.) we still treat as external for safety.
        return True
    if not scheme:
        # Relative path — internal.
        return False
    parsed = urlparse(href)
    host = (parsed.hostname or "").lower()
    cu = credit_union_domain.lower().lstrip(".")
    if not host:
        return False
    if host == cu or host.endswith("." + cu):
        return False
    return True


def normalize_line_endings(text: str) -> tuple[str, bool]:
    """Return (normalized_text, has_mixed_line_endings)."""
    has_crlf = "\r\n" in text
    # Anything with \r alone is also weird, but rare; treat as CRLF for our purposes.
    has_lone_lf = bool(re.search(r"(?<!\r)\n", text))
    mixed = has_crlf and has_lone_lf
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized, mixed


def slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "article"


# ---------------------------------------------------------------------------
# Code-region masking — replace fenced/inline code with placeholders so
# typography rules don't fire inside code.
# ---------------------------------------------------------------------------

def mask_code_regions(source: str, tokens: list[Token]) -> str:
    """
    Replace the contents of fenced code blocks, inline code, and table separator
    rows with spaces of the same length. Preserves line numbers and column
    offsets so any line/col references we report still match the original
    source.

    Why mask table separator rows: the `|---|---|` row contributes dozens of
    `-` characters that are not real hyphens in body text. Without masking,
    M2 (hyphen overuse) fires on every table.
    """
    lines = source.split("\n")
    masked_lines = list(lines)

    # Mask fence and code_block tokens by their `map` line range.
    for tok in walk_tokens(tokens):
        if tok.type in {"fence", "code_block"} and tok.map:
            start, end = tok.map  # end is exclusive
            for i in range(start, min(end, len(masked_lines))):
                # Preserve length, replace with spaces (keep ` if it's a fence
                # marker so the regex side of M4 can still verify closure).
                masked_lines[i] = " " * len(masked_lines[i])

    # Mask table separator rows like `|---|---|` so dashes there don't count
    # toward M2 hyphen overuse. The pattern matches optional leading whitespace,
    # then runs of `|`, `-`, `:`, and whitespace only.
    sep_re = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
    for i, line in enumerate(masked_lines):
        if sep_re.match(line):
            masked_lines[i] = " " * len(line)

    # Now mask inline code on remaining lines.
    masked = "\n".join(masked_lines)
    masked = re.sub(
        r"(`+)([^`\n]*?)\1",
        lambda m: m.group(1) + " " * len(m.group(2)) + m.group(1),
        masked,
    )
    # Mask URLs in href position to avoid spell-checking domain names.
    # We don't strip them in M1 because dashes inside a URL are fine — but a URL
    # never contains an em/en dash anyway, so this doesn't matter for M1.
    return masked


def walk_tokens(tokens: list[Token]):
    """Yield every token, including children of inline tokens."""
    for tok in tokens:
        yield tok
        if tok.children:
            yield from walk_tokens(tok.children)


def is_in_blockquote(line_no: int, tokens: list[Token]) -> bool:
    """1-indexed line_no; True if any blockquote token covers this line."""
    for tok in tokens:
        if tok.type == "blockquote_open" and tok.map:
            # Find matching close
            depth = 1
            close_map = None
            idx = tokens.index(tok) + 1
            while idx < len(tokens) and depth > 0:
                if tokens[idx].type == "blockquote_open":
                    depth += 1
                elif tokens[idx].type == "blockquote_close":
                    depth -= 1
                    if depth == 0:
                        close_map = tokens[idx].map
                idx += 1
            start = tok.map[0]
            end = close_map[1] if close_map else tok.map[1]
            if start <= line_no - 1 < end:
                return True
    return False


# ---------------------------------------------------------------------------
# M1. Em / en dash
# ---------------------------------------------------------------------------

def suggest_dash_replacements(line: str, col: int, char: str) -> list[str]:
    """Return 2–3 replacement candidates for a dash at line[col]."""
    # Look at small context windows.
    left = line[:col].rstrip()
    right = line[col + 1 :].lstrip()
    # Trim leading/trailing whitespace once for the suggested forms.
    near_left = line[max(0, col - 12) : col]
    near_right = line[col + 1 : col + 13]

    suggestions: list[str] = []

    # Numeric range: 5–10
    if re.search(r"\d\s*$", line[:col]) and re.match(r"\s*\d", line[col + 1 :]):
        # Replace the dash (and any surrounding whitespace) with " to ".
        repl = f"{left} to {right}".strip()
        suggestions.append(f"`{repl}` (write the range out: \"5 to 10\")")
        return suggestions[:3]

    # Day range: Mon–Fri (3-letter day codes)
    days = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
    if re.search(days + r"\s*$", line[:col]) and re.match(r"\s*" + days, line[col + 1 :]):
        repl_left = re.search(days + r"\s*$", line[:col]).group(0).strip()
        repl_right_match = re.match(r"\s*" + days, line[col + 1 :])
        repl_right = repl_right_match.group(0).strip()
        full = (
            line[: col - len(repl_left) - (len(line[:col]) - len(line[:col].rstrip()))]
            + f"{repl_left} through {repl_right}"
            + line[col + 1 + len(repl_right_match.group(0)):]
        )
        suggestions.append('`Monday through Friday` (spell the day range out)')
        return suggestions[:3]

    # Page range: pp. 12–18
    if re.search(r"pp?\.\s*\d+\s*$", line[:col], re.I) and re.match(r"\s*\d", line[col + 1 :]):
        suggestions.append('`pp. 12 to 18` (or hyphen-minus if your style permits: "pp. 12-18")')
        return suggestions[:3]

    # Generic mid-sentence: detect colon / list-introduction context.
    # Heuristic: if the right side starts with a bare list of comma-separated
    # words ending in a noun phrase, suggest a colon.
    after_clean = right.rstrip(".!?")
    looks_like_list = bool(re.match(r"[a-z][a-z0-9 ,]+(?:and|or)\b", after_clean.lower()))

    # Generic fallbacks. We keep 3 candidates so the human picks.
    suggestions.append(
        f'`{left}; {right}` (semicolon — keeps the close coupling between clauses)'
    )
    suggestions.append(
        f'`{left}, {right}` (comma — softer, conversational)'
    )
    suggestions.append(
        f'`{left}. {right[:1].upper() + right[1:] if right else ""}` (split into two sentences)'
    )
    if looks_like_list:
        # Replace the first generic suggestion with a colon-form one.
        suggestions.insert(
            0,
            f'`{left}: {right}` (colon — introduces the list/clause that follows)',
        )

    return suggestions[:3]


def check_m1_dashes(
    masked: str,
    tokens: list[Token],
    severity_for: callable,
) -> list[Issue]:
    issues: list[Issue] = []
    lines = masked.split("\n")
    for line_idx, line in enumerate(lines):
        for col, ch in enumerate(line):
            if ch in DASH_CHARS:
                name, code = DASH_CHARS[ch]
                line_no = line_idx + 1
                in_quote = is_in_blockquote(line_no, tokens)
                base_severity = "WARN" if in_quote else "BLOCK"
                severity = severity_for("M1", base_severity)
                suggestions = suggest_dash_replacements(line, col, ch)
                note = (
                    "quoted text — verify replacement is faithful to source"
                    if in_quote
                    else ""
                )
                issues.append(
                    Issue(
                        severity=severity,
                        rule="M1",
                        title=f"{name.capitalize()} present ({code})",
                        location=f"line {line_no}, col {col + 1}",
                        line=line_no,
                        passage=line.strip()[:200],
                        suggestions=suggestions,
                        note=note,
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# M2. Hyphen overuse
# ---------------------------------------------------------------------------

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def split_paragraphs(masked: str) -> list[tuple[int, str]]:
    """Return (start_line, paragraph_text) tuples."""
    paragraphs = []
    cur: list[str] = []
    cur_start = 1
    for i, line in enumerate(masked.split("\n"), start=1):
        if line.strip() == "":
            if cur:
                paragraphs.append((cur_start, "\n".join(cur)))
                cur = []
            cur_start = i + 1
        else:
            if not cur:
                cur_start = i
            cur.append(line)
    if cur:
        paragraphs.append((cur_start, "\n".join(cur)))
    return paragraphs


def is_compound_allowed(token: str, allow: set[str]) -> bool:
    low = token.lower().strip(".,;:!?\"'()[]")
    if low in allow:
        return True
    # Match a longer compound that starts with an allowed compound, e.g.,
    # "first-time-homebuyer" should suppress "first-time" creep.
    for allowed in allow:
        if low.startswith(allowed + "-"):
            return True
    return False


def check_m2_hyphens(
    masked: str,
    compound_allow: set[str],
    severity_for: callable,
) -> list[Issue]:
    issues: list[Issue] = []
    severity = severity_for("M2", "WARN")
    seen = set()  # dedupe so a long compound only flags once

    # Per-sentence: walk paragraphs, then sentences.
    paragraphs = split_paragraphs(masked)
    for start_line, para in paragraphs:
        sentences = SENTENCE_SPLIT_RE.split(para)
        for sent in sentences:
            hyphen_count = sent.count("-")
            if hyphen_count >= HYPHENS_PER_SENTENCE_LIMIT:
                key = ("sent", sent[:80])
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    Issue(
                        severity=severity,
                        rule="M2",
                        title=f"Hyphen overuse — {hyphen_count} hyphens in one sentence",
                        location=f"paragraph starting line {start_line}",
                        line=start_line,
                        passage=sent.strip()[:200],
                        suggestions=[
                            "Rewrite to consolidate compounds — try replacing one or two of the hyphenated terms with their non-hyphenated form, or split into two sentences."
                        ],
                    )
                )

        # Per-paragraph density. Strip URLs first (hyphens in URLs aren't body
        # text). Require both the density threshold AND a real cluster of
        # hyphens — a single legitimate compound in a short paragraph isn't
        # "overuse."
        para_for_density = URL_RE.sub(" ", para)
        words = re.findall(r"\S+", para_for_density)
        word_count = len(words)
        para_hyphens = para_for_density.count("-")
        if (
            word_count >= 25
            and para_hyphens >= HYPHENS_PER_SENTENCE_LIMIT
            and para_hyphens / word_count > HYPHEN_DENSITY_LIMIT
        ):
            key = ("para", start_line)
            if key not in seen:
                seen.add(key)
                density_pct = 100 * para_hyphens / word_count
                issues.append(
                    Issue(
                        severity=severity,
                        rule="M2",
                        title=f"Hyphen density {density_pct:.1f}% (limit 2%)",
                        location=f"paragraph starting line {start_line}",
                        line=start_line,
                        passage=para.strip()[:200],
                        suggestions=[
                            "Reduce hyphenated compounds by rewording. Compounds in compound-allow.txt are exempt; consider whether your compounds qualify."
                        ],
                    )
                )

    # Compound creep — per-token internal hyphen count.
    for line_idx, line in enumerate(masked.split("\n"), start=1):
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-']*", line):
            internal_hyphens = token.count("-")
            if internal_hyphens >= COMPOUND_CREEP_INTERNAL_HYPHENS:
                if is_compound_allowed(token, compound_allow):
                    continue
                key = ("creep", token.lower())
                if key in seen:
                    continue
                seen.add(key)
                # Suggest dropping the last hyphen.
                last = token.rfind("-")
                rewritten = token[:last] + " " + token[last + 1 :]
                issues.append(
                    Issue(
                        severity=severity,
                        rule="M2",
                        title=f"Compound creep — \"{token}\" has {internal_hyphens} internal hyphens",
                        location=f"line {line_idx}",
                        line=line_idx,
                        passage=line.strip()[:200],
                        suggestions=[
                            f"Break the compound — e.g., `{rewritten}` keeps a single hyphen and reads cleaner."
                        ],
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# M3. Spelling
# ---------------------------------------------------------------------------

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
URL_RE = re.compile(r"https?://\S+|www\.\S+")


def collect_inline_text_with_lines(tokens: list[Token]) -> list[tuple[int, str]]:
    """
    Walk the AST. For each top-level inline token, yield (line_no, text) where
    text is the rendered plain-text content (excluding inline code, link URLs,
    image src). Heading text is included.
    """
    results: list[tuple[int, str]] = []
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            line_no = (tok.map[0] + 1) if tok.map else 0
            buf: list[str] = []
            for child in tok.children:
                if child.type == "text":
                    buf.append(child.content)
                elif child.type == "softbreak":
                    buf.append(" ")
                elif child.type == "hardbreak":
                    buf.append(" ")
                # link_open/close, em_open/close, strong_open/close: structural,
                # nothing to add. The wrapped text comes through as a `text`
                # child between the open/close tokens.
                # code_inline: skip (governed by M1's masking and M3's skip).
            results.append((line_no, " ".join(buf)))
    return results


def check_m3_spelling(
    tokens: list[Token],
    custom_dict: set[str],
    severity_for: callable,
) -> list[Issue]:
    issues: list[Issue] = []
    spell = SpellChecker()  # English is the default
    # Add custom dictionary words.
    spell.word_frequency.load_words(custom_dict)

    seen: set[str] = set()
    for line_no, text in collect_inline_text_with_lines(tokens):
        # Strip URLs first so we don't try to spell-check them.
        cleaned = URL_RE.sub(" ", text)
        for match in WORD_RE.finditer(cleaned):
            word = match.group(0)
            wlow = word.lower()
            # Single letters / numbers — skip.
            if len(wlow) < 3:
                continue
            if wlow in custom_dict:
                continue
            # Numbers attached (e.g., "401k") — skip if any digit.
            if any(c.isdigit() for c in word):
                continue
            if word in seen:
                continue
            # Possessive forms: "Heartland's" — strip 's then re-check
            base = re.sub(r"'s$", "", word)
            if base.lower() in custom_dict:
                continue
            misspelled = spell.unknown([base.lower()])
            if not misspelled:
                continue
            seen.add(word)
            correction = spell.correction(base.lower())
            candidates = list(spell.candidates(base.lower()) or [])
            high_confidence = (
                correction is not None
                and correction != base.lower()
                and correction in candidates
            )
            if high_confidence:
                severity = severity_for("M3", "BLOCK")
                title = f"Spelling — \"{word}\""
                suggestion = f"Suggested correction: `{correction}`"
                note = ""
            else:
                severity = severity_for("M3", "WARN")
                title = f"Spelling — \"{word}\" (low confidence)"
                suggestion = (
                    "verify spelling — possibly a proper noun not in dictionary"
                )
                note = (
                    "If this is a brand or product name, add it to dictionary.txt "
                    "with --add-to-dictionary."
                )
            issues.append(
                Issue(
                    severity=severity,
                    rule="M3",
                    title=title,
                    location=f"line {line_no}",
                    line=line_no,
                    passage=text.strip()[:200],
                    suggestions=[suggestion],
                    note=note,
                )
            )
    return issues


# ---------------------------------------------------------------------------
# M4. Markdown formatting integrity
# ---------------------------------------------------------------------------

def check_m4_formatting(
    source: str,
    tokens: list[Token],
    severity_for: callable,
) -> list[Issue]:
    issues: list[Issue] = []

    # Heading without space after #
    for line_idx, line in enumerate(source.split("\n"), start=1):
        m = re.match(r"^(#{1,6})([A-Za-z0-9])", line)
        if m:
            issues.append(
                Issue(
                    severity=severity_for("M4", "BLOCK"),
                    rule="M4",
                    title=f"Heading missing space after `#` — `{line[:30]}`",
                    location=f"line {line_idx}",
                    line=line_idx,
                    passage=line.strip()[:200],
                    suggestions=[
                        f"Add a space: `{m.group(1)} {line[len(m.group(1)):].lstrip()}`"
                    ],
                )
            )

    # Heading levels & multiple H1
    h1_lines: list[int] = []
    last_level = 0
    for tok in tokens:
        if tok.type == "heading_open" and tok.map:
            level = int(tok.tag[1])
            line_no = tok.map[0] + 1
            if level == 1:
                h1_lines.append(line_no)
            if last_level and level > last_level + 1:
                issues.append(
                    Issue(
                        severity=severity_for("M4", "WARN"),
                        rule="M4",
                        title=f"Skipped heading level — H{last_level} → H{level}",
                        location=f"line {line_no}",
                        line=line_no,
                        passage="",
                        suggestions=[
                            f"Insert an H{last_level + 1} between them, or demote H{level} to H{last_level + 1}."
                        ],
                    )
                )
            last_level = level
    if len(h1_lines) > 1:
        issues.append(
            Issue(
                severity=severity_for("M4", "WARN"),
                rule="M4",
                title=f"Multiple H1 headings ({len(h1_lines)})",
                location=f"lines {', '.join(str(n) for n in h1_lines)}",
                line=h1_lines[0],
                passage="",
                suggestions=[
                    "Use a single H1 per document; demote the others to H2 or lower."
                ],
            )
        )

    # Unclosed fence: count fence markers in source, expect even.
    # Only count fence markers at column 0 (or up to 3 spaces of indent).
    fence_lines = [
        i + 1
        for i, ln in enumerate(source.split("\n"))
        if re.match(r"^ {0,3}(```|~~~)", ln)
    ]
    if len(fence_lines) % 2 != 0:
        last_fence = fence_lines[-1]
        issues.append(
            Issue(
                severity=severity_for("M4", "BLOCK"),
                rule="M4",
                title="Unclosed fenced code block",
                location=f"line {last_fence}",
                line=last_fence,
                passage="",
                suggestions=[
                    "Add a matching closing ` ``` ` (or `~~~`) at the end of the code block."
                ],
            )
        )

    # Mismatched emphasis. Token approach:
    # markdown-it pairs em/strong tokens; if pairing fails, the markup is
    # rendered as text. We catch the most common case — `**word` or `*word`
    # at end of line with no closer — by line scan.
    for line_idx, line in enumerate(source.split("\n"), start=1):
        # Skip lines that are inside a fenced block — easier: skip if the line
        # has been masked to spaces. We don't have masked here; use a simpler
        # heuristic by counting unescaped `*` and `_` runs.
        if re.match(r"^ {0,3}(```|~~~)", line):
            continue
        # Count `**` runs and `*` runs.
        stars2 = len(re.findall(r"(?<!\*)\*\*(?!\*)", line))
        if stars2 % 2 != 0:
            issues.append(
                Issue(
                    severity=severity_for("M4", "BLOCK"),
                    rule="M4",
                    title="Mismatched emphasis — unclosed `**`",
                    location=f"line {line_idx}",
                    line=line_idx,
                    passage=line.strip()[:200],
                    suggestions=["Close the `**` pair or escape the literal asterisks."],
                )
            )

    # Broken table — body rows whose pipe-column count differs from the header.
    for tok in tokens:
        if tok.type == "table_open" and tok.map:
            tstart, tend = tok.map
            tlines = source.split("\n")[tstart:tend]
            if not tlines:
                continue
            header = tlines[0]
            header_cols = len(re.findall(r"(?<!\\)\|", header)) - 1
            for row_offset, row in enumerate(tlines[2:], start=2):  # skip header + separator
                if not row.strip().startswith("|") and "|" not in row:
                    continue
                row_cols = len(re.findall(r"(?<!\\)\|", row)) - 1
                if row_cols != header_cols:
                    issues.append(
                        Issue(
                            severity=severity_for("M4", "BLOCK"),
                            rule="M4",
                            title=(
                                f"Broken table — row has {row_cols} columns; header has {header_cols}"
                            ),
                            location=f"line {tstart + row_offset + 1}",
                            line=tstart + row_offset + 1,
                            passage=row.strip()[:200],
                            suggestions=[
                                "Add or remove `|` separators so this row matches the header column count."
                            ],
                        )
                    )

    # Broken link syntax: `[text](url` without close paren on same line/section.
    for line_idx, line in enumerate(source.split("\n"), start=1):
        # Find `[...](` runs that don't close on the same line. Simple regex.
        for m in re.finditer(r"\[[^\]]*\]\([^)]*$", line):
            issues.append(
                Issue(
                    severity=severity_for("M4", "BLOCK"),
                    rule="M4",
                    title="Broken link syntax — unclosed `(`",
                    location=f"line {line_idx}",
                    line=line_idx,
                    passage=line.strip()[:200],
                    suggestions=["Add the closing `)` after the URL."],
                )
            )

    # Reference link with undefined reference: walk source for [text][ref] and
    # check that [ref]: url is defined somewhere. markdown-it normalizes refs,
    # so if a reference is undefined the resulting token tree will have a
    # `text` token for the literal `[text][ref]` instead of `link_open`.
    refs_used = set()
    for m in re.finditer(r"\[([^\]\n]+)\]\[([^\]\n]*)\]", source):
        ref_label = (m.group(2) or m.group(1)).lower()
        refs_used.add(ref_label)
    refs_defined = set(re.findall(r"^\[([^\]]+)\]:", source, re.M))
    refs_defined_lower = {r.lower() for r in refs_defined}
    for ref in refs_used - refs_defined_lower:
        # Find first usage line.
        for line_idx, line in enumerate(source.split("\n"), start=1):
            if re.search(r"\[[^\]\n]+\]\[" + re.escape(ref) + r"\]", line, re.I):
                issues.append(
                    Issue(
                        severity=severity_for("M4", "BLOCK"),
                        rule="M4",
                        title=f"Reference link with undefined reference `[{ref}]`",
                        location=f"line {line_idx}",
                        line=line_idx,
                        passage=line.strip()[:200],
                        suggestions=[
                            f"Add a definition like `[{ref}]: https://example.com/...` at the bottom of the article, or use an inline `[text](url)` link instead."
                        ],
                    )
                )
                break
    return issues


# ---------------------------------------------------------------------------
# M5. Quote consistency
# ---------------------------------------------------------------------------

def check_m5_quotes(masked: str, severity_for: callable) -> list[Issue]:
    curly_count = sum(masked.count(c) for c in CURLY_QUOTES)
    straight_count = sum(masked.count(c) for c in STRAIGHT_QUOTES)
    if curly_count > 0 and straight_count > 0:
        return [
            Issue(
                severity=severity_for("M5", "WARN"),
                rule="M5",
                title=f"Mixed quote styles — {curly_count} curly, {straight_count} straight",
                location="document-wide",
                line=0,
                passage="",
                suggestions=[
                    'Prefer straight quotes (`"` and `\'`) in markdown source; the rendering pipeline applies smart quotes at render time.'
                ],
                note="consistent style is straight quotes in source; rendering applies curly",
            )
        ]
    return []


# ---------------------------------------------------------------------------
# M6. Whitespace and structural NITs
# ---------------------------------------------------------------------------

def check_m6_whitespace(
    raw_source: str, normalized_source: str, mixed_endings: bool, severity_for: callable
) -> list[Issue]:
    issues: list[Issue] = []

    # Trailing whitespace per line (use normalized so we don't double-count CRLF
    # as trailing whitespace).
    for line_idx, line in enumerate(normalized_source.split("\n"), start=1):
        if line != line.rstrip():
            issues.append(
                Issue(
                    severity=severity_for("M6", "NIT"),
                    rule="M6",
                    title="Trailing whitespace",
                    location=f"line {line_idx}",
                    line=line_idx,
                    passage=line.rstrip()[:120] + " ⇠[trailing space]",
                    suggestions=["Strip trailing whitespace from this line."],
                )
            )

    if mixed_endings:
        issues.append(
            Issue(
                severity=severity_for("M6", "NIT"),
                rule="M6",
                title="Mixed line endings (CRLF + LF in same file)",
                location="document-wide",
                line=0,
                passage="",
                suggestions=[
                    "Convert all line endings to LF (run `dos2unix` or your editor's normalize-line-endings command)."
                ],
            )
        )

    # 3+ consecutive blank lines.
    for m in re.finditer(r"\n[ \t]*\n[ \t]*\n[ \t]*(\n[ \t]*)+", normalized_source):
        line_no = normalized_source[: m.start()].count("\n") + 1
        issues.append(
            Issue(
                severity=severity_for("M6", "NIT"),
                rule="M6",
                title="3+ consecutive blank lines",
                location=f"line {line_no}",
                line=line_no,
                passage="",
                suggestions=["Collapse to at most one blank line between sections."],
            )
        )

    # Mixed bullet styles.
    bullet_chars = {"-": 0, "*": 0}
    for line in normalized_source.split("\n"):
        m = re.match(r"^( {0,3})([-*])\s+", line)
        if m:
            bullet_chars[m.group(2)] += 1
    if bullet_chars["-"] > 0 and bullet_chars["*"] > 0:
        issues.append(
            Issue(
                severity=severity_for("M6", "NIT"),
                rule="M6",
                title=(
                    f"Mixed bullet styles — {bullet_chars['-']} `-` items, "
                    f"{bullet_chars['*']} `*` items"
                ),
                location="document-wide",
                line=0,
                passage="",
                suggestions=["Pick one bullet character (recommend `-`) and use it everywhere."],
            )
        )

    # Tabs vs spaces in lists — flag if any list line uses a tab for indentation.
    for line_idx, line in enumerate(normalized_source.split("\n"), start=1):
        if re.match(r"^\t+[-*+] \s*\S", line) or re.match(r"^\t+\d+\. \s*\S", line):
            issues.append(
                Issue(
                    severity=severity_for("M6", "NIT"),
                    rule="M6",
                    title="Tab-indented list item",
                    location=f"line {line_idx}",
                    line=line_idx,
                    passage=line[:120],
                    suggestions=["Use spaces for indentation; markdown is more portable that way."],
                )
            )

    return issues


# ---------------------------------------------------------------------------
# HTML rendering with transforms
# ---------------------------------------------------------------------------

def build_md(credit_union_domain: str) -> tuple[MarkdownIt, dict]:
    """Return a MarkdownIt configured with our transforms, plus a transform-counter dict."""
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "breaks": False}).enable(
        "table"
    )
    transform_state: dict[str, int] = {
        "external_links_rewritten": 0,
        "internal_links_untouched": 0,
        "tables_classed": 0,
        "images_alt_preserved": 0,
        "images_alt_missing": 0,
    }

    default_link_open = md.renderer.rules.get("link_open")

    def link_open(tokens, idx, options, env):
        token = tokens[idx]
        href = token.attrGet("href") or ""
        ext = is_external_url(href, credit_union_domain)
        if ext is True:
            token.attrSet("rel", "nofollow")
            token.attrSet("target", "_blank")
            transform_state["external_links_rewritten"] += 1
        elif ext is False:
            transform_state["internal_links_untouched"] += 1
        if default_link_open:
            return default_link_open(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["link_open"] = link_open

    default_table_open = md.renderer.rules.get("table_open")

    def table_open(tokens, idx, options, env):
        token = tokens[idx]
        token.attrSet("class", "table")
        transform_state["tables_classed"] += 1
        if default_table_open:
            return default_table_open(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["table_open"] = table_open

    default_image = md.renderer.rules.get("image")

    def image(tokens, idx, options, env):
        token = tokens[idx]
        # markdown-it sets alt via the children's plain text and the `alt`
        # attribute is added by the default renderer. We don't need to add
        # anything; just count.
        if token.attrGet("alt") is not None or token.children:
            transform_state["images_alt_preserved"] += 1
        if default_image:
            return default_image(tokens, idx, options, env)
        return md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["image"] = image
    return md, transform_state


# ---------------------------------------------------------------------------
# H1–H4 — apply on rendered HTML
# ---------------------------------------------------------------------------

def check_html_rules(
    html: str,
    credit_union_domain: str,
    severity_for: callable,
) -> list[Issue]:
    issues: list[Issue] = []
    soup = BeautifulSoup(html, "html.parser")

    # H1: external link attributes.
    for a in soup.find_all("a"):
        href = a.get("href", "")
        ext = is_external_url(href, credit_union_domain)
        attrs = " ".join(f'{k}="{v}"' for k, v in a.attrs.items())
        rendered = f'<a {attrs}>{a.get_text()}</a>'
        if ext is True:
            rel = a.get("rel")
            rel_str = " ".join(rel) if isinstance(rel, list) else (rel or "")
            target = a.get("target", "")
            missing = []
            if "nofollow" not in rel_str:
                missing.append('rel="nofollow"')
            if target != "_blank":
                missing.append('target="_blank"')
            if missing:
                issues.append(
                    Issue(
                        severity=severity_for("H1", "BLOCK"),
                        rule="H1",
                        title="External link missing required attributes",
                        location=f"href={href}",
                        line=0,
                        passage=rendered[:200],
                        suggestions=[
                            f"Add: {' and '.join(missing)}. The renderer adds these automatically for markdown links — this looks like a raw HTML `<a>` in the markdown source."
                        ],
                    )
                )
        elif ext is False:
            target = a.get("target", "")
            if target == "_blank":
                issues.append(
                    Issue(
                        severity=severity_for("H1", "WARN"),
                        rule="H1",
                        title='Internal link with target="_blank"',
                        location=f"href={href}",
                        line=0,
                        passage=rendered[:200],
                        suggestions=[
                            'Internal links should open in the same tab; remove `target="_blank"`.'
                        ],
                    )
                )

    # H2: every <table> needs class="table".
    for table in soup.find_all("table"):
        klass = table.get("class") or []
        if isinstance(klass, str):
            klass = klass.split()
        if "table" not in klass:
            issues.append(
                Issue(
                    severity=severity_for("H2", "BLOCK"),
                    rule="H2",
                    title='Table missing class="table"',
                    location="raw HTML <table> in markdown",
                    line=0,
                    passage=str(table)[:200],
                    suggestions=[
                        'Add `class="table"` to the `<table>` tag, or rewrite the table in markdown so the renderer adds it automatically.'
                    ],
                )
            )

    # H3: every <img> needs an alt attribute.
    for img in soup.find_all("img"):
        if "alt" not in img.attrs:
            issues.append(
                Issue(
                    severity=severity_for("H3", "BLOCK"),
                    rule="H3",
                    title="Image missing alt attribute",
                    location=f"src={img.get('src', '?')}",
                    line=0,
                    passage=str(img)[:200],
                    suggestions=[
                        'Add an `alt` attribute. Use `alt=""` for decorative images.'
                    ],
                )
            )

    return issues


# ---------------------------------------------------------------------------
# Severity overrides
# ---------------------------------------------------------------------------

def make_severity_for(overrides: dict[str, str]):
    """
    Returns a function that, given a rule id and the default severity, returns
    the overridden severity if the rule id is in `overrides`, else the default.
    """
    def severity_for(rule_id: str, default: str) -> str:
        return overrides.get(rule_id, default)
    return severity_for


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

SEVERITY_ORDER = {"BLOCK": 0, "WARN": 1, "NIT": 2}


def render_report(
    article_path: Path,
    html_path: Path,
    mode: str,
    issues: list[Issue],
    transforms: dict[str, int],
) -> str:
    issues_sorted = sorted(issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.rule, i.line))
    block_count = sum(1 for i in issues if i.severity == "BLOCK")
    warn_count = sum(1 for i in issues if i.severity == "WARN")
    nit_count = sum(1 for i in issues if i.severity == "NIT")

    if block_count > 0:
        recommendation = "Fix BLOCK items before advancing to compliance review."
    elif warn_count > 0:
        recommendation = "Advance with WARN review — judgment calls remain."
    else:
        recommendation = "Clean — advance."

    title = article_path.stem.replace("-", " ").replace("_", " ").title()
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    lines = [
        f"# Article Hygiene Check — {title}",
        "",
        f"**Reviewed:** {timestamp}",
        f"**Article path:** {article_path}",
        f"**Mode:** {mode}",
        f"**Skill version:** {SKILL_VERSION}",
        f"**Rendered HTML:** {html_path}",
        "",
        "## Summary",
        "",
        f"- BLOCK issues: {block_count}",
        f"- WARN issues: {warn_count}",
        f"- NIT issues: {nit_count}",
        "",
        f"**Recommendation:** {recommendation}",
        "",
        "## Issues",
        "",
    ]

    if not issues_sorted:
        lines.append("_No issues found._")
        lines.append("")
    else:
        # Group by severity, with sequential numbering within severity.
        by_sev: dict[str, list[Issue]] = {"BLOCK": [], "WARN": [], "NIT": []}
        for issue in issues_sorted:
            by_sev[issue.severity].append(issue)
        for sev in ("BLOCK", "WARN", "NIT"):
            for n, issue in enumerate(by_sev[sev], start=1):
                lines.append(f"### {sev} {n}: {issue.title}")
                lines.append("")
                lines.append(f"**Location:** {issue.location}")
                lines.append(f"**Rule:** {issue.rule}")
                if issue.passage:
                    lines.append(f"**Passage:** {issue.passage}")
                if issue.suggestions:
                    lines.append("**Suggestions:**")
                    for s in issue.suggestions:
                        lines.append(f"- {s}")
                if issue.note:
                    lines.append(f"**Note:** {issue.note}")
                lines.append("")

    lines.append("## Renderer transforms applied")
    lines.append("")
    lines.append(
        f"- {transforms['external_links_rewritten']} external links rewritten with `rel=\"nofollow\" target=\"_blank\"`"
    )
    lines.append(f"- {transforms['tables_classed']} tables given `class=\"table\"`")
    lines.append(f"- {transforms['internal_links_untouched']} internal links left untouched")
    lines.append(
        f"- {transforms['images_alt_preserved']} images with alt preserved"
    )
    if transforms["images_alt_missing"]:
        lines.append(
            f"- {transforms['images_alt_missing']} images flagged for missing alt"
        )
    lines.append("")

    lines.append("## Reviewer sign-off")
    lines.append("")
    lines.append("- [ ] All BLOCK items resolved")
    lines.append("- [ ] WARN items reviewed and dispositioned")
    lines.append("- [ ] Rendered HTML reviewed visually")
    lines.append("- [ ] Final review by: __________________ (name)")
    lines.append("- [ ] Sign-off date: __________________")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="article-hygiene-check — pre-publish hygiene checker."
    )
    parser.add_argument("--article", type=Path, help="Path to the markdown article.")
    parser.add_argument(
        "--credit-union-domain",
        type=str,
        default="",
        help="Domain used to distinguish internal from external links.",
    )
    parser.add_argument(
        "--mode",
        choices=["markdown", "html", "both"],
        default="both",
        help="Run markdown checks, HTML checks, or both (default).",
    )
    parser.add_argument("--dictionary", type=Path, default=None)
    parser.add_argument("--compound-allow", type=Path, default=None)
    parser.add_argument("--output-html", type=Path, default=None)
    parser.add_argument("--severity-overrides", type=Path, default=None)
    parser.add_argument(
        "--add-to-dictionary",
        type=str,
        default=None,
        help="Append a word to the bundled dictionary.txt and exit.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON summary on stdout (in addition to writing files).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Override the report output path (default: <article>.hygiene-check.md).",
    )
    args = parser.parse_args(argv)

    bundled_dict = SKILL_DIR / "dictionary.txt"
    bundled_compound = SKILL_DIR / "compound-allow.txt"

    if args.add_to_dictionary:
        with bundled_dict.open("a", encoding="utf-8") as fh:
            fh.write("\n" + args.add_to_dictionary.strip() + "\n")
        print(f"Added '{args.add_to_dictionary}' to {bundled_dict}", file=sys.stderr)
        return 0

    if not args.article:
        parser.error("--article is required (unless using --add-to-dictionary).")

    if args.mode in ("html", "both") and not args.credit_union_domain:
        parser.error("--credit-union-domain is required for html/both modes.")

    if not args.article.exists():
        parser.error(f"Article not found: {args.article}")

    raw_source = args.article.read_text(encoding="utf-8")
    normalized, mixed_endings = normalize_line_endings(raw_source)

    md_for_parse = MarkdownIt("commonmark", {"html": True}).enable("table")
    tokens = md_for_parse.parse(normalized)

    masked = mask_code_regions(normalized, tokens)

    # Load dictionary (bundled + custom).
    custom_dict: set[str] = set()
    custom_dict |= load_word_list(bundled_dict)
    if args.dictionary and args.dictionary.exists():
        custom_dict |= load_word_list(args.dictionary)

    compound_allow: set[str] = set()
    compound_allow |= load_compound_allow(bundled_compound)
    if args.compound_allow and args.compound_allow.exists():
        compound_allow |= load_compound_allow(args.compound_allow)

    overrides = {}
    if args.severity_overrides and args.severity_overrides.exists():
        overrides = json.loads(args.severity_overrides.read_text(encoding="utf-8"))
    severity_for = make_severity_for(overrides)

    all_issues: list[Issue] = []
    if args.mode in ("markdown", "both"):
        all_issues += check_m1_dashes(masked, tokens, severity_for)
        all_issues += check_m2_hyphens(masked, compound_allow, severity_for)
        all_issues += check_m3_spelling(tokens, custom_dict, severity_for)
        all_issues += check_m4_formatting(normalized, tokens, severity_for)
        all_issues += check_m5_quotes(masked, severity_for)
        all_issues += check_m6_whitespace(raw_source, normalized, mixed_endings, severity_for)

    transforms_state = {
        "external_links_rewritten": 0,
        "internal_links_untouched": 0,
        "tables_classed": 0,
        "images_alt_preserved": 0,
        "images_alt_missing": 0,
    }
    rendered_html = ""
    html_out_path = args.output_html or args.article.with_suffix(".html")

    if args.mode in ("html", "both"):
        md, transforms_state = build_md(args.credit_union_domain)
        rendered_html = md.render(normalized)
        # Run HTML rule checks AFTER transforms, so we only flag raw-HTML violations.
        html_issues = check_html_rules(rendered_html, args.credit_union_domain, severity_for)
        # Reflect missing-alt count into transforms summary.
        transforms_state["images_alt_missing"] = sum(
            1 for i in html_issues if i.rule == "H3"
        )
        all_issues += html_issues
        # Write the HTML out.
        html_out_path.write_text(
            rendered_html if rendered_html.endswith("\n") else rendered_html + "\n",
            encoding="utf-8",
        )

    report_text = render_report(
        args.article,
        html_out_path,
        args.mode,
        all_issues,
        transforms_state,
    )
    report_path = args.report_path or args.article.with_suffix("").with_name(
        args.article.stem + ".hygiene-check.md"
    )
    report_path.write_text(report_text, encoding="utf-8")

    if args.json:
        summary = {
            "article": str(args.article),
            "report": str(report_path),
            "html": str(html_out_path) if args.mode in ("html", "both") else None,
            "mode": args.mode,
            "skill_version": SKILL_VERSION,
            "block_count": sum(1 for i in all_issues if i.severity == "BLOCK"),
            "warn_count": sum(1 for i in all_issues if i.severity == "WARN"),
            "nit_count": sum(1 for i in all_issues if i.severity == "NIT"),
            "issues": [i.to_dict() for i in all_issues],
            "transforms": transforms_state,
        }
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
