---
name: ncua-compliance-review
description: Review credit-union marketing content (articles, landing pages, blog posts, emails) against NCUA Part 740 advertising rules, Truth in Savings (Part 707), Regulation Z lending advertising, Regulation E electronic transfers, and Regulation B / fair lending. Produces a redline-style review report with severity flags (BLOCK/WARN/MISSING/NIT) and suggested rewrites. Use proactively whenever the user asks for a compliance review, an "NCUA check", "is this article compliant?", "review this for NCUA", "credit union compliance", "TISA review", "Reg Z check", or asks Claude to vet credit-union marketing copy of any kind. Trigger this skill even if the user only says "review this article" but the article is from a credit union or contains credit-union products. The skill is assistive only — every report it produces ends with a mandatory human compliance officer sign-off section.
---

# NCUA Compliance Review

This skill reviews credit-union marketing content against the federal regulatory framework that governs credit-union advertising. It catches obvious violations and flags gray areas. **It is assistive, not authoritative** — every report explicitly hands off to a human compliance officer for sign-off.

## When this skill runs

The user has handed you (a) an article and (b) a credit union name and charter type. Your job is to walk through the article, identify every passage that touches a regulated topic, run the relevant rule against it, and emit a redline-style review report.

## Inputs you need

Before you start, make sure you have:

- **`article_path`** (required) — path to a markdown file, HTML, or plain text article. If the user pasted the article inline rather than naming a path, save it to a file in their workspace folder first so the report has somewhere natural to land.
- **`credit_union_name`** (required) — used in suggested rewrites of the federal insurance statement and in the report header.
- **`charter_type`** (optional, default `federal`) — `federal` or `state`. State-chartered credit unions still follow Part 740 if they are federally insured. Note the charter type in the report header.
- **`field_of_membership`** (optional) — a one-paragraph description of who is eligible to join. If provided, use it to assess membership-eligibility claims. If not provided, treat broad eligibility claims ("anyone can join", "open to all in [state]") as WARN by default and ask the compliance officer to verify.

If any required input is missing, ask once for the missing pieces before starting the review. Don't guess credit_union_name from the article body — names get mangled.

## Workflow

Follow this sequence. Each step builds on the previous one.

### 1. Read the rule reference

Read `RULES.md` in this skill folder before reviewing. It contains the regulation excerpts, common violation patterns, and the suggested-rewrite phrasings you'll use. Don't try to compliance-review from memory — Part 740, Part 707, Reg Z, Reg E, and Reg B all have specific phrasings the report needs to cite correctly.

### 2. Read the article

Read the full article into context. As you read, mentally tag each passage by content category:

- **Insurance / safety language** — anything that talks about deposits being safe, insured, guaranteed, protected, FDIC/NCUA, etc.
- **Deposit-account terms** — savings, checking, share certificates, money market, CDs. APY, dividend rate, balance requirements, fees, "free", "bonus".
- **Lending terms** — mortgages, auto loans, personal loans, credit cards, HELOCs. Rates, payments, "as low as", refinance offers.
- **Electronic transfer / debit / ATM language** — Reg E territory.
- **Membership eligibility** — who can join, geographic scope, "anyone can join", "open to all".
- **Investment / non-deposit products** — annuities, mutual funds, brokered products, insurance products. These have their own disclosure regime.
- **Comparative / superlative claims** — "best", "lowest", "highest", "#1", "guaranteed savings".

A given passage can be in multiple categories. Note each one — you may need to apply multiple rules to a single sentence.

### 3. Run the deterministic scanner first

Run `scripts/scan_article.py` against the article. It catches the patterns that are easy to miss in a careful read — bare APY mentions, the word "free" co-occurring with fee language, FDIC instead of NCUA, rate-trigger terms in lending copy, missing federal insurance statement. Use it as a checklist, not as the final answer:

```bash
python3 <skill_path>/scripts/scan_article.py <article_path>
```

The script writes a JSON object listing matches by category, plus heuristic flags like `mentions_savings_products` and `has_federal_insurance_statement`. Read that JSON, then walk the article yourself — the scanner is intentionally narrow and will miss anything that isn't keyword-shaped (e.g., a mortgage payment claim phrased without a dollar sign, or "guaranteed" used in a non-deposit context).

### 4. Apply rules and assign severity

For each flagged passage, decide which rule applies and which severity bucket it falls into:

