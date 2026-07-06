#!/usr/bin/env python3
"""Build the Phase 9 compliance bundle PDF for an experiment.

Combines the article + decisions log + four review reports + supporting
context into a single paginated PDF (cover page, TOC, one document per
section) for the credit union's compliance officer.

Parameterized replacement for the per-experiment build-compliance-pdf.py
copies — point it at any experiments/<slug>/ folder:

    python3 tools/build-compliance-pdf.py \
      --experiment-dir experiments/<slug> \
      --credit-union "Heartland Credit Union" \
      --verdict "VIABLE / High Confidence" \
      --experiment-id 103 --campaign-id 512 \
      --targets "9 prompts; ~2,710/mo Wisconsin search demand" \
      --open-items "2 POC questions marked inline" \
      --summary-note "0 BLOCK items, 4 WARN items requiring disposition."

Section files are discovered by the project's naming convention
(article-<slug>.md, decisions.md, article-<slug>.<review>.md, evidence.md,
experiment.md, workflow-log.md); missing files are skipped with a warning.

Dependencies: markdown-it-py + weasyprint (weasyprint needs Homebrew
glib/pango/cairo on macOS; the script re-execs itself with
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib so the framework Python can
find them).
"""
import argparse
import datetime
import os
import re
import sys
from pathlib import Path

# macOS: dyld only reads DYLD_* at process start, so set the fallback path
# and re-exec before importing weasyprint.
if sys.platform == "darwin" and "/opt/homebrew/lib" not in os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", ""):
    env = dict(os.environ)
    env["DYLD_FALLBACK_LIBRARY_PATH"] = (
        env.get("DYLD_FALLBACK_LIBRARY_PATH", "") + ":/opt/homebrew/lib"
    ).lstrip(":")
    os.execve(sys.executable, [sys.executable] + sys.argv, env)

from markdown_it import MarkdownIt
from weasyprint import HTML, CSS


def sections_for(slug: str):
    # Order matters — this is the read order the compliance officer should follow.
    return [
        (f"article-{slug}.md",                      "Article",                   "the article being reviewed"),
        ("decisions.md",                            "Decisions log",             "the article-direction choices behind the draft"),
        (f"article-{slug}.hygiene-check.md",        "Pre-publish hygiene check", "typography, formatting, spelling, link/table attributes"),
        (f"article-{slug}.compliance-review.md",    "NCUA compliance review",    "Part 740, Reg Z, Reg B / fair lending, SAFE Act, state-specific"),
        (f"article-{slug}.accessibility-review.md", "ADA accessibility review",  "WCAG 2.1 AA content-level checks"),
        (f"article-{slug}.fact-check.md",           "Fact verification",         "claim-by-claim verification against authoritative sources"),
        ("evidence.md",                             "Evidence dossier",          "Phase 1 keyword + Phase 3 baseline empirical inputs"),
        ("experiment.md",                           "Experiment record",         "topic, audience, hypothesis, baseline summary"),
        ("workflow-log.md",                         "Workflow log",              "phase-by-phase status spine"),
    ]


