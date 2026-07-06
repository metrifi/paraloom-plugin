# Article Hygiene Rules

This file is the rule reference for the `article-hygiene-check` skill. The script `scripts/hygiene_check.py` enforces these rules. The rules below describe both the **what** (the pattern to detect) and the **why** (the reason credit-union content programs want this).

The rule IDs (M1–M6, H1–H4) appear in every report so a reviewer can trace any flag back to its source rule.

## Markdown-mode rules (run on the source)

### M1. Em / en dash usage — BLOCK

**What:** any of these characters in body text → BLOCK.

| Character | Codepoint | Name |
|-----------|-----------|------|
| `—` | U+2014 | Em dash |
| `–` | U+2013 | En dash |
| `‒` | U+2012 | Figure dash |
| `―` | U+2015 | Horizontal bar |
| `﹘` | U+FE58 | Small em dash |
| `－` | U+FF0D | Fullwidth hyphen-minus |

**Why:** em and en dashes are an LLM tell. Articles that include them read as machine-generated to many readers and to several search and AI-mode ranking signals. Credit unions especially care about reading "human-written" because trust is the product. Hyphen-minus (`-`, U+002D) is allowed but governed by M2.

**Replacement suggestions** — the script proposes 2–3 candidates per instance. The human picks because the choice changes meaning. The candidate set must avoid introducing new hyphens (rule M2):

| Original pattern | Context | Suggestions |
|------------------|---------|-------------|
| `... — ...` | mid-sentence pause | `...; ...` (semicolon) · `..., ...` (comma) · split into two sentences |
| `... — ...` | parenthetical aside | `... (...) ...` · drop the aside if minor |
| `... — ...` | introducing a list/clause | `...: ...` (colon) |
| `5–10` | numeric range | `5 to 10` |
| `Mon–Fri` | day range | `Monday through Friday` |
| `pp. 12–18` | page range | `pp. 12 to 18` (or hyphen-minus if house style permits) |

**Skip:** dashes inside fenced code blocks and inline code (`` ` ``) are ignored — they may be part of CLI flags or example text.

**Demote to WARN:** dashes inside blockquotes (lines starting with `>`) are flagged WARN with a "quoted text — verify replacement is faithful to source" note rather than BLOCK. Quoted material may be a direct quotation that the author cannot rewrite.

### M2. Hyphen overuse — WARN

A hyphen-minus (`-`) is fine in moderation. Overuse looks lazy and is itself an LLM tell. The thresholds:

- **Per-sentence:** any sentence with **≥3 hyphens** → WARN.
- **Per-paragraph density:** any paragraph where hyphens exceed **2% of word count**, with a guard that the paragraph also has **≥3 hyphens** in body text — URLs are stripped before counting because hyphens inside URLs are not body-text typography → WARN.
- **Compound creep:** any single token with **≥2 internal hyphens** (e.g., `first-time-homebuyer-loan`) → WARN with a suggestion to break the compound.

For each WARN, the script proposes a rewrite when one is straightforward (e.g., `first-time-homebuyer loan` keeps a single hyphen and reads cleaner).

**Allow-listed compounds** (loaded from `compound-allow.txt`) are not counted toward the per-token compound creep test. Examples: `first-time`, `long-term`, `short-term`, `co-op`, `not-for-profit`, `e-mail`, plus any campaign-specific phrasing the credit union has approved.

### M3. Spelling — BLOCK or WARN

**Library:** `pyspellchecker`.

**Skip:** fenced code blocks, inline code, URLs, image source paths, and tokens that match the merged dictionary (`dictionary.txt` plus any `--dictionary` path).

**Severity:**

- **High-confidence misspellings** (single edit-distance from a common word, and `pyspellchecker.correction()` returns a suggestion that is not the input itself) → **BLOCK** with the suggested correction.
- **Low-confidence misspellings** (no nearby dictionary match — possibly a proper noun) → **WARN** with `"verify spelling — possibly a proper noun not in dictionary"`.

**Markdown-aware tokenization:** strip markdown formatting before spell-checking. Don't try to spell-check `**bold**` as one word. The script does this by extracting the text from each `inline` AST node and tokenizing on whitespace + punctuation.

**Adding to the dictionary:** `--add-to-dictionary <word>` appends a word to `dictionary.txt` and exits. Use this when a proper noun keeps showing up in the campaign.

### M4. Markdown formatting integrity — BLOCK or WARN

Walk the AST and look for:

- **Unclosed fenced code block** (` ``` ` opened but not closed) → **BLOCK**.
- **Mismatched emphasis** (`**word`, `*word`, `_word` without closing pair) → **BLOCK**.
- **Broken table** — body rows whose pipe-column count differs from the header → **BLOCK**.
- **Heading without space after `#`** (e.g., `##Heading`) → **BLOCK**.
- **Skipped heading levels** (H1 → H3 with no H2) → **WARN** (also flagged by ADA skill, but useful to catch early).
- **Multiple H1 headings** → **WARN** (a document should have a single H1).
- **Broken link syntax** (`[text](url` missing close paren) → **BLOCK**.
- **Reference link with undefined reference** (`[text][ref]` where `[ref]: url` is missing) → **BLOCK**.

