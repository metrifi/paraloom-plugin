---
name: exp-build
description: >
  Phase 3-7 of a Paraloom experiment (the opportunity engine): analyze a campaign's LLM
  responses, score each prompt for a winnable visibility opportunity (demand x lender-slot
  openness x owned gap), lock the biggest viable target, create the Paraloom experiment record,
  write the strategy (evidence + decisions + Paraloom analysis & recommendation), and draft the
  article. On a WEAK/AVOID verdict it PIVOTS rather than shipping a weak target. Use once
  exp-research has created a campaign and its prompts have run (responses populated). Produces a
  draft ready for exp-review.
---

# exp-build — Phase 3-7 (analyze → design → strategy → draft)

Takes a populated campaign to a defensible draft article. Read
`${CLAUDE_PLUGIN_ROOT}/reference/EXPERIMENT_WORKFLOW.md` (Phases 3-7, the Viability Verdict
format) and `${CLAUDE_PLUGIN_ROOT}/reference/methodology-rules.md` (rules #3, #4, #8) first.

## Two ways to run it

**A. Deterministic (preferred when Workflow is available).**

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/exp-build.js",
  args: {
    slug, teamId, campaignId,
    stopAfter: "analyze",      // read-only: rank the opportunity, make NO writes (do this first)
    localOnly: true,           // generate all content files but skip every Paraloom write
    maxPivots: 2,
    mcpPrefix: "mcp__paraloom__"
  }
})
```

Run `stopAfter:"analyze"` first to sanity-check the opportunity ranking before any writes.

**B. Conversational playbook** (when Workflow is unavailable):

1. **Analyze (Phase 3, read-only).** Pull the baseline: `list-prompts` (per-prompt visibility %),
   `get-org-visibility` (competitive ranking — filter loan-program providers like WHEDA/FHA/VA out
   of the CU/bank competitor set), `list-responses` + `get-response` (full body text). Run the
   **lender-citation gate** (rule #3): per prompt, count how many baseline responses name a
   specific FI in body text. Score each prompt on demand × lender-slot openness × owned-content
   gap. Write `build-analysis.md`.
2. **Decide.** Produce the **Viability Verdict** — `STRONG | VIABLE | WEAK | AVOID` + confidence —
   as the opening block (format in the SOP). STRONG/VIABLE → lock the target. **WEAK/AVOID →
   PIVOT**: re-select among already-run prompts first (free), then create + run new
   keyword-grounded prompts (re-angle / re-scope) and re-score. A `re-campaign` (adjacent-market
   sibling campaign) is always returned to the human, never executed. Never ship a weak target.
3. **Design (Phase 4).** `create-experiment(team_id, name, campaign_id, description, status="draft")`
   → `update-experiment(prompt_ids=[...])` to attach targets. **Do not set `started_at`** — that
   starts the 28-day clock; it only gets set at publish.
4. **Evidence + decisions (Phase 5).** Write `evidence.md` (observations with citations) and
   `decisions.md` (article-direction choices with **rejected alternatives** — rule #4). Then write
   the Paraloom records: `set-experiment-analysis` (summary MUST open with the Viability Verdict) and
   `set-experiment-recommendation` (call `list-action-types` first; each action.type must match).
   These are **replace** writers — build the full payload.
5. **Outline (Phase 6)** then **Draft (Phase 7).** Write `article-<slug>.outline.md`, then
   `article-<slug>.md`. Draft to the verified live site (rule #9): claims in the site's own
   wording, published facts pulled from the site, softened-now + opt-in-ask when unsupported. No
   rate numbers in body (rule #5); no unsubstantiated superlatives (rule #6). Capture any
   `openItemsForReview`. There is **no draft-review stop** — continue to exp-review.

## Gotchas

- This is the suite's API-instability magnet. If it dies after the experiment record + content
  files exist on disk, finish the remaining phases by hand rather than re-running from scratch.
- `set-*` tools REPLACE, never patch — assemble the whole payload each call.
- Empirical patterns are observations, not prescriptions (rule #4). Do not mirror the competitor
  comparison surface inside the owned page.
