export const meta = {
  name: 'exp-review',
  description: 'Phase 8 review battery: run hygiene + NCUA + ADA + fact-check in parallel against a draft article, then synthesize a severity-ranked rollup for the compliance gate.',
  whenToUse: 'Phase 8 review battery — runs automatically on the Phase 7 draft as the suite continues (there is no human draft-review gate). Produces the four review reports plus a consolidated review-summary.md. Does NOT mutate the article or apply fixes — those happen back in conversation, then re-run.',
  phases: [
    { title: 'Review', detail: 'four review skills in parallel, read-only, each writes its report' },
    { title: 'Synthesize', detail: 'consolidate findings into a severity-ranked rollup' },
  ],
}

// ---- args contract -------------------------------------------------------
// args = {
//   slug:        "<experiment-slug>"            (required) folder is experiments/<slug>/
//   creditUnion: "Heartland Credit Union"       (required) owned CU name, for fact-check
//   domain:      "heartlandcu.org"              (required) owned domain, for hygiene link
//                                                          classification + fact-check scoping
//   article:     "experiments/<slug>/article-<slug>.md"  (optional) defaults from slug
//   dictionary:  "experiments/<slug>/.hygiene-dictionary.txt" (optional)
//   pocFacts:    "free-text POC-supplied facts/context"  (optional) fed to fact-check so it
//                                                          knows what the human has already
//                                                          confirmed vs what needs NHV
// }
// args may arrive as a parsed object or as a JSON string (depending on how the
// /exp-review command is invoked) — normalize to an object either way.
let a = args || {}
if (typeof a === 'string') {
  try { a = JSON.parse(a) } catch (e) {
    throw new Error('exp-review: args must be a JSON object (or JSON string); got an unparseable string')
  }
}
a = a || {}
if (!a.slug) throw new Error('exp-review: args.slug is required (the experiment folder under experiments/)')
if (!a.creditUnion || !a.domain) throw new Error('exp-review: args.creditUnion and args.domain are required')

const slug = a.slug
const dir = `experiments/${slug}`
const article = a.article || `${dir}/article-${slug}.md`
const dictArg = a.dictionary ? `--dictionary ${a.dictionary}` : ''
const pocFacts = a.pocFacts ? `\n\nPOC-supplied context (already confirmed by the human — treat as authoritative, do NOT re-flag as NHV unless the article contradicts it):\n${a.pocFacts}` : ''

const reports = {
  hygiene: `${dir}/article-${slug}.hygiene-check.md`,
  ncua: `${dir}/article-${slug}.compliance-review.md`,
  ada: `${dir}/article-${slug}.accessibility-review.md`,
  fact: `${dir}/article-${slug}.fact-check.md`,
  summary: `${dir}/article-${slug}.review-summary.md`,
}

// Structured return shape every review agent produces, so the synthesis step
// gets clean data instead of having to re-parse the markdown reports.
const FINDINGS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['review', 'report_path', 'counts', 'findings'],
  properties: {
    review: { type: 'string', description: 'hygiene | ncua | ada | fact' },
    report_path: { type: 'string', description: 'path of the report file this agent wrote' },
    counts: {
      type: 'object',
      additionalProperties: false,
      required: ['block', 'contradicted', 'warn', 'needs_human_verification', 'defer'],
      properties: {
        block: { type: 'integer' },
        contradicted: { type: 'integer' },
        warn: { type: 'integer' },
        needs_human_verification: { type: 'integer' },
        defer: { type: 'integer' },
      },
    },
    findings: {
      type: 'array',
      description: 'every BLOCK/CONTRADICTED finding, plus the most material WARN/NHV/DEFER items',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'location', 'issue'],
        properties: {
          severity: { type: 'string', description: 'BLOCK | CONTRADICTED | WARN | NEEDS_HUMAN_VERIFICATION | DEFER' },
          location: { type: 'string', description: 'section/heading or quoted snippet so a human can find it' },
          issue: { type: 'string' },
          suggested_fix: { type: 'string', description: 'concrete rewrite or action; empty for NHV/DEFER where a human must act' },
        },
      },
    },
  },
}

