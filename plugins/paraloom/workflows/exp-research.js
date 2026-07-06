export const meta = {
  name: 'exp-research',
  description: 'Phase 1-2: research a topic, generate keyword-grounded candidate prompts across intent angles / geographies / segments, triage to a demand-validated set, then create (or reuse) the Paraloom campaign, create the prompts, and run them. Pass dryRun:true to stop after triage with no writes.',
  whenToUse: 'First step of an experiment. Run it for a team + topic to stand up a demand-grounded campaign and kick off baseline LLM runs. Then (once responses populate) run /exp-build.',
  phases: [
    { title: 'Frame', detail: 'pick new/existing campaign + generate wide candidate prompt set' },
    { title: 'Ground', detail: 'keyword-research each candidate (chunked) for real demand' },
    { title: 'Triage', detail: 'Keep/Refine/Drop -> keyword-research.md + tracked-prompts.md' },
    { title: 'Instantiate', detail: 'create/reuse campaign, create prompts, run them (skipped on dryRun)' },
  ],
}

// ---- args ----------------------------------------------------------------
// {
//   slug, teamId, topic, geography      (required)
//   audience, creditUnion, domain       (recommended)
//   campaignId?   -> reuse this campaign instead of deciding new-vs-existing
//   seedPrompts?  -> start from these instead of (or in addition to) generated ones
//   dryRun?       -> true = stop after Triage, make NO Paraloom writes
// }
let a = args || {}
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { throw new Error('exp-research: args must be a JSON object or JSON string') } }
a = a || {}
for (const k of ['slug', 'teamId', 'topic', 'geography']) {
  if (a[k] === undefined || a[k] === null || a[k] === '') throw new Error(`exp-research: args.${k} is required`)
}
const slug = a.slug
const dir = `experiments/${slug}`
const dryRun = !!a.dryRun
// Paraloom MCP target. Default PROD (mcp__claude_ai_Paraloom__) per CLAUDE.md's environment rule;
// pass mcpPrefix:'mcp__paraloom-local__' to target the local dev checkout. Baseline runs (Instantiate)
// need the target team's subscription Active.
const PARALOOM = a.mcpPrefix || 'mcp__claude_ai_Paraloom__'
const CHUNK = 5 // candidates per keyword-research agent — small enough to dodge the DataForSEO bulk zero-volume quirk

function chunk(arr, n) {
  const out = []
  for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n))
  return out
}

const FRAME_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['campaignDecision', 'campaignName', 'framed', 'candidates'],
  properties: {
    campaignDecision: { type: 'string', description: "'new' or 'existing'" },
    campaignId: { type: ['integer', 'null'], description: 'set when reusing an existing campaign' },
    campaignName: { type: 'string' },
    campaignDescription: { type: 'string' },
    framed: {
      type: 'object', additionalProperties: false,
      required: ['topic', 'audience', 'geography', 'segments'],
      properties: {
        topic: { type: 'string' },
        audience: { type: 'string' },
        geography: { type: 'string' },
        segments: { type: 'array', items: { type: 'string' }, description: 'target-market variants to spread candidates across' },
      },
    },
    candidates: {
      type: 'array', description: '20-40 candidate prompts spread across intent angles, geographies, and segments',
      items: {
        type: 'object', additionalProperties: false,
        required: ['ref', 'prompt', 'angle'],
        properties: {
          ref: { type: 'string', description: 'short stable id, e.g. c01' },
          prompt: { type: 'string', description: 'consumer-phrased question; NEVER contains a brand name' },
          angle: { type: 'string', description: 'informational | comparative | transactional | locational' },
          geo: { type: 'string', description: 'geography this variant targets (may equal the campaign geography)' },
          segment: { type: 'string', description: 'target segment this variant targets' },
        },
      },
    },
  },
}

const GROUND_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['rows'],
  properties: {
    rows: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['ref', 'prompt', 'topPhrase', 'monthlyVolume'],
        properties: {
          ref: { type: 'string' },
          prompt: { type: 'string' },
          topPhrase: { type: 'string', description: 'highest-volume translated umbrella phrase' },
          monthlyVolume: { type: 'integer', description: 'search volume for topPhrase in the target geography (0 if none)' },
          phrases: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['phrase', 'volume'], properties: { phrase: { type: 'string' }, volume: { type: 'integer' } } } },
          aiModeNote: { type: 'string', description: 'context only (who AI Mode cites); NOT demand evidence' },
          suggestedRefine: { type: 'string', description: 'a higher-volume rephrasing if the prompt tracked poorly; empty otherwise' },
        },
      },
    },
  },
}

