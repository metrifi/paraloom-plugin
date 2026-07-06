# Paraloom Experiment Workflow

> SOP index for running a Paraloom experiment end-to-end. The mechanics live in the `/exp-*` workflow scripts (`.claude/workflows/`) — they are the executable source of truth. This doc holds what the scripts can't encode: the foundational decisions, the autonomy model, the human gates, and the formats shared across phases.

```
/exp-research  →  [responses populate]  →  /exp-build  →  /exp-review  →  Phase 9 human gate  →  publish  →  /exp-measure
   (Ph 1–2)                                  (Ph 3–7)        (Ph 8)        (FI sign-off)           (Ph 10)      (Ph 11)
```

## Phase index

| Phase | Vehicle | Human touchpoint | Key artifacts |
|-------|---------|------------------|---------------|
| 1. Campaign scoping | **`/exp-research`** (`dryRun:true` = stop after triage, no writes) | topic + team approval before launch | `experiment.md` (draft), `keyword-research.md`, `tracked-prompts.md` |
| 2. Campaign + prompt creation | **`/exp-research`** (same run) | — | campaign + prompts in Paraloom, baseline run triggered |
| 3. Baseline analysis | **`/exp-build`** (`stopAfter:"analyze"` = read-only) | — | `build-analysis.md` |
| 4. Experiment design | **`/exp-build`** | — (decides + reports) | experiment record (draft), hypothesis in `experiment.md` |
| 5. Evidence + decisions + Paraloom records | **`/exp-build`** | — (decides + reports) | `evidence.md`, `decisions.md` (incl. the cited-content **deliverable-length** decision, rule #20), Paraloom analysis + recommendation |
| 6. Outline | **`/exp-build`** (judge panel) | — (decides + reports) | `article-<slug>.outline.md` |
| 7. Draft | **`/exp-build`** (`localOnly:true` = content files, no Paraloom writes) | — (no draft-review stop; auto-continues to Phase 8) | `article-<slug>.md` + `openItemsForReview` |
| 8. Review battery | **`/exp-review`** | dispositions WARN / NEEDS_HUMAN items | four review reports + `article-<slug>.review-summary.md` |
| 9. Sign-off gate | conversational + `tools/build-compliance-pdf.py` | **FI sign-off (required human gate) — any designated recipient at the FI** | `compliance-bundle.pdf`, sign-off in `workflow-log.md` |
| 10. Publish | conversational (recipe below) | CMS paste (Ryan / credit union) | `article-<slug>.html`, experiment → `published` |
| 11. Measurement | **`/exp-measure`** (deferred — will be a `/loop`-backed cron) | reads weekly updates; approves conclusions | `weekly-update-*.md`, `retrospective.md`, Paraloom case study |

Folder and file conventions: `docs/conventions.md`. Methodology rules #1–#8 (the disciplines the workflows encode): `docs/methodology-rules.md` and `CLAUDE.md`. Workflow suite design + rationale: `docs/exp-workflow-suite-design.md`.

---

## Foundational decisions baked into this workflow

- **Articles are authored locally as files**, not in Paraloom's article editor. Final HTML is copy-pasted into the CMS at publish time.
- **Every article carries three sidecar files** — `evidence.md`, `decisions.md`, `workflow-log.md` — that travel with it from draft to publish to retrospective.
- **Empirical patterns are observations, not prescriptions.** Evidence is captured, then translated into tactics through judgment recorded in `decisions.md` with rejected alternatives. Translating "top performers mention competitors" directly into "we should mention competitors" is the failure mode this discipline prevents (rule #4).
- **Keyword traffic is the only demand signal we trust** (rule #1). AI Mode SERP richness is context, never demand evidence. Every prompt in a campaign must trace to measurable volume in `tracked-prompts.md` — the audit boundary between candidate hypotheses and things Paraloom actually runs.
- **Review skills are assistive, not authoritative.** A designated person at the FI signs off before publish; the skills shrink the surface they review, not the responsibility.
- **Almost every Paraloom action runs from the connector.** The one unavoidable exit is the CMS paste at Phase 10.

---

## The autonomy model

When run through the `/exp-*` suite (the default), the agent has **maximum autonomy**: Paraloom writes are allowlisted and auto-execute; the agent makes the prompt-keep, target-selection, and pivot decisions itself and *reports* them. The routine human gate is **one: the Phase 9 sign-off** (a required human gate — any designated recipient at the FI, not necessarily a licensed compliance officer), plus the **send-approval gate** on the client deliverable (the email only goes out with Ryan's explicit OK). **There is no draft-review stop** — the suite continues from `/exp-build` straight through `/exp-review` into `/exp-deliver`, because the pivot loop guarantees the draft is backed by a clear, defensible opportunity (a weak one halts and re-tries rather than shipping). The deliverable is produced and held at the send gate. A `/exp-review` BLOCK or an un-lockable opportunity halts the suite with a report — a genuine blocker, not a routine touchpoint.

- **Pivot, don't halt.** `/exp-build` is an opportunity-seeking loop. On a WEAK/AVOID verdict it pivots — re-selecting among already-run prompts first (free), then creating + running new keyword-grounded prompts (re-angle / re-scope) — until a viable target emerges or a guard trips (`maxPivots`, token budget, quota/subscription). A guard trip returns the closest opportunities plus a recommended human pivot; it never forces a bad target. A `re-campaign` pivot (sibling campaign for an adjacent market) is always returned to the human, not executed.
- **Safety = reporting + idempotency, not confirmations.** Every workflow returns exactly what it created (campaign/prompt/experiment ids). Creates dedupe against existing records, so re-running is safe — which is also how the async boundary is handled: if new prompts haven't populated within a run's wait budget, the workflow exits with instructions to re-run.
- **Never fabricate a human sign-off.** Workflow logs record what the agent did; sign-offs are the human's to write.
- **When running phases conversationally** (outside the suite), the legacy stop points apply: Phase 1 candidate-prompt sign-off, Phase 4 target-prompt lock, Phase 6 outline approval, Phase 9 FI sign-off.

---

## The Viability Verdict (canonical format)

Produced in `/exp-build`'s Decide phase, written to `build-analysis.md`, and required as the **opening block** of every `set-experiment-analysis` narrative. The call comes first — never buried inside findings.

```
**Viability Verdict: <STRONG | VIABLE | WEAK | AVOID> (confidence: <HIGH | MEDIUM | LOW>)**

<One-sentence rationale in plain language.>

**Why we're <confident | uncertain>:**
- **Lender slot:** <N/M> responses include a named financial institution in body text. <observation>
- **Source diversity:** <breakdown of cited source types>.
- **Competitor presence:** <named FI competitors, with frequency> OR "no FI competitors appear — opening a new category, which is much harder."
- **Answer shape:** <list-shaped (favors brand mentions) | explanatory (favors regulators/authoritative pages) | mixed>.
```

Decision rule: **STRONG/VIABLE** → lock the target and proceed. **WEAK/AVOID** → pivot (the workflow executes re-angle/re-scope itself; re-campaign goes to the human). Any verdict at LOW confidence is flagged in the run report. A prompt where zero responses name any FI is structurally hostile regardless of demand (rule #3 — the experiment-102 lesson).

---

## Writing standards for client-visible Paraloom content

Applies to `set-experiment-analysis`, `set-experiment-recommendation`, action descriptions, and the Phase 11 case study:

- **Plain language** for the credit-union marketing manager — no jargon ("intent funnel", "SERP density").
- **Reference keyword traffic numbers prompt by prompt** (from `tracked-prompts.md`).
- **Preserve substance, compress phrasing.** Every key insight from `evidence.md`/`decisions.md` surfaces in the Paraloom record.
- **30-second takeaway test:** a skimming reader knows what we found, why it matters, what we're doing about it.
- **`set-*` tools REPLACE, not patch** — build the full payload every call (true for the Phase 11 finals too).

---

## Phase 8 disposition rules

`/exp-review` produces the four reports plus `article-<slug>.review-summary.md`; it does not mutate the article. Its synthesize step also writes the manifest inputs to `manifest-inputs.json`: the checklist + action items + opportunity header, plus the **human-readable evidence layer** — a per-doc `dossierSummaries` map (plain-language summaries keyed by dossier filename) and a featured `evidenceOverview`. These translate the dense working files (`evidence.md`, `decisions.md`, etc.) into client-readable prose without touching the raw files, which still ship in the dossier behind a toggle. Work the findings conversationally, then re-run:

- **BLOCK / CONTRADICTED** — must be fixed before advancing.
- **WARN** — review with the human; record the disposition in `decisions.md` ("fixed" with the rewrite, or "kept with reasoning").
- **NEEDS_HUMAN_VERIFICATION** — the human verifies offline (or with the credit union); update the article or note the verification source in `decisions.md`.
- **DEFER (ADA page-level checks)** — carry to Phase 9 as a checklist for the rendered-page audit.

After fixes, re-run `/exp-review` to confirm they hold. Log each pass in `workflow-log.md`.

---

## Phase 9 — Human sign-off gate

A designated person at the FI signs off before publish — the point of contact, a compliance reviewer, or anyone they delegate who received the deliverable. It does not have to be a licensed compliance officer, but it remains a required human gate. The skills assist; they do not replace this step.

1. Build the bundle: `python3 tools/build-compliance-pdf.py --experiment-dir experiments/<slug> --credit-union <name> [cover args]` — article, decisions log, four review reports, evidence, experiment record, workflow log in one PDF (see `tools/README.md`).
2. The signer reviews the WARN items and NEEDS_HUMAN_VERIFICATION dispositions, and either signs off or returns the article to Phase 8.
3. The sign-off is captured in `workflow-log.md` with name and date — by the human, never by the agent.
4. The human (or credit union) runs the deferred rendered-page audit (axe DevTools, Lighthouse, or WAVE) on a staged version in the CMS. Outside Claude.

---

## Phase 10 — Publish (conversational recipe)

Deliberately not a workflow — it's one render plus one write, gated on the Phase 9 sign-off.

1. Render the approved article:
   ```bash
   python3 tools/focused-hygiene-check.py \
     --article experiments/<slug>/article-<slug>.md \
     --credit-union-domain <domain> \
     --output-html experiments/<slug>/article-<slug>.html
   ```
   Transforms applied: external links `rel="nofollow" target="_blank"`, tables `class="table"`, image `alt` preserved.
2. Ryan or the credit union pastes the HTML into the CMS (manual). Capture the live URL in `workflow-log.md`.
3. Start the measurement clock: `update-experiment` with `status: "published"` and `started_at` = publish date. This auto-computes the baseline window backward.
4. Verify with `get-experiment`: `started_at`, `baseline_started_at`, `baseline_ended_at`, `ended_at` all look right.

Until publish, the experiment stays `draft` with **no** `started_at`/`ended_at` — setting them early would start the clock before the article is live.

---

## Phase 11 — Measurement (`/exp-measure`, deferred)

To be built when a measurement window opens: a `/loop`-backed cron (`CronCreate`) polling weekly —

- `get-experiment-insights` — visibility vs baseline (leading signal).
- `get-ai-user-bot-traffic` — real AI-referral traffic (lagging signal). **Confirm AI Traffic tracking is set up at `/ai-traffic` first**; if not, the weekly update notes the lagging signal is unavailable.
- `list-prompts` — per-prompt breakdown.
- Writes `weekly-update-<date>.md`; surfaces inflections (visibility crossed baseline, competitor disruption, regression) with a recommended action.

At `ended_at`: final `set-experiment-analysis` + `set-experiment-recommendation` (full payloads — setters replace) + `set-experiment-case-study`, plus `retrospective.md` (what happened / which decisions held / follow-up hypothesis). Until built, run these steps conversationally.

---

## workflow-log.md

The spine. One section per phase: status, started/completed timestamps, artifacts, issues/blockers, and sign-offs (Phase 9 FI sign-off; outline approval when running conversationally). A glance tells anyone where the experiment is.

## When the workflow can be shortened

- **Repeat-pattern experiments:** carry forward Phase 1 keyword work; seed `decisions.md` from a prior experiment.
- **Article refreshes:** skip Phases 1–4; jump to Phase 5 with focused scope.
- **Time-pressured publishes:** never skip the Phase 8 review battery or the Phase 9 human gate. Everything else can compress.
