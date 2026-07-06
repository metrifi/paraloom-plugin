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

## Install

**Easiest (no commands, non-technical friendly):** in **Claude Desktop → code mode**, paste the
prompt in [`install-prompt.md`](install-prompt.md) and approve the steps. Claude installs the
plugin, installs the Python bits, saves your DataForSEO credentials, and checks everything — then
you run `/reload-plugins` and `/paraloom:start`. Ryan can hand teammates a version of that prompt
with the credentials already filled in, so they truly do nothing but paste and approve.

**Prefer to do it yourself?** Inside a Claude Code session (Desktop code mode or the CLI):
```
/plugin marketplace add metrifi/paraloom-plugin
/plugin install paraloom@paraloom-tools
/reload-plugins
```
plus a one-time `pip3 install --user markdown-it-py pyspellchecker requests beautifulsoup4` and a
`~/.dataforseo.env` with your DataForSEO login. Sign into `app.paraloom.ai` on first use.

Full step-by-step for every surface (including chat mode via **+ → Plugins**), prerequisites, and
troubleshooting: [`INSTALL.md`](INSTALL.md).

> Requires a paid Claude plan and a Paraloom login. The `metrifi/paraloom-plugin` marketplace goes
> live once the repo is pushed (see the note near the bottom).

## How to use it (just talk to it)

You don't memorize commands. Say what you want in plain language and the `start` router maps it to
the right step; every skill is also directly invocable as `/paraloom:<name>`. Run from the folder
you want this customer's work saved in — experiments land in `experiments/<slug>/` there.

**Start / run an experiment**
- *"Set up this project for `<credit union>`"* — checks the stack and asks the three scoping questions.
- *"Run an experiment for `<team>` on `<topic>`"* — kicks off the whole suite: research demand →
  design → draft → the four-check review battery → package the deliverable. It runs start to finish
  and only stops at the FI sign-off and before any client email.
- *"Just research demand for `<topic>` first, don't write anything yet"* — a dry run: keyword-grounded
  prompt triage with no writes to Paraloom.

**Check where things stand**
- *"Where are we with `<slug>`?"* · *"What needs me?"* · *"Status across the board"* — current phase,
  the Paraloom IDs, and anything waiting on a human.

**Deliverables**
- *"List the deliverables for `<team>`"* · *"What's live for `<team>`?"* — pulls them from Paraloom.
- *"Give me the client link for `<slug>`"* — the `/d/<token>` URL.
- *"Ship the `<slug>` deliverable to the client"* — builds and pushes it; the notification email only
  sends on your explicit OK.

**Revisions (the client round-trip)**
- *"Did the client respond on `<slug>`?"* — checks the deliverable for new answers, threads, checklist
  confirmations, and opt-outs.
- *"The client answered — apply it and push a revision"* — applies their input through the methodology
  (not as raw edits), re-runs the review battery if the article changed, and pushes a new revision.
  No-ops cleanly when there's nothing new.
- *"Re-verify the items the client confirmed"* — a confirmation isn't a verification; this re-checks
  them against the live site / source before trusting them.

Prefer explicit commands? `/paraloom:exp-research`, `/paraloom:exp-build`, `/paraloom:exp-review`,
`/paraloom:exp-deliver`, `/paraloom:exp-revise`, `/paraloom:exp-status`, `/paraloom:project-setup`,
and `/paraloom:start`.

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
