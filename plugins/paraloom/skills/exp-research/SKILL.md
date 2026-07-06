---
name: exp-research
description: >
  Phase 1-2 of a Paraloom experiment: research a topic, generate keyword-grounded candidate
  prompts across intent angles / geographies / segments, triage to a demand-validated set, then
  create (or reuse) the Paraloom campaign, create the prompts, and run them. Use as the first
  step of an experiment — "start an experiment for <team> on <topic>", "research this topic",
  "stand up a campaign". Offer a dry run (triage only, no writes) if the topic is unvalidated.
  After this, wait for responses to populate, then run exp-build.
---

# exp-research — Phase 1-2 (campaign scoping + creation)

Stands up a demand-grounded Paraloom campaign and kicks off baseline LLM runs. Read
`${CLAUDE_PLUGIN_ROOT}/reference/EXPERIMENT_WORKFLOW.md` (Phases 1-2) and
`${CLAUDE_PLUGIN_ROOT}/reference/methodology-rules.md` (rules #1, #2) before starting.

## Inputs you need

- **team** (Paraloom team id — call `list-teams` if unknown), **topic**, **geography** (required)
- **audience**, **credit union name**, **domain** (recommended)
- A short **slug** for the experiment folder (e.g. `southern-wi-first-time-homebuyer`)

## Two ways to run it

**A. Deterministic (preferred when the Workflow tool is available).** Run the bundled workflow:

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/exp-research.js",
  args: {
    slug, teamId, topic, geography,
    audience, creditUnion, domain,
    dryRun: true|false,                 // true = stop after triage, NO Paraloom writes
    mcpPrefix: "mcp__paraloom__"        // this plugin's bundled Paraloom MCP
  }
})
```

If `Workflow` is not available in this environment (e.g. Claude Desktop home/chat mode), run it
conversationally instead:

**B. Conversational playbook.**

1. **Frame.** Create `experiments/<slug>/` in the current working directory. Draft
   `experiment.md` (topic, audience, geography, hypothesis-to-be), `workflow-log.md`, and empty
   `evidence.md` / `decisions.md`. Decide new-vs-existing campaign (`list-campaigns` for the team).
   Generate a wide candidate-prompt set spread across intent angles, geographies, and segments.
   Write prompts the way a consumer asks an AI assistant — **never** put a brand name in the prompt.
2. **Ground.** Run the **`keyword-research`** skill on the candidates (in small chunks of ~5 to
   dodge the DataForSEO bulk zero-volume quirk). Lead with the shortest umbrella keyword form
   (rule #2). Capture volume, related queries, and AI Mode SERP context.
3. **Triage.** Keep / Refine / Drop each candidate on **measurable keyword volume** (rule #1 — AI
   Mode richness is never demand). Write `keyword-research.md` (the research output) and
   `tracked-prompts.md` (the client-shareable rollup: every kept prompt traced to a volume number).
   **If `dryRun`: stop here. Make no Paraloom writes.** Report the triaged set for approval.
4. **Instantiate** (skip on dry run). Check `get-team-usage` (prompts consume quota). Then:
   `create-campaign(team_id, name, description, location, keywords)` → `create-prompt` × N →
   `run-campaign-prompts(team_id, campaign_id, providers=["openai","anthropic","gemini"], count=4)`.
   Record the campaign id and prompt ids in `experiment.md`. Prompts come back `Active: No` at
   creation; the explicit run still queues responses.

## Gotchas

- **Baseline runs need the team's subscription Active.** Confirm on the team before running, or
  the run silently produces nothing.
- **Single-provider caveat:** `run-campaign-prompts` has returned OpenAI-only responses despite
  requesting all three providers. Note it in `workflow-log.md` for the eventual compliance bundle.
- Responses populate **asynchronously**. Don't block — end with "responses are running; re-run
  exp-build once they populate." exp-build is idempotent and safe to re-run.
- Paraloom MCP tool schemas are deferred — `ToolSearch` (`select:create-campaign,create-prompt,run-campaign-prompts`) before calling.