const SUMMARY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['summary_path', 'totals', 'must_fix', 'ready_for_compliance_gate', 'checklist', 'actionItems'],
  properties: {
    summary_path: { type: 'string' },
    checklist: {
      type: 'array',
      description: 'manifest-shaped checklist: one entry per check class, granular on purpose (the client deliverable surface renders this as the trust hero)',
      items: { type: 'object', additionalProperties: false, required: ['id', 'group', 'label', 'state'], properties: {
        id: { type: 'string', description: 'stable kebab-case id, e.g. ncua-740' },
        group: { type: 'string', description: 'e.g. NCUA compliance | Pre-publish hygiene | Fact verification | Accessibility | Sign-off | Publish steps' },
        label: { type: 'string', description: 'plain-language check name' },
        state: { type: 'string', description: 'pass | pending | n/a' },
        assigneeRole: { type: 'string', description: 'who owns a pending item: poc | compliance-officer | web-team | agent | paraloom' },
        stage: { type: 'string', description: 'pre-publish | publish-time | post-publish — when this check can actually be verified. Omit for pre-publish (the default). Checks that need the live page (CMS paste, page-template footer, staged-page WCAG, publish-date fact recheck) are publish-time; measurement-window checks are post-publish.' },
        assignee: { type: 'object', additionalProperties: false, required: ['name', 'email'], properties: { name: { type: 'string' }, email: { type: 'string' } }, description: 'named owner — ONLY when the POC has supplied a real person (never invent names); role is the normal fallback' },
        detail: { type: 'string', description: 'short human detail, e.g. "0 BLOCK / 2 dispositioned WARNs"' },
      } },
    },
    actionItems: {
      type: 'array',
      description: 'manifest-shaped action items: every finding that needs CLIENT input (NHV facts, compliance dispositions for their officer, attestations), quote-anchored into the article',
      items: { type: 'object', additionalProperties: false, required: ['id', 'type', 'status', 'assigneeRole', 'question', 'context', 'blocking'], properties: {
        id: { type: 'string', description: 'stable id: ai-1, ai-2, ...' },
        type: { type: 'string', description: 'fact-confirm | compliance-disposition | attestation | choice' },
        status: { type: 'string', description: 'open | answered | applied | returned' },
        assigneeRole: { type: 'string', description: 'poc | compliance-officer | web-team' },
        question: { type: 'string', description: 'the exact ask, plain language' },
        context: { type: 'string', description: 'why we are asking + what the article currently says' },
        anchor: { type: ['object', 'null'], additionalProperties: false, required: ['quote'], properties: {
          quote: { type: 'string', description: 'EXACT text copied from the article markdown (will be validated: must occur in the article)' },
          section: { type: 'string', description: 'nearest H2 heading' },
          prefix: { type: 'string', description: 'short exact text immediately before the quote, REQUIRED when the quote appears more than once' },
          suffix: { type: 'string', description: 'short exact text immediately after the quote' },
        }, description: 'null for items with no document location (e.g. attestations)' },
        blocking: { type: 'boolean', description: 'true if publish must wait on this item' },
      } },
    },
    totals: {
      type: 'object',
      additionalProperties: false,
      required: ['block', 'contradicted', 'warn', 'needs_human_verification', 'defer'],
      properties: {
        block: { type: 'integer' },
        contradicted: { type: 'integer' },
        warn: { type: 'integer' },
        needs_human_verification: { type: 'integer' },
        defer: { type: 'integer' },
      },
    },
    must_fix: {
      type: 'array',
      description: 'BLOCK + CONTRADICTED items that must be resolved before Phase 9',
      items: { type: 'string' },
    },
    ready_for_compliance_gate: {
      type: 'boolean',
      description: 'true only if zero BLOCK and zero CONTRADICTED remain',
    },
    notes: { type: 'string' },
  },
}

const common = `You are one reviewer in the Paraloom Phase 8 review battery for the experiment "${slug}".
Article under review: ${article}
Owned credit union: ${a.creditUnion} (domain: ${a.domain})

Rules:
- READ-ONLY on the article. Do NOT edit ${article}. You produce a report only.
- Empirical observations are observations, never prescriptions (methodology rule #4).
- Your final message MUST be the structured object the schema requires — your report file is written as a side effect, but the return value is the data.${pocFacts}`

phase('Review')

