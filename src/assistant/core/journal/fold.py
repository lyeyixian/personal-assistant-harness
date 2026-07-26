"""The Fold — the Experience Store's curation step, per the schema spec.

Rewrites every pending Journal Entry into a schema-conforming Achievement
mini-arc or Story note, propagates new skills to role/project frontmatter
and the Skills Inventory, then moves the entry under its journal file's
`## Folded` heading with a `→ [[target]]` pointer.

Target resolution (a `[[wikilink]]` hint, else the current role) is
deterministic, never the agent's call - the agent only classifies and
writes content; placement is decided in `run_fold` so a wikilink hint is
always respected regardless of what the model says, and pending files stay
idempotent without needing the model's cooperation. The harness never
commits: every write here lands on disk for the human to review as a
`git diff`.
"""

from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent

from assistant.core.agents import create_agent, usage_limits
from assistant.core.config import Settings
from assistant.core.journal.capture import PendingJournalFile, apply_fold, pending_journal_files
from assistant.core.journal.fold_types import FoldedEntry, FoldPlan
from assistant.core.journal.fold_writer import (
    append_achievement,
    create_story,
    propagate_skills,
    skills_registry,
    update_achievement,
)
from assistant.core.store.loader import load_store
from assistant.core.store.models import ExperienceStore, Note

_SYSTEM_PROMPT = """You curate a personal Experience Store vault by folding raw journal
entries into its structured notes.

For every pending entry given to you, decide:
- `kind`: "achievement" (day-to-day work) or "story" (a behavioral-interview
  anecdote - human material, not CV-facing).
- For an achievement: whether it extends an existing achievement
  (`operation="update"` + `existing_heading_slug` from the list given to you)
  or starts a new one (`operation="new"`). Write `heading` (a short title,
  ignored when updating - the original heading is kept so provenance refs
  never break), `body` (prose: what/how), and optionally `impact`/`lessons`.
- For a story: write `heading` (a short title used to slug the new note),
  `body` (the narrative), and `competencies` (behavioral competency tags).
- `skills`: any canonical skill slugs the entry demonstrates. Reuse an
  existing slug's exact spelling when the skill is already known; only
  invent a new slug when it truly is not in the list you were given. When a
  skill is new to the registry, set `new_skill_category` to the best-fitting
  existing category heading.

Never invent facts beyond what the entry says. Keep any metric qualifier the
entry gives (e.g. "projection", "per go-live email") inline next to the
number in `impact` rather than dropping it, and tag anything still awaiting
an upgrade (projection to actuals, pre-live to delivered) with `#revisit`.

You do not choose which note an achievement or story is filed under - that
is resolved deterministically outside of you. Return exactly one output
entry per input entry, each tagged with the same `source_index` you were
given."""


@dataclass(frozen=True, slots=True)
class FoldDeps:
    """The Fold agent's deps, injected via `RunContext` per ADR-0002 - the
    vault's current read-only snapshot, for any future tool that needs it."""

    store: ExperienceStore


@dataclass(frozen=True, slots=True)
class FoldedFileSummary:
    path: Path
    bullet_count: int


@dataclass(frozen=True, slots=True)
class FoldResult:
    files: tuple[FoldedFileSummary, ...]
    achievements_created: int
    achievements_updated: int
    stories_created: int
    skills_registered: int

    @property
    def entry_count(self) -> int:
        return sum(f.bullet_count for f in self.files)


