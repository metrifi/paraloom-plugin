export const meta = {
  name: 'exp-build',
  description: 'Phase 3-7 opportunity engine: analyze a campaign\'s LLM responses, score each prompt for a winnable visibility opportunity (demand x lender-slot openness x owned gap), lock the biggest viable target, create the Paraloom experiment, write the strategy (evidence/decisions + Paraloom analysis & recommendation), and draft the article. On a WEAK/AVOID verdict it PIVOTS: creates + runs new keyword-grounded prompts (re-angle / re-scope), waits for responses, and re-scores — up to maxPivots rounds. stopAfter:"analyze" runs read-only (no writes). localOnly:true generates all content files but skips every Paraloom write (for content validation).',
  whenToUse: 'After /exp-research has created a campaign and its prompts have run (responses populated). Takes it from a populated campaign to a draft article ready for /exp-review. Run stopAfter:"analyze" first to sanity-check the opportunity ranking.',
  phases: [
    { title: 'Census', detail: 'pull per-prompt visibility + org rankings' },
    { title: 'Analyze', detail: 'sample responses per prompt: lender-slot, competitors, answer shape' },
    { title: 'Decide', detail: 'viability verdict + opportunity ranking -> lock target or pivot' },
    { title: 'Pivot', detail: 'on WEAK/AVOID: create + run new keyword-grounded prompts, poll, re-analyze' },
    { title: 'Experiment', detail: 'create the draft Paraloom experiment + attach target prompts' },
    { title: 'Strategy', detail: 'evidence + decisions -> Paraloom analysis & recommendation' },
    { title: 'Outline', detail: 'judge-panel outline from the decisions' },
    { title: 'Draft', detail: 'write the article from the approved outline' },
  ],
}

// ---- args ----------------------------------------------------------------
// { slug, teamId, campaignId   (required)
//   creditUnion, domain        (recommended — owned org to score the gap for)
//   maxPivots?                 (default 3; pivot rounds before the guard trips)
//   stopAfter?                 ('analyze' = read-only single pass, stop after Decide; 'draft' (default) = full run)
//   localOnly?                 (content files only, zero Paraloom writes — pivots cannot execute)
//   samplePerPrompt?           (default 6 responses sampled per prompt for slot analysis)
// }
let a = args || {}
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { throw new Error('exp-build: args must be a JSON object or JSON string') } }
a = a || {}
for (const k of ['slug', 'teamId', 'campaignId']) {
  if (a[k] === undefined || a[k] === null || a[k] === '') throw new Error(`exp-build: args.${k} is required`)
}
const slug = a.slug
const dir = `experiments/${slug}`
const teamId = a.teamId
const campaignId = a.campaignId
const owned = a.creditUnion || '(the owned organization)'
const domain = a.domain || ''
const geography = a.geography || ''
const audience = a.audience || ''
// Paraloom MCP target. Default PROD (mcp__claude_ai_Paraloom__) per CLAUDE.md's environment rule;
// pass mcpPrefix:'mcp__paraloom-local__' to target the local dev checkout. NOTE: live baseline runs need
// the target team's subscription Active — the GATE in the pivot RUN step enforces that.
const PARALOOM = a.mcpPrefix || 'mcp__claude_ai_Paraloom__'
// stopAfter: 'analyze' = read-only stop after the first Decide; 'draft' = full run through the article draft.
const stopAfter = a.stopAfter || 'draft'
if (!['analyze', 'draft'].includes(stopAfter)) throw new Error(`exp-build: stopAfter must be 'analyze' or 'draft' (got '${a.stopAfter}')`)
// localOnly: do all the content phases as local files but skip EVERY Paraloom write (create-experiment,
// update-experiment, set-experiment-analysis, set-experiment-recommendation). For validating content quality.
const localOnly = !!a.localOnly
const maxPivots = a.maxPivots === undefined ? 3 : a.maxPivots
const sampleN = a.samplePerPrompt || 6
const CHUNK = 4 // prompts per analysis agent
const READY_FRACTION = 0.8 // matches the poll threshold: analyze once >=80% of prompts have responses
const MIN_BUDGET_FOR_PIVOT = 60000 // tokens; below this a pivot round won't fit
const PARALOOM_READS = `${PARALOOM}list-prompts,${PARALOOM}get-org-visibility,${PARALOOM}list-responses,${PARALOOM}get-response`

function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out }

const CENSUS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['prompts', 'orgs', 'totalResponses', 'ownedVisibilityOverall'],
  properties: {
    prompts: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['id', 'name', 'visibility', 'responseCount'], properties: {
      id: { type: 'integer' }, name: { type: 'string' },
      visibility: { type: 'number', description: 'owned-org visibility % on this prompt' },
      responseCount: { type: 'integer' },
    } } },
    orgs: { type: 'array', description: 'org visibility ranking (all orgs)', items: { type: 'object', additionalProperties: false, required: ['name', 'owned', 'visibilityPct', 'mentions'], properties: {
      name: { type: 'string' }, owned: { type: 'boolean' }, visibilityPct: { type: 'number' }, mentions: { type: 'integer' },
    } } },
    totalResponses: { type: 'integer' },
    ownedVisibilityOverall: { type: 'number' },
  },
}

