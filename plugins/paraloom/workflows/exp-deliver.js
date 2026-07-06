export const meta = {
  name: 'exp-deliver',
  description: 'Publish an experiment\'s deliverable to Paraloom: build + validate the manifest (tools/build-deliverable-manifest.py), push it (create-deliverable / push-deliverable-revision via MCP, or the local artisan ingest while the tools are not yet deployed), verify the rendered deliverable through the public API, and draft the client notification. Sending is gated: the email only goes out with send:true, which requires Ryan\'s explicit OK.',
  whenToUse: 'After /exp-review is green (or green-enough with client action items) and manifest-inputs.json exists. Produces the client-facing deliverable link. Re-running pushes a new revision (idempotent on slug).',
  phases: [
    { title: 'Build', detail: 'assemble + hard-validate deliverable.json' },
    { title: 'Push', detail: 'create-deliverable / revision push (MCP or local artisan ingest)' },
    { title: 'Verify', detail: 'fetch the public API and assert the deliverable materialized correctly' },
    { title: 'Reconcile', detail: 'repair a dropped dossier (inline MCP push) via the byte-exact artisan path' },
    { title: 'Notify', detail: 'draft the client email; send only when explicitly authorized' },
  ],
}

// ---- args ----------------------------------------------------------------
// { slug, teamId                  (required)
//   experimentId?                 (Paraloom experiment id to attach)
//   mode?                         ('mcp' (default) = Paraloom MCP tools; 'local' = artisan ingest into the
//                                  local paraloom checkout — byte-exact, preserves the dossier)
//   paraloomPath?                 (local mode; default )
//   apiBase?                      (public-API base for verification; default https://app.paraloom.ai (prod);
//                                  pass http://127.0.0.1:8002 when targeting the local checkout)
//   status? scheduledFor? optOutBy?  (forwarded to the manifest builder)
//   mcpPrefix?                    (MCP tool prefix; default 'mcp__claude_ai_Paraloom__' (prod connector);
//                                  pass 'mcp__paraloom-local__' to target the local server)
//   ENVIRONMENT DEFAULT IS PROD per CLAUDE.md. To target the local checkout, pass mode:'local',
//   mcpPrefix:'mcp__paraloom-local__', apiBase:'http://127.0.0.1:8002'.
//   send?                         (default false; true sends the client email — requires Ryan's OK) }
let a = args || {}
if (typeof a === 'string') { try { a = JSON.parse(a) } catch (e) { throw new Error('exp-deliver: args must be JSON') } }
a = a || {}
for (const k of ['slug', 'teamId']) if (!a[k]) throw new Error(`exp-deliver: args.${k} is required`)
const slug = a.slug
const dir = `experiments/${slug}`
const teamId = a.teamId
const mode = a.mode || 'mcp'
if (!['mcp', 'local'].includes(mode)) throw new Error(`exp-deliver: mode must be 'mcp' or 'local' (got '${a.mode}')`)
const paraloomPath = a.paraloomPath || ''
const mcp = a.mcpPrefix || 'mcp__claude_ai_Paraloom__'
const apiBase = a.apiBase || 'https://app.paraloom.ai'
const send = !!a.send

const BUILD_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['built', 'manifestPath', 'status', 'openBlocking', 'actionItemCount', 'checklistPass', 'checklistTotal'],
  properties: {
    built: { type: 'boolean' }, manifestPath: { type: 'string' },
    status: { type: 'string' }, openBlocking: { type: 'integer' },
    actionItemCount: { type: 'integer' }, checklistPass: { type: 'integer' }, checklistTotal: { type: 'integer' },
    failureOutput: { type: 'string', description: 'validator stderr when built=false' },
  },
}
const PUSH_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['deliverableId', 'token', 'clientUrl', 'revision'],
  properties: {
    deliverableId: { type: ['integer', 'string'] }, token: { type: 'string' },
    clientUrl: { type: 'string' }, revision: { type: 'integer', description: 'version number after this push' },
    notes: { type: 'string' },
  },
}
const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['verified', 'issues'],
  properties: {
    verified: { type: 'boolean' }, issues: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' },
    servedDossierCount: { type: 'integer', description: 'dossier entries returned by the public API' },
    manifestDossierCount: { type: 'integer', description: 'dossier entries in the on-disk deliverable.json' },
  },
}
// Reconcile repairs a push that landed but dropped content (see the Reconcile phase).
const RECONCILE_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['servedDossierCount'],
  properties: {
    deliverableId: { type: ['integer', 'string'] }, token: { type: 'string' },
    servedDossierCount: { type: 'integer', description: 'dossier entries served by the API after the artisan re-ingest' },
    notes: { type: 'string' },
  },
}
const NOTIFY_SCHEMA = {
  type: 'object', additionalProperties: false,
  required: ['draftPath', 'sent'],
  properties: { draftPath: { type: 'string' }, sent: { type: 'boolean' }, notes: { type: 'string' } },
}

