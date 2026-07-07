---
name: project-setup
description: |
  Bootstrap a new Paraloom customer project with this plugin: verify the stack (Paraloom MCP reachable, plugin skills loaded, DataForSEO credentials, Playwright MCP) and report in one concise message, then ask the three scoping questions needed before Phase 1. Use whenever someone says "set up this project", "bootstrap this project", "new project", "new customer project", "get this ready", or sends a first message in a fresh customer folder asking to get started. Holds all Paraloom and DataForSEO writes until the scoping answers are in.
---

# Project-Setup Skill

## Why this skill exists

Catches a broken MCP or missing credentials **before** any experiment work happens, and asks the
scoping questions Phase 1 needs. Read `${CLAUDE_PLUGIN_ROOT}/reference/EXPERIMENT_WORKFLOW.md` and
`${CLAUDE_PLUGIN_ROOT}/reference/methodology-rules.md` first if you haven't this session.

## First: pick a working folder

Experiments are created under `experiments/<slug>/` **in the current working directory**. Before
anything else, confirm the session is running in the folder you want to hold this customer's
experiments (in Claude Desktop code mode, that's the folder/project you opened). If you're in a
scratch or home directory, say so and suggest opening a dedicated customer folder.

## The four stack checks

Run all four, then report back in **one concise message** (a short checklist — pass/fail per item
plus the one detail that matters):

1. **Paraloom MCP connected.** Probe with `ToolSearch` (`select:list-teams`), load the tool, call
   `mcp__paraloom__list-teams`. Report which teams are visible. If only one team is visible, that's
   the customer for this project — note their `team_id` and team name. The Paraloom connector
   authorizes separately from the plugin install: in **Claude Desktop → Settings → Connectors**
   (sign in once), or via `/mcp` in the Claude Code CLI. **Attempt the call rather than assuming
   it's blocked** — only if `list-teams` errors with an auth failure, point the user to authorize
   the Paraloom connector there (a one-time UI step), then retry. Don't claim this session can't do it.

2. **Plugin skills loaded.** Confirm the paraloom plugin's skills resolve — the experiment skills
   (`exp-research`, `exp-build`, `exp-review`, `exp-deliver`, `exp-revise`, `exp-status`) and the
   review skills (`keyword-research`, `article-hygiene-check`, `ncua-compliance-review`,
   `ada-accessibility-review`, `fact-verification`). On Paraloom work, use the bundled
   `${CLAUDE_PLUGIN_ROOT}/tools/focused-hygiene-check.py` for the AI-tell/spelling pass rather than
   the canonical `article-hygiene-check` skill (which flags financial compound terms as false
   positives) — that's by design.

3. **DataForSEO credentials discoverable.** Check the working directory for `.dataforseo.env`, then
   `~/.dataforseo.env`. Don't read the values — just confirm a file exists with non-empty
   `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` lines. `keyword-research` (Phase 1 demand grounding)
   needs these; without them, keyword volume is unavailable and Phase 1 triage can't run properly.

4. **Playwright MCP connected** (used by `fact-verification` in Phase 8). Probe with `ToolSearch`
   (`select:mcp__playwright__browser_navigate`). **This plugin does not bundle Playwright** — it
   must be connected separately in the environment. If it doesn't resolve, note that fact
   verification will fall back to manual/human verification until it's added.

If any check fails, say exactly what's broken and how to fix it — don't continue to scoping as if
the stack were healthy.

## The three scoping questions

After the checks pass, ask (in this order — the order Phase 1 needs them):

1. **Existing visibility surface.** Does the customer already have a Paraloom campaign for adjacent
   topics, or is this their first experiment?
2. **Topic and target audience.** Be specific — geo, buyer profile, intent angle.
3. **Point of contact and compliance relationship.** Who's the POC, and what's their
   compliance-officer relationship? (POC forwards to compliance is the typical pattern.)

## Hard rule: no writes until scoping is answered

Do not push anything to Paraloom or DataForSEO until all three answers are in. Once the exp-*
skills run, the safety model is reporting + idempotency with allowlisted writes (every phase
returns exactly what it created, and creates dedupe so re-runs are safe); `dryRun:true` on
`exp-research` is the no-writes preview when you want to inspect the triage before anything hits
Paraloom.