const ANALYSIS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['rows'],
  properties: {
    rows: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['promptId', 'name', 'fiNamingResponses', 'sampled', 'ownedMentioned', 'competitorsNamed', 'answerShape'],
      properties: {
        promptId: { type: 'integer' }, name: { type: 'string' },
        fiNamingResponses: { type: 'integer', description: 'how many sampled responses name ANY financial institution in body text (the lender-slot count)' },
        sampled: { type: 'integer', description: 'responses actually sampled' },
        ownedMentioned: { type: 'integer', description: 'sampled responses naming the owned org in body' },
        competitorsNamed: { type: 'array', items: { type: 'string' }, description: 'distinct FI competitors named in bodies' },
        sourceTypes: { type: 'array', items: { type: 'string' }, description: 'cited source categories: .gov/program-admin, personal-finance media, bank/CU site, etc.' },
        answerShape: { type: 'string', description: 'list-shaped (favors brand mentions) | explanatory (favors regulators/authoritative) | mixed' },
        notes: { type: 'string' },
      } } },
  },
}

const DECISION_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verdict', 'confidence', 'ranking', 'pivot', 'reportPath'],
  properties: {
    verdict: { type: 'string', description: 'overall campaign verdict: STRONG | VIABLE | WEAK | AVOID — must reflect the BEST available target (if any prompt is VIABLE/STRONG the campaign is at least VIABLE)' },
    confidence: { type: 'string', description: 'HIGH | MEDIUM | LOW' },
    target: { type: ['object', 'null'], additionalProperties: false, required: ['promptIds', 'rationale'], properties: {
      promptIds: { type: 'array', minItems: 1, items: { type: 'integer' } },
      rationale: { type: 'string' },
    }, description: 'the locked target prompt(s); null if none viable (pivot needed)' },
    ranking: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['promptId', 'name', 'opportunity', 'verdict'],
      properties: {
        promptId: { type: 'integer' }, name: { type: 'string' },
        opportunity: { type: 'number', description: '0-100 opportunity score: demand x lender-slot openness x owned gap x winnability' },
        slotOpenness: { type: 'number', description: '0-1 fraction of responses naming any FI in body' },
        ownedGap: { type: 'number', description: '0-1, (1 - owned visibility) — room to grow' },
        demandNote: { type: 'string' },
        verdict: { type: 'string' },
      } } },
    pivot: { type: 'object', additionalProperties: false, required: ['needed'], properties: {
      needed: { type: 'boolean' },
      tier: { type: 'string', description: 're-angle | re-scope | re-campaign (re-select happens inside your ranking, never output it)' },
      plan: { type: 'string', description: 'concrete pivot: which angle/geography/segment to try and why the evidence says FIs get named there' },
      candidatePrompts: { type: 'array', description: '5-8 concrete consumer-phrased prompt texts for the pivot (no brand names), each with the angle it covers', items: { type: 'object', additionalProperties: false, required: ['text', 'angle'], properties: {
        text: { type: 'string' }, angle: { type: 'string' }, rationale: { type: 'string' },
      } } },
    } },
    reportPath: { type: 'string' },
  },
}

const PIVOT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['blocked', 'createdPromptIds'],
  properties: {
    blocked: { type: 'boolean', description: 'true if subscription/quota blocked the pivot — nothing was created or run' },
    blockedReason: { type: 'string' },
    createdPromptIds: { type: 'array', items: { type: 'integer' } },
    promptsCreated: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['id', 'text'], properties: {
      id: { type: 'integer' }, text: { type: 'string' },
      umbrellaKeyword: { type: 'string' }, monthlyVolume: { type: 'integer' },
    } } },
    droppedCandidates: { type: 'array', items: { type: 'string' }, description: 'candidates dropped at keyword triage (no measurable volume) or as duplicates' },
    ranAt: { type: 'string', description: 'note on when the new prompts were triggered' },
    notes: { type: 'string' },
  },
}

const POLL_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['populated', 'readyIds', 'pendingIds'],
  properties: {
    populated: { type: 'boolean', description: 'true when enough of the watched prompts have at least 1 response to analyze (>= 80%)' },
    readyIds: { type: 'array', items: { type: 'integer' } },
    pendingIds: { type: 'array', items: { type: 'integer' } },
    checksPerformed: { type: 'integer' },
    notes: { type: 'string' },
  },
}

const EXPERIMENT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['experimentId', 'attachedPromptIds'],
  properties: {
    experimentId: { type: ['integer', 'string'], description: 'created experiment id (or "LOCAL-ONLY" when localOnly)' },
    attachedPromptIds: { type: 'array', items: { type: 'integer' } },
    hypothesis: { type: 'string' },
    notes: { type: 'string' },
  },
}

const STRATEGY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['evidencePath', 'decisionsPath', 'analysisWritten', 'recommendationWritten'],
  properties: {
    evidencePath: { type: 'string' }, decisionsPath: { type: 'string' },
    analysisWritten: { type: 'boolean', description: 'set-experiment-analysis called (false when localOnly)' },
    recommendationWritten: { type: 'boolean' },
    actionTypesUsed: { type: 'array', items: { type: 'string' } },
    decisionCount: { type: 'integer' },
    lengthTargetWords: { type: 'integer', description: 'deliverable word-count target (midpoint of the band) decided in decisions.md, anchored to measured cited-content length' },
    lengthBasis: { type: 'string', description: 'one line: the cited-content measurement the length target is anchored to (e.g. "single-lender product pages cited on targets run ~900-1,600 words; comparison roundups excluded per rule #4")' },
    notes: { type: 'string' },
  },
}