phase('Build')
const build = await agent(
  `Build the deliverable manifest for experiment "${slug}".
Run: python3 tools/build-deliverable-manifest.py --experiment-dir ${dir}${a.status ? ` --status ${a.status}` : ''}${a.scheduledFor ? ` --scheduled-for ${a.scheduledFor} --opt-out-by ${a.optOutBy}` : ''}
- If it fails because ${dir}/manifest-inputs.json is missing: report built=false with that fact (the fix is running /exp-review, whose synthesize step writes it).
- If it fails validation: report built=false with the exact validator errors in failureOutput. Do NOT "fix" inputs yourself beyond obvious anchor prefix/suffix disambiguation taken verbatim from the article text.
- On success, Read ${dir}/deliverable.json enough to report the summary fields (the builder also prints them).`,
  { label: 'build-manifest', phase: 'Build', schema: BUILD_SCHEMA }
)
if (!build) return { slug, halted: true, mode: 'agent-died', reason: 'build agent returned null — re-run /exp-deliver' }
if (!build.built) return { slug, halted: true, mode: 'manifest-invalid', reason: build.failureOutput || 'manifest build failed — see failureOutput' }
log(`Manifest: status=${build.status}, ${build.actionItemCount} items (${build.openBlocking} open blocking), checklist ${build.checklistPass}/${build.checklistTotal}`)

phase('Push')
const push = await agent(
  mode === 'local'
    ? `Push the manifest into the LOCAL Paraloom instance (the deliverable MCP tools are not yet deployed to production).
Run (from ${paraloomPath}): php artisan deliverables:ingest ${'$(pwd)'.length ? '' : ''}${dir}/deliverable.json --team=${teamId}${a.experimentId ? ` --experiment=${a.experimentId}` : ''}
(Use an absolute path to the manifest. If the command name differs slightly, check ${paraloomPath}/DELIVERABLES-API.md and php artisan list | grep -i deliver, and use what exists.)
Parse the printed {deliverable_id, token, client_url}. Re-running is a revision push (idempotent on slug) — that is expected.
Then record deliverable id + token + client URL + revision in ${dir}/experiment.md and append a Deliverable entry to workflow-log.md (no human sign-offs). Return the structured object.`
    : `Push the manifest to Paraloom BY REFERENCE via MCP. The manifest's \`dossier\` array is large (~90KB of markdown across ~9 docs) and CANNOT be echoed inline through an MCP tool argument without silently truncating it. Stage it over HTTP first (no model in the byte path), then pass only the small ref.
1. Stage the manifest. Run in Bash:
     source .paraloom.env 2>/dev/null || source ~/.paraloom.env 2>/dev/null; curl -sf -X POST "${apiBase}/api/deliverable-manifests" -H "Authorization: Bearer $PARALOOM_API_TOKEN" -H "Content-Type: application/json" --data-binary @${dir}/deliverable.json
   Parse the JSON {ref, dossier_count, bytes}. SANITY: dossier_count MUST equal the number of entries in ${dir}/deliverable.json's \`dossier\` array — if it does not, STOP (never push a short manifest).
   - On HTTP 404 (endpoint not deployed) or 401 (missing/invalid token): STOP and return deliverableId="UNAVAILABLE", token="", clientUrl="", revision=0, notes="by-reference staging endpoint unavailable (404 = deploy the deliverable-manifest-by-reference branch to ${apiBase}; 401 = set PARALOOM_API_TOKEN in ~/.paraloom.env) — or run mode:'local'".
2. ToolSearch "select:${mcp}create-deliverable,${mcp}push-deliverable-revision". If neither exists on the connector, STOP and return deliverableId="UNAVAILABLE", token="", clientUrl="", revision=0, notes="deliverable MCP tools not on this connector — use mode:'local' or a different mcpPrefix".
3. ${dir}/experiment.md may already record a deliverable id: if so push-deliverable-revision(team_id ${teamId}, that id, manifest_ref = <ref from step 1>, changelog summarizing what changed); else create-deliverable(team_id ${teamId}${a.experimentId ? `, experiment_id ${a.experimentId}` : ''}, manifest_ref = <ref>). Pass manifest_ref, NOT manifest. (The PAT in ~/.paraloom.env must belong to the same Paraloom user the MCP connector authenticates as, or the ref is rejected as foreign.)
4. Record deliverable id + token + client URL + revision in ${dir}/experiment.md and workflow-log.md (no human sign-offs). Return the structured object.`,
  { label: `push:${mode}`, phase: 'Push', schema: PUSH_SCHEMA }
)
if (!push) return { slug, halted: true, mode: 'agent-died', reason: 'push agent returned null — check experiment.md/workflow-log.md for whether the push landed, then re-run (idempotent)' }
if (push.deliverableId === 'UNAVAILABLE') return { slug, halted: true, mode: 'mcp-tools-unavailable', reason: push.notes }
log(`Pushed: deliverable ${push.deliverableId} rev ${push.revision} — ${push.clientUrl}`)

