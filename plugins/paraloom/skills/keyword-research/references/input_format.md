# Input format

## Prompt list

The canonical input is the markdown bullet list produced by the Paraloom Connector's `list-prompts` tool. Each `-` or `*` bullet is one prompt. Headers and blank lines are ignored.

```markdown
# Heartland CU prompts — May 2026

- What's the best certificate of deposit for retirees in southern Wisconsin?
- How do I qualify for a first-time homebuyer loan in Dane County?
- Is a credit union safer than a bank in 2026?
- Sun Prairie credit union with the best auto loan rate?
- What HELOC rates can I get in Madison, WI right now?
```

`scripts/research.py` parses this with a forgiving regex — bullets win, but a non-bullet body line is also accepted as one prompt if no bullets are present.

## Prompt-to-keyword mapping (recommended)

Paraloom prompts are full natural-language questions. DataForSEO and Keyword Planner want short keyword phrases. The skill ships with a fallback heuristic (strip stopwords, keep content words) but it is **strongly preferred** that the calling Claude session generate 3–6 candidate keyword phrases per prompt. Language models are good at this; the heuristic is not.

Pass the mapping as a JSON file via `--keywords-per-prompt`:

```json
{
  "What's the best certificate of deposit for retirees in southern Wisconsin?": [
    "best cd rates wisconsin retirees",
    "highest cd rates southern wisconsin",
    "retiree cd rates wisconsin",
    "wisconsin certificate of deposit seniors"
  ],
  "How do I qualify for a first-time homebuyer loan in Dane County?": [
    "first time homebuyer loan dane county wisconsin",
    "first time homebuyer wisconsin requirements",
    "dane county first home buyer programs",
    "wisconsin fha loan first time buyer"
  ]
}
```

The keys must match the prompts exactly. If a key is missing, `research.py` falls back to its heuristic for that prompt only — other prompts still use the explicit list.

## Generating the mapping

The recommended pattern (from the calling session): right before invoking the skill, ask the language model to translate each prompt into 3–6 candidate phrases optimized for keyword tools — short, no question marks, lowercase, place names spelled out, brand names included where relevant. Save the result as JSON, then call `research.py --keywords-per-prompt <path>`.

Keep the mapping file alongside the report so the evidence dossier can show "this prompt was scored against these N keyword phrases."
