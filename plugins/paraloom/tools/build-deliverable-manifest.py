#!/usr/bin/env python3
"""Assemble and validate deliverable.json (the manifest) for an experiment.

The manifest is the contract between the agent, Paraloom (system of record),
and the client deliverable app — schema in docs/deliverables-architecture.md
(this repo) and DELIVERABLES-API.md (paraloom repo, authoritative).

Deterministic assembly only: the judgment-heavy inputs (opportunity header,
checklist, action items) are authored by the agent (the /exp-review synthesize
step writes <experiment-dir>/manifest-inputs.json) or by hand. This script
merges them with the article and dossier files, validates everything, and
writes deliverable.json — refusing loudly on any contract violation so bad
manifests never reach Paraloom.

    python3 tools/build-deliverable-manifest.py \
      --experiment-dir experiments/<slug> \
      [--inputs <dir>/manifest-inputs.json] [--status needs-input] \
      [--scheduled-for YYYY-MM-DD --opt-out-by YYYY-MM-DD] \
      [--output <dir>/deliverable.json]

Validations:
  - action item ids unique; types/statuses/roles from the contract enums
  - every non-null anchor quote occurs in the article markdown; ambiguous
    quotes (multiple occurrences) must carry a prefix/suffix that resolves
    to exactly one occurrence
  - checklist states from the enum; blocking open items force status needs-input
"""
import argparse
import json
import re
import sys
from pathlib import Path

ITEM_TYPES = {"fact-confirm", "compliance-disposition", "attestation", "choice"}
ITEM_STATUSES = {"open", "answered", "applied", "returned"}
CHECK_STATES = {"pass", "pending", "n/a"}
CHECK_STAGES = {"pre-publish", "publish-time", "post-publish"}
ROLES = {"poc", "compliance-officer", "web-team", "agent", "paraloom"}
DELIVERABLE_STATUSES = {"needs-input", "ready", "scheduled", "published", "measuring"}

# Dossier discovery: (label, filename) in client-reading order; missing files skipped.
# Each discovered doc may carry an optional plain-language `summary` (keyed by
# filename in inputs["dossierSummaries"]); the raw markdown is always preserved.
def dossier_candidates(slug):
    return [
        ("Review summary", f"article-{slug}.review-summary.md"),
        ("Decisions log", "decisions.md"),
        ("Evidence dossier", "evidence.md"),
        ("Keyword research", "keyword-research.md"),
        ("Opportunity analysis", "build-analysis.md"),
        ("Pre-publish hygiene check", f"article-{slug}.hygiene-check.md"),
        ("NCUA compliance review", f"article-{slug}.compliance-review.md"),
        ("ADA accessibility review", f"article-{slug}.accessibility-review.md"),
        ("Fact verification", f"article-{slug}.fact-check.md"),
    ]


def first_h1(md: str):
    m = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    return m.group(1).strip() if m else None


def resolve_anchor(anchor, article_md, errors, where):
    """Anchor quotes must resolve to exactly one occurrence in the article markdown."""
    quote = anchor.get("quote", "")
    if not quote:
        errors.append(f"{where}: anchor has an empty quote")
        return
    count = article_md.count(quote)
    if count == 0:
        errors.append(f"{where}: anchor quote not found in article: \"{quote[:80]}\"")
        return
    if count == 1:
        return
    prefix, suffix = anchor.get("prefix", ""), anchor.get("suffix", "")
    if not prefix and not suffix:
        errors.append(
            f"{where}: anchor quote occurs {count} times and has no prefix/suffix to disambiguate: \"{quote[:80]}\""
        )
        return
    qualified = article_md.count(f"{prefix}{quote}{suffix}")
    if qualified != 1:
        errors.append(
            f"{where}: anchor quote occurs {count} times; prefix/suffix narrow it to {qualified} matches (need exactly 1)"
        )


