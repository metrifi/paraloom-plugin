---
name: exp-review
description: >
  Phase 8 review battery for a Paraloom experiment: run the four pre-publish checks — hygiene,
  NCUA compliance, ADA accessibility, and fact verification — in parallel against a draft article,
  then synthesize a severity-ranked rollup for the compliance gate and write the manifest inputs.
  Use when a draft article is ready to be reviewed before publication ("review this draft", "run
  the review battery", "is this ready to ship"). Does NOT mutate the article — fixes happen back
  in conversation, then re-run.
---

# exp-review — Phase 8 (pre-publish review battery)

Runs the four checks and produces a consolidated summary plus `manifest-inputs.json`. It never
edits the article. Read `${CLAUDE_PLUGIN_ROOT}/reference/EXPERIMENT_WORKFLOW.md` (Phase 8
disposition rules) first.

## Two ways to run it

**A. Deterministic (preferred when Workflow is available).**

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/exp-review.js",
  args: { slug, creditUnion, domain, mcpPrefix: "mcp__paraloom__" }
})
```

**B. Conversational playbook** (when Workflow is unavailable) — run the four checks against
`experiments/<slug>/article-<slug>.md`:

1. **Hygiene** — use the project's focused check, not the canonical hygiene skill (it flags
   financial compound terms as false positives):
   `python3 "${CLAUDE_PLUGIN_ROOT}/tools/focused-hygiene-check.py" --article experiments/<slug>/article-<slug>.md --credit-union-domain <domain>`.
   It detects AI tells (em/en dashes, AI-typical phrasing), spelling, and markdown integrity.
2. **NCUA compliance** — run the **`ncua-compliance-review`** skill. Part 740, Reg Z trigger
   terms, TISA, Reg B / fair lending. Flags BLOCK / WARN / MISSING / NIT.
3. **ADA accessibility** — run the **`ada-accessibility-review`** skill (WCAG 2.1 AA, content
   level). Page-level checks DEFER to the Phase 9 rendered-page audit.
4. **Fact verification** — run the **`fact-verification`** skill (Playwright-driven against the
   FI's live site and authoritative sources). Anything unverifiable → NEEDS_HUMAN_VERIFICATION.

Then **synthesize**: write the four reports (`article-<slug>.{hygiene-check,compliance-review,accessibility-review,fact-check}.md`),
a `article-<slug>.review-summary.md`, and `manifest-inputs.json` (checklist + action items +
opportunity header + a plain-language `dossierSummaries` map and `evidenceOverview`).

## Disposition rules (work these conversationally, then re-run)

- **BLOCK / CONTRADICTED** — must be fixed before advancing. If any survive, the suite **halts**
  with a report rather than proceeding to exp-deliver.
- **WARN** — review with the human; record the disposition in `decisions.md` ("fixed" + rewrite,
  or "kept with reasoning").
- **NEEDS_HUMAN_VERIFICATION** — the human verifies offline; update the article or note the
  source in `decisions.md`.
- **DEFER** (ADA page-level) — carry to Phase 9 as a rendered-page checklist.

After applying fixes, re-run this battery to confirm they hold. Log each pass in `workflow-log.md`.
Target zero action items (rule #9): prefer softened site-supported wording now over a client ask.