phase('Verify')
let verify = { verified: false, issues: ['verification skipped: no apiBase provided'], notes: '' }
if (apiBase) {
  verify = await agent(
    `Verify the deliverable materialized correctly. GET ${apiBase}/api/public/deliverables/${push.token} (curl -s).
Assert against ${dir}/deliverable.json:
- HTTP 200; deliverable.status matches the manifest status
- actionItems count matches; every manifest action item's sourceId/id appears
- no thread/item that has an anchor in the manifest is flagged orphaned
- checklist length matches; article markdown is present and non-empty; dossier count matches
Also report servedDossierCount (dossier entries in the API response) and manifestDossierCount (dossier entries in deliverable.json) as integers — these drive the Reconcile step, so always include them even when they match.
Report verified=true only if ALL hold; list every discrepancy in issues.`,
    { label: 'verify', phase: 'Verify', schema: VERIFY_SCHEMA }
  ) || verify
  log(verify.verified ? 'Verified clean against the public API' : `Verification issues: ${verify.issues.join(' | ')}`)
} else {
  log('Verification skipped (no apiBase)')
}

// Reconcile: the MCP push has an agent emit the manifest inline, which can silently drop
// the largest field — the ~90KB dossier (the failure that shipped an empty evidence tab on
// deliverable 5, 2026-06-12). The artisan/file path is byte-exact, so when the served dossier
// is short of the file on the MCP path, repair deterministically against the SAME local
// instance; for a remote/prod server we cannot ingest from here, so halt with remediation.
if (mode === 'mcp' && apiBase
    && typeof verify.manifestDossierCount === 'number'
    && typeof verify.servedDossierCount === 'number'
    && verify.servedDossierCount < verify.manifestDossierCount) {
  const localServer = mcp.includes('paraloom-local')
  if (!localServer) {
    return { slug, deliverableId: push.deliverableId, token: push.token, clientUrl: push.clientUrl, revision: push.revision,
      halted: true, mode: 'dossier-dropped-on-push', status: build.status, openBlocking: build.openBlocking,
      reason: `Inline MCP push stored ${verify.servedDossierCount}/${verify.manifestDossierCount} dossier docs — the push agent dropped manifest content too large to echo inline. Cannot auto-repair a remote instance from here. Re-push so create-deliverable receives the manifest by reference, or have an operator ingest ${dir}/deliverable.json directly into the target instance. NOT notifying the client.` }
  }
  phase('Reconcile')
  log(`Dossier short on MCP push (${verify.servedDossierCount}/${verify.manifestDossierCount}) — re-ingesting byte-exact via artisan`)
  const reconcile = await agent(
    `The MCP push landed but stored only ${verify.servedDossierCount} of ${verify.manifestDossierCount} dossier docs — the inline manifest dropped content. Re-ingest the byte-exact manifest from disk into the SAME local instance (the file path preserves the full dossier; the LLM-inlined manifest does not).
Run (from ${paraloomPath}): php artisan deliverables:ingest ${dir}/deliverable.json --team=${teamId}
(ingest is slug-idempotent — it updates the same deliverable_id + token, no new record. Omit --experiment: the local DB may not carry the prod experiment id, and it is cosmetic locally.)
Parse the printed {deliverable_id, token, client_url} and confirm the token matches ${push.token}. Then GET ${apiBase}/api/public/deliverables/${push.token} (curl -s) and report servedDossierCount = the dossier entries now served. Return the structured object.`,
    { label: 'reconcile:artisan', phase: 'Reconcile', schema: RECONCILE_SCHEMA }
  )
  if (reconcile && reconcile.servedDossierCount >= verify.manifestDossierCount) {
    verify = { ...verify, verified: true, servedDossierCount: reconcile.servedDossierCount,
      issues: verify.issues.filter(i => !/dossier/i.test(i)),
      notes: `${verify.notes ? verify.notes + ' | ' : ''}dossier reconciled via artisan re-ingest (${reconcile.servedDossierCount}/${verify.manifestDossierCount}) after the inline MCP push dropped it` }
    log(`Reconciled: dossier now ${reconcile.servedDossierCount}/${verify.manifestDossierCount} served`)
  } else {
    return { slug, deliverableId: push.deliverableId, token: push.token, clientUrl: push.clientUrl, revision: push.revision,
      halted: true, mode: 'dossier-reconcile-failed', status: build.status, openBlocking: build.openBlocking,
      reason: `Artisan re-ingest did not restore the dossier (served ${reconcile ? reconcile.servedDossierCount : 'unknown'}/${verify.manifestDossierCount}). Inspect ${dir}/deliverable.json and ${paraloomPath} before notifying the client. NOT notifying.` }
  }
}

