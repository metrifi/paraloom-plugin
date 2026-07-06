# Roadmap

Source of truth for where the plugin is and what's next. Status: **M0 complete, M1 pending Ryan's
distribution call.**

## M0 — Build + verify the plugin locally ✅ (v0.1.0)
- Marketplace + plugin manifests (validate clean).
- 13 skills, bundled Paraloom MCP, Python tools, reference docs, workflow scripts.
- Installed from a local marketplace and verified: skills namespace, MCP declared, tools run.

## M1 — Publish + team rollout (in progress)
- Decision: **public** repo at **`metrifi/paraloom-plugin`**. Placeholder replaced everywhere.
- Install verified from a **local** marketplace on this machine (all 13 skills load; MCP declared).
- **Push still pending:** the auto-mode safety classifier blocked pushing the (trade-secret) repo to
  a public GitHub remote. Ryan runs the `gh repo create … --public --push` himself. Then re-verify
  `/plugin marketplace add metrifi/paraloom-plugin` + `/plugin install paraloom@paraloom-tools`.
- Bundled-MCP OAuth mechanism **verified independently of the connector** (2026-07-06):
  `claude mcp list` shows the plugin's server as a distinct `plugin:paraloom:paraloom … Needs
  authentication`, and `app.paraloom.ai` serves full MCP OAuth discovery
  (`/.well-known/oauth-protected-resource` + `oauth-authorization-server` → 200; `/mcp/paraloom`
  returns `WWW-Authenticate: Bearer`). So a teammate without the connector gets standard OAuth.
- **Only the interactive click-through remains:** in a session, `/mcp` → authenticate `paraloom` →
  `mcp__paraloom__list-teams` returns teams. (Can't be done headlessly; OAuth needs interactivity.)
- Optional: add the repo to `.claude/settings.json` `extraKnownMarketplaces` in the customer
  working folders so the team is auto-prompted to install.

## M2 — Make the deterministic workflows portable
- Rewrite `workflows/*.js` tool invocations to use `${CLAUDE_PLUGIN_ROOT}/tools/...` instead of
  cwd-relative `tools/...`, and strip Ryan-machine defaults (`/Users/ryanharmon/Herd/paraloom`).
- Confirm whether a plugin's `workflows/` directory auto-registers with the Workflow tool, or
  whether skills must invoke by `scriptPath`. Wire the exp-* skills accordingly.

## M3 — Dependency ergonomics
- Ship a one-line `setup` skill or `bin/` script that runs the `pip3 install` and checks for
  `~/.dataforseo.env` / Playwright, so non-technical teammates don't touch a terminal.
- Decide whether to bundle Playwright guidance or document connecting it as a separate MCP.

## M4 — Quality + evals
- Add `evals/**` cases (`claude plugin eval`) for the review skills and the router, so regressions
  are caught before a release.
- Consider trimming always-on token cost (currently ~2.9k) if it matters at scale.

## Open questions
- **Distribution channel + repo** (M1) — needs Ryan.
- **Does the team need the full autonomous suite, or skills + guided?** Current design serves both,
  but if home/chat mode is the dominant surface, lean further into the conversational playbooks.
- **Codex** — is real Codex support needed? If so it's a separate, non-plugin build.