CSS_STYLE = """
@page {
    size: Letter;
    margin: 0.75in 0.85in 0.85in 0.85in;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 9pt;
        color: #71717a;
    }
    @top-right {
        content: string(doc-header);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        font-size: 8pt;
        color: #a1a1aa;
    }
}
@page :first {
    @top-right { content: none; }
    @bottom-center { content: none; }
}
.doc-header-source { string-set: doc-header content(); display: none; }
* { box-sizing: border-box; }
html, body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: #18181b;
    line-height: 1.55;
    font-size: 10.5pt;
    -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4 {
    font-weight: 600;
    line-height: 1.25;
    color: #09090b;
    letter-spacing: -0.01em;
}
h1 { font-size: 22pt; margin-top: 0; margin-bottom: 0.6em; }
h2 { font-size: 15pt; margin-top: 1.6em; margin-bottom: 0.5em; padding-top: 0.6em; border-top: 1px solid #e4e4e7; }
h3 { font-size: 12pt; margin-top: 1.4em; margin-bottom: 0.4em; }
h4 { font-size: 10.5pt; margin-top: 1em; margin-bottom: 0.3em; color: #3f3f46; }
p { margin: 0.6em 0; }
a { color: #18181b; text-decoration: underline; text-decoration-color: #d4d4d8; }
strong { font-weight: 600; color: #09090b; }
em { font-style: italic; }
code { font-family: 'SF Mono', Monaco, 'Cascadia Mono', 'Roboto Mono', Consolas, monospace; font-size: 0.9em; background: #f4f4f5; padding: 1px 5px; border-radius: 3px; color: #18181b; }
pre { background: #fafafa; border: 1px solid #e4e4e7; border-radius: 4px; padding: 0.8em 1em; overflow-x: auto; }
pre code { background: transparent; padding: 0; font-size: 0.85em; }
ul, ol { margin: 0.5em 0; padding-left: 1.4em; }
li { margin: 0.25em 0; }
li > p { margin: 0.2em 0; }
blockquote {
    margin: 1em 0;
    padding: 0.7em 1em;
    border-left: 3px solid #e4e4e7;
    background: #fafafa;
    color: #3f3f46;
    border-radius: 0 4px 4px 0;
}
blockquote p { margin: 0.3em 0; }
table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 9.5pt; }
th, td { border: 1px solid #e4e4e7; padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: #fafafa; font-weight: 600; color: #18181b; }
tbody tr:nth-child(even) td { background: #fafafa; }
hr { border: none; border-top: 1px solid #e4e4e7; margin: 2em 0; }

/* Cover page */
.cover {
    page-break-after: always;
    padding: 2.2in 0.5in 0.5in;
    text-align: left;
}
.cover .eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.18em;
    font-size: 9pt;
    color: #71717a;
    font-weight: 500;
    margin-bottom: 1.4em;
}
.cover h1 {
    font-size: 32pt;
    line-height: 1.1;
    margin: 0 0 0.5em;
    letter-spacing: -0.02em;
}
.cover .subtitle {
    font-size: 13pt;
    color: #52525b;
    margin: 0 0 2.2em;
    line-height: 1.5;
}
.cover .meta {
    margin-top: 2.2in;
    font-size: 9.5pt;
    color: #52525b;
    border-top: 1px solid #e4e4e7;
    padding-top: 1em;
}
.cover .meta dt { font-weight: 600; color: #18181b; }
.cover .meta dl { display: grid; grid-template-columns: 1.6in 1fr; row-gap: 0.5em; margin: 0; }
.verdict-badge {
    display: inline-block;
    background: #052e16;
    color: white;
    padding: 6px 14px;
    border-radius: 4px;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.8em;
}

/* Section break */
.section-break {
    page-break-before: always;
    padding-top: 0.5em;
}
.section-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.15em;
    font-size: 8.5pt;
    color: #a1a1aa;
    font-weight: 500;
    margin-bottom: 0.4em;
}

/* TOC */
.toc-page {
    page-break-after: always;
}
.toc-page ol { list-style: none; padding-left: 0; counter-reset: toc; }
.toc-page ol li { counter-increment: toc; padding: 0.4em 0; border-bottom: 1px dotted #e4e4e7; }
.toc-page ol li::before { content: counter(toc) ". "; color: #a1a1aa; font-variant-numeric: tabular-nums; margin-right: 0.5em; }
.toc-page ol li .toc-desc { display: block; color: #71717a; font-size: 9pt; margin-top: 0.15em; padding-left: 1.6em; }
"""


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def first_h1(md_path: Path) -> str | None:
    for line in md_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            return m.group(1).strip()
    return None


def render_section(md_path: Path, eyebrow: str, parser: MarkdownIt) -> str:
    body_html = parser.render(md_path.read_text(encoding="utf-8"))
    return f"""
<div class="section-break">
    <div class="section-eyebrow">{esc(eyebrow)}</div>
    {body_html}
</div>
"""


