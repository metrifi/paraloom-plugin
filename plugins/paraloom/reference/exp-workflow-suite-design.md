# `/exp-*` workflow suite — design doc

Status (2026-06-10): **PROVEN END-TO-END through Phase 9.** `/exp-research`, `/exp-build` (including the Part 2b write-enabled pivot loop), and `/exp-review` are committed and live-proven on campaign 519 / experiment 106 (2026-06-10): STRONG verdict, targets 13978/13979/13980, review battery green (0 BLOCK / 0 CONTRADICTED), compliance-officer sign-off relayed by Ryan, Phase 10 staged (HTML rendered, awaiting CMS paste). The pivot loop's write path (create + run pivot prompts) is the one branch not yet live-exercised: validated read-only on campaign 511 (VIABLE under best-available-target semantics, see §8.3), it now waits only on encountering a genuinely barren campaign (subscription is Active). `EXPERIMENT_WORKFLOW.md` is slimmed to the thin index (§7 done). Remaining: `/exp-measure` (deferred until a measurement window opens); Phase 10 is conversational by decision (single render + single write: `tools/build-compliance-pdf.py` + `focused-hygiene-check.py --output-html` + `update-experiment`).

**Update (2026-06-12):** a full research→build→review→deliver run executed end-to-end on a new product area — experiment 108 / campaign 521 (`southern-wi-home-equity`, HELOC/home-equity), VIABLE-HIGH no-pivot, review green, deliverable id 5 pushed to the local instance. `/exp-deliver` gained a **Reconcile phase**: Verify now reports served-vs-manifest dossier counts, and an MCP push that drops the large dossier (an LLM abbreviating the inlined manifest — see `docs/deliverables-architecture.md` "Operational notes & known failure modes") auto-repairs via the byte-exact artisan ingest on the local server, or halts without notifying on a remote one.

Read alongside `EXPERIMENT_WORKFLOW.md` (phase definitions), `docs/methodology-rules.md` (the disciplines encoded here), and `CLAUDE.md`.

---

## 1. The goal (Ryan, 2026-06-09)

> From **no experiment → a validated, high-opportunity experiment with content ready for review**, for any team, reusing or creating a campaign. Run it and walk away. The agent navigates its own checkpoints and **pivots — on prompts, geography, target market, or the campaign itself — until it finds an opportunity.** There should (almost) always be an opportunity; the biggest are found and addressed first. A complete roadblock is rare, and when one happens the agent pivots rather than stops. **Intelligent, flexible autonomy.**

Two implications that drive everything below:

- **Writes auto-execute.** Creating the campaign, prompts, and experiment record is the job, not something to confirm. The Paraloom write tools are **allowlisted** so workflows just do them — no per-call prompts. (This reverses the earlier "leave writes un-allowlisted" idea, which would have buried Ryan in confirmations.)
- **`/exp-build` is an opportunity-seeking loop, not a pipeline.** It doesn't stop at a weak verdict — it pivots and re-evaluates until it has a viable target, then proceeds to draft.

---

## 2. Principles

**P1 — No draft-review stop; the routine human gate is the Phase 9 FI sign-off.** `/exp-review` runs automatically on the draft as the suite continues — it does **not** pause for a human to read the draft. Everything from research through the deliverable runs autonomously. The agent makes the prompt-keep, target-selection, and pivot decisions itself and *reports* them; it does not block for sign-off. The draft never needs a human read because the pivot loop guarantees it is backed by a clear, defensible opportunity (a weak one halts and re-tries rather than shipping). The retained human gates are the **Phase 9 sign-off gate** (a required human gate — any designated recipient at the FI, not necessarily a licensed compliance officer) and the **send-approval gate** on the client deliverable. A `/exp-review` BLOCK or an un-lockable opportunity halts the suite with a report — a genuine blocker, not a routine touchpoint.

