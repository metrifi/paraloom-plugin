#!/usr/bin/env python3
"""
Deterministic first-pass scanner for the ncua-compliance-review skill.

Reads an article (markdown / HTML / plain text), looks for keyword patterns
that map to common BLOCK / WARN / MISSING items, and emits a JSON object
listing matches by category. The skill uses this as a checklist alongside
its own careful read — the scanner is intentionally narrow and will miss
non-keyword-shaped issues. False positives are expected; the human (or
the LLM driving the skill) decides what counts.

Usage:
  python3 scan_article.py <article_path>

Output: JSON on stdout.
"""

import json
import re
import sys
from pathlib import Path


# ---- Pattern definitions -------------------------------------------------

# Each pattern is (name, regex, flags). Matches are returned with the
# matched substring + 80-char context window before/after.

DEPOSIT_PRODUCT_TERMS = [
    r"\bsavings account\b",
    r"\bchecking account\b",
    r"\bshare certificate\b",
    r"\bshare certificates\b",
    r"\bcertificate of deposit\b",
    r"\bCDs?\b",
    r"\bmoney market\b",
    r"\bIRA\b",
    r"\bdeposit account\b",
    r"\bshare account\b",
]

LENDING_PRODUCT_TERMS = [
    r"\bmortgage\b",
    r"\bauto loan\b",
    r"\bauto loans\b",
    r"\bcar loan\b",
    r"\bpersonal loan\b",
    r"\bcredit card\b",
    r"\bHELOC\b",
    r"\bhome equity\b",
    r"\bRV loan\b",
    r"\bboat loan\b",
    r"\bstudent loan\b",
    r"\brefinance\b",
]

NON_DEPOSIT_PRODUCT_TERMS = [
    r"\bannuity\b",
    r"\bannuities\b",
    r"\bmutual fund\b",
    r"\bbrokerage\b",
    r"\bsecurities\b",
    r"\binsurance product\b",
    r"\bvariable annuity\b",
    r"\bfixed annuity\b",
]

EFT_TERMS = [
    r"\bdebit card\b",
    r"\batm\b",
    r"\bmobile banking\b",
    r"\bonline bill pay\b",
    r"\bzelle\b",
    r"\bvenmo\b",
    r"\bp2p\b",
    r"\bwire transfer\b",
    r"\bwire transfers\b",
]

# Pattern groups that are red flags on their own.
HARD_FLAGS = [
    ("fdic_mentioned", r"\bFDIC\b"),
    ("100_pct_safe", r"\b100%?\s*(safe|guaranteed|secure|protected)\b"),
    ("absolutely_guaranteed", r"\b(absolutely|completely|fully)\s+guaranteed\b"),
    ("backed_by_government", r"\bbacked by\b[^.]{0,40}\b(federal\s+government|U\.?S\.?\s+government|government)\b"),
    ("anyone_can_join", r"\b(anyone\s+can\s+join|open\s+to\s+all)\b"),
    ("anyone_in_state_can_join", r"\banyone\s+(in|across|throughout)\s+\w+\s+(can|may)\s+join\b"),
]

# "Free" patterns — flagged for review against fee mentions.
FREE_PATTERNS = [
    r"\bfree\s+checking\b",
    r"\bfree\s+savings\b",
    r"\bfree\s+account\b",
    r"\bno[- ]cost\s+account\b",
    r"\bno[- ]cost\s+checking\b",
]

# Fee mentions — co-occurrence with FREE patterns is a BLOCK candidate.
FEE_PATTERNS = [
    r"\$\d+(?:\.\d{1,2})?\s*(?:monthly\s+fee|maintenance\s+fee|service\s+fee|per\s+month)",
    r"\bmonthly\s+(?:maintenance|service)?\s*fee\b",
    r"\bmaintenance\s+fee\b",
    r"\bservice\s+charge\b",
    r"\boverdraft\s+fee\b",
    r"\bactivity\s+fee\b",
    r"\bminimum\s+balance\s+fee\b",
    r"\bfee\s+waived\b",  # Conditional waiver still means a fee exists.
]

