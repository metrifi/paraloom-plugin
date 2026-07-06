# Fact-Check Report — {{article_title}}

**Reviewed:** {{iso_timestamp}}
**Article path:** {{article_path}}
**Credit union:** {{credit_union_name}}
**Primary source:** {{credit_union_website}}
**Skill version:** fact-verification 1.0.0

## Summary

- Verified: {{n_verified}}
- Contradicted: {{n_contradicted}}
- Needs human verification: {{n_nhv}}
- Total claims checked: {{n_total}}

**Recommendation:** {{recommendation}}

> ⚠️ This skill verifies what it can web-confirm. Quoted statements, internal data not on the public website, and recent or future-dated claims may need human verification. Always re-check rate claims at publish time.

## Contradicted claims (must fix)

<!-- One block per CONTRADICTED claim. Skip this section entirely if there are zero. -->

### CONTRADICTED 1: {{short_label}}

**Article claim:** "{{verbatim_article_text}}"
**Type:** {{type_number}} — {{type_name}}
**Source URL:** <{{source_url}}>
**Source quote (verified {{iso_timestamp}}):** "{{verbatim_source_quote}}"
**Status:** CONTRADICTED — {{one_line_explanation}}
**Suggested fix:** {{actionable_suggestion}}

## Needs human verification

<!-- One block per NHV claim. Skip this section entirely if there are zero. -->

### NHV 1: {{short_label}}

**Article claim:** "{{verbatim_article_text}}"
**Type:** {{type_number}} — {{type_name}}
**Reason:** {{why_cant_be_web_verified}}
**What would verify it:** {{what_evidence_is_needed}}

## Verified claims

| # | Claim | Type | Source URL | Source quote | Verified |
|---|-------|------|------------|--------------|----------|
| 1 | "{{verbatim_article_text}}" | {{type_number}} — {{type_name}} | <{{source_url}}> | "{{verbatim_source_quote}}" | {{iso_timestamp}} |

## Time-sensitive claims to re-verify before publish

<!-- A focused list pulled from the verified set: any rate claim, any "current"-tense numeric claim, any hours/address claim. Even if VERIFIED, list them here so the human reviewer re-checks at publish time. -->

- {{verbatim_article_text}} — verified {{iso_timestamp}} from <{{source_url}}>. **Re-verify at publish time.**

## Reviewer sign-off

- [ ] All CONTRADICTED claims fixed
- [ ] All NHV claims dispositioned (verified by human, removed, or softened)
- [ ] Rates and time-sensitive claims re-verified at publish time
- [ ] Final review by: __________________ (name)
- [ ] Sign-off date: __________________
