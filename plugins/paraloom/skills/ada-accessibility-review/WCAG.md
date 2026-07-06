# WCAG 2.1 criteria checked by `ada-accessibility-review`

This file is the embedded reference the skill uses when citing criteria in the
generated report. It mirrors the criteria list in the skill spec and is grouped
by conformance level, with notes on what the skill can verify at the content
level versus what must DEFER to a rendered-page audit.

---

## Level A (must conform)

### 1.1.1 Non-text Content
Every image needs an `alt` attribute. Use a descriptive `alt` for content
images; use `alt=""` for purely decorative images so assistive tech skips them.

**What this skill checks:** every markdown `![alt](url)` and HTML `<img>`
embed. Missing alt → BLOCK. `alt=""` (explicit empty) is treated as an
intentional decorative marker and passes silently, but the report notes the
count so reviewers can spot-check.

### 1.3.1 Info and Relationships
Semantic structure must be present in the markup, not just visually implied.
Headings use `#` (H1–H6), lists use `-` / `*` / `1.`, tables use header rows.
Bold paragraphs are not headings; bullet-glyph paragraphs are not lists.

**What this skill checks:**
- Heading hierarchy: there is exactly one H1 and no skipped levels (H1→H3 is a
  BLOCK).
- Pseudo-list paragraphs: lines starting with `•`, `●`, `▪`, or "Item N:" /
  "Step N:" patterns outside a real list block are flagged.
- Tables without a header row are flagged.

### 1.3.2 Meaningful Sequence
Reading order has to make sense linearly. Content that depends on visual
position ("the box on the left", "see the column on the right") fails when the
content is linearized for assistive tech.

**What this skill checks:** scans body text for spatial-position language and
flags as BLOCK.

### 1.4.1 Use of Color
Information conveyed by color alone is invisible to color-blind users and to
screen readers. Phrases like "click the red button," "items in green are
recommended," "see the highlighted section" all fail.

**What this skill checks:** scans for color-only references in body text and
flags as BLOCK. The check intentionally ignores cases where color is paired
with another cue (e.g., "the red 'Delete' button"), but flags ambiguous cases
for reviewer judgment.

### 2.4.2 Page Titled
Every article needs a clear, descriptive title (in markdown that's the H1 or
front-matter title). Generic titles ("Untitled", "New post") fail.

**What this skill checks:** missing H1 → BLOCK. Generic H1 text → WARN.

### 2.4.4 Link Purpose (In Context)
Link anchor text should describe the destination. "Click here", "read more",
"this link", "learn more" without surrounding clarification fail.

**What this skill checks:** every link extracted from the AST. Anchor text in
the bad-anchor list (case-insensitive) → BLOCK, with the criterion citation.

### 3.1.1 Language of Page
The page should declare its primary language. This is almost always a
page-level concern in markdown (the rendered HTML's `<html lang>` attribute),
so the skill flags it as DEFER unless the markdown front matter explicitly
sets a language.

### 3.3.2 Labels or Instructions
Embedded form inputs need labels. Almost always page-level; flagged as DEFER.

---

## Level AA (must conform for ADA per DOJ guidance)

### 1.4.3 Contrast (Minimum)
Text/background contrast must be ≥ 4.5:1 (normal text) or ≥ 3:1 (large text).
Depends on the rendered CSS — DEFER.

### 1.4.5 Images of Text
Use real text, not images of text, except for logos. A pull-quote rendered as
a JPG fails.

**What this skill checks:** image alt text that looks like a long sentence or
quote (≥ 8 words, ends in punctuation) is flagged as WARN — likely an image of
text that should be a real `<blockquote>`.

### 2.4.6 Headings and Labels
Headings should describe the content of the section. "Section 1",
"Introduction", "More info" are non-descriptive.

**What this skill checks:** heading text in a generic-heading list →
WARN.

### 2.4.7 Focus Visible
Page-level — DEFER.

### 3.1.2 Language of Parts
Phrases in another language should be marked with their language. In markdown
that's typically a page-level `<span lang="es">` concern.

**What this skill checks:** crude detection of common Spanish/French phrases
in an otherwise-English article. Flags as NIT (low confidence) so the
reviewer decides.

### 3.2.4 Consistent Identification
The same component or product should be referred to by the same name
throughout. Inconsistent shifts ("Heartland Saver" → "the Saver account" →
"our savings product") create cognitive load.

**What this skill checks:** crude term-frequency comparison; flags large name
variants of capitalized noun phrases as NIT.

---

## Level AAA (best practice; not required for ADA but recommended for financial / member-facing content)

### 3.1.5 Reading Level
Content should be readable at the lower-secondary education level (grade 7–9).
Financial content carries unavoidable terms-of-art (APR, APY, escrow), so the
skill flags but doesn't BLOCK.

**What this skill checks:**
- Computes Flesch-Kincaid Grade Level, SMOG Index, and Gunning Fog.
- If any metric exceeds the target grade level (default 9) → WARN.
- Identifies the three hardest sentences (highest sentence-level FK grade) and
  surfaces them in the report so the writer has a place to start simplifying.

### 2.4.10 Section Headings
Long content sections should be broken up with headings. The skill flags any
content section (run of body content under one heading) > 300 words without an
intermediate heading as NIT.

---

## Severity model used in the report

- **BLOCK** — clear Level A or Level AA failure that's content-level (e.g.,
  image with no alt text, "click here" link). Must be fixed before publication.
- **WARN** — Level AA borderline or AAA financial-content reading-level
  miss. Reviewer judgment required.
- **NIT** — best-practice nit, including AAA language-of-parts, consistent
  identification, and section-heading density.
- **DEFER** — page-level concern this skill can't verify; flag for downstream
  rendered-page audit (axe DevTools, Lighthouse, or WAVE).

The report always emits the DEFER section, even on a clean article, so the
reviewer remembers the rendered-page audit step.
