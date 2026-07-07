# Installing the Paraloom plugin

> The marketplace is **`paraloom-tools`**, the plugin is **`paraloom`**, and it lives in the public
> GitHub repo **`metrifi/paraloom-plugin`**.

## Read this first: installing is two separate steps

This trips everyone up, so it's worth stating plainly. Getting the plugin working is **two
things**, done in two different places:

1. **Install the plugin** (its skills) — via the Plugins UI or a command.
2. **Authorize the Paraloom connector** (its data connection) — in **Settings → Connectors**,
   a one-time sign-in.

Installing the plugin does **not** auto-connect Paraloom. The bundled Paraloom MCP shows up as a
**connector** you approve once in Settings → Connectors. Until you do, the skills load but any
Paraloom action (list teams, create a campaign) fails. This is normal Claude Desktop behavior for
any plugin that ships an MCP server — it's not specific to this plugin.

A third thing is needed for **keyword research and the hygiene check** to work: Python packages and
DataForSEO credentials (see [Prerequisites](#prerequisites-python--credentials)). The paste-once
prompt route below sets those up for you; the UI route does not.

---

## Route A — Claude Desktop UI (recommended, no terminal)

This is the smoothest way to get the plugin in.

1. **Settings → Plugins → Add → Add marketplace → Add from a repository.**
2. Enter `https://github.com/metrifi/paraloom-plugin` and **Sync**, then **Install** the `paraloom`
   plugin. It shows "ready to use."
3. **Authorize Paraloom:** open the **Connectors** tab, click **Install** next to **Paraloom** (the
   button then changes to **Connect**), click **Connect**, and sign in at `app.paraloom.ai`. Claude
   shows "Connected." This one-time connection is the step that actually wires up Paraloom.
4. **Restart Claude** (fully quit and reopen) if a chat you already had open doesn't see the plugin.
5. Set up the Python packages + DataForSEO creds once — see [Prerequisites](#prerequisites-python--credentials).

Then start a chat and say *"set up this project"* or *"run an experiment for a team on a topic"*,
or run `/paraloom:start`.

---

## Route B — Paste-once prompt (also installs Python deps + your creds)

Use this when you want one paste to handle *everything*, including the Python packages and DataForSEO
credentials that Route A leaves to you. It runs in **Claude Desktop code mode** (the Claude Code
panel) or the Claude Code CLI — a session that can run commands.

1. Open the prompt in [`install-prompt.md`](install-prompt.md) (Ryan sends the version with the
   DataForSEO credentials already filled in).
2. Paste it into a **code-mode** session and approve the steps.
3. When it finishes, **fully quit and reopen** Claude (a running session started before the install
   won't see the new plugin, and `/reload-plugins` isn't always available), then run `/paraloom:start`.
4. Authorize Paraloom in **Settings → Connectors** as in Route A, step 3.

Honest note: this route is more powerful (it does the Python + creds) but clunkier than Route A —
it needs a code-mode session and a restart. If Python and creds are already set up on the machine,
Route A is simpler.

---

## Route C — Command line

Inside a Claude Code session (Desktop code mode or the `claude` CLI):
```
/plugin marketplace add metrifi/paraloom-plugin
/plugin install paraloom@paraloom-tools
/reload-plugins
```
Then authorize Paraloom in Settings → Connectors, and do the [Prerequisites](#prerequisites-python--credentials).

To test without installing, point Claude at a local checkout:
```bash
git clone https://github.com/metrifi/paraloom-plugin
claude --plugin-dir ./paraloom-plugin/plugins/paraloom
```

---

## Route D — Upload a zip (no repo access needed)

For a machine that shouldn't pull from GitHub. **Settings → Plugins → Add → Upload plugin**, and
select a zip **whose root is the plugin** (contains `.claude-plugin/plugin.json` at the top level).

Build that zip from a checkout — zip the *plugin folder's contents*, not the whole repo:
```bash
cd paraloom-plugin/plugins/paraloom
zip -rq ~/paraloom-plugin.zip . -x '*.DS_Store'
```
(A prebuilt `dist/paraloom-plugin.zip` is produced in the repo for convenience.) Then authorize the
Paraloom connector and do the Prerequisites, same as the other routes.

---

## Prerequisites: Python + credentials

Needed for keyword research and the hygiene check (Route B installs these for you; the others don't):

1. A **paid Claude plan** (Pro / Max / Team / Enterprise) — plugins don't work on free.
2. A **Paraloom login** with access to your team(s).
3. **Python 3** + packages:
   ```bash
   pip3 install --user markdown-it-py pyspellchecker requests beautifulsoup4
   ```
   (If pip says "externally managed environment," add `--break-system-packages`.)
4. **DataForSEO credentials** — create `~/.dataforseo.env`:
   ```
   DATAFORSEO_LOGIN=your-login
   DATAFORSEO_PASSWORD=your-password
   ```
   Ask Ryan for the shared credentials.
5. **A real browser tool** for fact-checking (Playwright MCP or Claude-in-Chrome). Not bundled; if
   absent, fact-checking falls back to manual verification.

---

## Everyday use

- **Run an experiment:** *"run an experiment for `<team>` on `<topic>`"*, or step through
  `/paraloom:exp-research` → `/paraloom:exp-build` → `/paraloom:exp-review` → `/paraloom:exp-deliver`.
- **Check status:** `/paraloom:exp-status` or *"where are we with `<slug>`?"*
- **Client answered:** `/paraloom:exp-revise`.
- **Just a review:** ask for a compliance / fact / hygiene / keyword check and the matching skill fires.

See the README's "How to use it" for a fuller list of prompts.

## Updating / removing

```
/plugin marketplace update paraloom-tools
/plugin update paraloom@paraloom-tools
/reload-plugins
```
```
/plugin uninstall paraloom@paraloom-tools
/plugin marketplace remove paraloom-tools
```

---

## Troubleshooting

- **Claude says Paraloom "needs a sign-in this session can't do" / refuses to call it:** it's
  probably already connected — tell it to **just try the call**. The Paraloom connection is a
  one-time authorization in **Settings → Connectors**, not something a chat has to perform. Once
  that connector shows connected, the tools work.
- **`/paraloom:start` is "unknown command" right after install:** the running session started before
  the plugin loaded. **Fully quit and reopen Claude** (Cmd+Q on Mac), then try again. `/reload-plugins`
  works only in the Claude Code CLI, not every Desktop surface.
- **Plugin installed but Paraloom tools missing:** you installed the plugin but haven't authorized
  the connector. Go to **Settings → Connectors → Paraloom → sign in**.
- **Zip upload rejected — "missing .claude-plugin/plugin.json":** you zipped the whole repo; the
  uploader wants a zip whose **root** is the plugin. See Route D.
- **Keyword research / hygiene errors on a missing Python module:** do the Prerequisites `pip3
  install` (add `--break-system-packages` if asked).
- **Keyword research returns no volume:** `~/.dataforseo.env` is missing or empty.
- **Skills don't show up after install:** `rm -rf ~/.claude/plugins/cache`, restart, reinstall.
