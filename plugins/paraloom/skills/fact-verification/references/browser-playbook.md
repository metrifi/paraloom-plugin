# Browser playbook — driving Playwright

Read this before your first navigate call in a verification session. Playwright is this project's standard browser driver (it replaced Claude in Chrome). Tools are namespaced `mcp__playwright__*`.

## Pre-flight

There is **no "connect a browser" step** — Playwright launches and manages its own browser the first time you call `browser_navigate`. The MCP runs `--isolated`, so it's a fresh profile each session with no saved logins. For fact-verification that's fine: every page you need (CU sites, regulator/agency sites) is public.

If `browser_navigate` errors out before loading anything (browser binaries missing, sandbox/network failure), stop and tell the user — verification can't proceed without live source access. (Fix: `npx playwright install chromium`.)

## The standard verify cycle

For each verifiable claim, repeat this loop:

1. **Navigate.** `mcp__playwright__browser_navigate({url})` with the planned URL.
2. **Wait if needed.** Single-page apps render asynchronously. If the content you need may be client-rendered, `mcp__playwright__browser_wait_for({text: "<a phrase you expect>"})` before reading. For static CU pages you usually don't need this.
3. **Read.**
   - `mcp__playwright__browser_snapshot()` is the default read — it returns the accessibility tree (headings, links, text, form fields) and is better than a screenshot. Each interactive element carries a `ref` you can reuse as `target`.
   - If the snapshot is thin or you want raw article text, `mcp__playwright__browser_evaluate({function: "() => document.body.innerText"})` returns the full rendered text.
4. **Find.** If the page is long, narrow with `browser_evaluate` against a selector, e.g. `() => document.querySelector('main')?.innerText` or `() => Array.from(document.querySelectorAll('h2,h3,p')).map(n => n.innerText).join('\n')`. You can also just search the captured text for a phrase from the claim.
5. **Capture.** Pull the verbatim sentence(s) that bear on the claim. Trim only outer whitespace; preserve internal capitalization and punctuation.
6. **Record.** Save URL, source quote, ISO timestamp, and any caveats.
7. **Move on.** Sleep 1–2 seconds before the next navigate.

## Recovery patterns

### Page returned 404 or the navigate failed

- Navigate to the canonical homepage, `browser_snapshot()`, and look in the nav links for the topic. Click through with `browser_click({target: "<ref>", element: "<description>"})`.
- If still not found, the claim becomes `NEEDS_HUMAN_VERIFICATION` with the load error captured as the reason. Do not silently move on.

### The page loaded but the snapshot is mostly nav/footer

- Switch to `browser_evaluate({function: "() => document.body.innerText"})`, which returns the full rendered visible text and handles most JS-rendered content.
- If that's also thin, the content may be lazy-loaded — `browser_wait_for({text})` on an expected phrase, then re-read. Or query a specific container: `() => document.querySelector('main, #content, .content')?.innerText`.

### The page text is dynamically generated (rates, hours)

- Capture both the text *and* the page's `lastModified` via `browser_evaluate({function: "() => document.lastModified"})`, so the report can note recency.
- If the rates appear to be inside an iframe (some CUs embed third-party rate widgets), follow the iframe's `src` URL (`() => document.querySelector('iframe')?.src`), navigate there directly, and verify there. Note the iframe origin in the source URL field.

### A pop-up or cookie banner is blocking interaction

- `browser_snapshot()` to find the accept/dismiss button's `ref`, then `browser_click({target, element})`.
- Reading text usually works regardless — `browser_evaluate(() => document.body.innerText)` returns text behind overlays, so you often don't need to dismiss the banner at all.

### The product/eligibility page exists but doesn't contain the claim's text

- Look at the CU's main navigation (in the snapshot). Try the next-most-likely page (e.g., article said "VA loans" and `/loans` doesn't list them — check `/mortgages`, `/home-loans`, then site search at `/search?q=VA+loans` if exposed).
- If after a reasonable look (≤3 pages) the product still isn't named on the site, treat as `CONTRADICTED` per type-3 strategy, with the source URL set to the product index page and the source quote describing what was searched.

### The site is down or geographically blocked

- Mark all dependent claims `NEEDS_HUMAN_VERIFICATION` with the access error. Do not retry endlessly. Move on; a human can re-run the skill later.

## Off-domain navigation policy

For internal claims (types 1–6), stay on the CU's domain. The CU's website is the authoritative source for "do they offer this product" and "who's their CEO."

For external statistics (type 7) and regulatory claims (type 9), navigate to the cited regulator/agency directly. Don't chase off-domain links from the CU's own site for verification purposes.

For NCUA call-report verification specifically:

- `mapping.ncua.gov` is the lookup tool. Navigate, search by charter number or name, capture the latest call-report row.
- The fields you'll likely want: total assets (TOTAL ASSETS), members (NUMBER OF MEMBERS), branches (NUMBER OF OFFICES). All are quarterly snapshots.

## Rate limiting and courtesy

- 1–2 second pause between navigations. Default to 2 seconds for the same host more than five times in a row.
- Do not crawl. Visit only the pages you need to answer specific claims.
- Don't follow the CU's social media links during verification — that's not the source of truth and adds noise.

## Capturing exact quotes — what counts as "exact"

The `source quote` field must be verbatim text from the source page. Specifically:

- Same words, same order, same capitalization.
- Punctuation preserved.
- You may trim leading/trailing whitespace, ellipses around the quote (use `...` to indicate elision in the middle), and surrounding nav/breadcrumb noise.
- You may NOT paraphrase. If the source says "more than 80,000" and the article says "over 80,000," the quote is "more than 80,000" with a note that the wording differs.

If the relevant content is a table row (rates, branch hours), capture the header + the row. Example:

```
Term   |  APY
12 mo  |  4.50%
```

This is acceptable as the "source quote" because it's verbatim and the structure is necessary for interpretation.
