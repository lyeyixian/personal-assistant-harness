# Experience Store — Schema

Resolution of [#4 Design: experience store schema](https://github.com/lyeyixian/personal-assistant-harness/issues/4).
The experience store is a **new dedicated Obsidian vault** (markdown source of truth, private git repo, kept outside iCloud) that the assistant reads for job-fit analysis and resume generation, and writes to via the journaling fold. The schema optimizes for full-context retrieval and human readability now, while keeping finer-grained retrieval a mechanical refactor later.

> All examples below are illustrative (fictional companies/projects). Real career data lives only in the private vault, never in this repo.

## Vault layout

```
vault/
├── profile.md            stable CV-facing facts: contact, education, certifications, languages
├── direction.md          career direction & constraints — the fit-analysis lens
├── skills.md             categorized skills inventory + canonical slug registry + pinned top skills
├── roles/                one note per team stint
│   ├── acme-graduate-programme.md    programme-level context (assessment funnel, bootcamp, rotation mechanics)
│   ├── acme-payments-rotation.md
│   ├── acme-data-rotation.md
│   ├── acme-platform-team.md
│   ├── studio-x-intern.md
│   └── studio-x-parttime.md
├── projects/             personal / school / open-source work (work initiatives stay inside role notes)
│   ├── oss-contribution.md
│   └── uni-capstone.md
├── stories/              interview story bank — one behavioral narrative per note
│   ├── prod-migration-rollback.md
│   └── ...
├── jobs/                 captured job postings + fit analyses — schema in the job-fit spec
│   └── anthropic-ai-engineer.md
└── journal/              capture inbox
    └── 2026-07-17.md
```

## Note types

### Role note (`roles/`)

One note per **team stint** — a rotation, permanent team, internship, or freelance engagement. A multi-team tenure at one employer splits into one note per stint, plus an optional programme note for programme-level context; frontmatter (`company`, `programme`) lets resume generation regroup stints into outward-facing positions (e.g. one merged "graduate programme" entry on LinkedIn).

```markdown
---
type: role
company: Acme Corp
title: Software Engineer
team: Payments Platform
programme: acme-grad     # optional — groups rotations under a programme
start: 2025-03
end: null                # null = current role
skills: [csharp, dotnet-core, postgresql, testcontainers, ci-cd]
---
## Context
The payments platform handling order settlement across the group's storefronts…

## Achievements
### Settlement-service refactor
Collapsed several internal microservices that added unnecessary IPC and DB round-trips…
**Impact:** the codebase's first integration tests (Testcontainers + Postgres in Docker), built as a reusable pattern.
**Lessons:** time pure refactors to coincide with a UAT window.

### Partner-bank onboarding automation
Extended the settlement module to onboard a new partner bank…
**Impact:** ~500 txns/month automated (projection, per go-live email — upgrade to actuals #revisit); eliminated interim manual entry.

## Reflections
Role-level lessons, motivations, and narrative…
```

**Achievement mini-arc**: each achievement is a `###` heading containing free prose (what/how), then labeled lines — `**Impact:**` (required where impact is known; metrics carry honesty caveats inline) and `**Lessons:**` (optional). Role-level `## Context` and `## Reflections` bookend the note. The consistent labels are deliberate seams: the fold step, resume generation, and any future note-splitting rely on them.

### Project note (`projects/`)

Personal, school, open-source, or hackathon work done **outside** an employment role. Work initiatives within a job are achievements inside role notes, never project notes.

```markdown
---
type: project
kind: open-source        # open-source | coursework | hackathon | side-project
start: 2022-05
end: 2022-08
skills: [angular, typescript, jest]
link: https://github.com/example/project
on-profile: true         # made the LinkedIn cut
---
## Context
…
## Achievements
### …
```

### Story note (`stories/`)

The interview story bank — messy, human, "tell me about a time…" material that doesn't belong on a CV. One narrative per note.

```markdown
---
type: story
competencies: [ownership, learning-from-failure, systems-thinking]
roles: [acme-payments-rotation]
---
While improving a shared CI action used org-wide… (situation → action → lesson)
```

### `profile.md`

Stable, CV-facing facts: name, contact, spoken languages, education, certifications/focus areas. Rarely changes.

### `direction.md`

The volatile, personal layer: current sentiment, what's next, target roles, personal constraints on the search. **Fit analysis reads this as its lens**; resume generation mostly ignores it.

```markdown
---
type: direction
target-roles: [ai-engineer, backend-engineer]
updated: 2026-07
---
…
```

### `skills.md`

The single curated inventory, categorized (languages, frameworks, infra, testing, practices…), including resume-facing picks (pinned top skills). Doubles as the **canonical slug registry** — the one place that fixes `dotnet-core` vs `.net`. Per-skill facts like last-used or depth are **derived on demand** from role frontmatter and dates, never stored (stored copies go stale). Per-skill notes are deliberately deferred; if post-v1 skill-gap tracking lands, they can be generated mechanically from role frontmatter.

### Journal file (`journal/`)

One file per day, `journal/YYYY-MM-DD.md` — the Obsidian daily-note idiom. Captures append timestamped free-form bullets; zero structure required at capture time. A `[[role-slug]]` wikilink in a bullet hints the fold target; otherwise the agent infers (default: the current role).

```markdown
---
folded: false
---
- 18:05 praised by the BA for story vetting — story material?

## Folded
- 14:20 shipped the queue integration for the reporting pipeline ✓ → [[acme-platform-team]]
```

## Write path (capture → fold)

1. **Capture** (anytime, frictionless): append a timestamped bullet to today's journal file — via a CLI capture command or directly in Obsidian. Creating the file sets `folded: false`; appending to an already-folded day resets it to `false`.
2. **Fold** (on demand): the agent processes every `folded: false` journal file — rewrites each pending bullet into the right note (a new or updated achievement subsection, a new story note, `skills:` frontmatter additions, `skills.md` additions), then moves the bullet under the file's `## Folded` heading with a `→ [[target]]` pointer and flips the flag.
3. **Review**: the human reviews the fold as a `git diff` and commits. The raw journal stays as an audit trail.

Pending = unmarked bullets above `## Folded`. This keeps fold idempotent despite per-day (not per-entry) files.

## Conventions

- **Slugs & linking**: filename = kebab-case slug; frontmatter references use bare slugs (`roles: [acme-platform-team]`); body prose uses `[[wikilinks]]`.
- **Metrics honesty**: caveats ride inline next to the number and are never dropped — e.g. `~500 txns/month (projection, per go-live email)`. Anything awaiting an upgrade (projection → actuals, pre-live → delivered) carries a `#revisit` tag; "things to revisit" is a tag query, not a maintained list.
- **Dates**: `YYYY-MM` in frontmatter; `end: null` means current.

## Retrieval contract

v1 retrieval is **full-context**: the corpus (~10k tokens seeded, slow growth) fits comfortably in one agent context, so fit analysis and resume generation read the curated vault whole (journal excluded — curated notes are the single source of truth after folding; `jobs/` excluded — postings are inputs under analysis, not experience). The schema additionally supports **grep-style selective retrieval** (consistent frontmatter: `type`, `skills`, dates, `competencies`) and keeps **atomization mechanical** (per-achievement headings + labeled fields) if the retrieval-strategy decision ([#6](https://github.com/lyeyixian/personal-assistant-harness/issues/6)) ever demands finer granularity.

## Seeding map (input to #5)

The seed artifacts (the pre-vault experience document + the LinkedIn profile rewrite) are private and stay out of this repo. Their content maps onto the schema as:

| Seed material | Destination |
|---|---|
| Profile basics (contact, education, certifications) | `profile.md` |
| Career context & motivations | `direction.md` |
| Technical skills inventory | `skills.md` |
| Employer/programme overview | `roles/<programme>.md` |
| Per-stint role detail | `roles/*.md` (one per stint) |
| Personal / school / open-source projects | `projects/*.md` |
| Interview story bank | `stories/*.md` |
| Metrics quick-reference (with honesty notes) | inline caveats at point of use |
| "Things to revisit" list | `#revisit` tags at point of use |

The LinkedIn rewrite informs `on-profile:` flags, pinned skills, and role summaries but is not itself migrated — it's an output-shaped document, and outputs are generated, not stored.
