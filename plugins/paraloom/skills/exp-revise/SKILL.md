---
name: exp-revise
description: >
  Apply new client activity to a live Paraloom deliverable: fetch answers, threads, attestations,
  checklist confirmations/assignments, and opt-outs; apply answers to the article AS METHODOLOGY
  INPUTS (never raw edit commands); re-verify any client-confirmed checklist item against the real
  thing; re-run the review battery when the article changed; rebuild the manifest; and push a
  revision. No-ops cleanly when there is nothing new. Use when the client has responded or the
  deliverable needs revising ("the client answered", "revise the deliverable", "apply the client's
  answers").
---

# exp-revise — apply client input, push a revision

The automatic half of the deliverable round-trip. Halts with a report instead of pushing if the
review battery is not green after applying. Read
`${CLAUDE_PLUGIN_ROOT}/reference/deliverables-architecture.md` and the methodology rules.

## Two ways to run it

**A. Deterministic (preferred when Workflow is available).**

```
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/workflows/exp-revise.js",
  args: {
    slug, teamId, experimentId,
    mode: "mcp",
    apiBase: "https://app.paraloom.ai",
    mcpPrefix: "mcp__paraloom__"
  }
})
```

**B. Conversational playbook** (when Workflow is unavailable):

1. **Fetch new activity.** `get-deliverable-activity` — answers, threads, attestations, checklist
   confirmations and assignments, opt-outs. If nothing new, **no-op**: report "nothing new" and stop.
2. **Apply answers as methodology inputs, not edit commands.** A client answer is an *input* to the
   methodology — run it through rules #4-#9, not as a literal "change X to Y". If an answer doesn't
   apply under the rules, flip that item to "returned" with a plain-language explanation instead of
   forcing it in.
3. **Re-verify confirmations.** A client confirming a checklist item is **not** a verification.
   Re-verify client-confirmed items against the real source (the live site / the fact) before
   trusting them.
4. **Re-run the battery** (`exp-review`) if the article changed. If it's not green, **halt** with a
   report — do not push.
5. **Rebuild + push.** Rebuild the manifest (`build-deliverable-manifest.py`) and push a revision
   (`push-deliverable-revision`). Verify the dossier count landed. Do not send a follow-up email
   unless the owner approves.

## Gotchas

- Safe to run on a schedule — it no-ops when there's nothing new.
- Never apply a raw client edit command verbatim to the article; methodology rules #4-#9 still govern.
- Never treat a confirmation as a verification.