const reviews = await parallel([
  // 1. Hygiene — project-local focused script (NOT the canonical skill; see CLAUDE.md)
  () => agent(
    `${common}

Task: HYGIENE check. Use the project-local focused checker, not the canonical skill.

Run:
  python3 tools/focused-hygiene-check.py --article ${article} --credit-union-domain ${a.domain} ${dictArg} --output-report ${reports.hygiene} --output-html ${dir}/.hygiene-render.html

Then Read ${reports.hygiene}. Translate its findings into the schema:
- Em dashes and broken markdown (empty anchors, missing image alt) → BLOCK.
- En dashes, AI-typical phrases, spelling, minor markdown → WARN.
Report counts and list every BLOCK plus the material WARN items. report_path is ${reports.hygiene}.`,
    { label: 'review:hygiene', phase: 'Review', schema: FINDINGS_SCHEMA }
  ),

  // 2. NCUA compliance
  () => agent(
    `${common}

Task: NCUA COMPLIANCE review. Read .claude/skills/ncua-compliance-review/SKILL.md and RULES.md, then apply the full rule set (Part 740 advertising, Part 707 TISA, Reg Z trigger terms, Reg B / fair lending, membership eligibility) to ${article}. Run the skill's helper script if its SKILL.md directs you to.

Paraloom watchpoints (CLAUDE.md):
- Reg Z 1026.24(d): a specific rate/APR/payment/finance-charge/down-payment-% tied to a ${a.creditUnion} offer in the BODY → BLOCK. Rate context should link to the lender's rates page, not state numbers.
- "best / top-rated / trusted" superlatives about ${a.creditUnion} without substantiation → BLOCK (Part 740).
- Membership-eligibility claims must reflect the actual field of membership; "anyone can join" when the FOM is narrower → BLOCK.
- Page-template footer items (NCUA insurance statement, EHL, NMLS ID, charter disclosure) are MISSING-not-BLOCK at the article level — the web team handles them at publish. Map these to DEFER.

Write the report to ${reports.ncua} using the skill's assets/report-template.md, ending with the mandatory human-compliance-officer sign-off section. Then return the schema object. report_path is ${reports.ncua}.`,
    { label: 'review:ncua', phase: 'Review', schema: FINDINGS_SCHEMA }
  ),

  // 3. ADA accessibility
  () => agent(
    `${common}

Task: ADA / WCAG 2.1 AA content-level review. Read .claude/skills/ada-accessibility-review/SKILL.md, then run its scripts against the article, e.g.:
  python3 .claude/skills/ada-accessibility-review/scripts/review.py ${article} --target-grade 9 --audience "general consumer" --json

Cover: heading hierarchy, descriptive link text, alt text, plain-language reading level (Flesch-Kincaid ≤ 9; accept ≤ 10 with documented reason), list/table semantics, color-only references. Page-level checks (contrast, keyboard nav, screen-reader render) are DEFER → Phase 9 staged-page audit.

Write ${reports.ada} using the skill's format, then return the schema object. report_path is ${reports.ada}.`,
    { label: 'review:ada', phase: 'Review', schema: FINDINGS_SCHEMA }
  ),

  // 4. Fact verification — Playwright-driven
  () => agent(
    `${common}

Task: FACT VERIFICATION. Read .claude/skills/fact-verification/SKILL.md and references/browser-playbook.md first.

This project's browser driver is Playwright. Load its tools with ToolSearch ("select:mcp__playwright__browser_navigate,mcp__playwright__browser_snapshot,mcp__playwright__browser_evaluate,mcp__playwright__browser_wait_for"). Playwright launches its own browser on first navigate — there is no "is a browser connected" gate. You are the ONLY browser user in this run.

Extract verifiable claims (counts, branches, products, eligibility, rates, leadership, external stats, comparatives, regulatory) and verify each:
- Internal claims → verify against ${a.domain} (the CU's own site).
- External stats / regulatory → verify against the cited authority directly.
- Direct quotes attributed to people → always NEEDS_HUMAN_VERIFICATION.
- Anything ambiguous or not findable → NEEDS_HUMAN_VERIFICATION (CONTRADICTED only when the source affirmatively disagrees).
Capture exact source quote + URL + ISO timestamp for each verified claim.

Write ${reports.fact} using the skill's assets/report-template.md, then return the schema object. report_path is ${reports.fact}. Map verification statuses: CONTRADICTED→contradicted, NEEDS_HUMAN_VERIFICATION→needs_human_verification.`,
    { label: 'review:fact', phase: 'Review', schema: FINDINGS_SCHEMA }
  ),
])

const good = reviews.filter(Boolean)
// A dead reviewer must NEVER produce a green gate: with its findings missing,
// "0 BLOCK / 0 CONTRADICTED" would be trivially true. Halt instead.
const expectedReviews = ['hygiene', 'ncua', 'ada', 'fact']
const missingReviews = expectedReviews.filter(n => !good.some(r => (r.review || '').toLowerCase().includes(n)))
if (missingReviews.length) {
  return {
    experiment: slug, article, reports, halted: true, missingReviews,
    completed: good.map(r => ({ review: r.review, counts: r.counts })),
    reason: `review agent(s) died before reporting: ${missingReviews.join(', ')} — the article is NOT cleared for the compliance gate; re-run /exp-review (completed reports are on disk)`,
  }
}
log(`Reviews complete: ${good.map(r => `${r.review}(B${r.counts.block}/C${r.counts.contradicted}/W${r.counts.warn})`).join('  ')}`)

