"""Walk a markdown-it AST and collect structural accessibility issues.

We rely on a real markdown parser rather than regex because:
- HTML embeds inside markdown need real parsing (e.g., raw `<img>` tags).
- Heading hierarchy needs a sequence of heading tokens, not a regex over `#`.
- Code blocks must be ignored (a `#` inside a fenced block is not a heading).
- Lists and tables must be detected as structures, not as bullet glyphs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from markdown_it import MarkdownIt
from markdown_it.token import Token


# Anchors that indicate the link text is non-descriptive. Lowercased for
# case-insensitive comparison.
BAD_ANCHORS = {
    "click here", "here", "read more", "more", "learn more", "this link",
    "link", "this", "click", "read this", "more info", "info",
}

# Heading text patterns that are too generic to describe their section.
GENERIC_HEADING_PATTERNS = [
    re.compile(r"^section\s*\d*\s*$", re.I),
    re.compile(r"^introduction\s*$", re.I),
    re.compile(r"^conclusion\s*$", re.I),
    re.compile(r"^overview\s*$", re.I),
    re.compile(r"^more\s+info(rmation)?\s*$", re.I),
    re.compile(r"^details\s*$", re.I),
    re.compile(r"^content\s*$", re.I),
    re.compile(r"^part\s*\d+\s*$", re.I),
    re.compile(r"^chapter\s*\d+\s*$", re.I),
]

# HTML img regex used only after we've confirmed we're inside an html_block /
# html_inline token. We do NOT use this on raw markdown.
_HTML_IMG = re.compile(
    r"<img\b([^>]*)>",
    re.I | re.S,
)
_HTML_ATTR = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


@dataclass
class Issue:
    severity: str  # BLOCK, WARN, NIT, DEFER
    title: str
    wcag: str
    location: str
    detail: str
    fix: str


@dataclass
class HeadingInfo:
    level: int
    text: str
    line: int


@dataclass
class LinkInfo:
    anchor: str
    href: str
    line: int


@dataclass
class ImageInfo:
    alt: Optional[str]  # None means attribute missing entirely
    src: str
    line: int
    is_html: bool


@dataclass
class TableInfo:
    has_header: bool
    line: int


@dataclass
class AuditResult:
    headings: List[HeadingInfo] = field(default_factory=list)
    links: List[LinkInfo] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)
    tables: List[TableInfo] = field(default_factory=list)
    paragraphs: List[tuple] = field(default_factory=list)  # (text, heading-section, line)
    body_text: str = ""
    issues: List[Issue] = field(default_factory=list)


def _flatten_inline_text(token: Token) -> str:
    """Concatenate text from an inline token's children, including link text."""
    parts: List[str] = []
    if token.children:
        for child in token.children:
            if child.type == "text":
                parts.append(child.content)
            elif child.type == "code_inline":
                parts.append(child.content)
            elif child.type == "softbreak" or child.type == "hardbreak":
                parts.append(" ")
            elif child.type in ("strong_open", "strong_close", "em_open", "em_close",
                                "s_open", "s_close"):
                continue
            elif child.type == "image":
                # markdown-it represents image alt as the children text.
                pass
            else:
                # Fallback: strip tags from content if any.
                if child.content:
                    parts.append(child.content)
    else:
        parts.append(token.content)
    return "".join(parts).strip()


def _line_of(token: Token) -> int:
    if token.map is not None:
        return token.map[0] + 1  # 1-indexed
    return -1


