# DataForSEO reference

Read this when you need endpoint payload shapes, the location/language vocabulary, or the cache layout. The wrapper scripts already encode this — this file exists so a future session doesn't have to dig through DataForSEO's docs.

## Authentication

HTTP Basic, login + password from a DataForSEO account. The wrappers read these from the environment:

- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`

The `Authorization` header is built as `Basic <base64(login:password)>`. The shared helper `scripts/_dfs.py` handles this; the actual values are never logged or echoed.

If either env var is missing, the wrappers exit with a clear message and a pointer to the browser fallback.

## Location and language

DataForSEO accepts either `location_code` (numeric) or `location_name` (string). We use `location_name` because it's self-documenting. Examples:

- `"United States"`
- `"Wisconsin,United States"` — state-level
- `"Madison,Wisconsin,United States"` — DMA / city level (when supported)

For `language_name`, English-language US targeting uses `"English"`. Spanish in the US is `"Spanish"`. The valid sets are listed in DataForSEO's docs; mismatches return a clear error.

## Endpoint payload examples

Each example is a single well-formed request body. The wrappers wrap dicts in a list automatically (DataForSEO accepts an array of task objects per call).

### 1. Search volume (exact)

`POST /v3/keywords_data/google_ads/search_volume/live`

```json
{
  "keywords": [
    "first time homebuyer loan dane county wisconsin",
    "best cd rates wisconsin retirees"
  ],
  "location_name": "Wisconsin,United States",
  "language_name": "English"
}
```

Up to 1000 keywords per call. `search_volume` returns `0` for terms with no measured volume (it is **not** an error).

### 2. Keywords for keywords (related)

`POST /v3/keywords_data/google_ads/keywords_for_keywords/live`

```json
{
  "keywords": ["cd rates wisconsin"],
  "location_name": "Wisconsin,United States",
  "language_name": "English",
  "limit": 200
}
```

### 3. Keyword ideas (with intent)

`POST /v3/dataforseo_labs/google/keyword_ideas/live`

```json
{
  "keywords": ["cd rates wisconsin"],
  "location_name": "Wisconsin,United States",
  "language_name": "English",
  "limit": 200,
  "include_serp_info": false
}
```

This is the only endpoint that returns `search_intent_info.main_intent` (one of `informational`, `commercial`, `transactional`, `navigational`). Use it when intent classification matters.

### 4. Google AI Mode SERP

`POST /v3/serp/google/ai_mode/live/advanced`

```json
{
  "keyword": "best cd rates wisconsin retirees",
  "location_name": "Wisconsin,United States",
  "language_name": "English"
}
```

The response shape varies by query — sometimes the AI Mode block sits at `tasks[].result[].items[]`, sometimes inline at `tasks[].result[]`. The wrapper walks defensively rather than assume one shape, and pulls every `http(s)` URL it finds as a citation candidate.

### 5. AI Overview (optional, not wrapped)

`POST /v3/serp/google/organic/live/advanced`

```json
{
  "keyword": "best cd rates wisconsin retirees",
  "location_name": "Wisconsin,United States",
  "language_name": "English",
  "device": "desktop"
}
```

Look for the `ai_overview` element inside the SERP item array. Use `scripts/raw_post.py` if you need this.

## Reading competition values

`competition` is one of `LOW`, `MEDIUM`, `HIGH`, or `null` (no data). It's the Google Ads advertiser-competition signal — useful as an organic-difficulty proxy but not a perfect SEO difficulty score.

`competition_index` is 0–100 (higher = more competition). It is not always populated.

A keyword with `null` competition usually means insufficient data, not "no competition". Treat null as unknown.

## Cache layout

Each endpoint script caches POST bodies for 24 hours under:

```
~/.cache/keyword-research/<endpoint-slug>/<sha256-of-payload>.json
```

The slug replaces `/` with `__`. Example:

```
~/.cache/keyword-research/keywords_data__google_ads__search_volume__live/<hash>.json
```

The cache key is the full sorted JSON payload, so changing location, language, or keyword order produces a new cache entry. Pass `--no-cache` to any wrapper to force a fresh call.

The cache writes are best-effort — disk failures are swallowed rather than crashing the lookup.

## Cost

Public list prices in May 2026 (these change — verify in DataForSEO's dashboard before running large batches):

- search_volume/live ~ $0.05 per call (up to 1000 keywords per call)
- keywords_for_keywords/live ~ $0.05 per call
- dataforseo_labs/google/keyword_ideas/live ~ $0.01 per call
- serp/google/ai_mode/live/advanced ~ $0.005 per call
- serp/google/organic/live/advanced ~ $0.002 per call

`scripts/research.py` prints a cost preview before any run that exceeds 50 unique keywords and aborts with exit code 7 unless `--confirm-cost` is passed.
