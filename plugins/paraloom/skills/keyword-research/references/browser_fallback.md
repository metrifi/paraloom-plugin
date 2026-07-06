# Browser fallback: Google Ads Keyword Planner via Playwright

Use this path when:

- DataForSEO returns no rows for a long-tail term (regional / very specific phrasings).
- The session wants to verify DataForSEO data against Google's own UI.
- `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` are not set and the user can't get them right now.

> **Major caveat — isolated profile, no login.** The Playwright MCP runs `--isolated`: a fresh browser profile with **no saved Google account**. Keyword Planner requires a signed-in Google Ads account, so this path will hit a sign-in wall unless a human completes Google OAuth in the launched browser during the session. There's no stored credential to fall back on. **Path A (DataForSEO) is the real backend now that `~/.dataforseo.env` exists — prefer it.** Only attempt Path B if someone can sign in interactively; otherwise emit a clear "no demand data available for <term>" note instead.

## Tools used

Playwright exposes browser primitives namespaced `mcp__playwright__*`. The ones this flow uses:

- `mcp__playwright__browser_navigate` — load a URL.
- `mcp__playwright__browser_snapshot` — accessibility-tree snapshot; returns element `ref`s to use as `target` for clicks/typing. This is how you "find" elements (there's no find-by-description tool — you read the snapshot and pick the ref).
- `mcp__playwright__browser_type` — type into an input (`target` = ref, `text` = value, optional `submit: true` to press Enter).
- `mcp__playwright__browser_click` — click an element by `ref`.
- `mcp__playwright__browser_evaluate` — run JS, e.g. `() => document.body.innerText`, to capture the rendered results table as text.
- `mcp__playwright__browser_wait_for` — wait for expected text before reading (Keyword Planner renders results asynchronously).

## Keyword Planner has two relevant tabs

1. **Discover new keywords** — analogous to DataForSEO's `keywords_for_keywords` + `keyword_ideas`. Input a seed; get related ideas with avg monthly searches and competition.
2. **Get search volume and forecasts** — analogous to DataForSEO's `search_volume`. Paste a list of known keywords; get exact-ish monthly volume.

Pick the tab that matches the question:

- "How much volume does this specific phrase get?" → **Get search volume and forecasts**.
- "What else are people searching that's adjacent to this?" → **Discover new keywords**.

## Worked example: volume for `"credit union sun prairie"` in Wisconsin

This is test case #4. The flow is:

1. **Open Keyword Planner.**

   ```
   mcp__playwright__browser_navigate(url="https://ads.google.com/aw/keywordplanner/home")
   ```

   Then `browser_snapshot()`. If the snapshot shows a Google sign-in page, stop — see the caveat above.

2. **Click "Get search volume and forecasts".** Read the snapshot, find the ref for that card/link, and click it.

   ```
   mcp__playwright__browser_snapshot()
   mcp__playwright__browser_click(target="<ref of the 'Get search volume and forecasts' card>",
                                  element="the 'Get search volume and forecasts' card on the Keyword Planner home")
   ```

3. **Set location to Wisconsin** before entering keywords. Re-snapshot, click the Locations chip in the targeting bar (top of the planner), type `Wisconsin`, and select the result.

   ```
   mcp__playwright__browser_snapshot()
   mcp__playwright__browser_click(target="<ref of the Locations targeting chip>", element="the Locations chip")
   mcp__playwright__browser_type(target="<ref of the location search box>",
                                 element="the location search box inside the locations panel",
                                 text="Wisconsin")
   ```

   Re-snapshot and click the `Wisconsin` option that appears.

4. **Enter the seed keyword.**

   ```
   mcp__playwright__browser_type(target="<ref of the multi-line 'Enter keywords' input>",
                                 element="the keyword input labeled 'Enter keywords'",
                                 text="credit union sun prairie")
   ```

   Click the "Get started" / "Get results" submit button (find its ref in the snapshot):

   ```
   mcp__playwright__browser_click(target="<ref of the submit button>",
                                  element="the 'Get started' / 'Get results' submit button")
   ```

5. **Capture the results table.** Wait for the table to render, then read the page text.

   ```
   mcp__playwright__browser_wait_for(text="Avg. monthly searches")
   mcp__playwright__browser_evaluate(function="() => document.body.innerText")
   ```

   Look for a table with columns like:

   | Keyword | Avg. monthly searches | Competition | Top of page bid (low) | Top of page bid (high) |

   (If `innerText` is noisy, target the table directly: `() => document.querySelector('table')?.innerText`.)

6. **Parse into the same JSON shape Path A produces.** The downstream consumer (`research.py`) expects a list of rows like:

   ```json
   [
     {
       "keyword": "credit union sun prairie",
       "search_volume": 320,
       "competition": "LOW",
       "competition_index": null,
       "cpc": null,
       "low_top_of_page_bid": 0.40,
       "high_top_of_page_bid": 1.80,
       "monthly_searches": []
     }
   ]
   ```

   Map Keyword Planner's "Avg. monthly searches" range (e.g. `100–1K`) to a single number using the geometric mean, or take the lower bound — whichever the calling session prefers, but **be consistent within a report and note the choice in the source line**.

7. **Note the source.** When passing browser-derived rows into `research.py`, set the report `source` to `"Google Ads Keyword Planner via browser"` so consumers know the row came from the UI (and may be range-bucketed rather than exact).

## Common gotchas

- **Locations stick across sessions.** If a previous run left location set to "United States", a Wisconsin-only search will return inflated volumes. Always set the location explicitly.
- **Login walls.** Because Playwright runs isolated, the sign-in page is the *default* state, not an edge case. If `browser_snapshot` / `browser_evaluate` returns the Google sign-in page, stop and tell the user — don't try to guess credentials.
- **Volume buckets.** Keyword Planner returns ranges (`100–1K`, `1K–10K`, etc.) for non-spending accounts. Document which bucket-to-number mapping you used.
- **Rate limiting.** Aggressive automated input can trip Google Ads' bot protection. Don't loop more than ~10 lookups per minute.