const OUTLINE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['outlinePath', 'sections'],
  properties: {
    outlinePath: { type: 'string' },
    chosenVariant: { type: 'string', description: 'which of the judged outline variants won, and why' },
    sections: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['heading', 'wordTarget'], properties: {
      heading: { type: 'string' }, purpose: { type: 'string' }, wordTarget: { type: 'integer' },
    } } },
  },
}

const DRAFT_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['articlePath', 'wordCount'],
  properties: {
    articlePath: { type: 'string' },
    wordCount: { type: 'integer' },
    lengthTargetWords: { type: 'integer', description: 'the deliverable length target from decisions.md the draft was written to' },
    withinLengthTarget: { type: 'boolean', description: 'true if wordCount lands inside the decided length band; if false, explain in openItemsForReview' },
    sectionsWritten: { type: 'integer' },
    citationsIncluded: { type: 'integer', description: 'inline source citations for the fact-checker to verify' },
    openItemsForReview: { type: 'array', items: { type: 'string' }, description: 'POC-supplied facts or claims to carry into /exp-review and the deliverable action items / Phase 9 review — NOT a draft-review stop; the suite continues automatically' },
  },
}

// ---- round helpers (Census / Analyze / Decide / poll, reusable across pivot rounds)

async function takeCensus(tag) {
  return agent(
    `You are taking a visibility census of Paraloom campaign ${campaignId} (team ${teamId}); owned org: ${owned}. (${tag})
Load the Paraloom read tools: ToolSearch "select:${PARALOOM_READS}".
1. list-prompts(team_id ${teamId}, campaign_id ${campaignId}) — per-prompt owned-org visibility % and responseCount.
2. get-org-visibility(team_id ${teamId}, campaign_id ${campaignId}, limit 0) — the full org ranking (owned vs competitors).
Return the census object (mark which org row is the owned one: ${owned}).`,
    { label: `census:${tag}`, phase: 'Census', schema: CENSUS_SCHEMA }
  )
}

async function analyzePrompts(promptRows, tag) {
  if (!promptRows.length) return []
  return (await parallel(
    chunk(promptRows, CHUNK).map((grp, gi) => () =>
      agent(
        `You are analyzing the LLM responses behind specific prompts in Paraloom campaign ${campaignId} (team ${teamId}); owned org: ${owned}. (${tag})
Load Paraloom read tools: ToolSearch "select:${PARALOOM_READS}".

For EACH prompt below: list-responses(team_id ${teamId}, prompt_id <id>), sample up to ${sampleN} responses, and get-response for the ones you need to read the body. Then assess:
- fiNamingResponses: how many sampled responses name ANY financial institution (bank / credit union / mortgage lender) IN THE BODY TEXT. This is the LENDER-SLOT signal (methodology rule #3) — a prompt where 0 responses name any FI is structurally hostile no matter the demand.
- ownedMentioned: how many name ${owned} in body.
- competitorsNamed: distinct FI competitors named.
- sourceTypes: what kinds of sources are cited (.gov / program-administrator, personal-finance media, bank/CU site, aggregator).
- answerShape: list-shaped (favors brand mentions) | explanatory (favors regulators/authoritative pages) | mixed.

Prompts (${tag}, chunk ${gi + 1}):
${JSON.stringify(grp.map(p => ({ id: p.id, name: p.name, ownedVisibility: p.visibility })), null, 2)}

Return one row per prompt.`,
        { label: `analyze:${tag}:chunk-${gi + 1}`, phase: 'Analyze', schema: ANALYSIS_SCHEMA }
      )
    )
  )).filter(Boolean).flatMap(r => r.rows || [])
}

