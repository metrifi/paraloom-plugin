# The one-paste install prompt

Give this to a teammate to install and set up the Paraloom plugin with almost no manual work.
It runs in **Claude Desktop → code mode** (the Claude Code panel in the desktop app) or the
Claude Code CLI. It does **not** work in regular chat mode — see [`INSTALL.md`](INSTALL.md) for that.

## How you (Ryan) prepare it

1. Copy the prompt in the box below.
2. Replace `PASTE_LOGIN_HERE` and `PASTE_PASSWORD_HERE` with the shared DataForSEO credentials.
3. Send the filled-in prompt to your teammate with one instruction: *"Open Claude Desktop, switch to
   code mode, paste this, and approve the steps it asks about."*

## How your teammate uses it

1. Open **Claude Desktop**, switch to **code mode** (the Claude Code panel).
2. Paste the prompt and send it.
3. When Claude asks permission to run a command, click **Allow** (or turn on auto-accept).
4. When Claude finishes, run `/reload-plugins`, then `/paraloom:start`. The first time it touches
   Paraloom you'll be asked to sign in at `app.paraloom.ai` — approve it. That's the only sign-in.

---

## The prompt (copy everything in this box)

```text
You are setting up the Paraloom plugin on my Mac for me. I am not technical — do everything
yourself by running the commands, explain each step in plain language, and don't ask me to open a
terminal. If a step needs my permission, ask and wait. Go in this order and report what happened:

1. Install the plugin:
   - Run: claude plugin marketplace add metrifi/paraloom-plugin
   - Run: claude plugin install paraloom@paraloom-tools --scope user
   If either command isn't found, tell me my Claude Code may be out of date and stop.

2. Make sure Python 3 and the tool dependencies are installed:
   - Run: python3 --version
   - If Python 3 is missing: install it with Homebrew (run: brew install python). If Homebrew
     isn't installed, install it from https://brew.sh first, then install Python. If none of that
     works, tell me to download Python from https://www.python.org/downloads/ and stop.
   - Then install the packages: pip3 install --user markdown-it-py pyspellchecker requests beautifulsoup4
     If that errors with "externally managed environment", run it again with --break-system-packages
     added on the end.

3. Save my DataForSEO credentials so keyword research works. If the file ~/.dataforseo.env does not
   already exist, create it with exactly these two lines. Do not print the values back to me.
       DATAFORSEO_LOGIN=PASTE_LOGIN_HERE
       DATAFORSEO_PASSWORD=PASTE_PASSWORD_HERE

4. Check whether a Playwright browser tool is available (used for automated fact-checking). Look for
   a tool whose name contains "browser_navigate". If it isn't there, just tell me fact-checking will
   fall back to manual verification for now — do not try to install it.

5. Wrap up: confirm the plugin installed, confirm the Python packages installed, and confirm the
   credentials file exists. Then tell me to (a) run /reload-plugins to activate the plugin, (b) run
   /paraloom:start to begin, and (c) expect a one-time app.paraloom.ai sign-in the first time it
   uses Paraloom. List anything that still needs me.
```
