# Changelog

All notable changes to the Paraloom plugin are recorded here. Versions follow the `plugin.json`
`version` field (semver).

## [0.1.3] — 2026-07-07

Fix the Claude Desktop "Upload plugin" route.

### Fixed
- Removed angle-bracket placeholders (`<team>`, `<topic>`, `<slug>`, `<experiment/team>`) from the
  `start`, `exp-research`, and `exp-status` skill **descriptions**. The Desktop plugin uploader
  validates stricter than `claude plugin validate` and rejected them as XML tags
  ("SKILL.md description cannot contain XML tags"), failing the zip upload. Descriptions now use
  plain wording; the triggers are unchanged in meaning. Rebuilt `dist/paraloom-plugin.zip`.

## [0.1.2] — 2026-07-07

Fixes from the first internal install test.

### Fixed
- The `start` and `project-setup` skills no longer tell the user the Paraloom connection "can't be
  done this session." They explain that the Paraloom connector authorizes **once in Settings →
  Connectors** (Desktop) or via `/mcp` (CLI), separately from the plugin install, and instruct the
  agent to **attempt the call** rather than preemptively refuse.

### Changed / Added
- INSTALL.md rewritten around the real two-step reality — install the plugin, then authorize the
  connector — with four routes: Desktop UI (recommended), the paste-once prompt, the CLI, and a
  **zip upload** route. Added a prebuilt `dist/paraloom-plugin.zip` (plugin-root zip for the
  uploader) and a one-page PDF install guide (`docs/Paraloom-Plugin-Install-Guide.pdf`, source
  `docs/install-guide.html`) for the Upload-plugin → Connectors flow.

## [0.1.1] — 2026-07-07

Install ergonomics + cleanup ahead of the internal team test. No behavior change to the skills.

### Added
- `install-prompt.md` — a paste-once prompt for Claude Desktop code mode that has Claude install
  the plugin, install the Python deps (handling missing Python via Homebrew and the pip
  "externally managed" error), write `~/.dataforseo.env`, and check for a browser tool. Intended to
  be distributed with the DataForSEO credentials filled in.
- README "How to use it" (example prompts by workflow) and "Install" sections; INSTALL.md rewritten
  to lead with the paste-once path.

### Changed
- Stripped machine-specific absolute paths: `conventions.md` no longer references copying a local
  `_paraloom-agent` kit; the `exp-deliver`/`exp-revise` workflows use `${dir}`-relative paths and an
  empty `paraloomPath` default instead of `/Users/ryanharmon/...` hardcodes.

### Notes
- Repo published public at `metrifi/paraloom-plugin`.
- Direction set for a future server-side MCP migration (no Python/pip/creds/forced-Playwright);
  plan tracked on the Paraloom branch `geo-plugin-mcp-tooling`. See `docs/ROADMAP.md`.

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
