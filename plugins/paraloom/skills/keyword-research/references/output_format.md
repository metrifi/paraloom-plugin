# Output format

## Markdown (default)

The skill emits exactly one markdown document, designed to drop into an experiment's `evidence.md` sidecar.

```markdown
# Keyword research — <topic>

**Generated:** 2026-05-05T14:32:11+00:00  
**Source:** DataForSEO  
**Location:** Wisconsin,United States  
**Language:** English

## Per-prompt results

### Prompt: "What's the best certificate of deposit for retirees in southern Wisconsin?"

| Keyword phrase | Monthly volume | Competition | CPC range | Search intent |
|----------------|----------------|-------------|-----------|---------------|
| best cd rates wisconsin retirees | 1,300 | MEDIUM | $1.20–$3.40 | commercial |
| highest cd rates southern wisconsin | 90 | LOW | $0.80–$2.10 | commercial |
| retiree cd rates wisconsin | 40 | LOW | — | informational |

**AI Mode SERP for this prompt:**
- Cited sources: [bankrate.com](https://...), [nerdwallet.com](https://...), [heartlandcu.com](https://...)
- AI answer summary: For Wisconsin retirees, current top CD rates range 4.50–5.10% APY for 12-month terms. Heartland Credit Union and Summit Credit Union are highlighted for senior-friendly terms.
- Owned org appearance: yes
- Competitor appearance: bankrate.com, nerdwallet.com

### Prompt: "How do I qualify for a first-time homebuyer loan in Dane County?"
...

## Aggregate signals

- **Highest-volume prompts:** "What's the best certificate of deposit for retirees in southern Wisconsin?" (1,300/mo); "Sun Prairie credit union with the best auto loan rate?" (480/mo); "What HELOC rates can I get in Madison, WI right now?" (320/mo)
- **Prompts where competitors are cited by AI Mode:** "What's the best certificate of deposit..."; "Is a credit union safer than a bank in 2026?"
- **Prompts with no AI Mode answer (first-to-publish candidates):** "Sun Prairie credit union with the best auto loan rate?"
- **Prompts with zero search volume across all candidates (consider deprecating):** "..."
```

The `Source` line is `DataForSEO` for Path A and `Google Ads Keyword Planner via browser` for Path B.

## JSON (`--format json`)

The same data, machine-shaped:

```json
{
  "topic": "Heartland CU — May 2026 prompts",
  "generated_at": "2026-05-05T14:32:11+00:00",
  "source": "DataForSEO",
  "location": "Wisconsin,United States",
  "language": "English",
  "prompts": [
    {
      "prompt": "What's the best certificate of deposit for retirees in southern Wisconsin?",
      "keywords": [
        {
          "keyword": "best cd rates wisconsin retirees",
          "search_volume": 1300,
          "competition": "MEDIUM",
          "competition_index": 47,
          "cpc": 2.10,
          "low_top_of_page_bid": 1.20,
          "high_top_of_page_bid": 3.40,
          "search_intent": "commercial",
          "monthly_searches": [{"year": 2026, "month": 4, "search_volume": 1280}]
        }
      ],
      "ai_mode": {
        "query": "What's the best certificate of deposit for retirees in southern Wisconsin?",
        "ai_answer": "For Wisconsin retirees, current top CD rates ...",
        "citations": [
          {"domain": "bankrate.com", "url": "https://...", "title": "..."}
        ],
        "raw": { "...full SERP item..." : "..." }
      },
      "owned_appears": true,
      "competitor_domains": ["bankrate.com", "nerdwallet.com"]
    }
  ],
  "aggregate": {
    "highest_volume": [["...prompt...", 1300]],
    "competitor_cited_prompts": ["..."],
    "no_ai_mode_prompts": ["..."],
    "zero_volume_prompts": []
  }
}
```

`search_intent` is populated only when the calling session also runs `keyword_ideas` and merges the intent column in. By default, `research.py` uses `search_volume` (which doesn't return intent) so `search_intent` will be null/missing for most rows. To populate intent, run `keyword_ideas.py` separately and merge — that's a follow-up enhancement, not a default behavior.