const TRIAGE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['keptCount', 'droppedCount', 'uniqueVolume', 'totalVolume', 'kept', 'files'],
  properties: {
    keptCount: { type: 'integer' },
    droppedCount: { type: 'integer' },
    uniqueVolume: { type: 'integer', description: 'demand counting each DISTINCT top phrase once (the honest client-facing number)' },
    totalVolume: { type: 'integer', description: 'raw sum of per-prompt top-phrase volume (double-counts shared phrases)' },
    kept: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['prompt', 'topPhrase', 'monthlyVolume', 'verdict'],
        properties: {
          prompt: { type: 'string' },
          topPhrase: { type: 'string' },
          monthlyVolume: { type: 'integer' },
          verdict: { type: 'string', description: 'Keep | Refined→Kept | Rescued' },
        },
      },
    },
    files: { type: 'object', additionalProperties: true, description: 'paths written (keyword-research.md, tracked-prompts.md, experiment.md)' },
  },
}

const INSTANTIATE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['campaignId', 'createdCampaign', 'promptIds', 'ranBatch'],
  properties: {
    campaignId: { type: 'integer' },
    createdCampaign: { type: 'boolean', description: 'true if a new campaign was created, false if reused' },
    promptIds: { type: 'array', items: { type: 'integer' } },
    ranBatch: { type: 'boolean' },
    usageNote: { type: 'string', description: 'get-team-usage check result / quota caveat' },
    notes: { type: 'string' },
  },
}

// ---- Frame ---------------------------------------------------------------
phase('Frame')
const reuseClause = a.campaignId
  ? `Reuse the existing campaign with id ${a.campaignId} (campaignDecision='existing', campaignId=${a.campaignId}).`
  : `Decide new-vs-existing: load Paraloom tools (ToolSearch "select:${PARALOOM}list-teams,${PARALOOM}list-campaigns"), call list-campaigns for team ${a.teamId}, and if an existing campaign clearly covers this topic, reuse it; otherwise propose a new campaign (campaignDecision='new', campaignId=null) with a clear name + description tied to the topic.`

const frame = await agent(
  `You are framing a new Paraloom experiment for team ${a.teamId}.
Topic: ${a.topic}
Audience: ${a.audience || '(derive a sensible primary audience)'}
Geography: ${a.geography}
Owned org: ${a.creditUnion || '(not specified)'}${a.domain ? ` (${a.domain})` : ''}

1. ${reuseClause}

2. Frame the experiment: a one-paragraph topic statement, the primary audience, the geography, and 2-4 target-market SEGMENTS worth spreading prompts across (e.g. first-time buyers vs refinancers; different counties/metros within the geography).

3. Generate a WIDE candidate prompt set (aim 24-36 prompts) spread across:
   - intent angles: informational, comparative, transactional, locational
   - the segments and any geography variants from step 2
   The breadth is deliberate: a later workflow (/exp-build) picks the biggest opportunity from this set and pivots among these prompts, so cover the space.
   RULES: write each prompt the way a consumer would ask an AI assistant. NEVER put a brand/credit-union name in the prompt text — we measure which brands the LLM mentions organically. ${a.creditUnion ? `Do NOT mention ${a.creditUnion}.` : ''}

4. Write the opening of ${dir}/experiment.md: title, topic statement, audience, geography, segments, and a "Status: Phase 1 — scoping" line. Create the ${dir}/ folder if needed (your file tools will).

Return the structured object.`,
  { label: 'frame', phase: 'Frame', schema: FRAME_SCHEMA }
)

if (!frame) throw new Error('exp-research: frame agent returned null (subagent died) — re-run, nothing was written to Paraloom')
const reuseCampaign = frame.campaignDecision === 'existing' || !!a.campaignId
const reuseId = a.campaignId ?? frame.campaignId
if (reuseCampaign && !reuseId) {
  throw new Error(`exp-research: frame chose to reuse an existing campaign ("${frame.campaignName}") but returned no campaignId — re-run, or pass args.campaignId explicitly`)
}
const candidates = (frame.candidates || []).slice(0, 40)
if (a.seedPrompts && Array.isArray(a.seedPrompts)) {
  a.seedPrompts.forEach((p, i) => candidates.push({ ref: `seed${i + 1}`, prompt: p, angle: 'seed', geo: a.geography, segment: '' }))
}
log(`Framed: ${frame.campaignDecision} campaign "${frame.campaignName}", ${candidates.length} candidate prompts across ${(frame.framed.segments || []).length} segments`)