def validate(manifest, errors):
    d = manifest["deliverable"]
    if d["status"] not in DELIVERABLE_STATUSES:
        errors.append(f"deliverable.status \"{d['status']}\" not in {sorted(DELIVERABLE_STATUSES)}")
    article_md = d["article"]["markdown"]
    if not article_md.strip():
        errors.append("article markdown is empty")

    seen = set()
    open_blocking = 0
    for item in manifest["actionItems"]:
        where = f"actionItems[{item.get('id', '?')}]"
        for key in ("id", "type", "status", "assigneeRole", "question", "context"):
            if not item.get(key):
                errors.append(f"{where}: missing required field \"{key}\"")
        if item.get("id") in seen:
            errors.append(f"{where}: duplicate id")
        seen.add(item.get("id"))
        if item.get("type") not in ITEM_TYPES:
            errors.append(f"{where}: type \"{item.get('type')}\" not in {sorted(ITEM_TYPES)}")
        if item.get("status") not in ITEM_STATUSES:
            errors.append(f"{where}: status \"{item.get('status')}\" not in {sorted(ITEM_STATUSES)}")
        if item.get("assigneeRole") not in ROLES:
            errors.append(f"{where}: assigneeRole \"{item.get('assigneeRole')}\" not in {sorted(ROLES)}")
        if "blocking" not in item:
            errors.append(f"{where}: missing \"blocking\" (must be explicit)")
        if item.get("anchor") is not None:
            resolve_anchor(item["anchor"], article_md, errors, where)
        # "open_blocking" here means a blocking item still needing client input
        # (open) or bounced back to them (returned) — it forces needs-input below.
        # An answered-but-unapplied fact-confirm CORRECTION is also unresolved, but
        # that distinction lives server-side (DeliverableActionItem::isResolved); by
        # the time the agent builds a manifest it has already applied such answers
        # and marks the item "applied", so it is not counted here. See the app repo
        # (Deliverable::readyToPublish) and docs/deliverables-architecture.md.
        if item.get("blocking") and item.get("status") in ("open", "returned"):
            open_blocking += 1

    for check in manifest["checklist"]:
        where = f"checklist[{check.get('id', '?')}]"
        for key in ("id", "group", "label", "state"):
            if not check.get(key):
                errors.append(f"{where}: missing required field \"{key}\"")
        if check.get("state") not in CHECK_STATES:
            errors.append(f"{where}: state \"{check.get('state')}\" not in {sorted(CHECK_STATES)}")
        if check.get("assigneeRole") and check["assigneeRole"] not in ROLES:
            errors.append(f"{where}: assigneeRole \"{check['assigneeRole']}\" not in {sorted(ROLES)}")
        if check.get("stage") and check["stage"] not in CHECK_STAGES:
            errors.append(f"{where}: stage \"{check['stage']}\" not in {sorted(CHECK_STAGES)} (omit for pre-publish)")
        assignee = check.get("assignee")
        if assignee is not None:
            if not isinstance(assignee, dict) or not assignee.get("name") or not assignee.get("email"):
                errors.append(f"{where}: assignee must be an object with non-empty \"name\" and \"email\"")

    if open_blocking and d["status"] in ("ready", "scheduled", "published"):
        errors.append(
            f"deliverable.status is \"{d['status']}\" but {open_blocking} blocking action item(s) are open/returned — must be needs-input"
        )

    opp = manifest.get("opportunity") or {}
    for key in ("headline", "demand", "verdict"):
        if not opp.get(key):
            errors.append(f"opportunity.{key} is required (the client-facing \"why this exists\" header)")
    return open_blocking