**P2 — Writes are allowlisted; safety comes from reporting + idempotency, not confirmations.**
- Allowlisted writes (9 tools; `.claude/settings.json` is the source of truth): `create-campaign`, `create-prompt`, `run-campaign-prompts`, `run-prompt` (what the pivot loop uses to run only the new prompts), `create-experiment`, `update-experiment`, `set-experiment-analysis`, `set-experiment-recommendation`, `set-experiment-case-study`.
- Every workflow **returns exactly what it created** (campaign/prompt/experiment ids) so it's auditable.
- **Dedupe before create** (`list-campaigns` / `list-prompts`) so a re-run never doubles records.
- Respect quota: check `get-team-usage` before large prompt-run batches (runs consume quota).
- The write-bearing workflows are **validated on a throwaway team first**.
- These are designed for interactive CLI use; in `claude -p`/SDK there are no permission prompts anyway, which is fine because writes are allowlisted.

**P3 — Files are the handoff state.** State lives in `experiments/<slug>/` (the existing convention) plus the Paraloom records. `slug` + ids flow forward via `args`. The workflow *script* has no filesystem/MCP access — its **agents** do all reads, writes, and tool calls.

**P4 — Encode the methodology as hard logic.**
- Rule #1/#2 (keyword volume is the only demand signal; translate to umbrella forms) → `/exp-research` triage.
- Rule #3 (FI lender-slot gate) → `/exp-build`'s opportunity score.
- Rule #4 (observations ≠ prescriptions; the "mimic the comparison surface" trap) → `/exp-build`'s decisions step keeps rejected alternatives.
- The Viability Verdict (STRONG/VIABLE/WEAK/AVOID) → the **pivot trigger** in `/exp-build`.

**P5 — Cast a wide enough net in research that build can pivot cheaply.** `/exp-research` deliberately creates prompts across several **intent angles, geographies, and target segments** (all keyword-grounded). That way `/exp-build`'s first pivot move is *re-selecting* among already-run prompts — no new provider runs, no wait. Only when the whole net is barren does build generate-and-run new prompts.

---

## 3. The suite

```
/exp-research   →   [responses populate]   →   /exp-build   →   /exp-review
  (Ph 1–2)                                        (Ph 3–7)          (Ph 8, built)
  create/reuse campaign,                          find the opportunity (pivoting
  keyword-grounded prompts,                        as needed), create experiment,
  run them                                         strategy, outline, draft
```

Two launches, then review. `/exp-build` can be launched right after `/exp-research`; it **polls for responses to populate** before analyzing, so Ryan doesn't have to time the wait.

| Workflow | Phases | Reads | Writes (allowlisted) |
|----------|--------|-------|----------------------|
| `/exp-research` | 1–2 | DataForSEO, list-teams, list-campaigns, get-team-usage | create-campaign, create-prompt×N, run-campaign-prompts |
| `/exp-build` | 3–7 | list-prompts, get-org-visibility, list-responses, get-response, list-action-types | create-prompt×N + run (pivots), create-experiment, update-experiment, set-experiment-analysis, set-experiment-recommendation |
| `/exp-review` | 8 | (article + skills) | none — ✅ built |

---

## 4. `/exp-research` — Phases 1–2

**args:** `{ slug, teamId, topic, audience, geography, creditUnion, domain, campaignId?, seedPrompts? }`
(`campaignId` present → reuse that campaign; absent → decide new-vs-existing from `list-campaigns`, create if needed.)

