export const meta = {
  name: 'exp-revise',
  description: 'The automatic half of the deliverable round-trip: fetch new client activity (answers, threads, attestations, check confirmations/assignments, opt-outs), apply answers to the article AS METHODOLOGY INPUTS (never raw edit commands; rules #4-#8 enforced; non-applicable answers flip to "returned" with an explanation), re-verify client-confirmed checklist items against the real thing (a confirmation is never a verification), re-run the /exp-review battery when the article changed, rebuild the manifest, and push a revision. No-ops cleanly when there is nothing new, so a /loop cron can run it on a schedule.',
  whenToUse: 'On a /loop cron after a deliverable is live (e.g. /loop 3h /exp-revise {...}), or manually when Ryan knows answers arrived. Halts with a report instead of pushing if the battery is not green after applying.',
  phases: [
    { title: 'Activity', detail: 'fetch new client input since the last revision' },
    { title: 'Apply', detail: 'fold answers in through the methodology; flag non-applicable ones as returned' },
    { title: 'Re-verify checks', detail: 'verify client-confirmed checklist items against the real thing' },
    { title: 'Re-review', detail: 'full /exp-review battery on the revised article' },
    { title: 'Push', detail: 'rebuild manifest + push the revision with a changelog' },
  ],
}

// ---- args ----------------------------------------------------------------
// { slug, teamId, creditUnion, domain   (required)
//   deliverableId?, token?              (from experiment.md if omitted — the agents read it)
//   mode?                               ('mcp' (default) | 'local')
//   mcpPrefix?                          (default 'mcp__claude_ai_Paraloom__' (prod); pass 'mcp__paraloom-local__' for local)
//   paraloomPath?, apiBase?             (checkout path + public API base; apiBase default https://app.paraloom.ai (prod))
//   dictionary?                         (hygiene dictionary path for the re-review)
//   since?                              (ISO; default: the last revision push recorded in workflow-log.md)
//   ENVIRONMENT DEFAULT IS PROD per CLAUDE.md; pass mode:'local' + the local mcpPrefix + a local apiBase to target the dev checkout. }
let a = args || {}
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { throw new Error('exp-revise: args must be JSON') } }
a = a || {}
for (const k of ['slug', 'teamId', 'creditUnion', 'domain']) if (!a[k]) throw new Error(`exp-revise: args.${k} is required`)
const slug = a.slug
const dir = `experiments/${slug}`
const teamId = a.teamId
const mode = a.mode || 'mcp'
if (!['mcp', 'local'].includes(mode)) throw new Error(`exp-revise: mode must be 'mcp' or 'local'`)
const paraloomPath = a.paraloomPath || '/Users/ryanharmon/Herd/paraloom'
const mcp = a.mcpPrefix || 'mcp__claude_ai_Paraloom__'

const ACTIVITY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['any', 'newAnswers', 'newThreads', 'attestations', 'checkConfirmations', 'checkAssignments', 'optOuts'],
  properties: {
    any: { type: 'boolean', description: 'true if there is ANY new client input to process' },
    newAnswers: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['sourceId', 'text'], properties: {
      sourceId: { type: 'string' }, text: { type: 'string' }, author: { type: 'string' }, at: { type: 'string' },
    } } },
    newThreads: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['body'], properties: {
      body: { type: 'string' }, quote: { type: 'string' }, author: { type: 'string' }, at: { type: 'string' },
    } } },
    attestations: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['sourceId'], properties: {
      sourceId: { type: 'string' }, typedName: { type: 'string' }, at: { type: 'string' },
    } } },
    checkConfirmations: { type: 'array', description: 'client marked a checklist item done ("mark done, we verify")', items: { type: 'object', additionalProperties: false, required: ['checkId'], properties: {
      checkId: { type: 'string' }, note: { type: 'string' }, author: { type: 'string' }, at: { type: 'string' },
    } } },
    checkAssignments: { type: 'array', description: 'a person was assigned to a checklist item in-app (record-only; the server owns assignments)', items: { type: 'object', additionalProperties: false, required: ['checkId', 'name', 'email'], properties: {
      checkId: { type: 'string' }, name: { type: 'string' }, email: { type: 'string' }, at: { type: 'string' },
    } } },
    optOuts: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}
