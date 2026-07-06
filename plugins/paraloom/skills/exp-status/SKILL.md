---
name: exp-status
description: |
  Status rollup for Paraloom experiments: read each experiment's workflow-log.md and experiment.md, report current phase, IDs, what's next per EXPERIMENT_WORKFLOW.md, and everything waiting on a human (draft review, Phase 9 compliance sign-off, client answers, send approval). Use whenever Ryan asks to check in — "check in on <slug>", "status of <experiment/team>", "where are we with <team>?", "what's the latest", "how's <slug> going", "what needs me?", "what's waiting on me?", "resume <slug>" — for one experiment or across all of them. Read-only: never mutates files or Paraloom.
---

# Exp-Status Skill

## Why this skill exists

Checking in on an experiment used to require Ryan to spell out which files to read. The per-experiment files are self-describing, so this skill standardizes the rollup: same shape every time, whether it's one experiment or the whole portfolio.

## Scope resolution

- **Ryan names a slug or team/topic** ("check in on the vehicle refinance one") → match it to a folder under `experiments/`. If the match is ambiguous, list the candidates and ask.
- **Ryan asks portfolio-wide** ("what needs me?", "status across the board") → roll up every folder under `experiments/`.

## What to read (per experiment, in this order)

1. `workflow-log.md` — the phase-by-phase spine; where the experiment actually is.
2. `experiment.md` — hypothesis, current state, Paraloom IDs (team, campaign, experiment, deliverable).
3. `${CLAUDE_PLUGIN_ROOT}/reference/EXPERIMENT_WORKFLOW.md` — what the next phase requires and which human gates apply.
4. If a deliverable is live and the question implies freshness ("did the client respond?"), optionally probe Paraloom read-only via the MCP (e.g. `get-experiment`, deliverable-activity tools — load schemas with `ToolSearch` first). Local files are the default; only probe when the answer isn't on disk.

## Report format

Per experiment, one compact block:

- **Experiment** — slug, team, topic (one line)
- **Phase** — current phase number/name and what's been completed
- **IDs** — campaign / experiment / deliverable IDs if they exist
- **Next step** — the single next action per the SOP
- **Waiting on a human?** — the load-bearing line. Call out explicitly anything blocked on Ryan, the POC, or the compliance officer: draft review, Phase 9 sign-off, client answers, `send:true` approval. If nothing is blocked, say "nothing — I can proceed" and name what I'd do next.

For portfolio rollups, lead with the experiments that need a human, then the ones in flight, then anything done/dormant.

## Hard rule: read-only

This skill never edits files, never writes to Paraloom, never re-runs prompts. If the status reveals obvious next work ("responses populated, ready for /exp-build"), offer it — don't start it.
