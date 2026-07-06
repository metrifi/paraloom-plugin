---
name: keyword-research
description: Research keyword search volume, related queries, competition, and Google AI Mode SERP visibility for prompts and topics. Use this skill whenever prioritizing Paraloom prompts, building experiment evidence dossiers, or generating content briefs grounded in real demand. Triggers include "keyword volume", "search volume", "AI search demand", "is there demand for", "keyword research", "AI mode SERP", "what are people searching", or any time the user wants to ground a Paraloom prompt list in real consumer demand data. Use this even when the user does not explicitly say "keyword" — if they're asking whether a topic is worth writing about, whether competitors own a query, or how much real-world traffic a Paraloom prompt represents, this is the right skill.
---

# keyword-research

A research tool for grounding Paraloom prompt prioritization, experiment recommendations, and content briefs in real keyword + AI-search-demand data. Produces per-prompt evidence (search volume, AI Mode visibility, related queries, intent) shaped to drop directly into an experiment's `evidence.md` sidecar.

## When to use this skill

Use whenever the calling session needs to know:

- Which Paraloom prompts represent real consumer demand vs. zero-volume noise
- What Google's AI Mode currently says about a prompt and which sources it cites
- Related queries that could become additional Paraloom prompts
- Intent classification (informational, commercial, transactional) for a prompt set

The skill is the gateway to two execution paths — a DataForSEO API path (default) and a Google Ads Keyword Planner browser fallback. Pick based on what's available; the rest of this document explains how.

## Two paths, one skill

### Path A — DataForSEO (default, programmatic)

Use this whenever `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` are present in the environment. Reliable, structured JSON, low per-request cost, covers all the endpoints we need.

The four endpoint wrappers live in `scripts/`. Each accepts CLI args, writes structured JSON to stdout, exits non-zero on error, and never logs credentials.

| Need | Script | Endpoint |
|------|--------|----------|
| Exact monthly volume + competition + CPC for known keywords | `scripts/search_volume.py` | `/v3/keywords_data/google_ads/search_volume/live` |
| Related keywords expanding from a seed | `scripts/keywords_for_keywords.py` | `/v3/keywords_data/google_ads/keywords_for_keywords/live` |
| Keyword ideas with intent classification | `scripts/keyword_ideas.py` | `/v3/dataforseo_labs/google/keyword_ideas/live` |
| Google AI Mode answer + cited sources for a query | `scripts/ai_mode_serp.py` | `/v3/serp/google/ai_mode/live/advanced` |

A fifth, optional, AI Overview endpoint (`/v3/serp/google/organic/live/advanced` with `device: desktop`, parsed for `ai_overview`) is documented in `references/dataforseo.md` but not wrapped — call it via `scripts/raw_post.py` if needed.

The end-to-end orchestrator is `scripts/research.py`. It accepts a Paraloom prompt list (file or inline), translates each prompt into 3–6 candidate keyword phrases, runs volume + AI Mode lookups, and emits the markdown report (or JSON when `--format json`).

### Path B — Browser fallback via Playwright

Reach for this when DataForSEO returns no data for a long-tail term, when the session wants to verify against Google's own UI, or when credentials are not available. The flow is documented in detail in `references/browser_fallback.md` — read that file when this path is needed.

The short version: navigate to <https://ads.google.com/aw/keywordplanner/home> with Playwright (`mcp__playwright__browser_navigate`), snapshot the page to find the seed input field, type the keywords in, capture the volume table with `browser_evaluate(() => document.body.innerText)`, and parse into the same JSON shape Path A produces.

> **Caveat — isolated profile:** the Playwright MCP runs `--isolated`, so the browser has **no saved Google login**. Keyword Planner requires a signed-in Google Ads account, so this fallback will land on a sign-in wall unless someone completes the OAuth dance in the launched browser. Treat Path B as degraded. Now that DataForSEO credentials are in place (`~/.dataforseo.env`), Path A is the real backend — prefer it, and surface a clear "no demand data available" note rather than forcing Path B if sign-in isn't possible.

## Core workflow

