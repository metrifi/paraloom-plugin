---
name: article-hygiene-check
description: Pre-publish hygiene check on a draft article — typography (em/en dashes, hyphen overuse, quote consistency), markdown formatting integrity, spelling, link and image and table attribute rules — plus rendering the markdown to HTML with the configured transforms applied (external links carry `rel="nofollow"` and `target="_blank"`, tables carry `class="table"`, image `alt` attributes preserved). Use as the first step of the review battery before NCUA compliance, accessibility, and fact checks. Triggers — "hygiene check", "pre-publish check", "render to html", "check formatting", "fix dashes", "spell check this article", "ready to render". Strongly prefer this skill any time a markdown article is about to be reviewed or rendered for publication, even if the user only says "check my article" or "get this ready to ship".
---

# Article Hygiene Check

This skill is the first stop in the pre-publish review battery. It catches the mechanical issues — typography, markdown formatting, spelling, and rendered-HTML attribute correctness — so the heavier downstream skills (NCUA compliance, ADA accessibility, fact verification) get a clean, attribute-correct article to work on.

The skill always runs in two coordinated passes: the **markdown pass** scans the source, and the **HTML pass** renders the markdown with the configured transforms (external links → `rel="nofollow" target="_blank"`, tables → `class="table"`, image `alt` preserved) and checks the rendered output. Both passes feed into one combined report, and the rendered HTML is written next to the article so phase 9 of the experiment workflow has a finished file to ship.

## When this skill runs

The user has handed you a draft markdown article and wants it pre-publish-clean. Triggers include any phrasing about hygiene, pre-publish, rendering to HTML, fixing dashes, spell-checking, or "is this ready to ship/review/render?". Run this skill first; downstream skills assume the article has already been hygiene-checked.

## Inputs you need

- `article_path` (required) — path to the markdown file. If the user pasted the article inline, save it to a `.md` file in their workspace first so the report has somewhere natural to land.
- `credit_union_domain` (required for HTML mode) — the credit union's own domain (e.g., `heartlandcu.org`). Used to distinguish internal from external links. If the user has not provided one, ask once. (Markdown-only mode does not need it.)
- `mode` (optional, default `both`) — one of `markdown`, `html`, or `both`. Default is `both`.
- `dictionary_path` (optional) — extra dictionary file. Defaults to the `dictionary.txt` shipped inside this skill folder. Custom dictionaries are merged with the bundled one, not replaced.
- `compound_allow_path` (optional) — defaults to the `compound-allow.txt` shipped inside this skill folder.
- `output_html_path` (optional) — where to write the rendered HTML. Defaults to `<article-name>.html` next to the source.
- `severity_overrides` (optional) — JSON file or inline mapping that lets a campaign override a default severity (e.g., demote em dash from BLOCK to WARN). Use sparingly; the defaults exist for good reasons.

## Workflow

Read this whole section before starting. The order matters because later passes depend on the earlier ones cleaning up first.

### 1. Read the rules

Read `RULES.md` once before reviewing. It contains the full M1–M6 markdown rules and H1–H4 HTML rules with severity defaults, replacement-suggestion patterns, and the rationale for each rule. Don't review from memory — the replacement suggestions for em dashes and the hyphen-overuse thresholds in particular have to come from the rule reference, not be invented per-article.

### 2. Run `scripts/hygiene_check.py`

This is the deterministic pass. Invoke it like:

```
python3 scripts/hygiene_check.py \
  --article <path-to-article.md> \
  --credit-union-domain <domain> \
  --mode both \
  [--dictionary <path>] [--compound-allow <path>] \
  [--output-html <path>] [--severity-overrides <path>]
```

The script:

1. Reads the article and parses it with `markdown-it-py`.
2. Walks the AST to apply M1 (em/en dash detection, with 2–3 replacement suggestions per instance), M2 (hyphen overuse), M3 (spelling via `pyspellchecker` with the bundled dictionary plus any custom one), M4 (markdown formatting integrity), M5 (quote consistency), and M6 (whitespace NITs). Code blocks and inline code are skipped for typography and spelling rules.
3. Renders the markdown to HTML with the configured transforms applied (external links rewritten with `rel="nofollow" target="_blank"`, tables given `class="table"`, image `alt` preserved).
4. Walks the rendered HTML to apply H1–H4 (external link attributes, internal link target rule, table class, image alt).
5. Writes the rendered HTML to `<article-name>.html` (or the `--output-html` path) and the report to `<article-name>.hygiene-check.md`.

The script is the source of truth for the report shape. Don't hand-write the report.

### 3. Verify the renderer-transforms-applied summary

Every report ends with a "Renderer transforms applied" section showing how many external links were rewritten, how many tables got `class="table"`, how many internal links were left untouched, and how many images had alt preserved. This makes the rendering pipeline auditable. Confirm it's present and matches the article's actual link/table/image counts before handing the report off.

### 4. Hand the report and rendered HTML to the user

Tell the user:

- Where the report landed (`<article-name>.hygiene-check.md`).
- Where the rendered HTML landed (`<article-name>.html`).
- The BLOCK / WARN / NIT counts from the summary.
- If there are BLOCK items, recommend fixing them before advancing to NCUA compliance review.

If the user asks, walk them through the BLOCK items individually and propose fixes, but **don't auto-apply em/en dash replacements** — replacement choice changes meaning and the human has to pick.

## Severity model

- **BLOCK** — must be fixed before publish. Em/en dashes, broken markdown, missing required HTML attributes, high-confidence misspellings.
- **WARN** — gray area requiring a judgment call. Hyphen overuse, ambiguous spelling, mixed quote styles, internal link with `target="_blank"`.
- **NIT** — best-practice item. Trailing whitespace, mixed bullet styles, multiple blank lines.

The defaults in `RULES.md` reflect what most credit-union content programs want. The `--severity-overrides` flag lets a campaign override a default for a stylistic reason; document the reason in the campaign record when you do.

## What this skill does NOT do

- Doesn't assess content quality, voice, or tone. That's editorial judgment.
- Doesn't verify factual accuracy. That's the `fact-verification` skill.
- Doesn't assess WCAG criteria beyond the presence of attributes. That's the `ada-accessibility-review` skill.
- Doesn't auto-apply em/en dash replacements. The replacement choice changes meaning.
- Doesn't grammar-check (subject-verb agreement, comma usage). Out of scope.

## Bundled resources

- `RULES.md` — full rule reference (M1–M6 markdown, H1–H4 HTML).
- `dictionary.txt` — credit-union-friendly seed terms (Heartland, NCUA, APY, HELOC, etc.). Merged with any `--dictionary` path.
- `compound-allow.txt` — compounds exempt from the hyphen-overuse rule (`first-time`, `long-term`, etc.).
- `scripts/hygiene_check.py` — the deterministic checker and renderer.
- `assets/report-template.md` — the report shape; the script fills it in.
- `tests/` — 15 fixture cases covering each rule. Useful when iterating on the skill itself.

## Output format

A single markdown file named `<article-name>.hygiene-check.md` next to the source, plus `<article-name>.html` (the rendered output). The report includes a summary, an "Issues" section grouped by severity with location and suggested fixes, a "Renderer transforms applied" section, and a reviewer sign-off block. `assets/report-template.md` shows the exact shape; the script populates it.