### M5. Quote and apostrophe consistency — WARN

The recommended source style is **straight quotes** in markdown; the rendering pipeline applies smart-quote conversion at render time.

- Mixed curly (`"`, `"`, `'`, `'` — U+201C, U+201D, U+2018, U+2019) and straight (`"`, `'` — U+0022, U+0027) within the same document → **WARN** with note `"consistent style is straight quotes in source; rendering applies curly"`.
- Curly apostrophes inside contractions (`don't`) are tolerated — most authors paste from formatted sources — but flagged WARN if mixed with straight ones.

The script flags **at most one** WARN per document for quote consistency, with a count of each style, so the reviewer sees the issue without being drowned in per-character flags.

### M6. Whitespace and structural NITs

- **Trailing whitespace** on lines → **NIT**.
- **Mixed line endings** (CRLF + LF in same file) → **NIT**.
- **3+ consecutive blank lines** → **NIT**.
- **Mixed bullet styles** (`-` and `*` for unordered list items in same document) → **NIT**.
- **Tabs vs spaces in lists** (inconsistent indentation) → **NIT**.

NITs are reported but never block publication. Reviewers may fix them, ignore them, or batch-fix them with a formatter.

## HTML-mode rules (run on the rendered output)

### H1. External link attributes — BLOCK or WARN

**External link** = an `<a href>` whose host resolves to a domain other than `--credit-union-domain`. Anchor links (`#section`), `mailto:`, and `tel:` are not external; they need no rel/target.

- Every external `<a>` must have **both** `rel="nofollow"` AND `target="_blank"`. Missing either → **BLOCK**.
- Internal links (same domain or relative path) must NOT have `target="_blank"` — opens internal pages in new tabs unnecessarily and breaks the back button → **WARN** if present.

The renderer adds `rel="nofollow" target="_blank"` to external links automatically during the markdown → HTML pass. So a BLOCK on H1 typically means the author embedded raw HTML `<a>` tags directly in the markdown that bypassed the renderer.

### H2. Table attributes — BLOCK

- Every `<table>` must have `class="table"`. Missing → **BLOCK**.
- `role="presentation"` is **not** required and should not be added — tables retain their semantic role for screen reader users.

The renderer adds `class="table"` automatically. A BLOCK on H2 typically means the author wrote a raw `<table>` in the markdown.

### H3. Image alt attributes — BLOCK

- Every `<img>` must have an `alt` attribute. Missing → **BLOCK**.
- `alt=""` (empty) is permitted for decorative images and not flagged.
- The skill cannot judge whether the alt text is *good* — that's the ADA skill. M3 only checks presence.

### H4. Renderer transform report — informational

After rendering, the script appends a list of transforms applied to the report:

- N external links rewritten with `rel="nofollow" target="_blank"`.
- N tables given `class="table"`.
- N internal links left untouched.
- N images with alt preserved.

This makes the rendering pipeline auditable and gives the reviewer a sanity check that the article's link, table, and image counts match what they expect.

## Severity quick reference

- **BLOCK** — fix before publish. Em/en dashes, broken markdown, missing HTML attributes, high-confidence misspellings.
- **WARN** — judgment call. Hyphen overuse, ambiguous spelling, mixed quotes, internal link with `target="_blank"`, blockquoted dashes.
- **NIT** — best-practice. Trailing whitespace, mixed bullet styles, blank-line runs.

The skill is assistive. The human reviewer signs off on every report.
