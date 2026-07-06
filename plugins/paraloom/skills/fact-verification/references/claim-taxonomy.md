# Claim taxonomy — the 9 types

Use this reference when classifying each extracted claim. Each type has its own verification target, evidence bar, and "what makes me default to NHV" criteria.

If a claim plausibly fits two types, pick the one with the *stricter* evidence bar (e.g., a "rates page lists 4.50% APY on a 12-month CD" is both type 5 — Rates — and type 3 — Products. Treat as type 5 because the rate is the time-sensitive part).

---

## Type 1 — Specific counts and numbers about the credit union

**What it looks like.** "12 branches," "$1.2B in assets," "serving over 80,000 members," "founded in 1953," "more than 200 employees."

**Where to verify.**

1. The CU's About / About Us / Our Story / Press / Newsroom pages.
2. For asset and member counts, the most authoritative source is the CU's NCUA Form 5300 Call Report, accessible via `mapping.ncua.gov` or `ncua.gov`'s research pages. Call reports are quarterly snapshots, so a recent value may lag the article's claim by up to a quarter — note the recency.

**Evidence bar.** Direct text match or close numeric equivalent ("over 80,000" matches a source that says "more than 81,000"). Slight rounding is OK if the article uses a hedge word ("more than," "approximately") and the source supports the hedge.

**Defaults to NHV when.** The source page is undated and the claim is about a "current" count. The source uses a different unit (article: "members," source: "accounts"). The article cites a specific source that the verifier cannot reach.

---

## Type 2 — Branch locations and hours

**What it looks like.** "Branches in Madison, Sun Prairie, and Janesville," "lobby hours 9–5 Monday through Friday," "drive-thru open Saturdays."

**Where to verify.** The CU's Locations / Branches / Find a Branch page. For hours, drill into the specific branch detail page if the index shows a list.

**Evidence bar.** For city lists: every named city must appear on the locations page; any city named in the article that does not appear is `CONTRADICTED`. For counts: must match exactly. For hours: the live page's stated hours must match the article verbatim or to-the-minute equivalents (5:00 PM ≈ 5 PM is fine; 5:30 PM ≠ 5 PM is a contradiction).

**Defaults to NHV when.** The locations page is interactive (map-only) and the simple text tools cannot extract the list — flag for human review with an explanation. Hours are seasonal and the article implies year-round.

---

## Type 3 — Products and services offered

**What it looks like.** "Heartland CU offers VA loans," "we have a high-yield money market," "online bill pay is included with checking," "investment advisory services available."

**Where to verify.** Product pages — Loans, Mortgages, Savings, Checking, Business, Investment Services, etc. Use the CU's own primary navigation; don't crawl indiscriminately.

**Evidence bar.** Strict. The product must be named (or unambiguously described) on the CU's own website on a page that's a reasonable home for it. "VA loans" should appear on a mortgages or loans page. If the CU has multiple loan pages and the product isn't on any of them, the absence is itself evidence.

**Special rule.** This is the highest-stakes type — past articles have hallucinated products. If the product isn't listed anywhere on the CU's site after a reasonable search (homepage, product index, sitemap, top-nav products), the status is `CONTRADICTED` (not NHV). Use the source quote field to record what you searched and what you found ("Searched /loans, /mortgages, /personal — no mention of VA loans").

**Defaults to NHV when.** The article's product name is generic enough that it could match multiple offerings ambiguously (e.g., article says "a high-yield savings account" and the CU offers a "premier savings" — describe the ambiguity and let the human decide).

---

## Type 4 — Membership eligibility

**What it looks like.** "Anyone in Wisconsin can join," "membership open to residents of Dane and Sauk counties," "must be a current or former employee of XYZ Corp."

**Where to verify.** Membership / Become a Member / Eligibility / Join page. Capture the field-of-membership statement verbatim.

**Evidence bar.** The source's eligibility statement must support the article's claim word-for-word in scope. "Anyone in Wisconsin" is a *broader* claim than "anyone in Dane or Sauk County." Article-broader-than-source is `CONTRADICTED`. Article narrower than source is `VERIFIED` with a note that the article could legally be more inclusive.

