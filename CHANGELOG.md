# Changelog

All notable changes to the Paraloom plugin are recorded here. Versions follow the `plugin.json`
`version` field (semver).

## [0.1.0] — 2026-07-06

Initial release. Packages the `paraloom-agent` toolkit as an installable Claude Code plugin +
marketplace.

### Added
- **Marketplace** (`.claude-plugin/marketplace.json`, `paraloom-tools`) and **plugin**
  (`plugins/paraloom`, `paraloom`) manifests. Both pass `claude plugin validate`.
- **13 skills** under the `paraloom:` namespace:
  - `start` — new orientation + intent-router skill carrying the operating context (who you are,
    the phase map, the human gates, the hard methodology rules) adapted from the project `CLAUDE.md`.
  - `exp-research`, `exp-build`, `exp-review`, `exp-deliver`, `exp-revise` — new phase skills. Each
    runs the bundled deterministic workflow when the Workflow tool is available, and falls back to
    an equivalent conversational playbook when it isn't (so they work in Claude Desktop code mode).
  - `exp-status`, `project-setup` — carried over, repointed at the plugin's bundled reference docs.
  - `keyword-research`, `article-hygiene-check`, `ncua-compliance-review`, `ada-accessibility-review`,
    `fact-verification` — the five review skills, vendored verbatim (test fixtures excluded to keep
    the plugin lean).
- **Bundled Paraloom MCP** (`.mcp.json`) as a remote HTTP server at `https://app.paraloom.ai/mcp/paraloom`.
  Connects via OAuth on first use — no manual connector setup.
- **Python tools** (`tools/`): `build-deliverable-manifest.py`, `focused-hygiene-check.py`,
  `build-compliance-pdf.py`, `backfill-evidence-summaries.py`, `requirements.txt`. Skills invoke
  them via `${CLAUDE_PLUGIN_ROOT}`.
- **Reference docs** (`reference/`): the 11-phase SOP, methodology rules, conventions, deliverables
  architecture, MCP tool list, workflow-suite design.
- **Workflow scripts** (`workflows/`): the original `/exp-*` `.js` orchestration, carried for
  Workflow-capable environments.
- **README.md** (with an honest per-surface capability matrix) and **INSTALL.md** (team-facing).

### Verified
- Manifests validate; plugin installs from the local marketplace; all 13 skills load and namespace
  correctly; the `paraloom` MCP server is declared (always-on cost ~2.9k tokens); `${CLAUDE_PLUGIN_ROOT}`
  resolves in the install cache; `focused-hygiene-check.py` runs end to end from the cache.

### Known limitations
- The bundled `workflows/*.js` still contain cwd-relative tool paths and a few Ryan-machine defaults;
  they're reliable in the Workflow-capable CLI but the **conversational playbook is the supported path**
  for the team. Generalizing them is a follow-up (see `docs/ROADMAP.md`).
- Home/chat mode runs skills only (no sub-agent orchestration). Playwright and `weasyprint` are not
  bundled. Codex is not supported (Claude-plugin format only).