- **BLOCK** — clear violation as written. Cannot publish without rewrite. Examples: "free checking" when there's any fee, deposit terms with no APY, "FDIC insured", trigger term with no APR.
- **WARN** — gray area, judgment call. The compliance officer needs to decide. Always include a specific question for them. Examples: broad geographic eligibility claim, "as low as" rate without explicit credit-qualification language, comparative claims you can't verify.
- **MISSING** — something required is absent from the article entirely. Most common: federal insurance statement absent on an article that promotes insured deposits.
- **NIT** — best-practice suggestion. Optional. Use sparingly — too many NITs drown out the real issues.

Cite the specific regulation (e.g., "12 CFR §740.4", "12 CFR §707.8(c)", "12 CFR §1026.24(d)") for each issue. Imprecise citations make the report less useful to the compliance officer.

### 5. Write the report

Write the report to `<article_path_without_extension>.compliance-review.md` — same directory as the article, same base filename, with `.compliance-review.md` appended. So `cd-promo.md` becomes `cd-promo.compliance-review.md`. This convention lets reviewers find the review next to the draft.

Use the exact template in `assets/report-template.md`. Don't deviate from the section order or headings — downstream tooling and human readers expect this shape.

The summary recommendation is one of:

- **"Do not publish without addressing BLOCK items."** — any BLOCK present.
- **"Address MISSING items, then advance to compliance officer review."** — no BLOCK but at least one MISSING.
- **"Safe to advance to compliance officer review."** — no BLOCK or MISSING; only WARN and/or NIT.
- **"No major issues found. Compliance officer should still sign off before publish."** — completely clean.

### 6. Always include the sign-off section

Every report ends with the compliance-officer sign-off checklist. **Never skip it.** Even on a clean article, the human signs off. The skill's value is taking first-pass burden off the human, not replacing them. The report's leading callout (`> ⚠️ This is an automated assistive review...`) and the trailing checklist together communicate this clearly — keep both, every time.

## Severity assignment cheatsheet

When you're unsure between BLOCK and WARN, ask: "would the credit union's compliance officer reject this on sight, or would they need to think about it?"

- Rejected on sight → BLOCK. Examples: missing required disclosure, FDIC instead of NCUA, "100% guaranteed" on deposits, "free" with stated fee.
- Need to think → WARN. Examples: "best rates in town" (might be defensible with substantiation), narrow geographic membership claim, "second-chance" credit phrasing.

When you're unsure between WARN and NIT, ask: "is this actually a compliance question, or just a writing improvement?"

- Compliance question → WARN.
- Writing improvement → NIT (or omit entirely; not every nit is worth filing).

## Suggested rewrites

For BLOCK and MISSING items, always include a suggested rewrite or specific instruction. Examples of well-formed suggested rewrites:

- For a missing insurance statement: `Add the following statement at the end of the article in a clear and conspicuous location: "Federally insured by NCUA."`
- For a "free checking" violation when there's a $5 fee: `Replace "free checking" with "checking with no minimum balance" (or whichever feature is actually free).`
- For an APY without disclosures: `Add to the same paragraph: "APY accurate as of [date]. Minimum balance to obtain APY: $[X]. [If time account: minimum term, early withdrawal penalty.]"`
- For a trigger-term violation: `If the $299/month payment is referenced, add to the same paragraph: "[Down payment %], [number of payments], APR [X.XX%]. Rate subject to credit qualification."`

If the rewrite needs information the article doesn't supply (the actual minimum balance, the actual APR), say so explicitly: `Compliance officer to supply: minimum balance to obtain APY, time requirement.` Don't fabricate numbers.

## What this skill does not do

- **Does not verify factual accuracy.** It can't check whether "13 branches" is true. That's the `fact-verification` skill's job.
- **Does not assess accessibility.** Heading structure, alt text, reading level — that's `ada-accessibility-review`.
- **Does not replace the compliance officer.** Always include the sign-off section; always recommend human review.
- **Does not rewrite the whole article.** Suggested rewrites are passage-level only. The author owns the prose.

## Example invocation

```
User: Run the NCUA compliance review on this CD promo article.
Path: /Users/.../Heartland CU/articles/cd-promo-may.md
Credit union: Heartland Credit Union (federal charter)
Field of membership: anyone who lives, works, worships, or attends school in Dane County, Wisconsin.
```

You would:
1. Read RULES.md, then the article.
2. Run the scanner script.
3. Note: deposit product → Part 740 + Part 707 active; check for insurance statement, APY/disclosure pairing, "free" misuse, "guaranteed" misuse. Membership claims → check against Dane County FOM.
4. Walk the article passage-by-passage.
5. Write `cd-promo-may.compliance-review.md` next to the article.
6. Tell the user where the report is and summarize counts (e.g., "1 BLOCK, 2 WARN, 1 MISSING — see report").