The Paraloom agent calls this skill with a prompt list (markdown bullets is the canonical input shape produced by the Paraloom Connector's `list-prompts` tool). The skill follows this flow:

1. **Parse the prompt list.** Each bullet → one prompt entry with full natural-language text.
2. **Translate prompts → candidate keyword phrases.** This is critical — DataForSEO and Keyword Planner want short phrases like "best cd rates wisconsin retirees", not the full natural-language question. The calling Claude session should generate 3–6 candidate phrases per prompt and pass them to `scripts/research.py` via the `--keywords-per-prompt` JSON file (see `references/input_format.md`). If candidate phrases are not provided, `research.py` will use a built-in heuristic (strip stopwords, keep entities + intent words) but the model-driven approach is much better and should be preferred.
3. **Run volume + intent on every candidate phrase.** `research.py` batches up to 1000 keywords per `search_volume/live` call to control cost.
4. **Run AI Mode SERP on each original prompt** (not on the keyword phrases — Google's AI Mode parses natural language well, so the prompt itself is the right input).
5. **Assemble the report.** Markdown by default, JSON when `--format json`.

The prompt-to-keyword mapping is preserved end-to-end so the evidence dossier can show "this prompt was scored against these N keyword phrases, here are the volumes." Don't lose that traceability.

## Output format

The default output is a single markdown report shaped for inclusion in an experiment's `evidence.md` sidecar. The exact structure is in `references/output_format.md`. The high-level shape:

```markdown
# Keyword research — <topic>

**Generated:** <ISO timestamp>
**Source:** DataForSEO (or "Google Ads Keyword Planner via browser")
**Location:** <e.g., Wisconsin,United States>

## Per-prompt results

### Prompt: "<full prompt text>"

| Keyword phrase | Monthly volume | Competition | CPC range | Search intent |
|----------------|----------------|-------------|-----------|---------------|
| ... | ... | ... | ... | ... |

**AI Mode SERP for this prompt:**
- Cited sources: [domain1](url1), [domain2](url2), ...
- AI answer summary: <2–3 sentences quoting key claims>
- Owned org appearance: yes/no
- Competitor appearance: <list>

### Prompt: "<next prompt>"
...

## Aggregate signals

- Highest-volume prompts: <top 3>
- Prompts with strong AI Mode citation by competitors: <list>
- Prompts with no AI Mode answer: <list — likely first-to-publish candidates>
- Prompts with zero search volume: <list — flag for possible deprecation>
```

JSON mode (`--format json`) returns the same data as a structured object — see `references/output_format.md` for the schema.

## Cost discipline

DataForSEO charges per request. The skill enforces three guardrails so research runs don't surprise anyone with a bill:

- **Batching.** `search_volume/live` accepts up to 1000 keywords per call; `research.py` batches accordingly.
- **24h cache.** Every endpoint script caches responses to `~/.cache/keyword-research/<endpoint>/<payload-hash>.json` for 24 hours. The cache is keyed on `(endpoint, full payload)` so identical lookups within a day cost nothing. Pass `--no-cache` to force a fresh call.
- **Cost preview.** Before any run that would exceed 50 keywords, `research.py` prints an estimated cost (count × per-call rate) and waits for `--confirm-cost` unless the flag is already set.

The cache directory and TTL are documented in `references/dataforseo.md`. If the calling session is doing exploratory work that should not be cached (e.g., a true cost-estimate run), use `--no-cache`.

## Authentication

Path A reads `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` from the environment. The scripts construct an HTTP Basic auth header from those values and never log or echo them.

If the env vars aren't set, the auth helper auto-loads a `.dataforseo.env` file from (in order): `$DATAFORSEO_ENV`, the current working directory, any parent directory walking up from CWD, then `~/.dataforseo.env`. The file is plain `KEY=value` per line with `#` comments allowed. Explicit env vars always win over the file, so callers can still override per-invocation.

If neither path produces credentials (or the file still has the placeholder values), the script exits with a clear message pointing the user to set them or fall back to Path B.

For Path B, Keyword Planner requires a signed-in Google Ads account. The Playwright MCP runs `--isolated` (no saved login), so this path lands on a sign-in wall unless someone completes Google OAuth in the launched browser. Prefer Path A.

## Non-goals

This skill does not:

- Optimize content or rewrite copy — that's a separate skill.
- Persist keywords into the Paraloom database. The output is an evidence file, not a Paraloom record.
- Scrape Google search results directly without DataForSEO or Keyword Planner. That's brittle and against TOS.

## Reference files

The detailed reference material lives next to this file. Read the relevant one when you need it; don't preload them all.

- `references/dataforseo.md` — endpoint payload examples, location/language format, competition value scale, cache layout, fifth optional endpoint
- `references/browser_fallback.md` — full Playwright flow with worked example and parser sketch
- `references/input_format.md` — Paraloom prompt list parser + prompt-to-keyword mapping schema
- `references/output_format.md` — exact markdown template + JSON schema
- `tests/test_cases.md` — the four test cases the skill must pass

## Test cases

Run with `bash tests/run_tests.sh` after credentials are exported. Tests #1–3 hit DataForSEO; test #4 is browser-driven and is documented but skipped in the automated runner. Each test prints `PASS` or `FAIL` and a short reason; the runner exits non-zero if any test fails.

The four cases:

1. Search volume for `"first time homebuyer loan dane county wisconsin"` in Wisconsin returns a structured row.
2. A Paraloom prompt list of 5 prompts produces a per-prompt report with 5 prompt sections.
3. An unknown long-tail keyword returns 0 volume gracefully (not an error).
4. Browser fallback: navigate to Keyword Planner, enter `"credit union sun prairie"`, capture the volume table, parse into JSON.