phase('Synthesize')

const summary = await agent(
  `You are synthesizing the Paraloom Phase 8 review battery for experiment "${slug}" (article ${article}).

Here are the four reviewers' structured findings:
${JSON.stringify(good, null, 2)}

The full reports are on disk — Read any you need for detail:
- ${reports.hygiene}
- ${reports.ncua}
- ${reports.ada}
- ${reports.fact}

Produce a consolidated rollup and write it to ${reports.summary} with these sections:
1. Verdict line: ready for the Phase 9 compliance gate, or not — and why. NOT ready if any BLOCK or CONTRADICTED remains.
2. MUST-FIX before Phase 9 — every BLOCK + CONTRADICTED, grouped by review, each with location + suggested fix.
3. WARN — for the agent to disposition autonomously (fix it, or keep-with-reasoning → record in decisions.md); not a human-review stop.
4. NEEDS_HUMAN_VERIFICATION — facts only the client/POC can confirm offline; these become deliverable action items, not a draft-review gate.
5. DEFER — ADA page-level + Part-740 footer items carried to the Phase 9 staged-page audit.
6. Cross-review notes — e.g. a hygiene rewrite that would change a compliance finding; flag where re-running a review after fixes is warranted.

7. DISTILL THE MANIFEST INPUTS (for the client deliverable surface). Build the structures below and ALSO write them to ${dir}/manifest-inputs.json as {"shortTitle": "...", "opportunity": {...}, "checklist": [...], "actionItems": [...], "dossierSummaries": {...}, "evidenceOverview": "..."} (merge with that file's other keys if it already exists — never drop keys you didn't produce). Set "shortTitle": a 2-6 word client-facing label for the deliverable's header chrome (usually the experiment topic, e.g. "Southern Wisconsin Home Equity") — never the full article title, which is long by design:
   - opportunity: the client-facing "why this exists" header, REQUIRED by tools/build-deliverable-manifest.py (the build hard-fails without it). Read ${dir}/build-analysis.md, ${dir}/experiment.md, ${dir}/decisions.md, and ${dir}/tracked-prompts.md and distill REAL values (never invent figures): headline (2-4 plain-language sentences — the AI-visibility gap this article closes and why it is winnable, no jargon), demand (the honest unique monthly search demand plus the head phrases the targets ride, from tracked-prompts.md/keyword-research.md), verdict (the /exp-build viability verdict verbatim: STRONG | VIABLE | WEAK | AVOID), and targetPrompts (one {id, text, baseline} per locked target prompt — baseline = its one-line open-slot / owned-gap state from build-analysis.md).
   - checklist: one granular entry per check class across all four reviews plus the gates (POC facts, compliance sign-off, publish steps like the CMS paste / page-template footer / staged-page audit). Mostly-pass with a few pendings is the expected, honest shape. Plain language labels; pending items get an assigneeRole. Set stage honestly: checks that can only be verified on the live/staged page are "publish-time", measurement-window checks "post-publish", everything else omits stage (pre-publish). The client app scopes its readiness seal by stage, so a mis-staged check lies to the client. Add assignee {name, email} only when the POC has supplied that person.
   - actionItems: ONLY findings that need a CLIENT human (POC fact confirmations, compliance-officer dispositions/attestation, web-team items). Each gets a quote-based anchor whose quote is copied EXACTLY from the article markdown (Read the article and copy-paste; if the quote appears more than once, add a prefix that makes it unique). Items the agent itself must fix are NOT action items — they belong in must_fix/notes.

   THE SELF-RESOLUTION GATE — a finding becomes an action item ONLY after it fails ALL THREE of these, applied in order. The target is zero action items; every one that ships is a small failure that must justify itself:
   a. WEBSITE-WORDING TEST: can the finding be resolved by rewriting the claim to mirror what the credit union's live website already publishes (or by deleting an unsupported qualifier)? The website is presumed compliant for its own published wording — fall back to it. If yes: fix the article (or list it in must_fix), no action item. (Classic case: the draft says "high CLTV" but the site says "up to 100% combined loan-to-value" — use the site's words.)
   b. SELF-VERIFY TEST: can the agent verify it by browsing the live site or an authoritative source (Playwright/web)? Published branch addresses, phone numbers, page URLs, application channels, product features, and eligibility wording are on the site — go read them. If verifiable: verify it, cite the URL, no action item. Pre-fill values you found and at most ask a NON-blocking "confirm what we found" question.
   c. FACT-CHECK RECONCILIATION: did the fact-verification report ALREADY verify this claim against the live site? A claim the fact-checker verified is substantiated — never ask a human to confirm what a reviewer already confirmed. Cross-reference every candidate action item against the fact-check's Verified table before authoring it.
   What legitimately survives the gate: claims the site does not support and only the client can settle (internal facts, charter/FOM scope beyond published wording, capability claims like "originated and serviced locally"), genuine compliance-officer dispositions, and the Phase 9 attestation. Default-soften: when a claim fails verification, ship the article with the softened site-supported wording NOW and make the stronger claim an OPT-IN, non-blocking ask — do not leave the article blocked on an answer.
   Never author an action item that duplicates a publish-time checklist row (footer/template disclosures, staged-page audit, CMS paste) — those live in the checklist only.

   STYLE CONTRACT for question + context (these render verbatim to a non-technical client):
   - question: ONE ask, <= 20 words, plain second person ("Is your Janesville location full-service?"), no regulation numbers, no AND-bundling of two asks.
   - context: <= 2 sentences. Sentence 1 = why it matters; for compliance items NAME the specific regulation in plain terms ("NCUA's advertising rule, Part 740.3, prohibits unsubstantiated comparative claims"). Sentence 2 = the default if unanswered ("If we don't hear back, we'll keep the wording from your website."). Every non-attestation item MUST have a stated default — that default is what makes it non-blocking.
   - blocking: true ONLY for the attestation and for items where publishing without the answer would create a compliance violation that no softening can avoid. Everything with a safe default is blocking: false.
   - Order actionItems by the sequence the client should handle them; the attestation is ALWAYS last.
   These feed tools/build-deliverable-manifest.py, which hard-validates anchors against the article — sloppy quotes will fail the build.

8. DISTILL THE HUMAN-READABLE EVIDENCE LAYER (renders verbatim on the client deliverable's Evidence tab, above and alongside the raw documents). The dossier still ships every raw working file unchanged for the audit trail; your job here is a friendly plain-language layer ON TOP, never a rewrite of those files.
   - dossierSummaries: a map keyed by the EXACT dossier filename, each value a short plain-language summary of that document for a credit-union marketing or compliance reader (NOT the agent). Produce one entry for each of these files that exists in ${dir}: "evidence.md", "decisions.md", "build-analysis.md", "keyword-research.md", "article-${slug}.review-summary.md", "article-${slug}.hygiene-check.md", "article-${slug}.compliance-review.md", "article-${slug}.accessibility-review.md", "article-${slug}.fact-check.md". (Skip a key if its file does not exist.)
     Summary rules: strip every internal token (Paraloom prompt IDs like 10246, campaign/experiment/team IDs, methodology rule numbers like "rule #8", cross-file pointers like "see build-analysis.md"); translate jargon into plain outcomes (e.g. "10246 sits at 28% owned, ownedGap 0.72" becomes "When local drivers ask AI which lender has the best auto-loan rate, your credit union is named only about one in four times, versus at or near the top on nearly every other question"); be terse (3-6 sentences or 3-5 bullets; the four review reports get a 1-2 sentence "what we checked and what we found"); preserve the real conclusions and the basis for confidence but invent nothing; no em dashes; match the article's voice. The full raw document is one click away on the page, so each summary must be FAITHFUL, not exhaustive.
   - evidenceOverview: a single plain-language narrative (4-8 sentences) answering "why are we confident this article will move the needle?" — tie together the real monthly search demand, the specific AI-visibility gap it closes, the mechanism that closes it, and the outcome of the review battery (compliant, accurate, accessible). Client-facing and honest; no internal IDs, no rule numbers. This is the featured card at the top of the Evidence tab.

This is assistive only — it does NOT replace the human compliance officer (Phase 9). Then return the schema object. summary_path is ${reports.summary}; ready_for_compliance_gate is true ONLY if totals.block and totals.contradicted are both 0.`,
  { label: 'synthesize', phase: 'Synthesize', schema: SUMMARY_SCHEMA }
)

if (!summary) {
  return {
    experiment: slug, article, reports, halted: true,
    reviews: good.map(r => ({ review: r.review, counts: r.counts })),
    reason: 'synthesis agent returned null — the four reports are on disk; re-run /exp-review to rebuild the rollup (do NOT treat this run as a gate verdict)',
  }
}

return {
  experiment: slug,
  article,
  reports,
  reviews: good.map(r => ({ review: r.review, counts: r.counts })),
  summary,
}