def main():
    ap = argparse.ArgumentParser(description="Build the compliance bundle PDF for an experiment folder.")
    ap.add_argument("--experiment-dir", required=True, help="experiments/<slug> folder")
    ap.add_argument("--slug", help="experiment slug (default: experiment-dir basename); used to find article-<slug>.* files")
    ap.add_argument("--credit-union", default="", help="credit union name (cover eyebrow + running header)")
    ap.add_argument("--title", help="bundle title (default: the article's H1)")
    ap.add_argument("--subtitle", default="Pre-publish compliance review bundle: the article, the decision log behind it, and the four assistive review reports.", help="cover subtitle")
    ap.add_argument("--verdict", default="", help='viability badge text, e.g. "VIABLE / High Confidence" (omit to hide)')
    ap.add_argument("--compiled", default=datetime.date.today().isoformat(), help="compiled date (default: today)")
    ap.add_argument("--experiment-id", default="", help="Paraloom experiment id")
    ap.add_argument("--campaign-id", default="", help="Paraloom campaign id")
    ap.add_argument("--targets", default="", help='target summary, e.g. "9 prompts; ~2,710/mo search demand"')
    ap.add_argument("--open-items", default="", help="open POC items summary for the cover")
    ap.add_argument("--summary-note", default="", help="one-paragraph review rollup for the TOC page (BLOCK/WARN counts etc.)")
    ap.add_argument("--output", help="output PDF path (default: <experiment-dir>/compliance-bundle.pdf)")
    args = ap.parse_args()

    exp_dir = Path(args.experiment_dir)
    if not exp_dir.is_dir():
        sys.exit(f"ERROR: not a directory: {exp_dir}")
    slug = args.slug or exp_dir.resolve().name
    output = Path(args.output) if args.output else exp_dir / "compliance-bundle.pdf"

    article = exp_dir / f"article-{slug}.md"
    title = args.title or (first_h1(article) if article.exists() else None) or slug

    md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table").enable("strikethrough")
    eyebrow = f"{args.credit_union} compliance bundle" if args.credit_union else "Compliance bundle"

    sections = sections_for(slug)
    sections_html, included = [], []
    for fname, sec_title, desc in sections:
        path = exp_dir / fname
        if not path.exists():
            print(f"WARNING: missing {fname} — skipped", file=sys.stderr)
            continue
        sections_html.append(render_section(path, eyebrow, md))
        included.append((sec_title, desc))

    if not sections_html:
        sys.exit(f"ERROR: no section files found in {exp_dir} for slug '{slug}'")

    toc_items = "".join(
        f'<li><strong>{esc(t)}</strong><span class="toc-desc">{esc(d)}</span></li>'
        for t, d in included
    )
    meta_rows = "".join(
        f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>"
        for k, v in [
            ("Article", f"article-{slug}.md"),
            ("Compiled", args.compiled),
            ("Experiment", f"Paraloom ID {args.experiment_id}" if args.experiment_id else ""),
            ("Campaign", f"Paraloom ID {args.campaign_id}" if args.campaign_id else ""),
            ("Targets", args.targets),
            ("Open items", args.open_items),
        ] if v
    )
    badge = f'<div class="verdict-badge">Experiment Viability: {esc(args.verdict)}</div>' if args.verdict else ""
    summary = f'<p style="color: #71717a; font-size: 9pt; margin-top: 2em; line-height: 1.6;">{esc(args.summary_note)}</p>' if args.summary_note else ""
    header_text = " — ".join(x for x in [args.credit_union, title] if x)

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{esc(header_text)} — Compliance Bundle</title>
</head>
<body>
<span class="doc-header-source">{esc(header_text)}</span>

<div class="cover">
    <div class="eyebrow">{esc(args.credit_union or "Paraloom")} &middot; Pre-publish review</div>
    <h1>{esc(title)}</h1>
    <p class="subtitle">{esc(args.subtitle)}</p>
    {badge}
    <dl class="meta">{meta_rows}</dl>
</div>

<div class="toc-page">
    <h1>Contents</h1>
    <ol>{toc_items}</ol>
    <p style="color: #71717a; font-size: 9pt; margin-top: 2em; line-height: 1.6;">
        This bundle is the compliance-review package for the article in section 1. The hygiene, NCUA
        compliance, ADA accessibility, and fact-verification sections are assistive review reports;
        each ends with the human compliance officer sign-off section. The remaining sections are
        supporting context (evidence, experiment record, workflow log).
    </p>
    {summary}
</div>

{''.join(sections_html)}

</body>
</html>
"""

    HTML(string=html_doc).write_pdf(output, stylesheets=[CSS(string=CSS_STYLE)])
    print(f"Wrote {output} ({output.stat().st_size:,} bytes, {len(included)} sections)")


if __name__ == "__main__":
    main()
