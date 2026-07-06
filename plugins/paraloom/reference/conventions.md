# Project conventions

## Folder layout

```
<customer-project>/
├── CLAUDE.md                       # auto-loaded; per-project Paraloom Agent context
├── EXPERIMENT_WORKFLOW.md          # SOP reference (copy from setup kit)
├── docs/                           # methodology + connector + skills reference
├── tools/                          # focused-hygiene-check + build scripts
├── .claude/workflows/              # /exp-* workflow scripts
├── .claude/skills/                 # five vendored canonical skills
├── .dataforseo.env                 # DataForSEO credentials (gitignored)
├── .gitignore                      # excludes env files, .netlify state, etc.
└── experiments/
    └── <experiment-slug>/
        ├── experiment.md           # brief + Phase 3 baseline summary
        ├── workflow-log.md         # phase-by-phase spine
        ├── evidence.md             # Phase 5 dossier
        ├── decisions.md            # Phase 5 choices + rejected alternatives
        ├── tracked-prompts.md      # Phase 1 client-shareable rollup
        ├── keyword-research.md     # Phase 1 raw + triage
        ├── build-analysis.md       # Phase 3/5 opportunity analysis (from /exp-build)
        ├── poc-questions.md        # consolidated POC question list
        ├── article-<slug>.outline.md  # Phase 6
        ├── article-<slug>.md       # Phase 7 draft (gets edited through Phase 8)
        ├── article-<slug>.html     # Phase 10 rendered HTML
        ├── article-<slug>.hygiene-check.md
        ├── article-<slug>.compliance-review.md
        ├── article-<slug>.accessibility-review.md
        ├── article-<slug>.fact-check.md
        ├── article-<slug>.review-summary.md  # Phase 8 rollup (from /exp-review)
        ├── compliance-bundle.pdf    # Phase 9 PDF for the FI sign-off
        ├── build-review-package.py  # per-experiment v1 HTML builder (optional)
        ├── review-package.html      # client-facing HTML deliverable (optional)
        └── netlify-deploy/          # static-site deploy folder (optional)
            ├── index.html
            ├── compliance-bundle.pdf
            ├── _headers
            ├── _redirects
            └── README.md
```

## Naming conventions

- **Experiment slug:** short, lowercase, hyphenated, tied to the topic. Examples: `southern-wi-first-time-homebuyer`, `dane-county-auto-refi`, `southwest-wi-cd-rates`. Never `experiment-87`.
- **Campaign name:** title case, descriptive, geo-anchored where relevant. Examples: `Southern WI First-Time Homebuyer Lender Decision`, `Dane County Auto Loan Refinance`.
- **Prompt content:** how a real consumer would ask. No brand names (the goal is organic mentions). Include location context when relevant.
- **Article slug:** lowercase, hyphenated, descriptive. `article-southern-wi-fthb-lender-guide.md` not `article.md`.
- **Article URL slug at publish:** `/loans/mortgage-options/<topic-slug>/` or similar — should sit inside the customer's existing URL structure, not at root.

## Credential convention

- DataForSEO: `~/.dataforseo.env` (preferred — works across all customer projects) OR `<project>/.dataforseo.env` (project-local override). Plain `KEY=value` per line.
- Paraloom API token: stored in the MCP config via `claude mcp add paraloom --env PARALOOM_API_TOKEN=<token>`. Never committed to the project.
- Heartland-specific (or other customer-specific) credentials: same pattern — `<project>/.<service>.env`, gitignored.

## Sidecar pattern

Every article carries three sidecar files that travel with it from Phase 5 through Phase 11:

- **`evidence.md`** — empirical inputs feeding decisions. Each entry is an observation with a citation, not a prescription.
- **`decisions.md`** — content choices and reasoning. Choice / Evidence / Alternatives shape per decision. Rejected alternatives must include the explicit "rejected because" line. Must include a **deliverable-length decision** (a word-count band anchored to the measured length of the competitor pages the baseline cited for the target prompts, rule #20) — length is a recorded, evidence-backed choice, never an unexamined by-product of the outline.
- **`workflow-log.md`** — phase-by-phase status spine. Statuses, sign-offs, run sequence, methodology lessons.

## Stop points (LEGACY: conversational runs only)

Under the `/exp-*` suite (the default execution path), the agent makes the prompt-keep, target-selection, and pivot decisions itself and reports them. **There is no draft-review stop** — the suite auto-continues `/exp-research` → `/exp-build` → `/exp-review` → `/exp-deliver`, holding the deliverable at the send gate. The routine human gate is one: the Phase 9 FI sign-off (a required human gate; any designated recipient at the FI can sign, not just a compliance officer), plus the send-approval gate on the client deliverable. The stop points below apply when running phases conversationally outside the suite:

1. **End of Phase 1 step 4** — Ryan signs off on the refined candidate prompt list before keyword research runs.
2. **End of Phase 4** — Ryan signs off on the target prompts and hypothesis before the Paraloom experiment record is created.
3. **End of Phase 6** — Ryan signs off on the article outline before Phase 7 drafting begins.
4. **End of Phase 8** — Phase 8 review reports get packaged for the FI sign-off (Phase 9). Article does not publish until that sign-off arrives.

Don't push past these without explicit go-ahead. Document each sign-off in `workflow-log.md` with name + date.

## .gitignore template

```
# credentials
.dataforseo.env
.*.env

# netlify state
.netlify/

# cache
__pycache__/
*.pyc
.cache/

# build artifacts
*.pdf
*.html
review-package.html

# But DO commit:
!compliance-bundle.pdf      # the canonical PDF for compliance archival
!article-*.html              # the publish-ready HTML
!netlify-deploy/             # the deploy folder shape (excluding state)
```

(Adjust per customer based on whether they want PDFs/HTML in the repo.)

## When to create a new customer project vs new experiment

- **New customer project:** new credit union. New CLAUDE.md, new MCP team_id, new credentials. Copy the `_paraloom-agent/` kit as starting point.
- **New experiment in existing project:** same customer, new topic. New `experiments/<slug>/` folder. Reuse the project's CLAUDE.md, docs, tools.

## Per-experiment kickoff checklist

When starting a new experiment:

- [ ] Confirm customer + team_id by listing Paraloom teams
- [ ] Read prior experiment's workflow-log to see what worked / didn't (institutional memory)
- [ ] Confirm whether the topic fits an existing campaign or needs a new one
- [ ] Confirm geographic scope, target audience, intent angle
- [ ] Confirm who at the FI will sign off at Phase 9 (the POC, a compliance reviewer, or whoever they designate — POC forwarding to a compliance reviewer is typical)
- [ ] Confirm CMS for publish (WordPress is the default; verify)
- [ ] Confirm any launch deadline (work backward through phase durations)
- [ ] Run `/exp-research` with `{slug, teamId, topic, audience, geography, creditUnion, domain}`: it creates the experiment folder, generates and triages keyword-grounded candidate prompts across intent angles, creates (or reuses) the campaign, creates the prompts, and kicks off the baseline run. Pass `dryRun:true` to stop after triage (no writes) if the prompt list should be previewed first.
