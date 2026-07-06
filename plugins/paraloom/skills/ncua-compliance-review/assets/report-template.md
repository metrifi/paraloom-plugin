# NCUA Compliance Review — {{article_title}}

**Reviewed:** {{iso_timestamp}}
**Article path:** {{article_path}}
**Credit union:** {{credit_union_name}}, {{charter_type}} charter
**Skill version:** {{skill_version}}

## Summary

- BLOCK issues: {{block_count}}
- WARN issues: {{warn_count}}
- MISSING items: {{missing_count}}
- NIT items: {{nit_count}}

**Recommendation:** {{recommendation}}

> ⚠️ This is an automated assistive review. A licensed compliance officer at {{credit_union_name}} must sign off before publication. Issues this skill missed are still the publisher's responsibility.

## Issues

{{#each issues}}
### {{severity}} {{index}}: {{title}}

**Passage:** "{{passage_quote}}"
**Rule:** {{rule_citation}}
**Why:** {{explanation}}
**Suggested rewrite:** {{rewrite_or_instruction}}

{{/each}}

{{#if missing_items}}
{{#each missing_items}}
### MISSING {{index}}: {{title}}

{{description}}

**Suggested action:** {{action}}

{{/each}}
{{/if}}

## Compliance officer sign-off

- [ ] All BLOCK items resolved
- [ ] All WARN items reviewed and dispositioned
- [ ] All MISSING items addressed
- [ ] Final review by: __________________ (name)
- [ ] Sign-off date: __________________
