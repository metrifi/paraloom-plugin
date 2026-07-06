"""WCAG criterion checks layered on top of the AST audit + reading metrics.

The AST audit (`markdown_audit.audit`) gathers structural facts. This module
turns those facts into WCAG-cited Issues, and adds the body-text checks
(color-only references, spatial-position language, long paragraphs, generic
headings, pseudo-list paragraphs).
"""

from __future__ import annotations

import re
from typing import List

from markdown_audit import (
    AuditResult,
    Issue,
    is_bad_anchor,
    is_generic_heading,
)
from reading_level import ReadingLevelMetrics, hardest_sentences


# Color words that, when used to identify content, fail 1.4.1 unless paired
# with another cue. We err on the side of flagging — the reviewer can dismiss.
COLOR_WORDS = {
    "red", "green", "blue", "yellow", "orange", "purple", "pink",
    "black", "white", "gray", "grey", "brown", "violet", "teal",
    "cyan", "magenta", "highlighted", "highlighted-in",
}

# Patterns that trigger 1.4.1: color word adjacent to a noun without other
# distinguishing context.
_COLOR_ONLY_PATTERNS = [
    # "click the green button", "items in red", "see the highlighted ..."
    re.compile(
        r"\b(?:the|items?|sections?|rows?|cells?|boxes?|buttons?|links?|"
        r"options?|fields?|texts?|words?|figures?)\s+"
        r"(?:in\s+|highlighted\s+in\s+|colored\s+|marked\s+in\s+)?"
        r"(red|green|blue|yellow|orange|purple|pink|black|white|gray|grey|brown)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:click|select|choose|tap|press)\s+the\s+"
        r"(red|green|blue|yellow|orange|purple|pink|black|white|gray|grey)\s+"
        r"(?:button|link|item|option|tab|icon)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:items?|rows?|entries|sections?)\s+highlighted\s+in\s+\w+\b",
        re.I,
    ),
    re.compile(
        r"\bhighlighted\s+(?:in\s+)?(red|green|blue|yellow|orange|purple|pink)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:items?|things?|entries|options?)\s+(?:in|marked|colored)\s+"
        r"(red|green|blue|yellow|orange|purple|pink)\s+are\b",
        re.I,
    ),
]

# Spatial-position phrases (1.3.2).
_SPATIAL_PATTERNS = [
    re.compile(r"\b(?:the\s+)?box\s+(?:on\s+the\s+)?(left|right)\b", re.I),
    re.compile(r"\bthe\s+column\s+(?:on\s+the\s+)?(left|right)\b", re.I),
    re.compile(r"\bin\s+the\s+(left|right|top|bottom)\s+(corner|panel|sidebar|column)\b", re.I),
    re.compile(r"\bsee\s+the\s+(?:image|figure|chart)\s+(?:above|below|to\s+the\s+(?:left|right))\b", re.I),
]

# Pseudo-list patterns: lines that look like lists but render as prose.
_PSEUDO_LIST = re.compile(
    r"(?:^|\n)\s*(?:[•●▪▫◦]|[-*]\s|Item\s+\d+:|Step\s+\d+:)\s+",
    re.I,
)

# A markdown image where the alt text is so long it's probably image-of-text
# (1.4.5).
def _looks_like_image_of_text(alt: str) -> bool:
    if not alt:
        return False
    words = alt.split()
    if len(words) < 8:
        return False
    return alt.rstrip().endswith((".", "!", "?", '"', "”"))


