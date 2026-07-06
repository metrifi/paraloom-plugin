# Installing the Paraloom plugin

This plugin replaces cloning the `paraloom-agent` repo. **Most people should use the easy way
below** — you paste one prompt and Claude does the whole setup for you.

> The marketplace is named **`paraloom-tools`**, the plugin is **`paraloom`**, and it lives in the
> public GitHub repo **`metrifi/paraloom-plugin`**.

---

## The easy way — paste one prompt (recommended, non-technical friendly)

You don't run any commands yourself. Claude installs the plugin, installs the Python bits, saves
your keyword-research credentials, and checks everything.

1. Open the **Claude Desktop** app.
2. Switch to **code mode** (the Claude Code panel — the coding view, not the normal chat).
3. Open the [`install-prompt.md`](install-prompt.md) prompt (Ryan will send you the filled-in
   version). Paste it and send.
4. When Claude asks permission to run a step, click **Allow**.
5. When it's done, type `/reload-plugins`, then `/paraloom:start`.
6. The first time it uses Paraloom you'll get a one-time sign-in at `app.paraloom.ai` — approve it.

That's it. If a Paraloom experiment folder is what you want, Claude tells you what to do next from
there. See [`install-prompt.md`](install-prompt.md) for the prompt itself and notes for whoever
distributes it.

> **Why code mode?** Only code mode can run commands and install plugins for you. Regular chat mode
> can't — for that, see "Chat / home mode" near the bottom.

---

## Manual install (if you'd rather do it yourself)

**One-time prerequisites**

1. A **paid Claude plan** (Pro, Max, Team, or Enterprise) — plugins don't work on free.
2. A **Paraloom login** with access to your team(s).
3. **Python 3** with the tool packages:
   ```bash
   pip3 install --user markdown-it-py pyspellchecker requests beautifulsoup4
   ```
   (If pip says "externally managed environment," add `--break-system-packages` to the end.)
   Optional, only for the compliance **PDF** (the deliverable is also readable from its web link):
   `pip3 install weasyprint` plus, on macOS, `brew install glib pango cairo`.
4. **DataForSEO credentials** for keyword research — create `~/.dataforseo.env`:
   ```
   DATAFORSEO_LOGIN=your-login
   DATAFORSEO_PASSWORD=your-password
   ```
   Ask Ryan for the shared credentials.

**Install the plugin** — inside a Claude Code session (Desktop code mode or the `claude` CLI):
```
/plugin marketplace add metrifi/paraloom-plugin
/plugin install paraloom@paraloom-tools
/reload-plugins
```
Then sign into `app.paraloom.ai` the first time a Paraloom tool runs, and start with
`/paraloom:start` from the folder you want this customer's work saved in.

To test without installing, point Claude at a local checkout:
```bash
git clone https://github.com/metrifi/paraloom-plugin
claude --plugin-dir ./paraloom-plugin/plugins/paraloom
```

---

## Chat / home mode (Claude Desktop or claude.ai, normal chat)

Regular chat mode can use the **review skills** (compliance check, fact check, hygiene, keyword
research, status) but **not** the full experiment automation (sub-agents are disabled there). Use
it for one-off reviews, not for running an experiment end to end.

1. In the app, open the **+** menu → **Plugins**.
2. Add the repository `metrifi/paraloom-plugin` as a marketplace.
3. Install **paraloom** from it, and sign into Paraloom when prompted.

---

## Everyday use

- **Run an experiment:** just say *"run an experiment for `<team>` on `<topic>`"*, or step through
  `/paraloom:exp-research` → `/paraloom:exp-build` → `/paraloom:exp-review` → `/paraloom:exp-deliver`.
  The two human gates are the **FI sign-off** and the **send-approval** on the client email.
- **Check status:** `/paraloom:exp-status` or *"where are we with `<slug>`?"*
- **Client answered:** `/paraloom:exp-revise` or *"the client responded — apply it and push a revision."*
- **Just a review:** ask for a compliance / fact / hygiene / keyword check and the matching skill fires.

See the README's "How to use it" section for a fuller list of example prompts.

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
- **Paraloom tools don't appear / calls fail:** you haven't signed in yet. Trigger any Paraloom
  action and complete the `app.paraloom.ai` sign-in. Confirm your account has access to the team.
- **A Python tool errors on a missing module:** run the `pip3 install --user …` line above (add
  `--break-system-packages` if asked). For the compliance PDF, also install `weasyprint`.
- **Keyword research returns no volume:** `~/.dataforseo.env` is missing or empty.
- **Fact verification can't browse:** the Playwright MCP isn't connected (it's not bundled). Fact
  checks fall back to manual verification until it's added.
- **Skills don't show up after install:** `rm -rf ~/.claude/plugins/cache`, restart, reinstall.