**Phases:**
1. **Frame** — confirm/derive topic, audience, geography; write the opening of `experiment.md`. `list-campaigns` for the team; if an existing campaign already covers the topic, reuse it (and its already-run prompts) instead of creating a new one.
2. **Generate (wide)** — produce candidate prompts across **multiple intent angles** (informational / comparative / transactional / locational) **and** a few **geography / target-segment variants** — the breadth that lets `/exp-build` pivot by re-selection (P5). Typically 20–40 candidates.
3. **Ground** — pipeline each candidate through the `keyword-research` skill: translate to umbrella keyword forms (rule #2), DataForSEO volume, AI-Mode SERP context. Chunk to ≤~5 concurrent to dodge the bulk zero-volume quirk; on a 0/mo, retry the bare-noun form once.
4. **Triage** — Keep/Refine/Drop (rule #1). Write `keyword-research.md` and `tracked-prompts.md` (the audit boundary; column 2 = source of truth for prompt creation).
5. **Instantiate** — `get-team-usage` (quota check); create-campaign if needed; `create-prompt` for each kept prompt (deduped against existing); `run-campaign-prompts`.

**Returns:** `{ campaignId, promptIds[], keptCount, totalVolume, ranBatchAt }`. Notes that responses need ~5–30 min; `/exp-build` will poll.

**Validation:** dry-run the Frame→Triage phases against DataForSEO only (no writes) on a real topic; inspect `tracked-prompts.md`. Then validate the Instantiate writes on a throwaway team.

---

## 5. `/exp-build` — Phases 3–7 (the opportunity engine)

**args:** `{ slug, campaignId, creditUnion, domain, maxPivots?, geography?, audience? }`

**Phase A — Wait & analyze.**
- Poll `list-prompts` / `list-responses` until responses have populated (timeout guard).
- Pipeline each prompt → sample responses → extract competitors named, sources cited, answer shape, and the **lender-slot count** (how many of N responses name *any* FI in body text — rule #3). `get-org-visibility` for owned vs competitor standing.

**Phase B — Score & decide (the pivot loop).**
- Compute a **Viability Verdict** per prompt and an **opportunity score** = demand (`tracked-prompts.md`) × owned-visibility gap × lender-slot openness. Rank; biggest opportunity first.
- **If the best prompt is VIABLE/STRONG → lock it as the target and exit the loop.**
- **Else pivot, in escalating tiers, and re-score:**
  1. **Re-select** — pick the next-best already-run prompt/angle (free; this is why research casts wide).
  2. **Re-angle** — generate new prompts for an untried intent/geography/segment, `create-prompt` + `run-campaign-prompts`, poll, re-analyze.
  3. **Re-scope** — shift geography or target market materially (new prompt cluster), run, poll, re-analyze.
  4. **Re-campaign** — only if a whole market is barren: stand up a sibling campaign for an adjacent market.
- Loop until a viable target emerges **or** a guard trips: `maxPivots` (default ~3), `budget.remaining()`, or `get-team-usage` quota. A guard-trip is the *rare* roadblock — return the closest opportunities + a recommended human pivot rather than forcing a bad target. **"Always an opportunity" is the default expectation, not a guarantee at any cost.**

**Implementation notes (as built, 2026-06-09):**
- Census→Analyze→Decide is a loop; only new prompts are analyzed on later rounds (prior rows carry forward).
- The campaign verdict reflects the **best available target** (any VIABLE/STRONG prompt ⇒ campaign at least VIABLE), so "re-select" never appears as an executed pivot — it happens inside the ranking. Pivot triggers when `!target || verdict ∈ {WEAK, AVOID}`.
- Pivot execution gates on `get-team-usage` (subscription Active + quota ≥ candidates × 3), keyword-grounds candidates via the keyword-research skill (rules #1/#2, zero-volume candidates dropped), dedupes against `list-prompts`, creates with `create-prompt`, and runs **only the new prompts** with per-prompt `run-prompt` (never `run-campaign-prompts`, which would re-run the whole campaign).
- `re-campaign` is returned to the human, never executed.
- **Async boundary:** a bounded poll agent (~25 min via Monitor waits) watches the new prompts; on timeout the run exits `pivot-prompts-running` with re-run instructions — re-running is idempotent (census picks up new prompts, experiment step reuses the draft experiment). The same poll guards round 0 when `/exp-build` is launched before the baseline populates (`awaiting-responses`).
- `localOnly` + pivot-needed returns `halted-no-target` (pivots require writes).

**Phase C — Commit the experiment.** `create-experiment` (status `draft`, **no** `started_at`/`ended_at` — they auto-derive at publish) + `update-experiment` `prompt_ids=[…]` for the locked target(s). Record id in `experiment.md`.

**Phase D — Strategy.** Parallel evidence readers → `evidence.md` (observations w/ citations). Decisions synthesizer → `decisions.md` **with rejected alternatives** (rule #4). Then `list-action-types` → `set-experiment-analysis` (narrative opens with the Viability Verdict block) + `set-experiment-recommendation` (+ actions), plain-language client standards. (`set-*` replace, not patch — build the full payload.)

**Phase E — Outline & draft.** Outline judge-panel (2–3 variants scored on `decisions.md` coverage) → `article-<slug>.outline.md`. Then draft the article section-by-section per the outline → `article-<slug>.md` (v1), citing sources inline so `/exp-review`'s fact-check has clean targets.

**Returns:** `{ experimentId, targetPromptIds, verdict, pivots: [...], articlePath }`. Ends: "content ready — run `/exp-review`."

**Validation:** point Phases A–B read-only at an existing Heartland campaign; confirm the opportunity ranking and a simulated pivot match a hand check before enabling writes. Then full run on a throwaway team.

---

## 6. `args` & file-state conventions

- Every workflow takes `slug`; derives `dir = experiments/<slug>/` and standard filenames.
- Paraloom ids flow forward via `args`, sourced from `experiment.md` (each workflow updates it). `creditUnion` + `domain` thread through anything that browses or scopes to the owned site.
- `args` may arrive as an object or JSON string — normalize with the parse-if-string guard (already in `/exp-review`); factor into a shared header snippet.

---

## 7. Slimmed `EXPERIMENT_WORKFLOW.md`

Once built, rewrite the SOP into a thin index: per phase, one row → `/exp-research` | `/exp-build` | conversational | `/exp-review`, plus the remaining human gate (Phase 9 compliance) and Phase 10 publish + Phase 11 measurement (deferred). Keep the prose workflows can't encode: foundational decisions, methodology rationale, the Phase 9 gate. The scripts become the executable source of truth for the mechanics.

---

## 8. Open questions / risks

1. **Wide-net cost.** Casting across angles/geos/segments in research = more prompts = more provider runs = quota. `get-team-usage` gate + a sane candidate cap. Tune on the dry run.
2. **Build is long-running** (poll-waits + pivots can span 30–90 min, multiple run cycles). Workflows resume only within a session; a dropped session restarts fresh. Mitigate: checkpoint progress into `experiment.md` so a restart can skip completed work; keep `maxPivots` modest.
3. **Autonomous target selection quality.** The opportunity score must genuinely reflect winnability (rule #3), or build will confidently pick a losing target. Validate the ranking against a known case (experiment 102 should score AVOID) before trusting it. *Validated 2026-06-09:* the read-only run on campaign 511 scored all 12 WHEDA/program prompts AVOID (0/6 lender slot — the exp-102 pattern) and locked 13875 "Best WI CU FTHB" (6/6 slot, Heartland already cited 2/6, open recommendation slot) + 13868 as the target. Note the semantics shift vs the earlier Pt1 validation, which rated 511 "WEAK" on its dominant pattern: under best-available-target semantics 511 is VIABLE because two open-slot prompts exist — re-selection found the opportunity instead of pivoting away from it.
4. **Pivot loops must terminate.** Hard guards: `maxPivots`, token budget, team-usage quota. Never an unbounded "keep trying."
5. **Draft quality from a fully-autonomous run** is lower than iterative authoring — acceptable because `/exp-review` + the Phase 9 human gate catch issues, and the goal is *review-ready*, not *publish-ready*.
6. **set-* replace semantics** — full payload every call (also true for Phase 11 finals, when built).