const APPLY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['applied', 'returned', 'articleChanged', 'changelog'],
  properties: {
    applied: { type: 'array', items: { type: 'string' }, description: 'sourceIds applied to the article/manifest-inputs' },
    returned: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['sourceId', 'why'], properties: {
      sourceId: { type: 'string' }, why: { type: 'string' },
    } } },
    articleChanged: { type: 'boolean' },
    changelog: { type: 'string', description: 'plain-language summary of what changed, for the client-facing revision notice' },
    notes: { type: 'string' },
  },
}
const CHECKS_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['checks', 'changelog'],
  properties: {
    checks: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['checkId', 'result', 'why'], properties: {
      checkId: { type: 'string' }, result: { type: 'string', description: 'pass | still-pending' }, why: { type: 'string' },
    } } },
    changelog: { type: 'string', description: 'plain-language client-facing summary of check verifications; empty string when nothing changed' },
    notes: { type: 'string' },
  },
}
const PUSH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['deliverableId', 'revision'],
  properties: { deliverableId: { type: ['integer', 'string'] }, revision: { type: 'integer' }, clientUrl: { type: 'string' }, notes: { type: 'string' } },
}

phase('Activity')
const activity = await agent(
  mode === 'local'
    ? `Detect new client input on the deliverable for experiment "${slug}" (LOCAL mode).
1. Read ${dir}/experiment.md for the deliverable token/id${a.token ? ` (or use token ${a.token})` : ''}.
2. curl -s ${a.apiBase || 'https://app.paraloom.ai'}/api/public/deliverables/<token>
3. Diff against the last-pushed state in ${dir}/deliverable.json: an action item whose API answer is non-null but whose manifest answer is null (or whose manifest status is open) is a NEW answer. Client-initiated threads (actionItemSourceId null) not represented locally are NEW threads. Items resolved by attestation where the manifest shows open are NEW attestations.
4. Checklist events: a checklist item in the API response that carries a client confirmation (confirmed-by/note/timestamp) while its state is still pending is a NEW check confirmation — UNLESS workflow-log.md already records that confirmation (same checkId + timestamp) as processed. A check whose API assignee (name/email) is absent from the manifest and not yet recorded in workflow-log.md is a NEW check assignment. Also check ${paraloomPath}/DELIVERABLES-API.md for an activity/artisan equivalent and prefer it if one exists.
Return the structured object; any=false when nothing is new (confirmations and assignments count as activity).`
    : `Detect new client input on the deliverable for experiment "${slug}" via MCP.
1. Read ${dir}/experiment.md for the deliverable id${a.deliverableId ? ` (or use ${a.deliverableId})` : ''}; read workflow-log.md for the last revision-push timestamp${a.since ? ` (or use since=${a.since})` : ''}.
2. ToolSearch "select:${mcp}get-deliverable-activity"; if the tool does not exist on the connector, return any=false with notes="get-deliverable-activity not on this connector — run in mode:'local' or set mcpPrefix".
3. get-deliverable-activity(team_id ${teamId}, deliverable_id <id>, since <last push>). Map answered/thread_opened/commented/attested/check_confirmed/check_assigned/opt_out_requested events into the structured object. any=false when empty.`,
  { label: `activity:${mode}`, phase: 'Activity', schema: ACTIVITY_SCHEMA }
)
if (!activity) return { slug, halted: true, mode: 'agent-died', reason: 'activity agent returned null — re-run /exp-revise' }
if (!activity.any) return { slug, mode: 'no-op', reason: activity.notes || 'no new client activity since the last revision' }
log(`Activity: ${activity.newAnswers.length} answers, ${activity.newThreads.length} threads, ${activity.attestations.length} attestations, ${activity.checkConfirmations.length} check confirmations, ${activity.checkAssignments.length} assignments, ${activity.optOuts.length} opt-outs`)

if (activity.optOuts.length) {
  log('OPT-OUT requested — halting for Ryan; no automatic changes on an opt-out')
  return { slug, halted: true, mode: 'opt-out-requested', optOuts: activity.optOuts, reason: 'client requested a publish hold — Ryan decides the response; no revision pushed' }
}

const hasApplyWork = !!(activity.newAnswers.length || activity.newThreads.length || activity.attestations.length)
const hasCheckWork = activity.checkConfirmations.length > 0

if (!hasApplyWork && !hasCheckWork) {
  // assignments only — server-owned state; record it here, no revision needed
  const rec = await agent(
    `Record check assignments for experiment "${slug}": a client assigned people to checklist items in the deliverable app (server-owned state; we mirror nothing into the manifest).
${JSON.stringify(activity.checkAssignments, null, 2)}
Append a short entry to ${dir}/workflow-log.md (checkId, assignee name + email as given, timestamp). No other files change. Return {recorded: true}.`,
    { label: 'record-assignments', phase: 'Apply', schema: { type: 'object', additionalProperties: false, required: ['recorded'], properties: { recorded: { type: 'boolean' }, notes: { type: 'string' } } } }
  )
  return { slug, mode: 'recorded', assignmentsRecorded: activity.checkAssignments.length, recorded: !!(rec && rec.recorded), reason: 'check assignments recorded; nothing to apply or verify — no revision pushed' }
}