# Lending trigger terms (Reg Z).
TRIGGER_TERM_PATTERNS = [
    ("payment_amount", r"\$\d{2,4}(?:\.\d{1,2})?\s*(?:/\s*month|per\s+month|a\s+month|monthly)"),
    ("number_of_payments", r"\b(?:over\s+|for\s+)?\d{2,3}[- ]?(?:month|year)s?\b\s*(?:financing|loan|term)?"),
    ("down_payment", r"\b(\$\d+|\d{1,2}\s*%)\s+down(?:\s+payment)?\b"),
    ("save_per_month", r"\bsave\s+\$\d+\s*(?:/\s*month|per\s+month|a\s+month|monthly)"),
    ("as_low_as_rate", r"\bas\s+low\s+as\s+\d+(?:\.\d+)?\s*%"),
    ("starting_at_rate", r"\bstarting\s+at\s+\d+(?:\.\d+)?\s*%"),
    ("from_rate", r"\bfrom\s+\d+(?:\.\d+)?\s*%"),
    ("rates_starting", r"\brates\s+(?:as\s+low\s+as|starting\s+at|from)\s+\d+(?:\.\d+)?\s*%"),
]

# Rate-mention patterns for deposit copy.
RATE_PATTERNS = [
    ("bare_percent", r"\b\d+(?:\.\d+)?\s*%"),
]

# APR / APY label patterns.
APR_LABEL = re.compile(r"\bAPR\b|\bannual\s+percentage\s+rate\b", re.IGNORECASE)
APY_LABEL = re.compile(r"\bAPY\b|\bannual\s+percentage\s+yield\b", re.IGNORECASE)
DIVIDEND_RATE_LABEL = re.compile(r"\bdividend\s+rate\b", re.IGNORECASE)

# Federal insurance statement patterns (any of these counts as "present").
INSURANCE_STATEMENT_PATTERNS = [
    r"federally\s+insured\s+by\s+(?:the\s+)?NCUA",
    r"federally\s+insured\s+by\s+(?:the\s+)?National\s+Credit\s+Union\s+Administration",
    r"insured\s+by\s+(?:the\s+)?NCUA",
    r"NCUA[- ]insured",
    r"This\s+credit\s+union\s+is\s+federally\s+insured",
]

# Non-deposit disclosure pattern (rough — three-statement combo).
NON_DEPOSIT_DISCLOSURE_PATTERN = re.compile(
    r"not\s+federally\s+insured.{0,80}may\s+lose\s+value",
    re.IGNORECASE | re.DOTALL,
)

# Bonus offer pattern.
BONUS_PATTERNS = [
    r"\bbonus\s+\$\d+",
    r"\$\d+\s+bonus\b",
    r"\bget\s+\$\d+\s+when\s+you\s+open\b",
    r"\bearn\s+\$\d+\s+when\s+you\s+open\b",
]


# ---- Scanning helpers ----------------------------------------------------

def find_matches(text: str, patterns, *, ignore_case=True):
    """Return a list of dicts: {pattern, match, context}."""
    flags = re.IGNORECASE if ignore_case else 0
    out = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            out.append(
                {
                    "pattern": pat,
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                    "context": text[start:end].replace("\n", " ").strip(),
                }
            )
    return out


def find_named_matches(text: str, named_patterns, *, ignore_case=True):
    """Same as find_matches but each pattern has a name; output keyed by name."""
    flags = re.IGNORECASE if ignore_case else 0
    out = []
    for name, pat in named_patterns:
        for m in re.finditer(pat, text, flags):
            start = max(0, m.start() - 80)
            end = min(len(text), m.end() + 80)
            out.append(
                {
                    "name": name,
                    "pattern": pat,
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                    "context": text[start:end].replace("\n", " ").strip(),
                }
            )
    return out


def has_any(text: str, patterns) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def detect_rate_without_apy(text: str) -> list:
    """
    Find numeric percentages in deposit-account context that aren't paired
    with an APY label nearby. Returns a list of context windows.

    Heuristic: for each '\\d+%' match, look at a +/- 60 char window. If APY
    appears in the window, it's fine. Otherwise flag.
    """
    out = []
    for m in re.finditer(r"\b\d+(?:\.\d+)?\s*%", text):
        start = max(0, m.start() - 60)
        end = min(len(text), m.end() + 60)
        window = text[start:end]
        if APY_LABEL.search(window):
            continue
        # Skip if APR is in window — that's lending copy, different rules apply
        # downstream.
        if APR_LABEL.search(window):
            continue
        out.append(
            {
                "match": m.group(0),
                "span": [m.start(), m.end()],
                "window": window.replace("\n", " ").strip(),
            }
        )
    return out