// ---- Ground (chunked keyword research) -----------------------------------
phase('Ground')
const groundResults = await parallel(
  chunk(candidates, CHUNK).map((grp, gi) => () =>
    agent(
      `You are grounding a chunk of candidate prompts in real keyword demand using the keyword-research skill.
Read .claude/skills/keyword-research/SKILL.md and references/input_format.md first.

Geography for volume scoping: ${a.geography}

For EACH prompt below, translate it to umbrella keyword phrases FIRST, ordered per methodology rule #2: shortest bare-noun phrase first (e.g. "best mortgage lender"), geo-anchored second, stacked-modifier prompt-literal last. Build the keywords-per-prompt mapping (the skill strongly prefers this over its heuristic translation), then run scripts/research.py with --format json scoped to ${a.geography}.

If a phrase returns 0/mo across a whole chunk, suspect the DataForSEO bulk zero-volume quirk: re-run that phrase in isolation and/or with --no-cache (see the project troubleshooting note) before believing the zero.

Return one row per prompt: ref, prompt, the highest-volume umbrella phrase (topPhrase) and its monthlyVolume, the full phrases list, an aiModeNote (who AI Mode cites — context only, NOT demand), and a suggestedRefine if a rephrasing would track to more volume.

Prompts (chunk ${gi + 1}):
${JSON.stringify(grp.map(c => ({ ref: c.ref, prompt: c.prompt })), null, 2)}`,
      { label: `ground:chunk-${gi + 1}`, phase: 'Ground', schema: GROUND_SCHEMA }
    )
  )
)
const rows = groundResults.filter(Boolean).flatMap(r => r.rows || [])
if (!rows.length) {
  return { slug, halted: true, mode: 'ground-failed', reason: 'no candidates were keyword-grounded (every Ground chunk failed or returned nothing) — check DataForSEO credentials/quota and re-run /exp-research; nothing was written to Paraloom' }
}
log(`Grounded ${rows.length} prompts; ${rows.filter(r => r.monthlyVolume > 0).length} have measurable volume`)

// ---- Triage --------------------------------------------------------------
phase('Triage')
const triage = await agent(
  `You are triaging keyword-grounded candidate prompts for experiment "${slug}" (geography: ${a.geography}).

Apply the Phase 1 verdicts (methodology rule #1 — keyword volume is the ONLY demand signal; AI Mode richness does NOT count):
- KEEP: non-trivial volume (>=50/mo, or >=10/mo if the owned org already shows in AI Mode) on at least one translated phrase.
- REFINED→KEPT: adopt a suggestedRefine that tracks to real volume; the refined phrase must clear the bar.
- DROP: 0/mo across all translated phrases. Default action. Override only as RESCUED with an explicit reason + re-check date.

Then **de-duplicate for a clean campaign.** The candidate set was generated wide on purpose, so several prompts are near-paraphrases that map to the SAME umbrella top phrase and the SAME intent (e.g. five ways of asking "lower my car payment"). Collapse each such cluster to its single strongest representative. **Preserve diversity across intent angle (informational/comparative/transactional/locational), geography, and segment** — that is the breadth /exp-build pivots across; only collapse true same-intent + same-phrase paraphrases. Target roughly 15-20 tracked prompts. List the collapsed paraphrases in the dropped section with reason "paraphrase of #N".

Compute TWO demand totals:
- **uniqueVolume** — sum each DISTINCT top phrase once. This is the honest demand figure; lead with it.
- **totalVolume** — the raw per-prompt sum (double-counts shared phrases); report secondarily, labeled as such.

Here are the grounded rows:
${JSON.stringify(rows, null, 2)}

Write three files into ${dir}/:
1. keyword-research.md — per-prompt detail (translated phrases, volumes, AI Mode note, verdict + reasoning). Clean, final prose only — NO thinking artifacts ("Wait —", "reclassified below", etc.); if you change your mind, state only the final verdict. Reference prompts by their final tracked-prompts row number, consistently.
2. tracked-prompts.md — the client-shareable table: # | Prompt | Top keyword phrase | Monthly volume | Verdict | Notes. This is the AUDIT BOUNDARY — only prompts here get created in Paraloom. Footer leads with "~{uniqueVolume}/mo unique demand across {N} distinct keyword phrases"; then notes the raw sum ({totalVolume}/mo) is higher because prompts share umbrella phrases. Geography in the caption.
3. Append a "Phase 1 — prompt grounding" summary to experiment.md (kept count, uniqueVolume, dropped count incl. paraphrases collapsed).

Return the structured object (kept = the final de-duplicated tracked set).`,
  { label: 'triage', phase: 'Triage', schema: TRIAGE_SCHEMA }
)
if (!triage) throw new Error('exp-research: triage agent returned null (subagent died) — re-run, nothing was written to Paraloom')
log(`Triaged: ${triage.keptCount} kept (~${triage.totalVolume}/mo total), ${triage.droppedCount} dropped`)