def main():
    ap = argparse.ArgumentParser(description="Assemble + validate deliverable.json for an experiment folder.")
    ap.add_argument("--experiment-dir", required=True)
    ap.add_argument("--slug", help="default: experiment-dir basename")
    ap.add_argument("--inputs", help="agent-authored inputs json (default: <dir>/manifest-inputs.json)")
    ap.add_argument("--status", help="override deliverable status (default: from inputs, else derived)")
    ap.add_argument("--scheduled-for", help="publishPlan.scheduledFor (YYYY-MM-DD)")
    ap.add_argument("--opt-out-by", help="publishPlan.optOutBy (YYYY-MM-DD)")
    ap.add_argument("--title", help="default: inputs title, else the article H1")
    ap.add_argument("--short-title", help="short header label (default: inputs shortTitle); the client app shows it in the top chrome instead of the full article title")
    ap.add_argument("--output", help="default: <dir>/deliverable.json")
    args = ap.parse_args()

    exp_dir = Path(args.experiment_dir)
    if not exp_dir.is_dir():
        sys.exit(f"ERROR: not a directory: {exp_dir}")
    slug = args.slug or exp_dir.resolve().name

    inputs_path = Path(args.inputs) if args.inputs else exp_dir / "manifest-inputs.json"
    if not inputs_path.exists():
        sys.exit(f"ERROR: inputs file not found: {inputs_path} (the /exp-review synthesize step writes it, or author by hand)")
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))

    article_path = exp_dir / f"article-{slug}.md"
    if not article_path.exists():
        sys.exit(f"ERROR: article not found: {article_path}")
    article_md = article_path.read_text(encoding="utf-8")
    html_path = exp_dir / f"article-{slug}.html"
    article_html = html_path.read_text(encoding="utf-8") if html_path.exists() else None

    ids = inputs.get("ids", {})
    action_items = inputs.get("actionItems", [])
    open_blocking_in = [i for i in action_items if i.get("blocking") and i.get("status") in ("open", "returned")]
    status = args.status or inputs.get("status") or ("needs-input" if open_blocking_in else "ready")

    publish_plan = inputs.get("publishPlan")
    if args.scheduled_for or args.opt_out_by:
        if not (args.scheduled_for and args.opt_out_by):
            sys.exit("ERROR: --scheduled-for and --opt-out-by must be provided together")
        publish_plan = {"scheduledFor": args.scheduled_for, "optOutBy": args.opt_out_by}

    # Human-readable layer (optional, generated by the /exp-review synthesize step):
    # a per-doc plain-language summary keyed by dossier filename, plus a single
    # featured "why we're confident" overview. Both stay optional so older
    # deliverables (no summaries) render exactly as before.
    dossier_summaries = inputs.get("dossierSummaries", {}) or {}
    used_summary_keys = set()
    dossier = []
    for label, fname in dossier_candidates(slug):
        path = exp_dir / fname
        if path.exists():
            item = {"label": label, "markdown": path.read_text(encoding="utf-8")}
            summary = dossier_summaries.get(fname)
            if isinstance(summary, str) and summary.strip():
                item["summary"] = summary
                used_summary_keys.add(fname)
            dossier.append(item)
        else:
            print(f"note: dossier file missing, skipped: {fname}", file=sys.stderr)
    for key in dossier_summaries:
        if key not in used_summary_keys:
            print(f"note: dossierSummaries key matched no dossier file, ignored: {key}", file=sys.stderr)

    evidence_overview = inputs.get("evidenceOverview")
    if not (isinstance(evidence_overview, str) and evidence_overview.strip()):
        evidence_overview = None

    short_title = args.short_title or inputs.get("shortTitle")
    manifest = {
        "manifestVersion": 1,
        "deliverable": {
            "slug": slug,
            "title": args.title or inputs.get("title") or first_h1(article_md) or slug,
            **({"shortTitle": short_title} if short_title else {}),
            "experimentId": ids.get("experimentId"),
            "campaignId": ids.get("campaignId"),
            "teamId": ids.get("teamId"),
            "status": status,
            "publishPlan": publish_plan,
            "article": {"markdown": article_md, **({"html": article_html} if article_html else {})},
        },
        "opportunity": inputs.get("opportunity", {}),
        "checklist": inputs.get("checklist", []),
        "actionItems": action_items,
        "dossier": dossier,
        **({"evidenceOverview": evidence_overview} if evidence_overview else {}),
    }

    errors = []
    open_blocking = validate(manifest, errors)
    if errors:
        print(f"INVALID — {len(errors)} contract violation(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output) if args.output else exp_dir / "deliverable.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    checks = manifest["checklist"]
    passing = sum(1 for c in checks if c["state"] == "pass")
    applicable = sum(1 for c in checks if c["state"] != "n/a")
    pct = round(100 * passing / applicable) if applicable else 0
    summarized = sum(1 for d in dossier if d.get("summary"))
    print(
        f"Wrote {output} ({output.stat().st_size:,} bytes): status={status}, "
        f"checklist {passing}/{applicable} pass ({pct}%), "
        f"{len(action_items)} action items ({open_blocking} open blocking), "
        f"{len(dossier)} dossier docs ({summarized} with plain-language summaries), "
        f"evidenceOverview {'present' if evidence_overview else 'absent'}"
    )


if __name__ == "__main__":
    main()
