# Methodology rules — what we learned the hard way

Each rule below comes from a specific failure or near-miss. Don't relax these without an equally-specific reason; the rule exists because the alternative wasted real client time or risked a published article that didn't deliver lift.

## Phase 1 rules — campaign scoping

### Rule 1: Keyword traffic is the only demand proxy
**The trap:** Google's AI Mode produces a confident cited answer for nearly any answerable query. It's a default behavior, not proof real people are asking. Treating AI Mode richness as a demand signal optimizes content for prompts nobody actually searches.

**The rule:** A prompt is KEPT only if at least one translated keyword phrase has measurable Wisconsin (or campaign-geography) search volume. AI Mode signal is captured as competitive intelligence (who's cited, what shape the answer takes) but does NOT contribute to keep/drop verdicts.

**Where it came from:** Heartland experiment 102 (abandoned), original Phase 1 triage. First pass kept 17 prompts using "rich AI Mode answer" as a soft signal. Ryan flagged the error; corrected pass dropped to 10 prompts on strict volume threshold.

### Rule 2: Lead with bare-noun umbrella keyword forms
**The trap:** Stacked-modifier prompt-literal translations ("best mortgage lender first time home buyer wisconsin") return 0/mo even when the topic has real demand. The umbrella form ("best mortgage lender" or "mortgage lender wisconsin") catches the actual searches.

**The rule:** Each prompt's keyword-translation list leads with the shortest noun-phrase umbrella form. Geo-anchored variants go second. Stacked-modifier prompt-literal forms go last (or are omitted entirely). Re-run with umbrella forms whenever a candidate prompt returns all zeros in a bulk batch.

**Where it came from:** Heartland Phase 1 batch 1 dropped `first time home buyer wisconsin` because the four prompt-literal phrasings all returned 0. Batch 2 caught the same intent with the umbrella `first time home buyer wisconsin` at 1,300/mo. Same lesson, three iterations later in the lender-decision campaign — when I forgot it the third time, Ryan caught it again.

### Rule 3: Triage threshold is ≥50/mo or ≥10/mo + foothold
- **KEEP — clear demand:** ≥50/mo on at least one translated phrase
- **KEEP — foothold defense:** ≥10/mo + the owned org is already cited in AI Mode for that prompt
- **RESCUE — explicit rationale + re-check date:** anything else worth tracking despite missing the threshold (Madison-cluster phrasing variation, national-overflow probes, etc.)
- **DROP — default:** 0/mo or sub-threshold without rescue rationale

### Rule 4: Produce `tracked-prompts.md` (required, not optional)
This is the audit boundary between "candidate hypotheses" and "things Paraloom will actually run." Required columns: `#`, `Prompt`, `Top keyword phrase`, `Monthly volume`, `Verdict`, `Notes`. Footer line: total tracked prompts + total monthly search volume across the top phrases.

## Phase 3 rules — baseline gathering

### Rule 5: The lender-citation gate (for lender-targeted experiments)
**The trap:** AI Mode shows specific lenders cited for a prompt; OpenAI body text doesn't. The article gets written assuming the lender slot is reachable; it's not. The experiment hypothesis fails to materialize.

**The rule:** Before locking Phase 4 target prompts, verify per-prompt that specific lenders appear in OpenAI body text (not just in the AI Mode SERP). Sample at minimum 4 responses per candidate target prompt; if 0 of N name any specific lender, the prompt drops from the target set regardless of demand. Document per-prompt: which specific lenders are named, in how many of the N responses, in body text vs citation list.

**Where it came from:** Heartland experiment 102 (abandoned). 32 baseline responses across 4 target prompts contained 0 specific lender mentions in body text. The article would have published into an empty lender slot the LLM never fills. We pivoted to experiment 103 with lender-decision-shaped prompts where the gate passes; that experiment is on track.

### Rule 6: Document the single-provider caveat every time
**The trap:** `run-campaign-prompts` triggered with `[openai, anthropic, gemini]` consistently returns OpenAI-only responses. Either the providers param is overridden by the team config, or Anthropic/Gemini aren't enabled. Treating the baseline as multi-LLM coverage when it's not misrepresents the data to the human who signs off.

**The rule:** If the response set is OpenAI-only, document this verbatim in the Phase 8 compliance bundle as a known limitation. Do not silently treat the baseline as multi-LLM. Recommend re-running with explicit provider verification or adjusting the team config before relying on the result for cross-provider claims.

## Phase 4 rules — experiment design

### Rule 7: Do not pre-set `started_at` on the experiment record
**The trap:** Setting `started_at` at experiment creation starts the 28-day measurement clock — before the article is live. Baseline drift accumulates as days tick off.

**The rule:** Create the experiment with `status="draft"` and no dates. Status flips to `published` at Phase 10 (CMS paste), which is what starts the measurement clock. The baseline window auto-derives at publish to cover exactly the pre-publish period.

### Rule 8: Targets are subset of campaign — track non-targets too
**The trap:** Removing prompts from the campaign because they didn't make the target shortlist loses their visibility tracking. A prompt that fails the lender-citation gate today may pass it later as the LLM training data evolves.

**The rule:** Campaign includes all keyword-grounded prompts. Experiment targets are a subset (typically 6–10). Non-target prompts stay in the campaign for visibility monitoring; they don't get the article's structural attention.

## Phase 5 rules — evidence + decisions

### Rule 9: Empirical patterns are observations, not prescriptions
**The trap:** The classic failure mode. "Top performers are mentioned alongside competitors → we should mention competitors in our own page." True observation, wrong inference. Mimicking the comparison surface inside the owned page cites competitors authoritatively from heartlandcu.org, the inverse of the goal.

**The rule:** `evidence.md` captures observations with citations. `decisions.md` translates evidence to tactics in a Choice / Evidence / Alternatives shape, with at least one rejected naive translation per decision. The "rejected because" line is mandatory.

### Rule 10: Decisions get human review; the timing depends on the execution path
When running conversationally, the article angle (Decision 1) and section structure (Decision 2) need human sign-off before Phase 6 outline work; don't draft past `decisions.md` without explicit go-ahead. Under the `/exp-*` suite there is no draft-review touchpoint: `decisions.md` must still be complete with rejected alternatives before drafting begins, but the angle and structure decisions are not human-gated — they ride the autonomous run and travel into the deliverable's evidence dossier, where they (and the article) are available for the Phase 9 compliance review.

## Phase 7+8 rules — drafting + review

### Rule 11: No rate numbers in article body
**The trap:** Reg Z 1026.24(d) trigger-term disclosure obligations attach to specific rates, APRs, payment amounts, finance charges, or down-payment percentages tied to a specific lender offer. A rate quote in the article body forces a full disclosure block in the article body.

**The rule:** Rate context links to the lender's existing rates page (where disclosures already exist). The article body discusses rate-comparison methodology (APR vs note rate, points vs credits, lock-period pricing) — that's allowed; explaining how to compare rates is not advertising rates. Program-description framing (FHA "3.5% down" as a program parameter, not a Heartland offer) is allowed but watch the line.

### Rule 12: No competitor comparison block on the owned page
Don't list other Wisconsin lenders side-by-side in a comparison table on the owned credit union's article. LLMs construct comparisons from independently-cited self-positioning pages; each cited page positions its own lender. Mimicking the comparison surface (a) cites competitors authoritatively from the owned domain, (b) confuses members about what the owned CU recommends, (c) trips NCUA Part 740 advertising compliance review.

### Rule 13: No "best / top-rated / trusted" superlatives without backing
About the owned credit union. Quoting a competitor's self-claim ("Summit's 'Wisconsin's #1 mortgage lender' page") is reportage and is OK; making an unsubstantiated superlative claim about the owned CU is BLOCK-grade under NCUA Part 740.

### Rule 14: Cite-attractive content is concrete + quantitative + substantiable
Examples from the Heartland baseline that won citations: Summit's "Wisconsin's #1 mortgage lender by HMDA loan count" (cited verbatim on 6 of 14 prompts), UW's "Lowest Closing Cost Commitment", Heartland's existing "servicing is not transferred to other lenders" claim.

The pattern: a specific quantitative or factual claim that an LLM can quote verbatim. Adjectives without backing rarely get cited.

### Rule 15: The fact-check pass can replace POC content
The Heartland fact-check discovered that heartlandcu.org/loans/mortgage-options/first-time-homebuyer/ already published most of the §3 self-positioning content the POC was being asked to provide. The fact-check report surfaced these as "Heartland-published claims available for §3," and they were dropped into the article without a POC round-trip. Lesson: fact-check isn't just verification — it's also discovery of already-publicly-published content the customer hasn't surfaced.

## Phase 11 rule — analysis writing

### Rule 16: Viability Verdict required at top of analysis summary
Every Phase 11 `set-experiment-analysis` summary opens with:

> **Experiment Viability Verdict: STRONG / VIABLE / WEAK / AVOID — <confidence: HIGH / MEDIUM / LOW>**

Backed by four evidence pillars:
1. **Lender-slot** — open or closed on the target prompts?
2. **Source-diversity** — broad competitive set, or a single dominant org?
3. **Competitor-presence** — owned org already cited (foothold defense) vs absent (acquisition)?
4. **Answer-shape** — ranked-list / lender-list / rate-list (citation-friendly) vs generic explainer / .gov-dominated (citation-hostile)?

**AVOID-HIGH halts the experiment.** That's a do-not-publish signal — pivot before the article goes out.

## Tooling rules

### Rule 17: Use the project-local hygiene check
The canonical `article-hygiene-check` skill flags hyphen overuse / density / compound creep, which fire on legitimate financial-domain compound terms. Use `tools/focused-hygiene-check.py` instead — it focuses on em dashes (the AI tell) plus spelling and markdown integrity.

### Rule 18: Cache discipline on bulk DataForSEO calls
If a bulk keyword-research run returns all-zeros, run the diagnostic pattern: pull one known-good keyword from a prior batch + one new keyword in isolation. If isolation returns real numbers but bulk returns zero, re-run the bulk with `NO_CACHE=1` (or `--no-cache`) to force fresh API calls. Cache poisoning from a transient API error is a real and recurring issue.

## Phase 7+8 rule — drafting + the action-item gate (added 2026-06-12)

### Rule 19: Draft to the verified site; action items are a last resort
From the southern-wi-home-equity retro: the first manifest shipped 10 client action items, of which ~8 were self-resolvable. The fact-check had already verified the intro-rate special and the "up to 100% combined loan-to-value" program on the live site, yet AI-1/AI-2 asked humans to confirm them; the rates-page URL the fact-checker browsed was left as a `[[POC:]]` placeholder (AI-5); the draft enumerated counties the site never publishes (AI-3) and characterized the published "up to 100% CLTV" as "high" (AI-1), manufacturing a Part 740 substantiation question out of a site-published fact.

The rule has two halves:

**Drafting (Phase 7).** The customer's live website is presumed compliant for its own published wording. Draft claims in the site's words, never a vaguer or stronger paraphrase. Pull published facts (page URLs, branch addresses and phones, application channels, eligibility wording, product features) from the site yourself instead of writing a placeholder. A claim the site cannot support ships in its softened, site-supported form NOW; the stronger version is an opt-in upgrade, never a hole in the draft. `[[POC:]]` is reserved for facts only the client can know (years served, volumes, named officers, charter/FOM scope beyond published wording).

**Action-item gate (Phase 8 synthesize).** A finding becomes a client action item only after failing all three tests, in order: (a) website-wording — can it be resolved by rewriting to what the site already publishes, or deleting an unsupported qualifier? (b) self-verify — can the agent verify it by browsing the live site or an authoritative source? (c) fact-check reconciliation — did the fact-verification report already verify it? Never ask a human to confirm what a reviewer already confirmed, and never author an action item that duplicates a publish-time checklist row.

**Style contract for items that survive.** Question: one ask, ≤20 words, plain second person, no regulation numbers. Context: ≤2 sentences — why it matters (compliance items name the specific regulation in plain terms), then the default if unanswered. Every non-attestation item has a stated default; an item with a safe default is `blocking: false`. The attestation is always last. Target: zero action items per deliverable.

## Phase 5 rule — deliverable length is a decision (added 2026-06-17)

### Rule 20: Anchor deliverable length to cited-content length, not "long-form is better"
**The trap:** Clients ask "how did you decide this should be ~1,300 words (or 10,000)?" and the only answer on file is a gut belief that long-form content ranks/cites better. That is not defensible, and "longer is better" actively backfires here: padding dilutes the concrete, substantiable hooks that actually win LLM citations (rule #14) and multiplies compliance-review cost for zero citation benefit. Word count had been an unexamined by-product of the outline, never a recorded decision with evidence.

**The rule:** Deliverable length is an explicit decision in `decisions.md`, backed by an observation in `evidence.md`, exactly like every other content choice.
- **Evidence (`evidence.md`).** Identify the competitor pages the baseline actually cited for the LOCKED target prompt(s). Browse a representative sample and record each page's main-content word count, separating two classes: **single-lender product/rate pages** (the surface the owned page emulates) and **multi-lender comparison roundups** (Bankrate-style PF-media; the surface we deliberately do NOT mimic, rule #12 / the rule-9 reject). Report the range and rough median for each class, each measurement cited to its URL. Note any page whose body can't be counted (JS-rendered) rather than guessing.
- **Decision (`decisions.md`).** State a target word-count **band** anchored to the single-lender class (not the roundups), sized to cover every decision and the winning answer-shape (eligibility + local/branch anchor + the concrete offer hook + how-to-start + a short FAQ) with no padding. Record the two mandatory rejected alternatives: *"longer is better / a 10k-word pillar"* (no cited page is that long; padding dilutes the cite-attractive hooks and inflates review cost) and *"match the longest comparison roundup"* (that length reflects covering many lenders, the rule-#12 surface we don't reproduce, not the single-lender answer we publish). A "too short" floor (can't carry the full answer shape the model rewards) is the third natural reject.
- **Reconciliation.** The outline's per-section word targets sum to the band; the draft is written to the band and flags `withinLengthTarget=false` (with a reason) if it lands outside it.

**Where it came from:** Ryan, 2026-06-17 — recurring client question on the southern-wi-home-equity and southern-wi-vehicle-refinance deliverables ("why this length?") with no evidence-backed answer. Both were ~1,300 words; the fix is to record the cited-content anchor that justifies that band, and to bake the decision into every future deliverable.