phase('Notify')
const notify = await agent(
  `Draft the client notification email for deliverable "${slug}" (status ${build.status}, ${build.openBlocking} open blocking items, link ${push.clientUrl}).
Write ${dir}/deliverable-notification.md: subject + body. Scenario wording:
- ready/scheduled, 0 open blocking: "We have a new deliverable, ready to publish, based on an opportunity we found to increase your AI visibility and AI traffic" + the publish plan/opt-out line if one exists + the link.
- needs-input: same opener + "N items need your input" + the link + a one-line list of who each item went to.
Plain language for a credit-union/bank marketing manager; no jargon; no em or en dashes.
${send && mode === 'mcp' ? `Then ToolSearch "select:${mcp}send-deliverable" and call send-deliverable(team_id ${teamId}, deliverable_id ${push.deliverableId}); sent=true on success.` : 'Do NOT send anything: sent=false. Sending requires Ryan\'s explicit OK (args.send=true) and the MCP send-deliverable tool.'}
Return the structured object.`,
  { label: 'notify', phase: 'Notify', schema: NOTIFY_SCHEMA }
)
if (!notify) return { slug, deliverableId: push.deliverableId, token: push.token, clientUrl: push.clientUrl, halted: true, mode: 'agent-died', reason: 'notify agent died after a successful push — deliverable is live; draft the email manually' }

return {
  slug, mode,
  deliverableId: push.deliverableId, token: push.token, clientUrl: push.clientUrl, revision: push.revision,
  status: build.status, openBlocking: build.openBlocking,
  verified: verify.verified, verificationIssues: verify.issues,
  notificationDraft: notify.draftPath, sent: notify.sent,
  nextStep: notify.sent
    ? 'client notified — the /loop poller + /exp-revise handle answers from here'
    : `deliverable is live at ${push.clientUrl}; notification drafted at ${notify.draftPath} awaiting Ryan's OK (re-run with send:true, or send manually)`,
}
