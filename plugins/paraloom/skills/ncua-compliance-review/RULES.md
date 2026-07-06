# NCUA / TISA / Reg Z / Reg E / Reg B reference

This file is the rule reference the `ncua-compliance-review` skill consults during a review. It is not an exhaustive treatise — it is the concentrated set of patterns that the skill needs to cite correctly and the suggested-rewrite phrasings the report uses.

## Table of contents

- [12 CFR Part 740 — Accuracy of advertising and notice of insured status](#12-cfr-part-740--accuracy-of-advertising-and-notice-of-insured-status)
- [12 CFR Part 707 — Truth in Savings](#12-cfr-part-707--truth-in-savings)
- [Regulation Z — 12 CFR Part 1026 — Lending advertising](#regulation-z--12-cfr-part-1026--lending-advertising)
- [Regulation E — 12 CFR Part 1005 — Electronic transfers](#regulation-e--12-cfr-part-1005--electronic-transfers)
- [Regulation B (ECOA) and Fair Housing Act — fair lending](#regulation-b-ecoa-and-fair-housing-act--fair-lending)
- [Membership eligibility / field of membership](#membership-eligibility--field-of-membership)
- [Cross-cutting BLOCK patterns](#cross-cutting-block-patterns)
- [Standard rewrite snippets](#standard-rewrite-snippets)

---

## 12 CFR Part 740 — Accuracy of advertising and notice of insured status

The dominant rule set for any savings-product advertising by a federally insured credit union.

### §740.4 — Official sign / Official advertising statement

A federally insured credit union must include the official advertising statement in advertising of insured products. Three acceptable forms:

- **Long form:** "This credit union is federally insured by the National Credit Union Administration."
- **Short form:** "Federally insured by NCUA."
- **The official NCUA sign image** (a graphical equivalent).

The statement must appear in a clear and conspicuous location. In long-form articles this typically means a footer line, a sidebar, or a closing paragraph — not a buried inline mention.

**BLOCK** if: an article promotes insured deposit products (savings, checking, money market, share certificates / CDs) and none of the three forms appears anywhere.

### §740.5 — Non-deposit investment products

Any content advertising securities, mutual funds, annuities, fixed/variable annuities, brokerage services, or insurance products must clearly disclose:

- Not federally insured
- Not guaranteed by the credit union
- May lose value

The disclosure must be conspicuous and must distinguish the non-deposit product from insured deposits. If the article promotes both insured products and non-deposit products, the distinction must be drawn — readers must not be left with the impression that the non-deposit product is insured.

**BLOCK** if: article promotes annuities / mutual funds / market-linked products without these three statements.

### §740.2 — Prohibition on misleading representations

No statement may misrepresent the credit union's services, accounts, financial condition, or relationship with NCUA or the federal government.

Common BLOCK patterns:
- "100% safe", "100% guaranteed", "absolutely guaranteed" applied to deposits — even though insured up to $250,000, an unqualified "100% safe" is a misrepresentation.
- "Backed by the federal government" used loosely — NCUA insurance is the correct framing; "backed by the federal government" is not.
- Implying the credit union is a government agency.
- "FDIC insured" — credit unions are insured by NCUA, not FDIC. Always BLOCK.

### §740.3 — Use of NCUA's official sign on websites and apps

When promoting insured products online, the official sign or statement must appear visibly on the page. For long-form articles published on a credit-union site, a static footer line satisfies this if the article appears within that site chrome. The skill flags MISSING when the article's own copy contains no statement, since the reviewer cannot rely on chrome they cannot see.

---

## 12 CFR Part 707 — Truth in Savings

Activates when the article discusses deposit accounts (savings, checking, share certificates, money market, IRAs that are deposit-based).

### §707.8 — Advertising rules

If an advertisement states a rate of return:

1. The rate must be expressed as **"annual percentage yield"** or **"APY"**.
2. The dividend rate may also appear, but it must be **no more conspicuous than the APY**. Same font size, same prominence, or smaller.
3. If APY is stated, the ad must also disclose:
   - Variable-rate or fixed (and whether the APY may change)
   - Time the APY is in effect ("APY accurate as of [date]" or "APY offered through [date]")
   - Minimum balance to obtain the advertised APY
   - Minimum balance to open the account (if higher than the obtain threshold)
   - Time requirement (for time deposits)
   - Early withdrawal penalty (for time deposits)
4. If a bonus is advertised:
   - Time required to maintain the deposit to receive the bonus
   - Minimum balance to obtain the bonus
   - When the bonus is paid

### §707.2 — Definitions

"Dividend rate" and "annual percentage yield" are defined separately and are not interchangeable. APY incorporates compounding; dividend rate does not. Using the two terms loosely is a violation.

### Restriction on the word "free"

An account may be advertised as "free" or "no-cost" only if there is **no maintenance or activity fee, no minimum balance fee, and no fee for the lowest tier of service**. If there is *any* recurring fee — even a small one disclosed elsewhere in the article — calling the account "free" is a violation.

Subtle pattern: "free checking" + "$5 monthly fee waived with direct deposit" is still a BLOCK. The fee exists; the account is conditionally free, not free.

Acceptable substitutes: "no minimum balance", "no monthly fee with direct deposit" (stated as the conditional that it is), "fee-free ATM access" (if true), "no overdraft fees" (if true).

### Common BLOCK patterns

- "Earn a great rate on your savings!" with a rate stated but no APY label.
- "Free checking" when any fee exists.
- "Bonus $200 when you open!" with no minimum balance, time requirement, or maintenance condition disclosed.
- Dividend rate displayed in larger font than APY.
- Stale "APY accurate as of" date or no date at all.

---

## Regulation Z — 12 CFR Part 1026 — Lending advertising

Activates when the article discusses any loan product: mortgages, auto loans, personal loans, credit cards, HELOCs, student loans, RV / boat loans.

### Trigger terms (§1026.24(d) for closed-end credit, §1026.16(b) for open-end)

The following terms in lending advertising are **trigger terms** that activate full disclosure requirements:

- The amount or percentage of any **down payment**.
- The amount of any **payment** (e.g., "$299/month").
- The **number of payments** or **period of repayment** (e.g., "60-month financing").
- The amount of any **finance charge**.

If any trigger term appears, the ad must clearly and conspicuously state:

- The amount or percentage of the down payment.
- The terms of repayment (payment amount, number of payments, the period over which payments are made).
- The annual percentage rate, using the term "APR".
- Whether the rate may increase after consummation (if applicable).

### APR rules

- If an APR is mentioned, it must use the term "annual percentage rate" or "APR".
- A simple interest rate may also be stated, but the APR must be at least as conspicuous.
- "As low as" rates are permitted only if the rate reflects a rate a meaningful number of borrowers actually qualify for, and the ad must make clear the rate is subject to credit qualification.

### §1026.24 — Closed-end credit advertising

Applies to mortgages, auto loans, personal installment loans. Specific rules:

- §1026.24(f): mortgage advertising with a payment example must compare APR with the simple rate and meet specific clear-and-conspicuous requirements.
- "No fees" or "no closing costs" claims on mortgages must be true on a net basis.
- Comparisons between products must be balanced (can't show "save $200/month" without explaining the trade-off — typically a longer term).

### §1026.16 — Open-end credit advertising

Credit cards and HELOCs.

- For credit cards, if a rate is mentioned, the disclosed APR must be the rate that actually applies to purchases (or each tier of rates if the card has multiple).
- HELOC introductory rates require disclosure of the period and the rate that applies thereafter.

### Common BLOCK patterns

- "Auto loans starting at 5.99%" with no APR disclosure.
- "Refinance and save $200/month" — payment-amount trigger; full disclosure required.
- "$299/month for 60 months" — payment + number of payments triggers; full disclosure required.
- "As low as 3.5%" without language clarifying that the rate is subject to credit qualification.
- Mortgage advertising with payment terms but no APR.
- Credit card "0% APR" with no disclosure of duration or post-promo rate.

---

## Regulation E — 12 CFR Part 1005 — Electronic transfers

Activates when the article discusses electronic transfers, debit cards, ATM access, mobile banking, online bill pay, P2P transfer products (Zelle, Venmo integrations), wire transfers initiated electronically.

Reg E's main marketing-relevant rule is the prohibition on misleading statements about EFT services. Marketing copy must not:

- Imply free or unlimited transfers when fees actually apply (per-transaction, foreign ATM, expedited transfer).
- Imply error-resolution rights that exceed the actual rights, or fail to direct readers to the actual disclosure document.
- Misrepresent the credit union's liability for unauthorized transfers.

The full error-resolution disclosure is required at account opening, not in marketing copy — but marketing copy must not contradict the disclosure.

**WARN** (typical, not BLOCK): unqualified "free ATM access" claims. Surface for compliance officer to confirm whether the network is truly fee-free at all locations.

---

## Regulation B (ECOA) and Fair Housing Act — fair lending

Activates when the article discusses credit, loans, or membership eligibility.

### Prohibited bases

ECOA: race, color, religion, national origin, sex, marital status, age (provided applicant has capacity), receipt of public assistance income, exercise of consumer-protection rights.

Fair Housing Act adds: familial status, handicap (in housing).

### Equal Housing Lender / Equal Housing Opportunity

Mortgage and home-loan advertising must include the Equal Housing Lender (or Equal Housing Opportunity) logo and statement. The skill flags MISSING when an article promotes home loans and the EHL line is absent.

### Membership eligibility statements

Must not exclude protected classes. State the eligibility criteria neutrally — "you can join if you live, work, worship, or attend school in Dane County" is fine; "join if you're a hardworking family man" is not.

### Common patterns

- WARN: "Second-chance credit" products described in ways that imply value judgments about borrowers.
- WARN: comparative advertising that uses demographic language.

---

## Membership eligibility / field of membership

Federal credit unions operate within a defined field of membership (FOM) approved by NCUA — common-bond, multiple-common-bond, or community charter. State-chartered credit unions operate under analogous state-law constraints.

Marketing must accurately describe eligibility:

- "Anyone in Wisconsin can join" — only correct if the FOM genuinely covers the entire state. For a county-bound community charter, this is a misrepresentation. **BLOCK** if you have the FOM and it doesn't match. **WARN** if the FOM wasn't supplied.
- "Open to all" — almost always inaccurate for a credit union; flag.
- "Anyone can join!" — same.

If the field of membership input is provided, compare specific geographic or affiliation claims in the article against it. If the article says "anyone in Wisconsin" and the FOM says "Dane County", that's a clear BLOCK. If the article hedges ("see if you qualify"), that's typically fine.

If the field of membership is not provided, flag the broad claim as WARN with a question for the compliance officer: "Confirm field of membership covers the geographic area asserted in this passage."

---

## Cross-cutting BLOCK patterns

Quick reference for the patterns that should always BLOCK regardless of context:

| Pattern | Rule | Why |
| --- | --- | --- |
| "FDIC insured" or "FDIC" applied to the credit union | §740.2 + §740.4 | Credit unions are NCUA-insured. FDIC is for banks. |
| Deposit terms with no APY label | §707.8(b) | Rate must be APY in advertising. |
| "Free [account]" with any fee | §707.8(a) "free" restriction | Conditional-free ≠ free. |
| Bonus offer with no maintenance condition disclosed | §707.8(d) | Bonus disclosures are mandatory. |
| Lending trigger term with no APR | §1026.24(d) / §1026.16(b) | Trigger terms activate full disclosure. |
| Annuity / mutual fund without "not insured / may lose value" | §740.5 | Non-deposit disclosure is mandatory. |
| Insured-product promo with no insurance statement anywhere | §740.4 | Statement must appear in advertising. (MISSING flag, not BLOCK, since it's an absence.) |
| "100% safe" / "100% guaranteed" on deposits | §740.2 | Misleading; insurance is to $250K and conditional. |

---

## Standard rewrite snippets

When suggesting rewrites, prefer these standard phrasings — they are the language a compliance officer is used to seeing.

### Federal insurance statement (short form)

> Federally insured by NCUA.

### Federal insurance statement (long form)

> This credit union is federally insured by the National Credit Union Administration.

### Non-deposit disclosure

> Not federally insured. Not guaranteed by [Credit Union Name]. May lose value.

### APY disclosure block (savings / money market)

> APY accurate as of [date]. Minimum balance to obtain APY: $[X]. APY may change after the account is opened. Fees may reduce earnings on the account.

### APY disclosure block (share certificate / CD)

> APY accurate as of [date]. Minimum balance to open and obtain APY: $[X]. Term: [N months]. A penalty may be imposed for early withdrawal.

### Bonus disclosure

> Bonus paid after [N days/months] from account opening. Minimum balance of $[X] required. Account must remain open and in good standing through bonus payment date.

### Lending trigger-term disclosure (closed-end)

> Example: $[loan amount] financed at [APR]% APR for [N] months. Monthly payment $[X]. [Down payment, if any.] Rate subject to credit qualification. Other rates and terms available.

### Lending "as low as" qualifier

> Rate shown is our best rate, available to qualified borrowers. Your rate may be higher based on creditworthiness, term, and other factors.

### Equal Housing Lender

> Equal Housing Lender. (Use the EHL logo where space permits.)

### Membership eligibility WARN question (when FOM not provided)

> Compliance officer to confirm: does the credit union's field of membership cover the geographic area / affiliation described in this passage as written?