phase('Apply')
let apply = { applied: [], returned: [], articleChanged: false, changelog: '', notes: 'no answers/threads/attestations this round' }
if (hasApplyWork) apply = await agent(
  `Apply new client input to experiment "${slug}" (owned org ${a.creditUnion}, ${a.domain}). Answers are INPUTS TO THE METHODOLOGY, never raw edit commands.

New answers (action item sourceId -> client text):
${JSON.stringify(activity.newAnswers, null, 2)}
New client-initiated threads (treat as feedback; apply only what passes the rules):
${JSON.stringify(activity.newThreads, null, 2)}
Attestations (record only — NEVER applied to the article, never resolved by you):
${JSON.stringify(activity.attestations, null, 2)}

For each answer:
1. Read ${dir}/manifest-inputs.json to find the action item (question + context + anchor) and ${dir}/article-${slug}.md.
2. Apply the answer to the article IF it can be applied compliantly: methodology rules hold absolutely — no competitor names in the body (#4), no rate/APR/payment numbers tied to ${a.creditUnion} (#5), no unsubstantiated best/top/trusted superlatives (#6), concrete substantiable phrasing (#8). NO em or en dashes anywhere.
3. If an answer cannot be applied compliantly (e.g. "say we have the best rates"), do NOT apply it: set that item's status to "returned" in manifest-inputs.json and rewrite its context to explain, in plain client-facing language, why and what we need instead.
4. Applied items: set status "applied" in manifest-inputs.json, store the answer object on the item, and update the checklist states that the answers resolve.
5. Record every disposition in ${dir}/decisions.md (next D-number; choice / evidence / rejected alternatives where real).
6. Update ${dir}/workflow-log.md with a revision entry (no human sign-offs; attestations are recorded as received, attributed exactly as given).
Return the structured object with a plain-language changelog.`,
  { label: 'apply', phase: 'Apply', schema: APPLY_SCHEMA }
)
if (!apply) return { slug, halted: true, mode: 'agent-died', reason: 'apply agent returned null — the experiment folder may be partially updated; inspect decisions.md/workflow-log.md and re-run' }
log(`Applied ${apply.applied.length}, returned ${apply.returned.length}, articleChanged=${apply.articleChanged}`)

let checkVerify = { checks: [], changelog: '' }
if (hasCheckWork) {
  phase('Re-verify checks')
  checkVerify = await agent(
    `Re-verify client-confirmed checklist items for experiment "${slug}" (owned org ${a.creditUnion}, ${a.domain}). THE RULE: a client confirmation is NEVER a verification — you verify the real-world condition yourself and only then flip the state. ("A commitment is not a verification.")

Confirmations received (checkId, note, author, timestamp):
${JSON.stringify(activity.checkConfirmations, null, 2)}
${activity.checkAssignments.length ? `Assignments also received (record in workflow-log.md only — server-owned, do not mirror into the manifest):
${JSON.stringify(activity.checkAssignments, null, 2)}` : ''}

For each confirmed check:
1. Read its entry in ${dir}/manifest-inputs.json (label, detail, stage) to understand what the check actually verifies.
2. Verify the REAL condition against the live state — fetch the live/staged page on ${a.domain} (WebFetch or the Playwright MCP browser tools) and check exactly what the label claims: e.g. the NCUA insurance statement renders on the published page, the article is live at its URL, rate figures are present in the static HTML (crawler-readable, not script-injected), page-level WCAG basics. Verify only what is checkable; never trust the confirmation text alone.
3. VERIFIED -> set the check's state to "pass" in ${dir}/manifest-inputs.json and set detail to a short plain-language note ("verified <date> after <author>'s confirmation: <what you observed>").
4. NOT verifiable or failed -> keep state "pending" and REWRITE detail to explain, in plain client-facing language, exactly what is missing or what must happen first (the client sees this — they must never sit in "awaiting verification" with no explanation). No em or en dashes anywhere.
5. Record every disposition (and any assignments) in ${dir}/workflow-log.md with the confirmation timestamps, so future runs do not re-process them.
Return the structured object; changelog summarizes only what a client would care about.`,
    { label: 'verify-checks', phase: 'Re-verify checks', schema: CHECKS_SCHEMA }
  )
  if (!checkVerify) return { slug, halted: true, mode: 'agent-died', applied: apply.applied, reason: 'check-verification agent returned null — manifest-inputs may be partially updated; inspect workflow-log.md and re-run' }
  log(`Checks: ${checkVerify.checks.filter(c => c.result === 'pass').length} verified pass, ${checkVerify.checks.filter(c => c.result !== 'pass').length} still pending (explained)`)
}

