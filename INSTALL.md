# Installing the Paraloom plugin

This is the plugin that replaces cloning the `paraloom-agent` repo. Pick the path that matches how
you use Claude. **Most of the team should use Option A (Claude Desktop, code mode).**

> Throughout, the marketplace is named **`paraloom-tools`** and the plugin is named **`paraloom`**.
> It lives in the public GitHub repo **`metrifi/paraloom-plugin`**.

---

## Before you start (one-time, per machine)

1. **Be on a paid Claude plan** (Pro, Max, Team, or Enterprise). Plugins don't work on free.
2. **Have a Paraloom login** with access to your team(s). The plugin's Paraloom connector signs in
   as you.
3. **Install the Python tool dependencies** (for the hygiene check, keyword research, and
   deliverable builder). In a terminal:
   ```bash
   pip3 install markdown-it-py pyspellchecker requests beautifulsoup4
   ```
   Optional (only for generating the compliance **PDF** — the deliverable is also reviewable from
   its web link without it): `pip3 install weasyprint` plus, on macOS, `brew install glib pango cairo`.
4. **DataForSEO credentials** (for keyword research): create `~/.dataforseo.env` with:
   ```
   DATAFORSEO_LOGIN=your-login
   DATAFORSEO_PASSWORD=your-password
   ```
   Ask Ryan for the shared credentials if you don't have them.

---

## Option A — Claude Desktop, code mode (recommended)

"Code mode" is the Claude Code panel inside the Claude Desktop app. This gives the full toolkit.

1. Open **Claude Desktop** and switch into **code mode** (the Claude Code panel).
2. In that panel, add the marketplace and install the plugin:
   ```
   /plugin marketplace add metrifi/paraloom-plugin
   /plugin install paraloom@paraloom-tools
   ```
3. Run `/reload-plugins` (or restart the panel).
4. **Connect Paraloom:** the first time a Paraloom tool is used, you'll be prompted to sign in to
   `app.paraloom.ai`. Approve it. (If you're already signed into Paraloom in that browser, it's one
   click.)
5. **Start:** open the folder you want to keep this customer's work in, then run `/paraloom:start`.
   That primes the operating context and routes you to the right next step. Or just say what you
   want in plain language: *"set up this project"*, *"run an experiment for Heartland on
   first-time homebuyers"*, *"check in on the vehicle-refinance one"*.

---

## Option B — Claude Code CLI (terminal)

If you use the `claude` command in a terminal:

```bash
claude
# then, inside Claude Code:
/plugin marketplace add metrifi/paraloom-plugin
/plugin install paraloom@paraloom-tools
/reload-plugins
```

Then the same first-run steps as Option A (sign into Paraloom on first tool use, run
`/paraloom:start` from your working folder).

You can also test without installing by pointing Claude at a local checkout:
```bash
git clone https://github.com/metrifi/paraloom-plugin
claude --plugin-dir ./paraloom-plugin/plugins/paraloom
```

---

## Option C — Claude Desktop / claude.ai, home (chat) mode

Regular chat mode can use the **skills** (compliance check, fact check, hygiene, keyword research,
status) but **not** the full multi-step experiment automation (sub-agents are disabled there).
Use this for one-off reviews, not for running an experiment end to end.

1. In the app, open the **+** menu → **Plugins** → **Add plugin / marketplace**.
2. Add the repository `metrifi/paraloom-plugin` as a marketplace.
3. Install **paraloom** from it.
4. Sign into Paraloom when prompted.

---

## Everyday use

- **Run an experiment:** `/paraloom:exp-research` → (wait for responses) → `/paraloom:exp-build` →
  `/paraloom:exp-review` → `/paraloom:exp-deliver`. Or let `/paraloom:start` drive it from a plain
  request. The suite runs without a draft-review stop; the two human gates are the **FI sign-off**
  and the **send-approval** on the client email.
- **Check status:** `/paraloom:exp-status` or *"where are we with <slug>?"*
- **Client answered:** `/paraloom:exp-revise`
- **Just a review:** `/paraloom:ncua-compliance-review`, `/paraloom:fact-verification`, etc. fire on
  their own when you ask for that kind of check.

## Updating

```
/plugin marketplace update paraloom-tools
/plugin update paraloom@paraloom-tools
/reload-plugins
```

## Removing

```
/plugin uninstall paraloom@paraloom-tools
/plugin marketplace remove paraloom-tools
```

---

## Troubleshooting

- **`/plugin` not recognized:** update Claude Code (`brew upgrade claude-code` or
  `npm install -g @anthropic-ai/claude-code@latest`), then restart.
- **Paraloom tools don't appear / calls fail:** the connector isn't authorized yet. Trigger any
  Paraloom action and complete the `app.paraloom.ai` sign-in. Confirm your account has access to
  the team.
- **A Python tool errors on a missing module:** run the `pip3 install …` line from the prereqs.
  For the compliance PDF specifically, install `weasyprint` and (macOS) the Homebrew libs.
- **Keyword research returns no volume:** `~/.dataforseo.env` is missing or empty.
- **Fact verification can't browse:** the Playwright MCP isn't connected in your environment (it's
  not bundled). Fact checks fall back to manual verification until it's added.
- **Skills don't show up after install:** `rm -rf ~/.claude/plugins/cache`, restart, reinstall.