async function decideRound(census, analysisRows, round, pivotHistory, unanalyzedIds) {
  const pivotContext = pivotHistory.length
    ? `\nPIVOTS ALREADY EXECUTED (do not propose these again; their new prompts appear in the census, and the analyzed ones are in the analysis rows):\n${JSON.stringify(pivotHistory, null, 2)}\n`
    : ''
  const pendingContext = unanalyzedIds.length
    ? `\nNOT YET ANALYZED (responses still pending for prompt ids ${JSON.stringify(unanalyzedIds)}): treat these as PENDING, not closed slots — do not score them AVOID for lack of data, and say so in the report if one of them could matter.\n`
    : ''
  return agent(
    `You are deciding the visibility opportunity for experiment "${slug}" from Paraloom campaign ${campaignId}; owned org: ${owned}. (decision round ${round + 1})

If ${dir}/tracked-prompts.md exists, Read it for per-prompt keyword DEMAND. If it does not exist, score on the Paraloom signals alone and mark demandNote "not available (Paraloom-data-only)".
${pivotContext}${pendingContext}
Census (owned visibility per prompt + org ranking):
${JSON.stringify(census, null, 2)}

Per-prompt response analysis:
${JSON.stringify(analysisRows, null, 2)}

For EACH analyzed prompt compute:
- slotOpenness = fiNamingResponses / sampled (0 = structurally hostile; methodology rule #3).
- ownedGap = 1 - (owned visibility / 100). High gap = room to grow.
- opportunity (0-100) = demand-weight x slotOpenness x ownedGap x winnability. Winnability is higher when the slot is open AND ${owned} already holds a foothold on adjacent prompts (shows the LLMs will cite it here). A 0% prompt where strong competitors ARE named is a prime gap; a 0% prompt where NO FI is named is NOT (closed slot).
- a per-prompt verdict (STRONG/VIABLE/WEAK/AVOID).

Then a CAMPAIGN-level Viability Verdict block (STRONG | VIABLE | WEAK | AVOID + confidence), exactly per the SOP Phase 5 format: lender slot (N/M), source diversity, competitor presence, answer shape. The campaign verdict reflects the BEST available target: if any prompt is VIABLE/STRONG, the campaign is at least VIABLE.

Decision rule:
- If the best prompt is VIABLE/STRONG → lock it (and any tightly-related prompts) as the target with at least one prompt id; pivot.needed = false.
- If NO prompt is viable (slots closed / owned locked out with no foothold; campaign verdict WEAK or AVOID) → target = null, pivot.needed = true. Re-selection among already-run prompts happens INSIDE your ranking — never output tier "re-select". Output the pivot to EXECUTE: tier "re-angle" (untried intent angle in the same market) or "re-scope" (materially different geography / target segment) — reserve "re-campaign" for a barren market where only an adjacent-market sibling campaign makes sense (it will be returned to the human, not executed). Provide pivot.candidatePrompts: 5-8 concrete consumer-phrased prompt texts (the way a consumer asks an AI assistant; NO brand names) targeting surfaces where the evidence says FIs DO get named (e.g. comparative/list-shaped surfaces), each with its angle. Ground them in the analysis: what answer shapes and source types had open lender slots?

Write ${dir}/build-analysis.md (overwrite if present): the campaign Viability Verdict block, the opportunity ranking table (prompt, opportunity, slotOpenness, ownedGap, verdict), the locked target (or the pivot plan), and a short "biggest opportunity, and why" paragraph for the owned-org reader. Then return the structured object.`,
    { label: `decide:round-${round + 1}`, phase: 'Decide', schema: DECISION_SCHEMA }
  )
}

async function pollForResponses(watchIds, tag, contextNote) {
  return agent(
    `You are waiting for Paraloom LLM responses to populate (${contextNote}). Watched prompt ids: ${JSON.stringify(watchIds)} (campaign ${campaignId}, team ${teamId}).
Responses typically take 5-30 minutes after a run is triggered.

Load: ToolSearch "select:${PARALOOM}list-prompts". Check responseCount per watched prompt via list-prompts(team_id ${teamId}, campaign_id ${campaignId}).
Poll with waits between checks: load the Monitor tool (ToolSearch "select:Monitor") and use it to wait ~3 minutes between checks, up to ~8 checks (~25 minutes total). If Monitor is unavailable or cannot wait, fall back to a few immediate re-checks and report honestly.

populated = true once >= 80% of the watched prompts have responseCount >= 1. Stop early when that holds. If the wait budget runs out first, return populated = false with the pending ids — do NOT overstate progress.`,
    { label: `poll:${tag}`, phase: 'Pivot', schema: POLL_SCHEMA }
  )
}

// Structured halt for a dead serial agent — never let a null deref eat the run
// state, especially after Paraloom writes may already have happened.
function agentDied(which, extra) {
  return {
    slug, campaignId, halted: true, mode: 'agent-died',
    pivotsExecuted,
    reason: `${which} agent returned null (subagent died or was skipped). ${extra || ''} Re-run /exp-build with the same args — the run is idempotent.`.trim(),
  }
}

// ---- the opportunity loop: Census -> Analyze -> Decide -> (Pivot) ---------
phase('Census')
const analysisById = new Map()
const pivotsExecuted = []
let census = null
let decision = null
let round = 0

