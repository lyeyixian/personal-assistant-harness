# Job-fit & gap analysis — Feature spec

Resolution of [#9 Spec: job-fit & gap analysis feature](https://github.com/lyeyixian/personal-assistant-harness/issues/9).
Builds on the [experience store schema](experience-store-schema.md), [ADR-0002 (harness architecture)](../adr/0002-harness-architecture.md), the [eval approaches research (#8)](https://github.com/lyeyixian/personal-assistant-harness/issues/8), and the sibling [resume-generation spec](resume-generation.md) (#10) — the two features share posting intake.

## Purpose

Given a job posting, answer two questions the dev actually acts on — **can I get this?** (capability fit vs the experience store) and **do I want this?** (alignment with `direction.md`) — and turn every shortfall into a concrete next move.

## Posting intake

**Pasted text only** in v1 — no URL fetching or scraping (LinkedIn/ATS pages block it; the manual paste costs seconds). A `--url` flag stores the posting's link as metadata for reference.

Each posting becomes a **job note** in a new `jobs/` folder of the experience-store vault — local-first and private like the rest of the vault, Obsidian-browsable, and the single input later features (resume generation hand-off, roadmap pipeline tracking) read:

```markdown
---
type: job
company: Anthropic
title: AI Engineer
market: remote           # sg | remote — inferred by the posting parser, --market overrides
url: https://…           # optional, metadata only
captured: 2026-07-19
verdict: null            # written by fit analysis: strong-fit | good-fit | stretch | skip
direction: null          # written by fit analysis: aligned | caution | conflict
analyzed: null           # date of last fit run
---
<pasted posting text, verbatim>
```

The filename is a minted kebab slug, `jobs/<company>-<title>.md` (e.g. `jobs/anthropic-ai-engineer.md`). The verbatim posting body is the source of truth for analysis and re-analysis; the raw paste is never edited by the agent.

## Pipeline

A fixed, code-orchestrated pipeline — barely agentic per ADR-0002; code drives, no tool loop. Two typed agent calls on top of the shared deterministic parse:

0. **Deterministic pre-step** — the posting parser shared with `pa jobs resume` produces the typed `JobPosting` model (title, company, market, requirements, keywords). Both v1 features consume identical posting input; the market inference and `--market` override behave exactly as the resume spec defines.
1. **Extract** (agent call 1): posting text → a typed `RequirementSet`. Each requirement carries:
   - `text` — the requirement, in the posting's own terms
   - `kind` — `must-have` | `nice-to-have`, as the posting frames it
   - `firmness` — `likely-firm` | `likely-flexible`, with a one-line `reason`. Postings are wishlists; this tag is the explicit calibration. Classic flexible signals: years-of-experience numbers, laundry-list tech, "expert in N frameworks". Classic firm signals: degree tied to visa sponsorship, security clearance, the role's named core stack.
   - `category` — e.g. language/framework, domain, seniority, practice — loose, for grouping in output
2. **Match** (agent call 2): full curated vault (journal *and* `jobs/` excluded, per the retrieval contract — other postings are noise when analyzing one) + `direction.md` + the `RequirementSet` → a typed `FitReport`.

## FitReport

The typed output of the match stage:

- **Per-requirement grades** — for every extracted requirement: `met` | `partial` | `gap`, with **evidence citations** for met/partial grades. A citation is a `<note-slug>#<achievement-heading>` ref (e.g. `acme-payments-rotation#partner-bank-onboarding-automation`) plus a one-line note — the same source-ref format as the resume spec's provenance field, checked by the same deterministic validator before the report is written. Every evidence claim must be entailed by the store; that is the eval hard-fail.
- **Verdict** — a capability-only tier: `strong-fit` | `good-fit` | `stretch` | `skip`, plus a 2–3 sentence rationale grounded in the per-requirement grades. No numeric score. The tier rubric **weighs gaps by firmness**: a gap on a likely-flexible requirement barely moves the tier; a gap on a likely-firm must-have moves it decisively.
- **Direction check** — a separate axis, never blended into the tier: `aligned` | `caution` | `conflict` against `direction.md` (target roles, constraints, what the dev is moving toward/away from), with reasons. "Strong fit / conflict" is a legal and meaningful combination — you'd get it, and it's the role you're leaving.
- **Gaps & bridging actions** — the requirements graded `partial`/`gap`, ordered must-haves first. Each carries one typed bridging action:
  - `positioning` — evidence exists in the store but needs reframing or surfacing. Direct fuel for tailored-resume generation.
  - `learning` — a real gap needing a project or course. The seam the roadmap skill-gap tracker later plugs into.

## Output

- The report renders as a **`## Fit analysis` section in the job note itself**, replaced wholesale on re-run — git history preserves earlier runs. Rendered order: verdict + rationale, direction check, per-requirement table (requirement, kind, firmness, grade, evidence), gaps with bridging actions.
- `verdict`, `direction`, and `analyzed` are lifted into the note's frontmatter so a vault listing shows fit at a glance.
- The same report pretty-prints to the terminal on every run.

Re-analysis is first-class and expected: the store grows via journaling folds and `direction.md` shifts, so `pa jobs fit` on an existing slug re-reads everything and overwrites the section.

## CLI surface

Three verbs on the `jobs` noun (matching `pa jobs resume`):

```
pa jobs add [file] [--url <url>]        # ingest: file, stdin, or $EDITOR when no file; prints the minted slug
pa jobs fit <slug|file> [--market sg|remote]  # run/re-run the analysis; a file path implies add first
pa jobs list                            # table from frontmatter: company, title, verdict, direction, analyzed
```

`pa jobs fit <file>` is the one-step paste-and-analyze flow: it mints the job note, then analyzes it. `pa jobs list` is where roadmap pipeline tracking (application status) later lands, as more frontmatter on the same notes.

## Evals

Per the eval research (#8), the two stages grade separately on the golden set of real postings + a profile snapshot:

- **Extraction** — reference-based: extracted requirements, kinds, and firmness tags vs golden labels. Firmness tagging is its own gradeable layer.
- **Match** — verdict tier grades by exact match against a golden label (discrete tiers are the point); per-requirement grades and direction check grade per-criterion; evidence entailment against the named source is the deterministic hard-fail, reusing the provenance validator.

## Kept-open evolution paths

Not v1 machinery; adopt when demanded:

- **Chaining resume generation off a `FitReport`** — v1 keeps the features siblings that share only `JobPosting` (per the resume spec); the per-requirement evidence map is the obvious future input to bullet selection.
- **`pa jobs resume <slug>`** — resume generation accepting a job-note slug instead of a posting file, once the jobs/ folder is the habitual intake path.
- **Skill-gap tracker absorbing analyses** — `learning` bridging actions accumulated across postings become the seed data for the roadmap's persistent skill-gap tracking.
- **Pipeline tracking** — application status frontmatter on job notes, surfaced in `pa jobs list`.