def _shorten(text: str, n: int = 80) -> str:
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def check_headings(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    headings = audit.headings

    h1s = [h for h in headings if h.level == 1]
    if not h1s:
        # No H1 at all → 2.4.2 BLOCK
        issues.append(
            Issue(
                severity="BLOCK",
                title="Article has no H1 title",
                wcag="2.4.2 Page Titled (Level A)",
                location="Top of document",
                detail=(
                    "No H1 was found. Screen-reader users rely on the H1 to "
                    "identify the page topic; without one, they have to scan "
                    "blind."
                ),
                fix="Add a single descriptive H1 at the top of the article.",
            )
        )
    elif len(h1s) > 1:
        issues.append(
            Issue(
                severity="WARN",
                title=f"Multiple H1 headings found ({len(h1s)})",
                wcag="1.3.1 Info and Relationships (Level A)",
                location=", ".join(f'"{h.text}" (line {h.line})' for h in h1s),
                detail=(
                    "Each article should have exactly one H1 — the page title. "
                    "Multiple H1s confuse the document outline."
                ),
                fix="Demote secondary H1s to H2 or restructure as separate articles.",
            )
        )

    # Heading hierarchy: never jump more than one level deeper.
    prev_level = 0
    for h in headings:
        if prev_level > 0 and h.level > prev_level + 1:
            issues.append(
                Issue(
                    severity="BLOCK",
                    title=f"Heading level skipped: H{prev_level} → H{h.level}",
                    wcag="1.3.1 Info and Relationships (Level A)",
                    location=f'"{h.text}" (line {h.line})',
                    detail=(
                        f"The heading hierarchy jumps from H{prev_level} to "
                        f"H{h.level}, skipping intermediate level(s). Screen "
                        "readers report headings as an outline; gaps break "
                        "that outline."
                    ),
                    fix=(
                        f"Insert an H{prev_level + 1} above this heading or "
                        f"change this heading to H{prev_level + 1}."
                    ),
                )
            )
        prev_level = h.level

    # Generic headings (2.4.6, Level AA).
    for h in headings:
        if is_generic_heading(h.text):
            issues.append(
                Issue(
                    severity="WARN",
                    title=f'Generic heading: "{h.text}"',
                    wcag="2.4.6 Headings and Labels (Level AA)",
                    location=f'Line {h.line}',
                    detail=(
                        "Headings should describe the section's content so a "
                        "screen-reader user navigating by heading can predict "
                        "what's in each section. Generic labels like "
                        '"Introduction" or "Section 1" force them to read on '
                        "to find out."
                    ),
                    fix=(
                        "Replace with a heading that summarizes the section's "
                        "topic (e.g., 'How HELOC rates compare to home "
                        "equity loans' rather than 'Section 2')."
                    ),
                )
            )

    # 2.4.10 Section headings (AAA): long content sections.
    # Walk paragraphs grouped by their section heading; flag when one section
    # exceeds 300 words.
    section_words: dict[str, int] = {}
    section_first_line: dict[str, int] = {}
    for text, sect, line in audit.paragraphs:
        wc = len(text.split())
        section_words[sect] = section_words.get(sect, 0) + wc
        section_first_line.setdefault(sect, line)
    for sect, wc in section_words.items():
        if wc > 300 and sect:  # ignore the "no heading yet" pseudo-section
            issues.append(
                Issue(
                    severity="NIT",
                    title=f'Long section without sub-headings: "{sect}" ({wc} words)',
                    wcag="2.4.10 Section Headings (Level AAA)",
                    location=f'Section "{sect}" starting around line {section_first_line[sect]}',
                    detail=(
                        "This section runs more than 300 words without an "
                        "intermediate heading. Long unbroken sections are "
                        "harder to scan, especially on small screens or with "
                        "screen-reader heading navigation."
                    ),
                    fix="Add at least one intermediate heading to break up the section.",
                )
            )
    return issues


def check_links(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    for link in audit.links:
        anchor = link.anchor.strip()
        if not anchor:
            issues.append(
                Issue(
                    severity="BLOCK",
                    title="Link with empty anchor text",
                    wcag="2.4.4 Link Purpose (In Context) (Level A)",
                    location=f"Line {link.line}, href: {link.href or '(none)'}",
                    detail=(
                        "An empty anchor gives screen-reader users no way to "
                        "preview the link destination."
                    ),
                    fix="Add descriptive anchor text that summarizes the destination.",
                )
            )
            continue
        if is_bad_anchor(anchor):
            issues.append(
                Issue(
                    severity="BLOCK",
                    title=f'Non-descriptive link text: "{anchor}"',
                    wcag="2.4.4 Link Purpose (In Context) (Level A)",
                    location=f"Line {link.line}, href: {link.href}",
                    detail=(
                        "Anchors like 'click here', 'read more', or 'learn "
                        "more' don't describe the destination. Screen-reader "
                        "users often skim a list of all links on the page; "
                        "non-descriptive anchors strip the link of meaning in "
                        "that context."
                    ),
                    fix=(
                        f'Rewrite to describe the destination — e.g., '
                        f'"View the {link.href.rsplit("/", 1)[-1] or "destination page"}" '
                        f'or "Read our HELOC rate guide".'
                    ),
                )
            )
    return issues


def check_images(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    for img in audit.images:
        # Markdown image alt is always present (possibly empty). HTML <img>
        # may have alt missing entirely → BLOCK.
        if img.is_html and img.alt is None:
            issues.append(
                Issue(
                    severity="BLOCK",
                    title="Image missing alt attribute",
                    wcag="1.1.1 Non-text Content (Level A)",
                    location=f"Line {img.line}, src: {img.src or '(none)'}",
                    detail=(
                        "An <img> tag with no alt attribute is announced "
                        "differently across screen readers — some read the "
                        "filename, some say 'image', some skip it. Always "
                        "include alt; use alt=\"\" only when the image is "
                        "purely decorative."
                    ),
                    fix=(
                        'Add alt="describe the image\'s purpose" or alt="" '
                        "if the image is decorative."
                    ),
                )
            )
            continue

        # Markdown ![](url) is treated as an explicit empty alt = decorative,
        # which is the convention. We don't flag it. But if alt is empty AND
        # the image src looks meaningful (e.g., a chart), surface a NIT.
        alt_text = img.alt or ""
        if not alt_text.strip():
            # Decorative: pass.
            continue

        # Image-of-text check (1.4.5).
        if _looks_like_image_of_text(alt_text):
            issues.append(
                Issue(
                    severity="WARN",
                    title="Image alt looks like a sentence — possible image-of-text",
                    wcag="1.4.5 Images of Text (Level AA)",
                    location=f"Line {img.line}, alt: \"{_shorten(alt_text, 60)}\"",
                    detail=(
                        "When the alt text is a full sentence, the image is "
                        "likely a quote or paragraph rendered as a graphic. "
                        "Screen readers can read alt, but users can't resize, "
                        "recolor, or copy the text the way they can with real "
                        "HTML."
                    ),
                    fix=(
                        "If this is a pull-quote or callout, render it as a "
                        "<blockquote> (markdown `>`) instead of an image."
                    ),
                )
            )
    return issues


def check_tables(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    for tbl in audit.tables:
        if not tbl.has_header:
            issues.append(
                Issue(
                    severity="BLOCK",
                    title="Table without a header row",
                    wcag="1.3.1 Info and Relationships (Level A)",
                    location=f"Line {tbl.line}",
                    detail=(
                        "Tables must have a header row so assistive tech can "
                        "associate each cell with its column."
                    ),
                    fix="Add a header row using markdown's `| h1 | h2 |` + `|---|---|` syntax.",
                )
            )
    return issues


def check_color_only(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    seen = set()
    for text, sect, line in audit.paragraphs:
        for pat in _COLOR_ONLY_PATTERNS:
            for m in pat.finditer(text):
                snippet = _shorten(text[max(0, m.start() - 20): m.end() + 20])
                key = (line, m.group(0).lower())
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    Issue(
                        severity="BLOCK",
                        title=f'Color-only reference: "{m.group(0)}"',
                        wcag="1.4.1 Use of Color (Level A)",
                        location=f'Section "{sect}", around "{snippet}" (line {line})',
                        detail=(
                            "This reference identifies content by color alone. "
                            "Color-blind users and screen-reader users can't "
                            "follow it."
                        ),
                        fix=(
                            "Add a non-color cue: a label, an icon described "
                            "in the text, or a position-independent name "
                            "(e.g., 'the items marked Recommended (highlighted "
                            "in green)')."
                        ),
                    )
                )
    return issues


def check_spatial(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    seen = set()
    for text, sect, line in audit.paragraphs:
        for pat in _SPATIAL_PATTERNS:
            for m in pat.finditer(text):
                snippet = _shorten(text[max(0, m.start() - 20): m.end() + 20])
                key = (line, m.group(0).lower())
                if key in seen:
                    continue
                seen.add(key)
                issues.append(
                    Issue(
                        severity="BLOCK",
                        title=f'Spatial-position reference: "{m.group(0)}"',
                        wcag="1.3.2 Meaningful Sequence (Level A)",
                        location=f'Section "{sect}", around "{snippet}" (line {line})',
                        detail=(
                            "Content that depends on visual position breaks "
                            "when it's linearized for screen readers or when "
                            "the layout reflows on small screens."
                        ),
                        fix=(
                            "Refer to the content by name or label rather "
                            "than position (e.g., 'the table titled Rate "
                            "Comparison' instead of 'the table on the right')."
                        ),
                    )
                )
    return issues


def check_long_paragraphs(audit: AuditResult) -> List[Issue]:
    issues: List[Issue] = []
    for text, sect, line in audit.paragraphs:
        wc = len(text.split())
        if wc > 100:
            issues.append(
                Issue(
                    severity="NIT",
                    title=f"Long paragraph ({wc} words)",
                    wcag="3.1.5 Reading Level / cognitive accessibility (Level AAA)",
                    location=f'Section "{sect}", line {line}',
                    detail=(
                        "Paragraphs longer than ~100 words are harder for "
                        "readers with cognitive disabilities or those reading "
                        "on small screens. They're also harder to skim for "
                        "the average reader."
                    ),
                    fix=(
                        "Split into two or more paragraphs at natural "
                        "topic-shift points."
                    ),
                )
            )
    return issues


def check_pseudo_lists(audit: AuditResult) -> List[Issue]:
    """Flag paragraph runs that look like a list but were written as prose."""
    issues: List[Issue] = []
    for text, sect, line in audit.paragraphs:
        # Count distinct pseudo-list-marker hits across the paragraph.
        matches = _PSEUDO_LIST.findall("\n" + text)
        if len(matches) >= 2:
            issues.append(
                Issue(
                    severity="WARN",
                    title="Paragraph uses pseudo-list markers (•, –, Item 1:) instead of a real list",
                    wcag="1.3.1 Info and Relationships (Level A)",
                    location=f'Section "{sect}", line {line}',
                    detail=(
                        "Bullet glyphs and 'Item N:' prefixes look like a "
                        "list but render as prose. Screen readers don't "
                        "announce them as a list, and users can't navigate "
                        "between items."
                    ),
                    fix=(
                        "Convert to a real markdown list using `-` or `1.` "
                        "at the start of each item line."
                    ),
                )
            )
    return issues


def check_reading_level(metrics: ReadingLevelMetrics, target_grade: int,
                        audience: str) -> List[Issue]:
    issues: List[Issue] = []
    grades = {
        "Flesch-Kincaid Grade": metrics.flesch_kincaid_grade,
        "SMOG Index": metrics.smog_index,
        "Gunning Fog": metrics.gunning_fog,
    }
    over = {n: g for n, g in grades.items() if g > target_grade}
    if over:
        worst = max(over.values())
        names = ", ".join(f"{n} {g:.1f}" for n, g in over.items())
        hardest = hardest_sentences(metrics, n=3)
        bullets = "\n".join(
            f'  {i+1}. "{_shorten(s, 120)}" — grade {g}'
            for i, (s, g) in enumerate(hardest)
        )
        severity = "WARN"  # Per spec: AAA reading level flags but doesn't BLOCK.
        issues.append(
            Issue(
                severity=severity,
                title=f"Reading level above target (grade {target_grade}) for {audience}",
                wcag="3.1.5 Reading Level (Level AAA)",
                location="Whole document",
                detail=(
                    f"At least one metric exceeds grade {target_grade}: {names}. "
                    f"Hardest passages by sentence-level Flesch-Kincaid:\n{bullets}"
                ),
                fix=(
                    f"Aim for grade ≤ {target_grade} (currently up to "
                    f"{worst:.1f}). Shorten sentences, swap multi-syllable "
                    "words for shorter equivalents where the meaning allows, "
                    "and define unavoidable terms-of-art on first use."
                ),
            )
        )
    return issues


def deferred_checks() -> List[Issue]:
    """The DEFER section is always emitted to remind reviewers about
    page-level audits this skill cannot perform."""
    return [
        Issue(
            severity="DEFER",
            title="Color contrast",
            wcag="1.4.3 Contrast (Minimum) (Level AA)",
            location="Rendered page",
            detail=(
                "This skill cannot verify color contrast at the content level. "
                "After the article is rendered on the live site, run an "
                "automated check (axe DevTools, Lighthouse, or WAVE) to "
                "verify all text-on-background contrasts meet 4.5:1 (normal "
                "text) or 3:1 (large text and UI components)."
            ),
            fix="Run axe DevTools, Lighthouse, or WAVE on the rendered page.",
        ),
        Issue(
            severity="DEFER",
            title="Keyboard navigation and focus order",
            wcag="2.1.1 Keyboard / 2.4.3 Focus Order / 2.4.7 Focus Visible (Levels A & AA)",
            location="Rendered page",
            detail=(
                "Keyboard reachability, logical focus order, and visible "
                "focus indicators all depend on the rendered DOM and CSS. "
                "Verify on the live page using only the Tab/Shift+Tab/Enter "
                "keys and observe whether every interactive element is "
                "reachable in a logical order with a visible focus ring."
            ),
            fix=(
                "Manually tab through the rendered page; use axe DevTools or "
                "Lighthouse to flag missing focus styles."
            ),
        ),
        Issue(
            severity="DEFER",
            title="Screen-reader announcement order",
            wcag="1.3.2 Meaningful Sequence (Level A)",
            location="Rendered page",
            detail=(
                "Screen readers traverse the DOM in source order, which may "
                "differ from the visual layout when CSS reorders sections "
                "(grid, flex with `order:`, absolute positioning). Verify "
                "with VoiceOver, NVDA, or JAWS."
            ),
            fix=(
                "Run a quick screen-reader pass (VoiceOver on macOS / NVDA "
                "on Windows) to confirm reading order matches the visual "
                "layout."
            ),
        ),
        Issue(
            severity="DEFER",
            title="Form labels and error states",
            wcag="3.3.2 Labels or Instructions / 3.3.1 Error Identification (Levels A & A)",
            location="Rendered page",
            detail=(
                "Any forms embedded on the page (subscription, calculator, "
                "contact) need visible labels, programmatic label/input "
                "association, and accessible error messaging. These are "
                "rendered-form concerns this skill can't see in the markdown."
            ),
            fix="Verify each form input has a <label> and that error states are announced.",
        ),
        Issue(
            severity="DEFER",
            title="Page language declaration",
            wcag="3.1.1 Language of Page (Level A)",
            location="Rendered <html lang>",
            detail=(
                "The page's primary language must be declared on the rendered "
                "<html> element. Verify the publishing system emits the right "
                "`lang` attribute."
            ),
            fix='Confirm the site template sets <html lang="en"> (or the appropriate locale).',
        ),
    ]


def run_all_checks(audit: AuditResult, metrics: ReadingLevelMetrics,
                   target_grade: int, audience: str) -> List[Issue]:
    issues: List[Issue] = []
    issues.extend(check_headings(audit))
    issues.extend(check_links(audit))
    issues.extend(check_images(audit))
    issues.extend(check_tables(audit))
    issues.extend(check_color_only(audit))
    issues.extend(check_spatial(audit))
    issues.extend(check_long_paragraphs(audit))
    issues.extend(check_pseudo_lists(audit))
    issues.extend(check_reading_level(metrics, target_grade, audience))
    return issues