while (true) {
  const tag = round === 0 ? 'initial' : `post-pivot-${round}`
  census = await takeCensus(tag)
  if (!census) return agentDied('census')
  log(`Census (${tag}): ${census.prompts.length} prompts, ${census.orgs.length} orgs, ${owned} overall visibility ${census.ownedVisibilityOverall}%`)

  // Population gate: analyze only once enough of the campaign has responses.
  // Mirrors the poll's >=80% threshold — an all-or-nothing check here would let a
  // mid-flight run (1 of 19 prompts populated) be scored as a near-empty campaign
  // and could trigger a quota-burning pivot on garbage data.
  const readyCount = census.prompts.filter(p => p.responseCount > 0).length
  if (census.prompts.length && readyCount / census.prompts.length < READY_FRACTION) {
    log(`Only ${readyCount}/${census.prompts.length} prompts have responses — polling for population (bounded ~25 min)`)
    const poll = await pollForResponses(census.prompts.map(p => p.id), `${tag}-populate`, round === 0 ? 'baseline run after /exp-research' : `population check before decision round ${round + 1}`)
    if (!poll || !poll.populated) {
      return {
        slug, campaignId, mode: 'awaiting-responses', halted: true, pivotsExecuted,
        pendingPromptIds: poll ? poll.pendingIds : census.prompts.filter(p => !p.responseCount).map(p => p.id),
        reason: `Responses have not reached the ${READY_FRACTION * 100}% population threshold (${poll ? (poll.notes || 'timed out waiting') : 'poll agent returned null'}). Re-run /exp-build with the same args once they have — the run is idempotent.`,
      }
    }
    census = await takeCensus(`${tag}-refreshed`)
    if (!census) return agentDied('census (refresh)')
  }

  // Analyze prompts that are new OR whose response set has grown since we
  // analyzed them (stale rows would freeze slotOpenness at the old sample).
  const newRows = census.prompts.filter(p => {
    if (p.responseCount <= 0) return false
    const prior = analysisById.get(p.id)
    return !prior || p.responseCount > prior.censusResponseCount
  })
  const analyzed = await analyzePrompts(newRows, tag)
  const countById = new Map(census.prompts.map(p => [p.id, p.responseCount]))
  for (const row of analyzed) analysisById.set(row.promptId, { ...row, censusResponseCount: countById.get(row.promptId) ?? 0 })
  const allRows = Array.from(analysisById.values())
  const unanalyzedIds = census.prompts.filter(p => !analysisById.has(p.id)).map(p => p.id)
  log(`Analyzed ${analyzed.length} new/updated prompts (${allRows.length} total, ${unanalyzedIds.length} still pending); ${allRows.filter(r => r.fiNamingResponses > 0).length} have an open lender slot`)

  decision = await decideRound(census, allRows, round, pivotsExecuted, unanalyzedIds)
  if (!decision) return agentDied('decide')
  const locked = !!(decision.target && Array.isArray(decision.target.promptIds) && decision.target.promptIds.length)
  log(`Verdict (round ${round + 1}): ${decision.verdict} (${decision.confidence}). ${locked ? `Target locked: prompts ${decision.target.promptIds.join(', ')}` : `No viable target — pivot tier: ${decision.pivot.tier || 'n/a'}`}`)

  const pivotNeeded = !locked || decision.verdict === 'WEAK' || decision.verdict === 'AVOID'
  if (!pivotNeeded) break

  // ---- guards: each returns the closest opportunities + a recommended human pivot
  // rather than forcing a bad target (design doc §5 Phase B).
  const guardResult = (mode, reason) => ({
    slug, campaignId, mode, halted: true,
    verdict: decision.verdict, confidence: decision.confidence,
    pivotsExecuted,
    topOpportunities: (decision.ranking || []).slice().sort((x, y) => y.opportunity - x.opportunity).slice(0, 5),
    recommendedPivot: decision.pivot,
    reportPath: decision.reportPath,
    reason,
  })

  if (stopAfter === 'analyze') {
    return { ...guardResult('analyze-only (read-only)', `Verdict ${decision.verdict}; pivot ${decision.pivot.needed ? `recommended (${decision.pivot.tier})` : 'not needed'} — read-only run, nothing executed.`), halted: false }
  }
  if (localOnly) {
    return guardResult('halted-no-target (localOnly)', `Verdict ${decision.verdict} and localOnly forbids the Paraloom writes a pivot needs. Recommended pivot: ${decision.pivot.plan || 'n/a'}`)
  }
  // Tier gate is a whitelist: only re-angle / re-scope execute autonomously.
  const tier = ((decision.pivot && decision.pivot.tier) || '').toLowerCase().trim()
  if (tier === 're-campaign') {
    return guardResult('halted-re-campaign', `The recommended pivot is a sibling campaign for an adjacent market — a human call. Plan: ${decision.pivot.plan || 'n/a'}. If you agree, run /exp-research for the new market, then /exp-build on its campaign.`)
  }
  if (!['re-angle', 're-scope'].includes(tier)) {
    return guardResult('halted-unknown-pivot-tier', `decide returned pivot tier '${decision.pivot.tier || '(none)'}' — only re-angle / re-scope execute autonomously; a human should choose the next move.`)
  }
  if (round >= maxPivots) {
    return guardResult('halted-max-pivots', `maxPivots (${maxPivots}) reached without a viable target. Closest opportunities + the next recommended pivot are attached; a human should choose the next move.`)
  }
  if (budget.total && budget.remaining() < MIN_BUDGET_FOR_PIVOT) {
    return guardResult('halted-token-budget', `Token budget too low for another pivot round (${Math.round(budget.remaining() / 1000)}k remaining < ${MIN_BUDGET_FOR_PIVOT / 1000}k needed).`)
  }
  if (!decision.pivot.candidatePrompts || !decision.pivot.candidatePrompts.length) {
    return guardResult('halted-no-pivot-plan', 'Pivot needed but the decision produced no candidate prompts — inspect build-analysis.md and pivot manually.')
  }

  // ---- execute the pivot: keyword-ground, dedupe, create, run ONLY the new prompts
  const pivotNum = round + 1
  log(`Pivot ${pivotNum}/${maxPivots} (${tier}): ${(decision.pivot.plan || '').slice(0, 120)}`)
  const pivot = await agent(
    `You are executing pivot round ${pivotNum} (tier: ${tier}) for experiment "${slug}" — Paraloom campaign ${campaignId}, team ${teamId}. Owned org: ${owned}. Geography: ${geography || '(see experiment.md)'}; audience: ${audience || '(see experiment.md)'}.

The analysis verdict was ${decision.verdict}; the pivot plan: ${decision.pivot.plan}

Candidate prompts (from the analysis):
${JSON.stringify(decision.pivot.candidatePrompts, null, 2)}

Steps, in order:
1. GATE: ToolSearch "select:${PARALOOM}get-team-usage" then get-team-usage(team_id ${teamId}). If Subscription is not Active, or remaining responses < (number of candidates x 3 providers), return blocked=true with the reason and STOP — create and run nothing.
2. KEYWORD-GROUND each candidate with the keyword-research skill (methodology rules #1/#2): translate to the SHORTEST umbrella noun-phrase keyword form FIRST ("auto refinance rates", not the stacked-modifier prompt literal); on a 0/mo result retry the bare-noun form once; a candidate whose umbrella form has no measurable volume is DROPPED. Keep the 3-6 best by volume.
3. DEDUPE: ToolSearch "select:${PARALOOM}list-prompts" then list-prompts(team_id ${teamId}, campaign_id ${campaignId}); drop any candidate that duplicates an existing prompt's intent.
4. CREATE: ToolSearch "select:${PARALOOM}create-prompt" then create-prompt for each kept candidate (consumer phrasing, NO brand names).
5. RUN ONLY THE NEW PROMPTS: ToolSearch "select:${PARALOOM}run-prompt" then run-prompt for EACH new prompt id, providers ["openai","anthropic","gemini"] if the tool accepts a providers parameter (otherwise its default). NEVER call run-campaign-prompts here — it would re-run the whole campaign and burn quota.
6. RECORD: append the new prompts (text, umbrella keyword, volume) to ${dir}/tracked-prompts.md (create it if missing) and log the pivot in ${dir}/workflow-log.md: round, tier, plan, new prompt ids. Do NOT record any human sign-off — sign-offs are the human's to write.

If every candidate is dropped at triage (no demand), return blocked=true with reason "no candidate survived keyword triage" — creating zero-demand prompts violates rule #1.
Return the structured object.`,
    { label: `pivot:round-${pivotNum}`, phase: 'Pivot', schema: PIVOT_SCHEMA }
  )

  if (!pivot) {
    return guardResult('halted-pivot-agent-died', `Pivot ${pivotNum} agent returned null mid-execution — check list-prompts(team ${teamId}, campaign ${campaignId}) and workflow-log.md for any prompts it created before dying, then re-run /exp-build (idempotent: the next census picks them up).`)
  }
  if (pivot.blocked) {
    return guardResult('halted-pivot-blocked', `Pivot ${pivotNum} blocked: ${pivot.blockedReason || 'unknown'}. Nothing was created or run.`)
  }
  pivotsExecuted.push({ round: pivotNum, tier, plan: decision.pivot.plan, createdPromptIds: pivot.createdPromptIds })
  log(`Pivot ${pivotNum}: created + ran ${pivot.createdPromptIds.length} prompts (${pivot.createdPromptIds.join(', ')}); ${(pivot.droppedCandidates || []).length} dropped at triage`)

  // ---- async boundary: wait (bounded) for the new prompts' responses
  const poll = await pollForResponses(pivot.createdPromptIds, `pivot-${pivotNum}`, `pivot ${pivotNum} prompts just triggered`)
  if (!poll || !poll.populated) {
    return {
      ...guardResult('pivot-prompts-running', ''),
      halted: false,
      reason: `Pivot ${pivotNum} created and ran ${pivot.createdPromptIds.length} new prompts (${pivot.createdPromptIds.join(', ')}) but their responses had not populated within the wait budget${poll ? '' : ' (poll agent returned null)'}. Re-run /exp-build with the same args in ~15-30 min — the run is idempotent (census picks up the new prompts; the experiment step reuses any existing draft experiment).`,
    }
  }
  round++
}