**Special rule.** Membership claims are regulatorily sensitive. False generosity (saying it's easier to join than it actually is) is a fair-lending and advertising-rules issue (12 CFR Part 740 and adjacent). Always quote the exact field-of-membership statement in the source quote field. When the eligibility text uses unusual qualifiers ("worship in"), include them in the quote.

**Defaults to NHV when.** The source describes a multi-prong eligibility (live/work/worship/attend school + employer groups + family members + association membership) and the article summarizes only one prong without disclaiming the others.

---

## Type 5 — Rates and APYs

**What it looks like.** "Earn 4.50% APY on our 12-month CD," "auto loans starting at 5.99% APR," "money market rates as high as 4.25% APY."

**Where to verify.** The CU's Rates page or product-specific pricing pages.

**Evidence bar.** Exact match on the rate, the term, and the product. "4.50% APY on a 12-month CD" must match a source row that says exactly "12-month" and "4.50%" — a "13-month" or "4.40%" is a contradiction.

**Special rule.** Rates change frequently. Even an exact match is `VERIFIED_AS_OF <ISO timestamp>` with the note "Rates change frequently — re-verify at publish time." This applies to *every* rate claim, even verified ones.

**Defaults to NHV when.** The rate is given as a range ("starting at") and the source doesn't explicitly use the same hedge. The rate is conditional ("with $10,000 minimum") and the article doesn't state the condition.

---

## Type 6 — Leadership and named people

**What it looks like.** "CEO Jane Smith," "Chief Lending Officer Bob Jones," "VP of Marketing Susan Lee said..."

**Where to verify.** The Leadership / About the Team / Our Team / Executive Team page.

**Evidence bar.** Name spelling and title must match exactly. Slight title variance ("Chief Lending Officer" vs. "CLO") is OK with a note.

**Special rule.** Direct quotations attributed to a named person are *always* `NEEDS_HUMAN_VERIFICATION`. The quote may have been written by a marketing team and not vetted by the named person — the only authority on whether the quote is accurate is the named person themselves. Even if a press release contains the same quote, NHV remains the verdict (press releases can be ghostwritten and pre-approved by the named person, but the verifier can't know that without contacting them).

**Defaults to NHV when.** The leadership page has been updated recently and the title might be in flux; or the page lists only some leadership and the named person isn't on it.

---

## Type 7 — External statistics and claims

**What it looks like.** "Credit unions returned $X to members nationally last year," "Wisconsin has Y credit unions," "the average 30-year mortgage rate in Wisconsin is...", "the median home price in Madison is..."

**Where to verify.** Identify the authoritative source by topic:

- Credit-union industry stats: NCUA (`ncua.gov`, especially `ncua.gov/analysis`).
- Mortgage rates: FRED (`fred.stlouisfed.org`, MORTGAGE30US or MORTGAGE15US).
- Bank rates and FDIC data: `fdic.gov`.
- Labor / employment / CPI: BLS (`bls.gov`).
- State-level credit-union stats: Wisconsin Department of Financial Institutions (`dfi.wi.gov`) for WI specifically.
- Home prices: Zillow Research, Redfin Data Center, or local Realtor association — but be cautious; these are not all equally authoritative. Match the article's cited source if it cited one.

**Evidence bar.** If the article cites a specific source, navigate to that source and confirm the cited number. Capture the URL and the value as published. If the article gives a number without a citation, find an authoritative source and check; if the source value is within ~1% of the article's value, `VERIFIED` with a note about the source. Larger discrepancies are `CONTRADICTED`.

**Defaults to NHV when.** No authoritative source for the topic. The article cites a source that requires login or paywall (note the access barrier). The number is described as "according to recent reports" with no specific source.

---

## Type 8 — Comparative and superlative claims

**What it looks like.** "The largest credit union in Dane County," "the best CD rates in southern Wisconsin," "more members than any other community bank in the area," "Wisconsin's leading credit union."

**Where to verify.** Almost always unverifiable from a single source.

**Evidence bar.** To verify a "largest in X" claim would require comparing the relevant metric across every entity in the comparison set. This is generally outside the skill's scope.

**Special rule.** Default to `NEEDS_HUMAN_VERIFICATION` and include in the reason what evidence would be needed. Examples:

- "To verify 'largest in Dane County' would require comparing total assets across all credit unions chartered in or serving Dane County via NCUA call reports, ranked by latest reported quarter."
- "To verify 'best CD rates in southern Wisconsin' would require comparing CD rates across all financial institutions in the region as of the publish date — generally not defensible."

Recommend softening the claim ("among the most competitive," "one of the largest") or providing supporting comparison data.

**Defaults to NHV when.** Always.

---

## Type 9 — Regulatory and legal claims

**What it looks like.** "Federally insured up to $250,000 per account," "as required by the Fair Credit Reporting Act," "in accordance with NCUA guidelines."

**Where to verify.** The regulator's website:

- NCUSIF coverage: `ncua.gov/share-insurance`.
- Truth in Savings (Reg DD / NCUA Part 707): `ncua.gov`.
- Fair Credit Reporting Act: `consumer.ftc.gov` or `cfpb.gov`.
- Reg E (electronic transfers): `cfpb.gov`.
- General consumer-finance law: `cfpb.gov`.

**Evidence bar.** Match against the regulator's published statement. The $250,000 NCUSIF coverage limit is a known constant; confirm it from `ncua.gov/share-insurance` and capture the quote.

**Defaults to NHV when.** The article states a regulatory consequence ("you have 60 days to dispute under federal law") that the verifier doesn't have authoritative footing to confirm — flag for compliance review rather than fact-checking.

---

## Quick decision tree

When stuck classifying a claim, use this:

1. Is it a direct quotation from a named person? → Type 6, status NHV always.
2. Is it a comparative or superlative ("most," "largest," "best")? → Type 8, status NHV.
3. Is there a number tied to a product on the CU's site (rate, APY, APR)? → Type 5.
4. Is the claim about who the CU is (size, age, locations, leadership, eligibility)? → Type 1, 2, 4, or 6.
5. Is the claim about what the CU does (offers product X, includes feature Y)? → Type 3 — strict.
6. Is the claim a number or fact about the world outside the CU? → Type 7.
7. Is the claim about a law, regulator, or insurance? → Type 9.
