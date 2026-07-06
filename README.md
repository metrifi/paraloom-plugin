# Paraloom plugin (`paraloom-plugin`)

A Claude Code **plugin** that packages everything the `paraloom-agent` project does — the
experiment workflow, the review skills, the Python tools, the methodology, and the Paraloom MCP
connector — into a single installable extension. Instead of cloning a repo and launching Claude
Code from inside it, a teammate installs one plugin and gets the whole toolkit, in the terminal
**or in the Claude Desktop app**.

The repo is the plugin **marketplace**; the plugin itself lives in [`plugins/paraloom/`](plugins/paraloom).

- **Install instructions:** [`INSTALL.md`](INSTALL.md)
- **What each skill does / how the workflow runs:** open the plugin and read
  [`plugins/paraloom/reference/EXPERIMENT_WORKFLOW.md`](plugins/paraloom/reference/EXPERIMENT_WORKFLOW.md)
- **Roadmap / maintainer notes:** [`docs/ROADMAP.md`](docs/ROADMAP.md)

## What's in the plugin

| Component | What it is |
|---|---|
| **13 skills** | `start` (orientation + intent router), the 5 experiment phases (`exp-research`, `exp-build`, `exp-review`, `exp-deliver`, `exp-revise`), `exp-status`, `project-setup`, and the 5 review skills (`keyword-research`, `article-hygiene-check`, `ncua-compliance-review`, `ada-accessibility-review`, `fact-verification`). All namespaced, e.g. `/paraloom:exp-research`. |
| **Paraloom MCP** | Bundled as a remote server pointing at `https://app.paraloom.ai/mcp/paraloom`. Nothing to wire up by hand — it connects on first use with a normal Paraloom sign-in (OAuth). |
| **Python tools** | Deliverable manifest builder, focused hygiene check, compliance-PDF builder — referenced by the skills via `${CLAUDE_PLUGIN_ROOT}` so they work from anywhere. |
| **Reference docs** | The 11-phase SOP, the methodology rules, folder conventions, the deliverables architecture, and the MCP tool list — the skills point at these for depth. |
| **Workflow scripts** | The original deterministic `/exp-*` orchestration (`.js`), used automatically when the Workflow tool is available; otherwise each skill runs the same phases conversationally. |

## Where it works (read this before sharing)

Claude Code plugins are an **Anthropic** format. They run in the Claude Code CLI and inside the
Claude apps — but the capability level differs by surface. This is the honest matrix:

| Surface | Skills | Bundled Paraloom MCP | Multi-agent `/exp-*` automation | How to install |
|---|---|---|---|---|
| **Claude Desktop → Code mode** (Claude Code in the desktop app) — **recommended for the team** | ✅ | ✅ (OAuth on first use) | ✅ full | Add the marketplace, then install (see INSTALL.md) |
| **Claude Code CLI** (terminal) | ✅ | ✅ | ✅ full | `/plugin marketplace add …` + `/plugin install …` |
| **Claude Desktop / claude.ai → Home (chat) mode** | ✅ | ⚠️ connector-style, best-effort | ❌ sub-agents are grayed out; phases run single-threaded/conversational | Add via the app's Plugins UI |
| **Claude Cowork** (Team/Enterprise) | ✅ | ✅ | ✅ | app Plugins UI |
| **OpenAI Codex** | ❌ not supported | ❌ | ❌ | — Codex does not read Claude plugins |

**Recommendation:** point teammates at **Claude Desktop "code mode"** (the Claude Code panel
inside the desktop app). It gives the full experience — skills, the bundled MCP, and the
multi-step experiment automation — without anyone touching a terminal. Home/chat mode is fine for
the standalone review skills (compliance check, fact check, hygiene, keyword research) but is not
where you run a full experiment.

> **Note on Codex:** the original ask mentioned installing this in Codex. Claude Code plugins are
> Anthropic-specific and Codex (OpenAI) can't load them. If Codex support is a real requirement,
> that's a separate build (an OpenAI-format equivalent), not this plugin.

## Requirements

- **Claude subscription** on a paid plan (plugins require Pro/Max/Team/Enterprise).
- **A Paraloom account** with access to the relevant team(s) — the MCP signs in as that user.
- **Python 3.11+** with the tool dependencies: `pip3 install -r plugins/paraloom/tools/requirements.txt`
  (needed for the hygiene check, deliverable manifest, and keyword research). The compliance-PDF
  builder additionally needs `weasyprint` + its system libraries — treat that one as optional
  (the client deliverable is reviewable from its web link without a PDF).
- **DataForSEO credentials** in `~/.dataforseo.env` (for keyword research / Phase 1 demand grounding).
- **Playwright MCP** connected separately if you want automated fact verification (not bundled).

See [`INSTALL.md`](INSTALL.md) for the step-by-step.
