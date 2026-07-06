---
name: fact-verification
description: |
  Identify verifiable factual claims in a marketing article (specific numbers, named products and services, branch and member counts, membership eligibility, hours, addresses, leadership, external statistics) and verify each by browsing the credit union's live website and authoritative external sources. Mark anything that cannot be verified as needs-human-verification. Use whenever a draft article, blog post, web page, or marketing copy is being reviewed before publication. Triggers include "fact check", "fact-check", "verify facts", "verify claims", "verify the article", "is this article accurate", "check the article for accuracy", "audit this for accuracy", "make sure the numbers are right", and "confirm the details in this draft".
---

# Fact-Verification Skill

## Why this skill exists

Past Paraloom articles have shipped with errors like "13 branches instead of 12," products the credit union does not actually offer, and overgenerous membership eligibility statements. These errors damage trust with credit-union customers and create real regulatory risk under fair-lending and advertising rules. This skill exists to catch those errors before publication.

The design is **dynamic, not dossier-based**: there is no frozen facts file. Every verification reaches the live source at review time, which means the skill stays correct as the credit union's website changes.

The skill's bias is **conservative**. The default for any ambiguity is `NEEDS_HUMAN_VERIFICATION`. False positives (flagging a correct claim for human review) are mildly annoying. False negatives (greenlighting a wrong claim) are exactly what this skill is here to prevent.

## When to invoke

Invoke this skill whenever a draft article, blog post, landing page, or other marketing copy is being prepared for publication. Typical user phrases: "fact-check this draft," "verify the claims in this article," "is this accurate?", "audit this for accuracy before we publish."

Don't invoke it for fiction, internal-only documents, or pieces with no factual claims (e.g., a CEO's personal letter that contains opinions only).

## Required inputs

The user (or the surrounding workflow) must provide:

- `article_path` — absolute path to the markdown file being reviewed.
- `credit_union_name` — used to disambiguate when verifying.
- `credit_union_website` — root URL of the credit union's site (e.g., `https://heartlandcu.org`).

Optional:

- `credit_union_charter_id` — NCUA charter number, useful for verifying via `mapping.ncua.gov`.

If any required input is missing, ask the user once before proceeding. Do not guess the website.

## Tools you will use

- File tools (Read, Write, Edit) to read the article and write the report.
- The **Playwright** connector for live verification (this project's standard browser driver):
  - `mcp__playwright__browser_navigate` — load a URL. Playwright launches its own browser on the first call; there is nothing to pre-connect.
  - `mcp__playwright__browser_snapshot` — accessibility-tree snapshot of the page; the default way to "read" a page. Returns element `ref`s you can pass back as `target` to interact.
  - `mcp__playwright__browser_evaluate` — run JS for full page text when the snapshot is too terse, e.g. `() => document.body.innerText`. Also the tool for JS-heavy pages.
  - `mcp__playwright__browser_wait_for` — wait for specific text to appear (or disappear) on slow / client-rendered pages before reading.
- WebSearch is permitted only as a *fallback* when the credit union's own website does not surface the relevant page (e.g., a press release that's only on the news wire). Internal claims (products, eligibility, branches) must be verified against the CU's own domain.

Playwright launches its own browser, so there's no "is a browser connected?" gate. If `browser_navigate` repeatedly fails to load a page (network error, browser binaries missing), stop and tell the user — do not attempt to verify any claim without live source access.

## The workflow

You execute the workflow in this order. Don't skip steps.

### Step 1 — Read the article and extract claims

Read the article. Then walk through it paragraph by paragraph and pull out every factual claim — anything a reader could in principle look up and prove or disprove. Be aggressive about extraction; a claim missed is a claim shipped.

What counts as a claim:

- Specific numbers: "12 branches," "$1.2B in assets," "founded in 1953," "80,000 members."
- Named products or services: "we offer VA loans," "online bill pay is included with checking."
- Membership / eligibility statements: "open to anyone in Wisconsin."
- Rates and APYs: "4.50% APY on 12-month CD."
- Hours and addresses: "open 9–5 Monday through Friday," "branch at 123 Main St."
- Named people and titles: "CEO Jane Smith," "CFO Bob Jones."
- External statistics with or without citations.
- Comparative or superlative claims: "the largest in Dane County," "the lowest rates."
- Regulatory and legal claims: "federally insured up to $250,000."
- Direct quotations attributed to a named person.

What does *not* count as a claim and should be skipped:

- Opinions, mission statements, marketing flourishes ("We believe in service," "Our members come first").
- Unfalsifiable generalities ("a friendly team," "a great place to bank").
- Author-voice transitions ("In this article we'll cover...").

For each claim, capture: the exact verbatim text from the article, the paragraph or section it appeared in, and your initial type assignment (one of the 9 types in `references/claim-taxonomy.md`).

### Step 2 — Categorize and plan verification

Read `references/claim-taxonomy.md` for the 9 types and their per-type strategies. For each claim, decide:

- **Type** (1–9).
- **Verification target URL(s)** — usually a specific page on the CU's website. If you don't know which page, plan to browse the homepage first and follow navigation; never guess at a URL.
- **What you're looking for** — the exact data point, product name, or statement that would confirm or contradict the claim.
- **What status would force `NEEDS_HUMAN_VERIFICATION` regardless of what you find** (e.g., direct quotes, comparatives, future-dated claims).

### Step 3 — Execute verification with Playwright

For each claim that requires browsing, follow the playbook in `references/browser-playbook.md`. The contract for every browser-verified claim is:

1. Navigate to the planned URL (`browser_navigate`). If it 404s or fails to load, mark `NEEDS_HUMAN_VERIFICATION` with the load error as the reason. Do not silently skip.
2. Read the page text — `browser_snapshot` is usually enough; fall back to `browser_evaluate(() => document.body.innerText)` for full rendered text, and `browser_wait_for` first if the content is client-rendered.
3. Narrow to the relevant section by searching the captured text (or pass a CSS selector to `browser_evaluate`) if the page is long.
4. Capture the **exact source quote** — verbatim text from the page that supports or contradicts the claim. Trim only surrounding whitespace; do not paraphrase.
5. Capture the **canonical URL** at the time of capture.
6. Capture the **timestamp** (ISO format) of the visit.
7. Sleep 1–2 seconds between page loads. The CU's website is a small site; don't hammer it.