def detect_trigger_terms_without_apr(text: str) -> list:
    """
    Find Reg Z trigger terms not paired with an APR disclosure within
    a +/- 200 char window. Returns matches with windows.
    """
    out = []
    for name, pat in TRIGGER_TERM_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = max(0, m.start() - 200)
            end = min(len(text), m.end() + 200)
            window = text[start:end]
            if APR_LABEL.search(window):
                continue
            out.append(
                {
                    "name": name,
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                    "window": window.replace("\n", " ").strip(),
                }
            )
    return out


def detect_free_with_fee(text: str) -> list:
    """
    Find 'free [account]' patterns and flag if any fee pattern appears
    elsewhere in the document. The skill (LLM) ultimately decides whether
    the fee actually applies to the same account.
    """
    free_hits = find_matches(text, FREE_PATTERNS)
    if not free_hits:
        return []
    fee_hits = find_matches(text, FEE_PATTERNS)
    if not fee_hits:
        return []
    return [
        {
            "free_match": fh,
            "fee_matches": fee_hits,
        }
        for fh in free_hits
    ]


def detect_bonus_without_disclosure(text: str) -> list:
    """
    Find bonus offers and flag if no minimum-balance / time-requirement /
    maintenance language appears within 300 chars after the bonus mention.
    """
    out = []
    for pat in BONUS_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = m.start()
            end = min(len(text), m.end() + 300)
            window = text[start:end]
            has_min_balance = bool(
                re.search(r"minimum\s+balance|maintain\s+\$\d+|keep\s+\$\d+", window, re.IGNORECASE)
            )
            has_time_req = bool(
                re.search(r"\d+\s*(?:days?|months?|years?)|maintain\s+(?:for|through)", window, re.IGNORECASE)
            )
            if has_min_balance and has_time_req:
                continue
            out.append(
                {
                    "match": m.group(0),
                    "span": [m.start(), m.end()],
                    "window": window.replace("\n", " ").strip(),
                    "missing": [
                        "minimum_balance" if not has_min_balance else None,
                        "time_requirement" if not has_time_req else None,
                    ],
                }
            )
    return out


# ---- Main ----------------------------------------------------------------

def scan(article_path: str) -> dict:
    text = Path(article_path).read_text(encoding="utf-8")

    deposit_terms = find_matches(text, DEPOSIT_PRODUCT_TERMS)
    lending_terms = find_matches(text, LENDING_PRODUCT_TERMS)
    non_deposit_terms = find_matches(text, NON_DEPOSIT_PRODUCT_TERMS)
    eft_terms = find_matches(text, EFT_TERMS)

    return {
        "article_path": article_path,
        "char_count": len(text),
        "categories_active": {
            "deposits": bool(deposit_terms),
            "lending": bool(lending_terms),
            "non_deposit_investments": bool(non_deposit_terms),
            "electronic_transfers": bool(eft_terms),
        },
        "category_matches": {
            "deposits": deposit_terms,
            "lending": lending_terms,
            "non_deposit_investments": non_deposit_terms,
            "electronic_transfers": eft_terms,
        },
        "hard_flags": find_named_matches(text, HARD_FLAGS),
        "free_with_fee_candidates": detect_free_with_fee(text),
        "bare_rate_in_deposit_copy": (
            detect_rate_without_apy(text) if deposit_terms else []
        ),
        "trigger_terms_without_apr": (
            detect_trigger_terms_without_apr(text) if lending_terms else []
        ),
        "bonus_without_disclosure": detect_bonus_without_disclosure(text),
        "has_federal_insurance_statement": has_any(text, INSURANCE_STATEMENT_PATTERNS),
        "has_non_deposit_disclosure": bool(NON_DEPOSIT_DISCLOSURE_PATTERN.search(text)),
        "has_apr_label": bool(APR_LABEL.search(text)),
        "has_apy_label": bool(APY_LABEL.search(text)),
        "has_dividend_rate_label": bool(DIVIDEND_RATE_LABEL.search(text)),
        "missing_insurance_statement_for_deposits": (
            bool(deposit_terms) and not has_any(text, INSURANCE_STATEMENT_PATTERNS)
        ),
        "missing_non_deposit_disclosure": (
            bool(non_deposit_terms) and not bool(NON_DEPOSIT_DISCLOSURE_PATTERN.search(text))
        ),
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: scan_article.py <article_path>", file=sys.stderr)
        sys.exit(2)
    result = scan(sys.argv[1])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
