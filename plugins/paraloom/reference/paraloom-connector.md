# Paraloom MCP connector — tool reference

Tool prefix: `mcp__<paraloom-mcp-id>__`. Schemas are deferred — load with `ToolSearch` before calling:

```
ToolSearch query: "select:create-experiment,update-experiment,set-experiment-analysis"
```

**Probe before assuming a tool exists.** The MCP added 8 tools mid-experiment in May 2026 (the entire experiment-management writer set plus get-ai-user-bot-traffic). Always run `ToolSearch` to confirm what's live, and update this doc when new tools surface.

## Current tool inventory (24 as of 2026-06)

### Read / inspect (15)

- `list-teams` — list teams visible to the authenticated account
- `list-campaigns` — list campaigns for a team
- `get-campaign` — get one campaign
- `list-prompts` — list prompts in a campaign, with per-prompt visibility
- `get-prompt` — get one prompt
- `list-responses` — list LLM responses for a prompt
- `get-response` — full content of one response
- `list-experiments` — list experiments for a team
- `get-experiment` — full experiment record (description, analysis, recommendation, prompts, metrics)
- `get-experiment-insights` — visibility metrics for an experiment
- `get-org-visibility` — organization visibility rankings for a campaign
- `get-team-usage` — team's API usage
- `get-team-health`: cross-team triage queue (verdict, reason, next action per team). Super-admin gated; returns a clear error for non-super-admins
- `get-ai-user-bot-traffic` — visits to the team's website from AI bots (ChatGPT-User, Claude-User, Perplexity-User). Requires `/ai-traffic` setup on the team
- `list-action-types` — valid action types for set-experiment-recommendation

### Write / act (9)

- `create-campaign` — new campaign on a team
- `create-prompt` — new prompt on a campaign
- `run-prompt` — trigger LLM runs on one prompt
- `run-campaign-prompts` — batch-trigger all prompts in a campaign across providers
- `create-experiment` — new experiment (name + campaign_id required; status defaults to `draft`)
- `update-experiment` — patch fields, change status, attach prompt_ids or article_ids
- `set-experiment-analysis` — replace analysis (summary + organizations + sources)
- `set-experiment-recommendation` — replace recommendation + 1–3 actions (each action.type must match a list-action-types value)
- `set-experiment-case-study` — replace case study (problem / strategy / results / takeaways / callouts)

## Critical usage patterns

### Phase 2 — creating a campaign and prompts

```
create-campaign(team_id, name, description, location, keywords)
  -> returns campaign_id
create-prompt(team_id, campaign_id, content) × N
run-campaign-prompts(team_id, campaign_id, providers=["openai","anthropic","gemini"], count=4)
```

**Watchpoint:** prompts come back with `Active: No` at creation. Explicit `run-campaign-prompts` still queues responses; the `Active` flag governs auto-rotation only (as far as we've observed).

**Watchpoint:** `run-campaign-prompts` triggered with `[openai, anthropic, gemini]` has consistently returned OpenAI-only responses. Either the providers param is overridden, or the team config doesn't have Anthropic/Gemini enabled. Document this every time as a Phase 8 compliance-bundle caveat.

### Phase 3 — pulling baseline data

```
list-prompts(team_id, campaign_id)  # per-prompt visibility %
get-org-visibility(team_id, campaign_id, limit=30)  # competitive ranking
list-responses(team_id, prompt_id)  # response IDs
get-response(team_id, response_id)  # full body text
```

The org-visibility table mixes loan programs (WHEDA, FHA, VA, USDA) with actual CU/bank competitors. Filter program-providers out manually before reporting the competitive set.

### Phase 4 — creating the experiment record

```
create-experiment(team_id, name, campaign_id, description, status="draft")
  -> returns experiment_id
update-experiment(team_id, experiment_id, prompt_ids=[...])  # attach targets
```

**Do not pass `started_at`** until Phase 10 publish — `status="published"` is what starts the 28-day measurement clock. Setting `started_at` early starts the clock before the article is live.

### Phase 11 — writing analysis, recommendation, and case study

```
set-experiment-analysis(team_id, experiment_id, summary, organizations[], sources[])
list-action-types()  # call BEFORE recommendation
set-experiment-recommendation(team_id, experiment_id, recommendation, actions[])
set-experiment-case-study(team_id, experiment_id, ...)
```

All three are dedicated **replace** writers (not patches). Build the full payload before calling. Analysis summary MUST include the viability verdict at the top (STRONG / VIABLE / WEAK / AVOID + confidence) per the project's `methodology-rules.md`.

### Per-experiment lifecycle quick map

```
Phase 2:  create-campaign → create-prompt × N → run-campaign-prompts
Phase 3:  list-prompts, get-org-visibility, list-responses, get-response
Phase 4:  create-experiment → update-experiment(prompt_ids=)
Phase 5+6+7: (no Paraloom calls — local artifact production)
Phase 8:  (no Paraloom calls — skill runs against local article)
Phase 10: update-experiment(status="published")  # starts 28-day clock
Phase 11: get-experiment-insights weekly via /exp-measure (deferred; will be a /loop-backed cron)
         → set-experiment-analysis (with VERDICT)
         → set-experiment-recommendation (with action types)
         → set-experiment-case-study
```

## Notes on schemas

- IDs are integers in Paraloom (team_id, campaign_id, prompt_id, experiment_id, response_id).
- Strings use UTF-8; markdown is accepted in description / summary / recommendation.description / action.description / case-study fields.
- Dates are `YYYY-MM-DD`. `baseline_started_at`, `baseline_ended_at`, `started_at`, `ended_at` are all optional — they auto-derive at publish.
- `confounded` (bool) + `confounded_note` (str) can be set via update-experiment if external factors affect the measurement window.

## When the surface changes

When you discover a new tool, or an existing one changes its schema, update this doc. Don't operate from memory — the MCP evolves and stale assumptions cause errors.