If the page renders but doesn't contain the relevant text, *don't* assume the claim is false on the basis of one page. Look for an obvious neighboring page (e.g., the article says "we offer mortgages" and `/loans` doesn't list them — check `/mortgages` or the site search). If after a reasonable look you can't find supporting text, the call depends on type:

- For **products**, treat absence as `CONTRADICTED` (per type 3 strategy — the CU's website is the authoritative source for "do they offer this product").
- For everything else, mark `NEEDS_HUMAN_VERIFICATION` with a note about what you searched.

### Step 4 — Score each claim

Assign a status for each claim:

- `VERIFIED` — the source page contains text that directly supports the article's claim. You captured the URL and exact quote.
- `CONTRADICTED` — the source page contains text that contradicts the article's claim, OR (for type-3 product claims only) the CU's website doesn't list the product anywhere it would reasonably be listed.
- `NEEDS_HUMAN_VERIFICATION` — anything else. This includes: ambiguous matches, format mismatches you can't reconcile, page load failures, direct quotes attributed to people, comparatives, claims about internal data not visible on the website, and any claim where you found yourself wanting to "give the article the benefit of the doubt."

When in doubt, `NEEDS_HUMAN_VERIFICATION`. Never guess.

### Step 5 — Re-flag time-sensitive claims

After scoring, do a sweep specifically for time-sensitive content:

- **Rates and APYs** — even a `VERIFIED` rate is `VERIFIED_AS_OF <ISO timestamp>` and the report's recommendation must include "re-verify all rate claims at publish time."
- **Hours and addresses** — note that branch hours can change with holidays and seasons; recommend re-verifying within 1 week of publish.
- **Asset and member counts** — note that NCUA call reports lag by a quarter; treat any matched asset/member count as `VERIFIED_AS_OF <ISO timestamp>` and recommend confirming with the CU if the article will run more than 3 months from now.
- **Leadership** — leadership pages can be stale; if the article uses a quote, NHV always; if it just names a person, `VERIFIED` is fine but note "names verified against the public team page; titles may have changed."

### Step 6 — Write the report

Write the report to a file next to the article: if the article is `/some/path/draft.md`, write `/some/path/draft.fact-check.md`. Use the exact template in `assets/report-template.md`. Do not deviate from the section ordering or the table headers — downstream tools and reviewers depend on the format.

Every `VERIFIED` and `CONTRADICTED` row must include:

- Claim (exact article text).
- Source URL.
- Source quote (verbatim from the source page).
- Verified-as-of timestamp.
- Notes (any caveats: format mismatches, recency lag, etc.).

Every `NEEDS_HUMAN_VERIFICATION` row must include:

- Claim.
- Type.
- Reason it can't be web-verified or what evidence would be needed.

Open the report with the summary counts and a recommendation:

- "Do not publish — N contradicted claims must be corrected" if any `CONTRADICTED` exists.
- "Safe to advance after human review of N flagged items" if only `NEEDS_HUMAN_VERIFICATION` exists.
- "No issues" if everything is `VERIFIED` (rare — there will almost always be at least one rate or quote to flag).

### Step 7 — Tell the user where the report is

Print a one-line summary to chat with the report path and the counts:

> Fact-check complete: 12 verified, 1 contradicted, 3 need human review. Report: `/some/path/draft.fact-check.md`.

Do not paraphrase the report contents in chat — the file is the deliverable. If something genuinely warrants surfacing (e.g., a contradicted claim that would change publishing timeline), say so in one short sentence after the path.

## Where to look for help

- `references/claim-taxonomy.md` — full per-type guidance, examples, and edge cases for the 9 claim types. Read this when you start categorizing claims.
- `references/browser-playbook.md` — Playwright calling pattern, recovery from load failures, JS-rendered pages. Read this before your first navigate call in a session.
- `assets/report-template.md` — the exact markdown template for the output. Copy it as a starting point.
- `tests/` — seven sample articles plus expected statuses. If you want to sanity-check the skill behavior, run a fixture and compare to the expected outcomes documented inline.

## What this skill should not do

- Don't try to verify quoted statements attributed to people — even if the same quote appears in a press release. The quote could have been mis-transcribed. Always `NEEDS_HUMAN_VERIFICATION` for direct quotes, with a recommendation to confirm with the source.
- Don't infer correctness from the article. The website is the source of truth. If the article doesn't match, mark contradiction even if the discrepancy is small ("12 vs. 13 branches" is a contradiction, not a rounding error).
- Don't try to use Google or third-party sources to verify internal claims. Internal claims (products, eligibility, branches) must be verified on the CU's own domain. Absence on the CU's site is itself evidence.
- Don't crawl deeply. Visit only the pages necessary to verify a specific claim. The CU's site is a small site and courteous limits matter.
- Don't follow off-domain links during verification of internal claims unless the CU clearly delegates that content (e.g., a partner investment-services link).
- Don't rewrite the article. The skill produces a fact-check report; the human author decides what to change.

## Success looks like

The user opens the `.fact-check.md` file and sees, for every factual claim, either: (a) a direct quote from the live source page that confirms or contradicts the claim with the URL and timestamp captured, or (b) a clear, specific reason the claim was flagged for human review. The user closes the file knowing exactly which lines they need to fix or confirm before publishing.
