# Playwright (browser) setup prompt

The Paraloom plugin's **fact-checking** needs a real browser to verify claims against live
websites. That browser is the **Playwright MCP**. It isn't bundled with the plugin — each person
sets it up once. This prompt does it for them.

## How your employee uses it

Runs in **Claude Desktop → code mode** (the Claude Code panel) or the Claude Code CLI — a session
that can run commands. Paste the prompt below and approve the steps. It needs **Node.js** (the
prompt installs it if missing).

---

## The prompt (copy everything in this box)

```text
Set up the Playwright browser tool on my Mac so the Paraloom plugin can fact-check against live
websites. I am not technical — do everything yourself by running the commands, explain each step in
plain language, and don't make me use a terminal. Ask before any step that needs my permission.

1. Check Node.js is installed:
   - Run: node --version
   - If it's missing, install it with Homebrew (run: brew install node). If Homebrew isn't
     installed, install it from https://brew.sh first, then install Node. If none of that works,
     tell me to download Node from https://nodejs.org and stop.

2. Add the Playwright browser tool to Claude:
   - Run: claude mcp add playwright -s user -- npx @playwright/mcp@latest --isolated --output-dir "$HOME/Library/Caches/playwright-mcp"
   - If it says a server named "playwright" already exists, that's fine — it's already set up.

3. Download the browser it uses (one-time, can take a minute):
   - Run: npx playwright install chromium

4. Confirm it registered:
   - Run: claude mcp list
   - You should see "playwright" in the list (it may say "connecting" until the next restart).

5. Wrap up: tell me to fully quit and reopen Claude (Cmd-Q, then relaunch) so it loads the browser
   tool. After that, fact-checking in Paraloom experiments works automatically. List anything that
   still needs me.
```

## Notes

- **Desktop chat mode can't do this** — the command has to run in code mode or the CLI. If someone
  only uses plain chat, fact-checking falls back to manual verification.
- The exact server this registers (verified working): `npx @playwright/mcp@latest --isolated
  --output-dir ~/Library/Caches/playwright-mcp`, at **user** scope, so it's available in every
  project. To remove it: `claude mcp remove playwright -s user`.