def audit(markdown_text: str) -> AuditResult:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    tokens = md.parse(markdown_text)

    result = AuditResult()
    body_chunks: List[str] = []

    # Iterate. Handle headings, paragraphs, links, images, lists, tables.
    i = 0
    current_section_heading = ""
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1])
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            heading_text = _flatten_inline_text(inline) if inline else ""
            line = _line_of(tok)
            result.headings.append(HeadingInfo(level=level, text=heading_text, line=line))
            current_section_heading = heading_text
            i += 3  # heading_open, inline, heading_close
            continue

        if tok.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            line = _line_of(tok)
            text = _flatten_inline_text(inline) if inline else ""
            if text:
                result.paragraphs.append((text, current_section_heading, line))
                body_chunks.append(text)
            # Walk inline children for links and images.
            if inline and inline.children:
                _collect_inline(inline, line, result)
            i += 3
            continue

        if tok.type == "table_open":
            line = _line_of(tok)
            # See if a thead is present before the next tbody/table_close.
            j = i + 1
            has_header = False
            while j < len(tokens) and tokens[j].type != "table_close":
                if tokens[j].type == "thead_open":
                    has_header = True
                    break
                j += 1
            result.tables.append(TableInfo(has_header=has_header, line=line))
            # We still want body text from cells for reading-level analysis.
            j = i + 1
            while j < len(tokens) and tokens[j].type != "table_close":
                if tokens[j].type == "inline":
                    body_chunks.append(_flatten_inline_text(tokens[j]))
                j += 1
            i = j + 1
            continue

        if tok.type == "html_block":
            _collect_html_block(tok.content, _line_of(tok), result)
            body_chunks.append(re.sub(r"<[^>]+>", " ", tok.content))
            i += 1
            continue

        if tok.type == "fence" or tok.type == "code_block":
            # Skip code from reading-level body text but keep going.
            i += 1
            continue

        # List items: capture text inside paragraph children but don't emit
        # the surrounding list as paragraphs.
        if tok.type == "bullet_list_open" or tok.type == "ordered_list_open":
            i += 1
            continue
        if tok.type in ("bullet_list_close", "ordered_list_close"):
            i += 1
            continue
        if tok.type == "list_item_open":
            i += 1
            continue
        if tok.type == "list_item_close":
            i += 1
            continue

        if tok.type == "inline":
            # Stray inline (e.g., inside tight list items).
            text = _flatten_inline_text(tok)
            if text:
                body_chunks.append(text)
                _collect_inline(tok, _line_of(tok), result)
            i += 1
            continue

        i += 1

    result.body_text = "\n\n".join(body_chunks)
    return result


def _collect_inline(inline: Token, parent_line: int, result: AuditResult) -> None:
    if not inline.children:
        return
    j = 0
    children = inline.children
    while j < len(children):
        child = children[j]

        if child.type == "link_open":
            href = ""
            for attr_name, attr_val in child.attrs.items():
                if attr_name == "href":
                    href = attr_val
            # Collect anchor text until link_close.
            anchor_parts = []
            j2 = j + 1
            while j2 < len(children) and children[j2].type != "link_close":
                if children[j2].type == "text":
                    anchor_parts.append(children[j2].content)
                elif children[j2].type == "code_inline":
                    anchor_parts.append(children[j2].content)
                elif children[j2].type == "image":
                    # Image-only links — anchor is the alt text.
                    alt = children[j2].content or ""
                    if not alt:
                        # Try the alt attribute (markdown-it stores alt as content).
                        for an, av in (children[j2].attrs.items() if children[j2].attrs else []):
                            if an == "alt":
                                alt = av
                    anchor_parts.append(alt)
                j2 += 1
            anchor = " ".join(p for p in anchor_parts if p).strip()
            result.links.append(LinkInfo(anchor=anchor, href=href, line=parent_line))
            j = j2 + 1
            continue

        if child.type == "image":
            # markdown-it: alt is in child.content; src is in attrs.
            src = ""
            alt = child.content
            for an, av in (child.attrs.items() if child.attrs else []):
                if an == "src":
                    src = av
                if an == "alt":
                    alt = av
            # markdown-it always emits an alt attribute for images written as
            # `![alt](url)`. The alt may be empty string. To detect "missing
            # alt entirely" in markdown, we'd need to distinguish `![](url)`
            # (empty alt — decorative) from a malformed link. CommonMark
            # treats `![](url)` as an image with empty alt, which is the
            # decorative convention — passing.
            result.images.append(ImageInfo(alt=alt, src=src, line=parent_line, is_html=False))
            j += 1
            continue

        if child.type == "html_inline":
            _collect_html_block(child.content, parent_line, result)
            j += 1
            continue

        j += 1


def _collect_html_block(html: str, line: int, result: AuditResult) -> None:
    """Find <img> tags inside raw HTML and capture alt presence/value."""
    for m in _HTML_IMG.finditer(html):
        attrs_text = m.group(1)
        attrs = {k.lower(): v for k, v in _HTML_ATTR.findall(attrs_text)}
        alt = attrs.get("alt")  # None if attribute missing
        src = attrs.get("src", "")
        result.images.append(ImageInfo(alt=alt, src=src, line=line, is_html=True))


def is_generic_heading(text: str) -> bool:
    return any(p.match(text.strip()) for p in GENERIC_HEADING_PATTERNS)


def is_bad_anchor(anchor: str) -> bool:
    return anchor.strip().lower().rstrip(".!?:") in BAD_ANCHORS
