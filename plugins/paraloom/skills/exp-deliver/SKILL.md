---
name: exp-deliver
description: >
  Publish a Paraloom experiment's client deliverable: build and hard-validate the deliverable
  manifest, push it to Paraloom (create-deliverable / push-deliverable-revision), verify the
  rendered deliverable through the public API, and draft the client notification email. Sending is
  gated — the email only goes out with explicit owner approval (send:true). Use after exp-review is
  green (or green-enough with client action items) and manifest-inputs.json exists ("ship it",
  "send the deliverable", "publish the deliverable"). Re-running pushes a new revision.
---

# exp-deliver — publish the client deliverable

Produces the client-facing deliverable link and holds at the send gate. Read
`${CLAUDE_PLUGIN_ROOT}/reference/deliverables-architecture.md` for the two-system contract
(this toolkit builds the manifest; the Paraloom SaaS stores it and serves the client experience
at `/d/<token>`).

## Preconditions

- exp-review is green (BLOCK/CONTRADICTED cleared) and `experiments/<slug>/manifest-inputs.json` exists.
- The Phase 9 FI sign-off has happened (or the deliverable itself is the sign-off surface). You
  never fabricate a sign-off.

## Two ways to run it

**A. Deterministic (preferred when Workflow is available).**

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/exp-deliver.js",
  args: {
    slug, teamId, experimentId,
    mode: "mcp",                    // production Paraloom MCP push (default)
    apiBase: "https://app.paraloom.ai",
    mcpPrefix: "mcp__paraloom__",
    send: false                     // true only with the owner's explicit OK
  }
})
```

**B. Conversational playbook** (when Workflow is unavailable):

1. **Build.** `python3 "${CLAUDE_PLUGIN_ROOT}/tools/build-deliverable-manifest.py" --experiment-dir experiments/<slug> ...`
   to assemble and hard-validate `deliverable.json`. Fix any validation failure before pushing.
2. **Push.** `create-deliverable` (first time) or `push-deliverable-revision` (subsequent) via the
   Paraloom MCP. Idempotent on slug — re-running creates a new revision. Capture the deliverable
   id, token, and client URL (`https://app.paraloom.ai/d/<token>`).
3. **Verify.** Fetch the public API for the deliverable and assert it materialized correctly —
   **especially the dossier count**: compare `servedDossierCount` (API) against the on-disk
   `deliverable.json` dossier count. A mismatch means content dropped on push — do not notify the
   client until it matches.
4. **Notify.** Draft the client email. **Do not send** unless the owner has explicitly approved
   (`send:true` / `send-deliverable`). Present the draft and the client link for approval.

## Gotchas

- **Dossier can drop on an inline MCP push.** If verify shows fewer served dossier entries than the
  manifest holds, reconcile before notifying (the workflow's Reconcile phase handles this; by hand,
  re-push and re-verify). Never announce a deliverable whose dossier didn't fully land.
- The send gate is a one-way door (an outbound client email). Always get an explicit OK first.
- Paraloom MCP schemas are deferred — `ToolSearch` (`select:create-deliverable,push-deliverable-revision,send-deliverable,get-deliverable`) before calling.
