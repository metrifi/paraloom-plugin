---
name: ada-accessibility-review
description: Review long-form marketing content (articles, blog posts, landing-page copy) against WCAG 2.1 AA at the content level — heading hierarchy, descriptive link text, alt text expectations, plain-language reading level, and structural semantics. Produce an issues list with WCAG criterion citations, severity, and fixes. Use this skill whenever the user mentions accessibility review, ADA check, WCAG check, "is this article accessible", reading level, plain-language audit, alt text review, or asks for an article to be checked before publication. Strongly prefer this skill over a hand-written audit any time a markdown article is the subject.
---

# ada-accessibility-review

Audits a draft markdown article for WCAG 2.1 AA conformance at the **content
level** and produces a prioritized issues list with WCAG criterion citations
and concrete fixes.

This skill is **assistive, not authoritative**. WCAG conformance is ultimately
verified at the rendered-page level (color contrast, keyboard navigation,
screen reader behavior). This skill catches what's visible in the markdown
before the content lands on a page, and always emits a DEFER section listing
the page-level checks that still need to happen downstream.

## When to use this skill

Trigger this skill when:

- The user asks for an "accessibility review", "ADA check", "WCAG check",
  "508 review", or asks whether an article is accessible.
- The user asks about reading level, plain-language compliance, or "can a
  member understand this".
- The user asks to "lint" or "audit" a draft article before publication.
- The user is preparing financial / member-facing / regulatory content and
  wants a pre-publication review.

If the article is shorter than ~150 words, run the skill anyway — the output
is still useful — but the reading-level metrics on very short content are
noisy and the report flags that explicitly.

## How to run it

The skill ships an entrypoint at `scripts/review.py`. Invoke it from the
session shell, passing the article path. The skill writes the report next to
the article as `<basename>.accessibility-review.md`.

Basic usage:

```bash
python /path/to/ada-accessibility-review/scripts/review.py \
  "/path/to/article.md"
```

With a custom target grade (e.g., for technical / regulatory content):

```bash
python /path/to/ada-accessibility-review/scripts/review.py \
  "/path/to/article.md" \
  --target-grade 10 \
  --audience "small-business owner"
```

The skill also accepts `--json` for a JSON summary on stdout (the markdown
report is still written to disk).

## Inputs

- **`article_path`** (required): path to the markdown file to review.
- **`--target-grade`** (optional, default `9`): reading-level target. Lower
  for member-facing general content (e.g., 8 for retail-banking articles);
  higher for technical / regulatory content (e.g., 10 for compliance copy).
- **`--audience`** (optional, default `"general consumer"`): label that
  appears in the report. Used to set expectations for the human reviewer.

## What the skill checks

### Content-level checks (in scope)

The skill parses the markdown with **markdown-it-py** and walks the AST — no
regex over `#` characters, so embedded code blocks and HTML tags are handled
correctly.

- **Heading hierarchy** (1.3.1, 2.4.2): one H1; no skipped levels (H1→H3 is a
  BLOCK); generic headings ("Section 1", "Introduction") are WARN.
- **Link purpose** (2.4.4): every anchor extracted from the AST. "click here",
  "read more", "learn more", "this link" → BLOCK.
- **Image alt text** (1.1.1, 1.4.5): `<img>` with no `alt` attribute → BLOCK.
  Markdown `![](url)` is treated as an explicit decorative marker and passes.
  Alt text that's a long sentence (likely image-of-text) → WARN.
- **List & table semantics** (1.3.1): tables without a header row → BLOCK.
  Paragraphs that look like a list (•, "Item N:") but aren't real markdown
  lists → WARN.
- **Use of color** (1.4.1): "click the green button", "items in red are
  recommended" → BLOCK.
- **Spatial-position language** (1.3.2): "the box on the left", "see the
  table to the right" → BLOCK.
- **Long paragraphs** (cognitive accessibility, AAA): any paragraph >100 words
  → NIT.