// ---- target locked ---------------------------------------------------------
const analyzeResult = {
  slug, campaignId,
  verdict: decision.verdict, confidence: decision.confidence,
  target: decision.target, pivot: decision.pivot, pivotsExecuted,
  topOpportunities: (decision.ranking || []).slice().sort((x, y) => y.opportunity - x.opportunity).slice(0, 5),
  reportPath: decision.reportPath,
}

if (stopAfter === 'analyze') return { ...analyzeResult, mode: 'analyze-only (read-only)' }

const targetIds = decision.target.promptIds
const targetNames = (decision.ranking || []).filter(r => targetIds.includes(r.promptId)).map(r => r.name)
const writeNote = localOnly ? ' (localOnly: write NOTHING to Paraloom — local files only)' : ''

// ---- Experiment ----------------------------------------------------------
phase('Experiment')
const experiment = await agent(
  `You are committing the Paraloom experiment for "${slug}" (team ${teamId}, campaign ${campaignId}).${writeNote}
Owned org: ${owned}. Locked target prompt ids: ${JSON.stringify(targetIds)} (${targetNames.join(' | ')}).

Read ${dir}/build-analysis.md for each target prompt's current owned visibility (the baseline to beat).

1. Write the hypothesis into ${dir}/experiment.md (SOP Phase 4 form): "If we publish a long-form answer page that <does X — the concrete substantiable hook from the analysis>, owned visibility on the target prompt(s) will rise from <current %> toward <target %> within <28 days default>, because the response analysis shows <the missing element>." Record the target prompt ids + names + baseline visibility.
${localOnly
  ? '2. localOnly run: DO NOT create a Paraloom experiment. Return experimentId = "LOCAL-ONLY" and attachedPromptIds = the target ids.'
  : `2. Load write tools: ToolSearch "select:${PARALOOM}list-experiments,${PARALOOM}create-experiment,${PARALOOM}update-experiment,${PARALOOM}get-experiment". IDEMPOTENCY FIRST, scoped to THIS experiment — never seize an unrelated draft: (a) Read ${dir}/experiment.md; if it already records a Paraloom experiment id for this experiment, reuse that id (verify with get-experiment). (b) Otherwise list-experiments(team_id ${teamId}, campaign_id ${campaignId}) and reuse a DRAFT experiment ONLY if it clearly belongs to this experiment — its name matches this topic/slug, or its attached prompt_ids are empty or overlap ${JSON.stringify(targetIds)}. A draft for a DIFFERENT topic may legitimately sit on this campaign (e.g. staged awaiting publish) — leave it alone. (c) Only if neither matches, create-experiment(team_id ${teamId}, name <tie to topic>, campaign_id ${campaignId}, status "draft") — do NOT pass started_at/ended_at (they auto-derive at publish; setting them early starts the clock). Then update-experiment to attach prompt_ids = the locked target ids (this experiment's targets are the ones THIS run selected). get-experiment to verify. Record the experiment id in experiment.md and workflow-log.md.`}
Return the structured object.`,
  { label: 'experiment', phase: 'Experiment', schema: EXPERIMENT_SCHEMA }
)
if (!experiment) return { ...analyzeResult, halted: true, mode: 'agent-died', reason: 'experiment agent returned null — it may have created/updated the Paraloom experiment before dying; check list-experiments + experiment.md, then re-run /exp-build (idempotent reuse).' }
const experimentId = experiment.experimentId
log(`Experiment: ${experimentId} (target prompts ${experiment.attachedPromptIds.join(', ')})`)

// ---- Strategy ------------------------------------------------------------
phase('Strategy')
const strategy = await agent(
  `You are writing the Phase 5 strategy for experiment "${slug}" (id ${experimentId}); owned org: ${owned}.${writeNote}
Inputs: ${dir}/build-analysis.md (the viability analysis, competitor hooks, locked target) and ${dir}/tracked-prompts.md if it exists (keyword demand).

1. Write ${dir}/evidence.md — every empirical input as an OBSERVATION WITH A CITATION (response patterns, cited sources, competitor moves like Summit's "WI #1 by HMDA" / UW's closing-cost commitment, best practices). Never a prescription. INCLUDE A LENGTH ANCHOR (rule #20): identify the specific competitor pages the baseline cited for the LOCKED target prompt(s), browse a representative sample (Playwright/web), and record each page's main-content word count as an observation — separating single-lender product/rate pages (the surface ${owned}'s page emulates) from multi-lender comparison roundups (Bankrate-style; the surface we do NOT emulate, rule #4). Report the distribution (range + rough median) for each class, each with its URL citation. If a cited page is JS-rendered and the body can't be counted headlessly, note that limit rather than guessing.
2. Write ${dir}/decisions.md — translate evidence into tactical content choices. For EACH: Choice / Evidence supporting / **Alternatives considered and rejected — and why**. You MUST include the canonical reject (methodology rule #4): do NOT mimic the comparison surface by listing competitor FIs in ${owned}'s own page — the pattern is that LLMs cite top performers in COMPARATIVE contexts, which does not mean the owned page should name competitors. Also encode: rates off-body linking to the rates page (rule #5), no "best/top/trusted" self-claims (rule #6), concrete + quantitative + substantiable hooks (rule #8). INCLUDE A "Deliverable length" DECISION (rule #20): a target word-count BAND anchored to the cited single-lender pages' measured lengths, sized to cover every decision and the winning answer-shape WITHOUT padding. Rejected alternatives MUST include both "longer is better / a 10k-word pillar" (no cited page is that long; padding dilutes the concrete hooks that win citations and raises compliance-review cost for zero citation benefit) AND "match the longest comparison roundup" (that is the rule-#4 surface we don't mimic; its length comes from covering many lenders, not from the single-lender answer we publish). Return lengthTargetWords (band midpoint) and lengthBasis.
${localOnly
  ? '3. localOnly run: DO NOT call set-experiment-analysis / set-experiment-recommendation. Note in the return that they were skipped.'
  : `3. Load write tools: ToolSearch "select:${PARALOOM}list-action-types,${PARALOOM}set-experiment-analysis,${PARALOOM}set-experiment-recommendation". Call list-action-types FIRST (BLOCK on guessing types). Then set-experiment-analysis (team ${teamId}, experiment ${experimentId}) — the narrative MUST open with the Viability Verdict block from build-analysis.md, then findings; plain language for a credit-union marketing manager, keyword volumes referenced prompt-by-prompt, 30-second-takeaway test. Then set-experiment-recommendation with a strategic summary + 1-3 action items (each title/description/valid type). set-* REPLACE not patch — build the full payload.`}
Return the structured object.`,
  { label: 'strategy', phase: 'Strategy', schema: STRATEGY_SCHEMA }
)
if (!strategy) return { ...analyzeResult, experimentId, halted: true, mode: 'agent-died', reason: 'strategy agent returned null — evidence/decisions and the Paraloom analysis may be partially written; check the experiment folder and the Paraloom record, then re-run /exp-build (set-* calls replace, so a re-run is safe).' }
log(`Strategy: ${strategy.decisionCount || '?'} decisions; Paraloom analysis ${strategy.analysisWritten ? 'written' : 'skipped'}`)

// ---- Outline (judge-panel) -----------------------------------------------
phase('Outline')
const outline = await agent(
  `You are producing the Phase 6 outline for experiment "${slug}". Read ${dir}/decisions.md and ${dir}/build-analysis.md.
Owned org: ${owned}. Geography: ${geography || '(from experiment.md)'}. Audience: ${audience || '(from experiment.md)'}.

Judge-panel: draft 2-3 DISTINCT outline approaches (e.g. narrative-explainer-with-sidebar vs structured-FAQ vs decision-guide). Score each on: coverage of every decision in decisions.md, brand-favorable answer shape (list/roster surfaces win citations here), and citation-attractiveness (concrete substantiable hooks, rule #8). Pick the winner; state which won and why (chosenVariant).

Write ${dir}/article-${slug}.outline.md: single H1, 4-8 H2 sections, H3 only where needed. Per section: Heading, Purpose, Key claims (referencing evidence.md items), Research gap (sources to pull), Word-count target, any table/visual. The SUM of the per-section Word-count targets MUST reconcile to the "Deliverable length" band in decisions.md (the cited-content anchor, rule #20) — size sections to cover the content, do not pad to hit an arbitrary long-form length. Encode rule #5 (rates off-body), #6 (no superlatives), #8 (concrete hooks). Return the structured object.`,
  { label: 'outline', phase: 'Outline', schema: OUTLINE_SCHEMA }
)
if (!outline) return { ...analyzeResult, experimentId, halted: true, mode: 'agent-died', reason: 'outline agent returned null — strategy files are written; re-run /exp-build to redo the outline + draft (Paraloom state is already committed and reused idempotently).' }
log(`Outline: ${outline.sections.length} sections (${outline.chosenVariant?.slice(0, 60) || ''})`)

// ---- Draft ---------------------------------------------------------------
phase('Draft')
const draft = await agent(
  `You are drafting the Phase 7 article for experiment "${slug}" from the approved outline ${dir}/article-${slug}.outline.md. Also read ${dir}/decisions.md.
Owned org: ${owned}${domain ? ` (${domain})` : ''}. Geography: ${geography || '(from experiment.md)'}.

Write the full article to ${dir}/article-${slug}.md following the outline section by section. Rules (hard):
- NO em-dashes (—) or en-dashes (–) ANYWHERE: not in prose, not inside link anchor text, not in review markers. They are the project's #1 AI-tell and the hygiene check BLOCKs them. Use commas, colons, or parentheses; in a link label use a colon, e.g. [WHEDA: first-time buyer programs](url). For a review marker use [[POC: ...]] (a colon, never a dash). Also avoid AI-typical phrases ("delve into", "in conclusion", "it's worth noting").
- Cite sources inline as you make factual claims so the Phase 8 fact-checker has clean targets.
- NO specific rate/APR/payment/down-payment numbers tied to ${owned} in the body — link to ${owned}'s rates page instead (Reg Z, rule #5).
- NO "best / top-rated / trusted" superlatives about ${owned} without substantiation (Part 740, rule #6).
- Lead ${owned}'s positioning with concrete, quantitative, substantiable hooks (rule #8); do NOT list competitor FIs in the body (rule #4).
- LENGTH (rule #20): write to the "Deliverable length" band in decisions.md (anchored to cited-content lengths). Cover every section fully; do NOT pad to reach a longer count. If the finished draft lands materially outside the band, set withinLengthTarget=false and explain why in openItemsForReview.
- Plain language, Flesch-Kincaid grade <= 9 where the terms-of-art allow; intro + conclusion last.
- DRAFT TO THE VERIFIED SITE (rule #9). Before asserting anything about ${owned}, browse ${owned}'s live website (Playwright/web) and draft the claim in wording the site itself supports: use the site's own published figures and framing ("up to 100% combined loan-to-value", "live or work in southern Wisconsin"), never a vaguer or stronger paraphrase ("high CLTV", a county list the site doesn't publish). Pull published facts (page URLs, branch addresses/phones, application channels, eligibility wording) FROM the site yourself instead of writing a placeholder for them. The website is presumed compliant for its own wording. A claim the site cannot support ships in its softened, site-supported form NOW; the stronger version is an opt-in upgrade flagged in openItemsForReview, never a hole in the draft. Every [[POC: ...]] placeholder becomes a client action item downstream, so the bar for writing one is "only the client can know this".
- Genuinely client-only facts (years served, volumes, named officers, internal program participation, charter/FOM scope beyond published wording) → write a clear placeholder and add it to openItemsForReview; do NOT invent it.
Return the structured object. This draft is v1, headed for /exp-review (it is review-ready, not publish-ready).`,
  { label: 'draft', phase: 'Draft', schema: DRAFT_SCHEMA }
)
if (!draft) return { ...analyzeResult, experimentId, halted: true, mode: 'agent-died', reason: 'draft agent returned null — outline and strategy are on disk; re-run /exp-build to redo the draft (earlier phases replay from idempotent state).' }
log(`Draft: ${draft.wordCount} words${draft.lengthTargetWords ? ` (target ~${draft.lengthTargetWords}, ${draft.withinLengthTarget === false ? 'OUT OF band — see openItems' : 'within band'})` : ''}, ${draft.citationsIncluded || 0} citations, ${(draft.openItemsForReview || []).length} POC items flagged`)

return {
  ...analyzeResult,
  mode: localOnly ? 'localOnly (content files; no Paraloom writes)' : 'full',
  experimentId,
  evidencePath: strategy.evidencePath,
  decisionsPath: strategy.decisionsPath,
  outlinePath: outline.outlinePath,
  articlePath: draft.articlePath,
  openItemsForReview: draft.openItemsForReview || [],
  nextStep: `run /exp-review on ${draft.articlePath} (and confirm any POC-supplied facts flagged in openItemsForReview)`,
}
