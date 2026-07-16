# Personal Assistant Harness

A personal AI assistant whose first module is job search: an agent reads a store of career experience to analyze job fit and generate tailored resumes, and keeps that store fresh through journaling.

## Language

**Experience Store**:
The dedicated Obsidian vault holding the canonical, curated record of career experience — the single source of truth the assistant reads.
_Avoid_: knowledge base, experience bank (that's the pre-vault seed document)

**Role Note**:
One note per team stint — a rotation, permanent team, internship, or freelance engagement.
_Avoid_: position, job note

**Achievement**:
A discrete piece of work recorded as a structured subsection inside a role or project note — never its own note.
_Avoid_: accomplishment, initiative

**Project Note**:
A note for personal, school, or open-source work done outside an employment role. Work initiatives within a job are Achievements, not Projects.

**Story**:
A behavioral-interview anecdote tagged by competency — human material kept apart from CV-facing achievements.
_Avoid_: anecdote

**Journal Entry**:
A free-form, timestamped capture of day-to-day work appended to a per-day inbox file. Raw material, not curated truth.
_Avoid_: log, daily note

**Fold**:
The curation step where the agent rewrites pending journal entries into the structured notes, reviewed by the human as a git diff.
_Avoid_: sync, ingest, import

**Direction**:
The volatile record of career intent — target roles, motivations, constraints — that fit analysis uses as its lens.
_Avoid_: goals, preferences

**Skills Inventory**:
The single curated, categorized list of skills; also the canonical registry of skill slugs used across note frontmatter.

**Seeding**:
The one-time migration of the seed artifacts (experience bank, LinkedIn rewrite) into the Experience Store's schema.