def run_fold(
    vault_path: Path,
    settings: Settings,
    *,
    agent: Agent[FoldDeps, FoldPlan] | None = None,
) -> FoldResult:
    """Fold every pending Journal Entry into the vault's curated notes.

    A no-op (no agent call, no writes) when nothing is pending - this is
    what makes an immediate re-run idempotent.
    """
    pending_files = pending_journal_files(vault_path)
    if not pending_files:
        return FoldResult(
            files=(),
            achievements_created=0,
            achievements_updated=0,
            stories_created=0,
            skills_registered=0,
        )

    store = load_store(vault_path)
    current_role = _current_role(store)
    fold_agent = agent if agent is not None else _build_agent(settings)

    flat_entry_count = sum(len(f.bullets) for f in pending_files)
    prompt = _build_prompt(store, current_role, pending_files)
    result = fold_agent.run_sync(
        prompt, deps=FoldDeps(store=store), usage_limits=usage_limits(settings)
    )
    plan = result.output

    by_index: dict[int, FoldedEntry] = {entry.source_index: entry for entry in plan.entries}
    missing = [i for i in range(flat_entry_count) if i not in by_index]
    if missing:
        raise ValueError(f"fold plan is missing entries for source_index {missing}")

    achievements_created = achievements_updated = stories_created = skills_registered = 0
    file_summaries: list[FoldedFileSummary] = []

    index = 0
    for file in pending_files:
        folded_lines: list[str] = []
        for bullet in file.bullets:
            entry = by_index[index]
            target_slug = _resolve_target(store, bullet.wikilink, current_role)
            target_note = store.note(target_slug)
            assert target_note is not None

            if entry.kind == "story":
                pointer_slug = create_story(vault_path, entry, roles=[target_slug])
                stories_created += 1
            elif entry.operation == "update" and entry.existing_heading_slug:
                update_achievement(vault_path, target_note, entry)
                achievements_updated += 1
                pointer_slug = target_slug
            else:
                append_achievement(vault_path, target_note, entry)
                achievements_created += 1
                pointer_slug = target_slug

            if entry.skills:
                skills_registered += propagate_skills(
                    vault_path, target_note, entry.skills, entry.new_skill_category
                )

            folded_lines.append(f"{bullet.raw} → [[{pointer_slug}]]")
            index += 1

        apply_fold(file.path, folded_bullet_lines=folded_lines)
        file_summaries.append(FoldedFileSummary(path=file.path, bullet_count=len(file.bullets)))

    return FoldResult(
        files=tuple(file_summaries),
        achievements_created=achievements_created,
        achievements_updated=achievements_updated,
        stories_created=stories_created,
        skills_registered=skills_registered,
    )


def _build_agent(settings: Settings) -> Agent[FoldDeps, FoldPlan]:
    return create_agent(
        FoldPlan, deps_type=FoldDeps, settings=settings, system_prompt=_SYSTEM_PROMPT
    )


def _current_role(store: ExperienceStore) -> Note:
    """The role note that defaults an entry's target when no wikilink hints otherwise."""
    current = [
        note for note in store.notes if note.type == "role" and note.frontmatter.get("end") is None
    ]
    if not current:
        raise ValueError(
            "no current role (a role note with `end: null`) to default the Fold target to"
        )
    return max(current, key=lambda note: str(note.frontmatter.get("start", "")))


def _resolve_target(store: ExperienceStore, wikilink: str | None, current_role: Note) -> str:
    if wikilink is not None:
        hinted = store.note(wikilink)
        if hinted is not None and hinted.type in ("role", "project"):
            return hinted.slug
    return current_role.slug


def _build_prompt(
    store: ExperienceStore, current_role: Note, pending_files: list[PendingJournalFile]
) -> str:
    lines = [
        "Fold the following pending journal entries into the Experience Store.",
        f"Current role (default target when an entry has no wikilink hint): {current_role.slug}",
        "",
        'Existing achievement headings by note - use `operation="update"` + '
        '`existing_heading_slug` to extend one, otherwise `operation="new"`:',
    ]
    for note in store.notes:
        if note.type in ("role", "project"):
            headings = (
                ", ".join(f"{a.slug} ({a.heading!r})" for a in note.achievements) or "(none yet)"
            )
            lines.append(f"- {note.slug}: {headings}")

    skills_note = store.note("skills")
    registry = skills_registry(skills_note.body) if skills_note is not None else {}
    lines.append("")
    lines.append("Known skill categories: " + ", ".join(sorted(set(registry.values()))))
    lines.append(
        "Known skill slugs (reuse the exact spelling for any of these): "
        + ", ".join(sorted(registry))
    )

    lines.append("")
    lines.append("Pending entries, one per line, each prefixed with its `source_index`:")
    index = 0
    for file in pending_files:
        for bullet in file.bullets:
            hint = f" [wikilink hint: {bullet.wikilink}]" if bullet.wikilink else ""
            lines.append(f"{index}. ({file.date}) {bullet.text}{hint}")
            index += 1

    lines.append("")
    lines.append(
        "Return exactly one FoldedEntry per source_index above, covering every index once."
    )
    return "\n".join(lines)