if (dryRun) {
  log('dryRun: stopping after Triage — no Paraloom writes.')
  return { slug, mode: 'dryRun', campaignDecision: frame.campaignDecision, candidates: candidates.length, triage, files: triage.files }
}

// ---- Instantiate (writes) ------------------------------------------------
phase('Instantiate')
const inst = await agent(
  `You are instantiating the Paraloom campaign for experiment "${slug}" on team ${a.teamId}.

Load the Paraloom tools you need with ToolSearch (e.g. "select:${PARALOOM}get-team-usage,${PARALOOM}list-campaigns,${PARALOOM}create-campaign,${PARALOOM}list-prompts,${PARALOOM}create-prompt,${PARALOOM}run-campaign-prompts").

Source of truth: ${dir}/tracked-prompts.md — Read it; column 2 (Prompt) is EXACTLY what to create. A prompt not in that table is never created.

Steps (idempotent — never double-create):
1. get-team-usage for team ${a.teamId}; if quota is clearly insufficient for ${triage.keptCount} prompt runs (x3 providers), stop and report rather than partially creating.
2. Campaign: ${reuseCampaign ? `reuse campaign id ${reuseId}.` : `create-campaign (team ${a.teamId}) named "${frame.campaignName}" with description "${frame.campaignDescription}". First list-campaigns to confirm no same-name campaign already exists; if it does, reuse it.`}
3. For each prompt row in tracked-prompts.md: list-prompts on the campaign first to skip any that already exist (dedupe by exact text), then create-prompt for the rest. Confirm each creation.
4. run-campaign-prompts to kick off provider runs across the connected LLMs.
5. Update experiment.md and create/append workflow-log.md with: campaign id, the created prompt ids, and the run timestamp. If run-campaign-prompts FAILS (e.g. inactive subscription / quota), set ranBatch=false, put the exact error in usageNote AND notes, and record the blocker — the campaign + prompts still exist (idempotent re-run is safe once resolved).
   Do NOT assert any human sign-off in the log (no "Ryan approved" / "green-lit"). The workflow ran autonomously; if noting authorization, write "auto-proceeded under go-live authorization." Stop-point sign-offs are recorded by the human, not the agent.

Return the structured object. Responses take ~5-30 min to populate — note that the next step is /exp-build (which polls for them).`,
  { label: 'instantiate', phase: 'Instantiate', schema: INSTANTIATE_SCHEMA }
)
if (!inst) {
  return { slug, halted: true, mode: 'agent-died', keptCount: triage.keptCount, reason: 'instantiate agent returned null AFTER the write phase began — check workflow-log.md and list-campaigns/list-prompts for what was created; re-running /exp-research is safe (creates dedupe by name/text)' }
}
log(`Campaign ${inst.campaignId}: ${inst.promptIds.length} prompts created, runs ${inst.ranBatch ? 'triggered' : 'NOT triggered'}`)

return {
  slug,
  campaignId: inst.campaignId,
  createdCampaign: inst.createdCampaign,
  promptIds: inst.promptIds,
  keptCount: triage.keptCount,
  totalVolume: triage.totalVolume,
  ranBatch: inst.ranBatch,
  usageNote: inst.usageNote,
  notes: inst.notes,
  nextStep: inst.ranBatch
    ? 'wait ~5-30 min for responses to populate, then run /exp-build'
    : `BLOCKED: campaign + prompts created but the baseline run did NOT trigger (${inst.usageNote || inst.notes || 'see workflow-log.md'}). Resolve, then run-campaign-prompts for the campaign, then /exp-build.`,
}