phase('Re-review')
if (apply.articleChanged) {
  const review = await workflow('exp-review', {
    slug, creditUnion: a.creditUnion, domain: a.domain,
    ...(a.dictionary ? { dictionary: a.dictionary } : {}),
    pocFacts: `Client answers applied this revision (authoritative, do not re-flag): ${JSON.stringify(activity.newAnswers)}`,
  })
  if (!review || review.halted) {
    return { slug, halted: true, mode: 'review-failed', reason: `re-review did not complete (${review && review.reason ? review.reason : 'null result'}) — fix and re-run /exp-revise; no revision was pushed` }
  }
  const totals = review.summary && review.summary.totals
  if (!totals || totals.block > 0 || totals.contradicted > 0) {
    return {
      slug, halted: true, mode: 'battery-not-green', applied: apply.applied, returned: apply.returned,
      reason: `battery after applying answers: ${totals ? `${totals.block} BLOCK / ${totals.contradicted} CONTRADICTED` : 'unknown totals'} — resolve conversationally, then re-run /exp-revise; no revision was pushed`,
    }
  }
  log('Re-review green')
} else {
  log('Article unchanged (dispositions/returns only) — skipping the full battery')
}

const changelog = [apply.changelog, checkVerify.changelog].filter(Boolean).join(' ')

phase('Push')
const push = await agent(
  `Rebuild and push the revised deliverable for "${slug}".
1. Run: python3 tools/build-deliverable-manifest.py --experiment-dir ${dir}
   (status auto-derives: open blocking items -> needs-input, else ready). If validation fails, report it verbatim and stop.
2. ${mode === 'local'
    ? `Push the revision locally: from ${paraloomPath}, php artisan deliverables:ingest /Users/ryanharmon/Documents/Code/paraloom-agent/${dir}/deliverable.json --team=${teamId} (idempotent on slug = revision push; check DELIVERABLES-API.md if the command differs).`
    : `Push the revision BY REFERENCE (the dossier is too large to echo inline through an MCP argument without truncating it):
   a. Stage over HTTP. Bash: source .paraloom.env 2>/dev/null || source ~/.paraloom.env 2>/dev/null; curl -sf -X POST "${a.apiBase || 'https://app.paraloom.ai'}/api/deliverable-manifests" -H "Authorization: Bearer $PARALOOM_API_TOKEN" -H "Content-Type: application/json" --data-binary @${dir}/deliverable.json ; parse {ref, dossier_count}. SANITY: dossier_count MUST equal ${dir}/deliverable.json's \`dossier\` length, else STOP. On HTTP 404/401 STOP and report halted with reason "by-reference staging endpoint unavailable (404 = deploy the deliverable-manifest-by-reference branch; 401 = set PARALOOM_API_TOKEN in ~/.paraloom.env), or run mode:'local'".
   b. ToolSearch "select:${mcp}push-deliverable-revision" and push-deliverable-revision(team_id ${teamId}, deliverable_id from ${dir}/experiment.md, manifest_ref = <ref>, changelog = ${JSON.stringify(changelog)}). Pass manifest_ref, NOT manifest.`}
3. Record the new revision number in ${dir}/experiment.md and workflow-log.md. Return the structured object.`,
  { label: `push:${mode}`, phase: 'Push', schema: PUSH_SCHEMA }
)
if (!push) return { slug, halted: true, mode: 'agent-died', applied: apply.applied, reason: 'push agent returned null after apply — manifest may be rebuilt but unpushed; re-run /exp-revise (push is idempotent)' }
log(`Revision ${push.revision} pushed`)

return {
  slug, mode: 'revised',
  applied: apply.applied, returned: apply.returned,
  attestationsRecorded: activity.attestations.map(t => t.sourceId),
  checksVerified: checkVerify.checks,
  assignmentsRecorded: activity.checkAssignments.length,
  changelog,
  deliverableId: push.deliverableId, revision: push.revision,
  nextStep: apply.returned.length
    ? `revision live; ${apply.returned.length} item(s) returned to the client with explanations — the poller picks up their next answers`
    : 'revision live; if all blocking items are closed the deliverable is ready for scheduling (set-deliverable-status / Ryan\'s call on the send)',
}
