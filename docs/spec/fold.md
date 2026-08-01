# The Fold — Feature spec

Resolution of [#42 `/fold` skill: Journal Entries into curated notes](https://github.com/lyeyixian/personal-assistant-harness/issues/42), re-scoped from [#26](https://github.com/lyeyixian/personal-assistant-harness/issues/26) under the [session-as-orchestrator re-scope (#36)](https://github.com/lyeyixian/personal-assistant-harness/issues/36).
Builds on the [experience store schema](experience-store-schema.md) (the capture → fold → review write path) and [ADR-0003](../adr/0003-role-level-notes-over-atomic-achievements.md) (achievements are subsections, not notes).

**The skill is the implementation**, in the vault at `.claude/skills/fold/SKILL.md`. This spec records the contract and the decisions behind it, not the instructions; where the two disagree, the skill wins.

## Purpose

Turn the raw day-to-day capture into durable career record. The Fold processes every journal file
with pending entries, rewrites each pending Journal Entry into the note where it belongs, and leaves
the result uncommitted so the human reviews the whole curation as a `git diff` before it lands.

This is the one place the Experience Store gets **rewritten** rather than appended to — which is why
the human gate is a diff and not a confirmation prompt. Capture itself stays in Obsidian: zero
friction, no session required.

## Surface

A Claude Code skill, `fold`, in the vault's `.claude/skills/` directory alongside `/fit` and
`/resume` — not a `pa` command. `pa` never writes into the Experience Store (#36), and the Fold is
entirely judgment: classifying an entry, placing it, and writing prose in the vault's voice. Once
the session does that, no deterministic core is left to own, so the whole feature is the skill's
instructions. Promotion to a Claude Code plugin is the agreed destination for all three skills and
is out of scope here; in-vault iterates faster.

## Contract

**Pending is positional.** A file's pending entries are the bullets above its `## Folded` heading;
everything below was folded already and is never reprocessed. That, not a flag, is what makes a
second run a no-op. The `folded:` frontmatter field is a fast index into which files have work in
them — when the two disagree, the bullets win, because hand-capture in Obsidian writes the bullets
and not always the flag. This reconciles #42's first two acceptance criteria; it supersedes the
schema spec's write-path step 2 ("processes every `folded: false` journal file"), which is left for
the #38 documentation sweep to restate.

**Target resolution is ordered and deterministic.** A `[[wikilink]]` in the entry that resolves to a
note under `roles/` or `projects/` wins outright — the human put it there deliberately. Otherwise the
target is inferred from content. Otherwise it defaults to the current role (the `roles/` note with
`end: null`).

**Destinations:**

| The entry is | It becomes |
|---|---|
| Day-to-day work with an outcome | A new `###` Achievement subsection in the target Role/Project Note, or an update to an existing one |
| Behavioural-interview material | A new note under `stories/`, kept apart from CV-facing Achievements |
| A skill exercised with no discrete outcome | `skills:` frontmatter + Skills Inventory additions only |
| Work done outside an employment role | An Achievement inside a Project Note, created if absent |
| Too ambiguous to place | Raised, not written |

**Invariants the skill is written to hold:**

- Achievements are always subsections inside a Role or Project Note, never their own notes (ADR-0003),
  and follow the schema's mini-arc: prose, then `**Impact:**` where known, then optional `**Lessons:**`.
- Updating an existing Achievement keeps its heading **verbatim** — headings are cited as
  `<note-slug>#<heading-slug>` by the fit analysis and the provenance gate, so rewording one silently
  breaks live citations.
- Metric caveats ride inline next to the number and are never dropped; anything awaiting an upgrade
  (projection → actuals, pre-live → delivered) carries `#revisit`.
- Impact is omitted rather than invented; thin material is raised rather than guessed at.
- The raw journal text is preserved verbatim as the audit trail — moved under `## Folded`, marked
  folded, and pointed at where it landed. The curated note is the rewrite; the journal is the record
  of what was actually captured.
- A file's `folded:` flag flips to `true` only when no pending entry is left in it. A file with a
  raised entry keeps `folded: false` — it still has work in it, and a flag saying otherwise would
  hide that from the next run.
- The skill never commits and never stages. It closes by reporting what landed where, what skills it
  registered, and every entry it raised.

## Raise, don't guess

An entry that records an intention rather than work done ("capture the volumes when they're
reported"), whose facts are too thin to write, or whose target genuinely can't be pinned down, is
left pending and reported with what would make it foldable. Raising is cheap and reversible; a
guessed Achievement is a false career record the human has to catch in a diff.

## Verification

No automated seam, per #36: the skill is markdown instructions, and a test asserting the file exists
would be theatre. It is verified by folding a real day's entries against the real vault and reading
the diff.

## Kept-open evolution paths

- **Plugin promotion** — moves all three skills into this repo, version-controlled and usable from
  any directory.
- **Per-entry journal files** — the positional pending rule exists because files are per-day; it
  becomes a per-file flag if that ever changes.
- **A `pa fold --check`-style lint** — if drift between `folded:` flags and bullet positions turns
  out to matter, it is a deterministic read-only check and therefore `pa`'s kind of work.