- **Long sections** (2.4.10): any section >300 words without a sub-heading
  → NIT.
- **Reading level** (3.1.5, AAA): Flesch-Kincaid Grade, SMOG, and Gunning
  Fog. Any metric exceeding the target → WARN with the three hardest sentences
  surfaced and a structural simplification hint.

### Page-level checks (DEFER — always emitted)

The report always includes a DEFER section with the rendered-page checks this
skill cannot perform:

- **1.4.3 Contrast** — depends on rendered CSS.
- **2.1.1 / 2.4.3 / 2.4.7 Keyboard navigation, focus order, focus visible** —
  depends on rendered DOM and CSS.
- **1.3.2 Screen-reader announcement order** — depends on DOM source order.
- **3.3.2 Form labels and error states** — depends on rendered forms.
- **3.1.1 Page language declaration** — depends on the `<html lang>` attribute.

The DEFER section recommends axe DevTools, Lighthouse, or WAVE on the rendered
page. Always include it in the report, even when the article is otherwise
clean — it's a checklist item the reviewer needs to schedule.

See `WCAG.md` (sibling file) for the embedded criterion-by-criterion
reference, including notes on what the skill checks for each criterion.

## Severity model

- **BLOCK** — clear Level A or AA failure that's content-level. Must be
  fixed before publication.
- **WARN** — Level AA borderline or AAA reading-level miss; reviewer
  judgment.
- **NIT** — best-practice nit (paragraph length, section density,
  language-of-parts).
- **DEFER** — page-level concern; flag for downstream rendered-page audit.

## Output format

The skill writes a markdown report next to the article. The structure is
fixed; downstream tooling (and reviewers' muscle memory) depends on the exact
section order. See `tests/01_missing_alt.md.accessibility-review.md` after
running the test suite for an example.

The report has six top-level sections, in order:

1. **Summary** — counts by severity + reading-level grades + a banner
   reminder that a rendered-page audit is still required.
2. **Issues** — grouped by severity (BLOCK → WARN → DEFER → NIT). Each issue
   has Location, WCAG criterion, Issue description, Fix.
3. **Reading-level breakdown** — sentence/word/syllable counts plus the top
   three hardest sentences with simplification hints.
4. **Reviewer sign-off** — checkbox list including the rendered-page audit
   reminder.

## How to interpret the report when reviewing with a human

When reviewing a generated report with the human reviewer:

- Walk through BLOCK items first — these are the things that must be fixed.
  Each one cites the WCAG criterion; quote the criterion if the reviewer
  pushes back.
- For WARN items, present the reviewer the choice: fix, or document a reason
  for the exception (especially common with reading-level WARNs in financial
  content where terms-of-art are unavoidable).
- For NIT items, batch them at the end — don't let them dominate the
  conversation.
- DEFER items are a checklist the reviewer takes to whoever owns the rendered
  page. Don't try to "resolve" them in the markdown.

## Implementation notes for future maintainers

- `scripts/markdown_audit.py` walks the markdown-it AST and gathers
  structural facts (headings, links, images, tables, paragraphs).
- `scripts/reading_level.py` implements FK Grade, SMOG, and Gunning Fog
  directly with a vowel-cluster syllable counter. No external syllable
  dictionary is required, which keeps the skill self-contained.
- `scripts/wcag_checks.py` turns audit facts into Issues with WCAG citations
  and produces the always-on DEFER list.
- `scripts/review.py` is the entrypoint: orchestrates audit + metrics +
  checks and renders the report.

When updating WCAG criteria coverage, edit both `WCAG.md` (the human-facing
reference) and the corresponding check in `scripts/wcag_checks.py`. Keep
those in sync.

## Test suite

`tests/` contains fixtures for the eight cases enumerated in the spec.
Running `python tests/run_tests.py` from inside the skill directory
re-runs the full suite and prints PASS/FAIL per case.
