"""The Fold — the Experience Store's curation step, per the schema spec.

Rewrites every pending Journal Entry into a schema-conforming Achievement
mini-arc or Story note, propagates new skills to role/project frontmatter
and the Skills Inventory, then moves the entry under its journal file's
`## Folded` heading with a `→ [[target]]` pointer.

Target resolution (a `[[wikilink]]` hint, else the current role) is
deterministic, never the agent's call - the agent only classifies and
writes content; placement is decided in `run_fold` so a wikilink hint is
always respected regardless of what the model says. The harness never
commits: every write here lands on disk for the human to review as a
`git diff`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from assistant.core.agents import create_agent, usage_limits
from assistant.core.config import Settings
from assistant.core.journal.capture import PendingJournalFile, apply_fold, pending_journal_files
from assistant.core.store.loader import load_store
from assistant.core.store.models import ExperienceStore, Note
from assistant.core.store.parser import slugify

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

Never invent facts beyond what the entry says. You do not choose which note
an achievement or story is filed under - that is resolved deterministically
outside of you. Return exactly one output entry per input entry, each tagged
with the same `source_index` you were given."""


class FoldedEntry(BaseModel):
    """The agent's per-entry classification + content - never placement."""

    source_index: int
    kind: Literal["achievement", "story"]
    operation: Literal["new", "update"] = "new"
    existing_heading_slug: str | None = None
    heading: str
    body: str
    impact: str | None = None
    lessons: str | None = None
    competencies: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    new_skill_category: str | None = None


class FoldPlan(BaseModel):
    entries: list[FoldedEntry]


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
    skills_added: int

    @property
    def entry_count(self) -> int:
        return sum(f.bullet_count for f in self.files)


def run_fold(
    vault_path: Path,
    settings: Settings,
    *,
    agent: Agent[None, FoldPlan] | None = None,
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
            skills_added=0,
        )

    store = load_store(vault_path)
    current_role = _current_role(store)
    fold_agent = agent if agent is not None else _build_agent(settings)

    flat_entry_count = sum(len(f.bullets) for f in pending_files)
    prompt = _build_prompt(store, current_role, pending_files)
    result = fold_agent.run_sync(prompt, usage_limits=usage_limits(settings))
    plan = result.output

    by_index = {entry.source_index: entry for entry in plan.entries}
    missing = [i for i in range(flat_entry_count) if i not in by_index]
    if missing:
        raise ValueError(f"fold plan is missing entries for source_index {missing}")

    achievements_created = achievements_updated = stories_created = skills_added = 0
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
                pointer_slug = _create_story(vault_path, entry, roles=[target_slug])
                stories_created += 1
            elif entry.operation == "update" and entry.existing_heading_slug:
                _update_achievement(vault_path, target_note, entry)
                achievements_updated += 1
                pointer_slug = target_slug
            else:
                _append_achievement(vault_path, target_note, entry)
                achievements_created += 1
                pointer_slug = target_slug

            if entry.skills:
                skills_added += _propagate_skills(
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
        skills_added=skills_added,
    )


def _build_agent(settings: Settings) -> Agent[None, FoldPlan]:
    return create_agent(
        FoldPlan, deps_type=type(None), settings=settings, system_prompt=_SYSTEM_PROMPT
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
    registry = _skills_registry(skills_note.body) if skills_note is not None else {}
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


def _note_path(vault_path: Path, note: Note) -> Path:
    directory = {"role": "roles", "project": "projects", "story": "stories"}[note.type]
    return vault_path / directory / f"{note.slug}.md"


def _split_frontmatter_block(text: str) -> tuple[str, str]:
    """Split raw note text into its exact frontmatter block (fences included)
    and body, without going through YAML parsing - keeps every byte of the
    frontmatter untouched by body edits, and vice versa for `header` edits."""
    lines = text.split("\n")
    assert lines[0] == "---", "note is missing its opening frontmatter fence"
    end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    header = "\n".join(lines[: end + 1]) + "\n"
    body = "\n".join(lines[end + 1 :])
    return header, body


_ACHIEVEMENTS_HEADING = "## Achievements"


def _render_achievement_block(heading: str, entry: FoldedEntry) -> str:
    lines = [f"### {heading}", entry.body.strip()]
    if entry.impact:
        lines.append(f"**Impact:** {entry.impact}")
    if entry.lessons:
        lines.append(f"**Lessons:** {entry.lessons}")
    return "\n".join(lines)


def _insert_achievement_block(body: str, block: str) -> str:
    if _ACHIEVEMENTS_HEADING not in body:
        raise ValueError(f"note has no `{_ACHIEVEMENTS_HEADING}` section to fold into")

    start = body.index(_ACHIEVEMENTS_HEADING) + len(_ACHIEVEMENTS_HEADING)
    next_heading = body.find("\n## ", start)
    end = next_heading if next_heading != -1 else len(body)

    existing = body[start:end].strip("\n")
    new_section = f"\n{existing}\n\n{block}\n" if existing else f"\n{block}\n"
    return body[:start] + new_section + body[end:]


def _append_achievement(vault_path: Path, note: Note, entry: FoldedEntry) -> None:
    path = _note_path(vault_path, note)
    header, body = _split_frontmatter_block(path.read_text())
    block = _render_achievement_block(entry.heading, entry)
    path.write_text(header + _insert_achievement_block(body, block))


def _replace_achievement_block(body: str, heading_slug: str, block: str) -> str:
    lines = body.split("\n")
    start = next(
        (
            i
            for i, line in enumerate(lines)
            if line.startswith("### ") and slugify(line.removeprefix("### ")) == heading_slug
        ),
        None,
    )
    if start is None:
        raise ValueError(f"no existing achievement matches heading slug {heading_slug!r}")

    end = start + 1
    while (
        end < len(lines) and not lines[end].startswith("## ") and not lines[end].startswith("### ")
    ):
        end += 1

    # Trim trailing blank lines from the consumed span so the separator
    # before whatever follows (next achievement, next section, EOF) survives.
    content_end = end
    while content_end > start + 1 and lines[content_end - 1].strip() == "":
        content_end -= 1

    return "\n".join([*lines[:start], *block.split("\n"), *lines[content_end:]])


def _update_achievement(vault_path: Path, note: Note, entry: FoldedEntry) -> None:
    assert entry.existing_heading_slug is not None
    original = next((a for a in note.achievements if a.slug == entry.existing_heading_slug), None)
    if original is None:
        raise ValueError(
            f"note {note.slug!r} has no achievement matching {entry.existing_heading_slug!r}"
        )

    path = _note_path(vault_path, note)
    header, body = _split_frontmatter_block(path.read_text())
    block = _render_achievement_block(original.heading, entry)
    path.write_text(header + _replace_achievement_block(body, entry.existing_heading_slug, block))


def _unique_slug(directory: Path, base_slug: str) -> str:
    if not (directory / f"{base_slug}.md").exists():
        return base_slug
    suffix = 2
    while (directory / f"{base_slug}-{suffix}.md").exists():
        suffix += 1
    return f"{base_slug}-{suffix}"


def _create_story(vault_path: Path, entry: FoldedEntry, *, roles: list[str]) -> str:
    stories_dir = vault_path / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    slug = _unique_slug(stories_dir, slugify(entry.heading))

    frontmatter = (
        "---\n"
        "type: story\n"
        f"competencies: [{', '.join(entry.competencies)}]\n"
        f"roles: [{', '.join(roles)}]\n"
        "---\n"
    )
    (stories_dir / f"{slug}.md").write_text(frontmatter + entry.body.strip() + "\n")
    return slug


_SKILLS_FIELD_PREFIX = "skills:"


def _add_skills_to_frontmatter(header: str, new_slugs: list[str]) -> tuple[str, list[str]]:
    """Append any `new_slugs` missing from the note's `skills:` list, leaving
    every other frontmatter line untouched. Returns the (possibly) updated
    header and the slugs that were actually new to this note."""
    lines = header.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith(_SKILLS_FIELD_PREFIX):
            continue
        value = line.removeprefix(_SKILLS_FIELD_PREFIX).strip().removeprefix("[").removesuffix("]")
        existing = [s.strip() for s in value.split(",") if s.strip()]
        added = [s for s in new_slugs if s not in existing]
        if not added:
            return header, []
        lines[i] = f"skills: [{', '.join([*existing, *added])}]"
        return "\n".join(lines), added
    return header, []


def _skills_registry(skills_body: str) -> dict[str, str]:
    """slug -> category heading, scanning every `## `-headed section except
    `## Pinned` (a curated subset, not a category of its own)."""
    registry: dict[str, str] = {}
    category: str | None = None
    for line in skills_body.split("\n"):
        if line.startswith("## "):
            category = line.removeprefix("## ").strip()
            continue
        if category is not None and category != "Pinned" and line.strip().startswith("- "):
            slug = line.strip().removeprefix("- ").strip()
            registry.setdefault(slug, category)
    return registry


def _add_skill_to_inventory(skills_body: str, category: str, slug: str) -> str:
    heading = f"## {category}"
    lines = skills_body.split("\n")
    if heading not in lines:
        while lines and lines[-1] == "":
            lines.pop()
        if lines:
            lines.append("")
        lines.append(heading)
        lines.append(f"- {slug}")
        lines.append("")
        return "\n".join(lines)

    start = lines.index(heading)
    end = start + 1
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    insert_at = end
    while insert_at > start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    lines.insert(insert_at, f"- {slug}")
    return "\n".join(lines)


def _resolve_skill_category(registry: dict[str, str], hint: str | None) -> str:
    if hint is not None:
        for category in set(registry.values()):
            if category.lower() == hint.strip().lower():
                return category
    return "Other"


def _propagate_skills(
    vault_path: Path, note: Note, skill_slugs: list[str], category_hint: str | None
) -> int:
    """Add any skills unknown to `note`'s frontmatter, and any skills unknown
    to the registry to `skills.md`. Returns the count of registry additions."""
    note_path = _note_path(vault_path, note)
    header, body = _split_frontmatter_block(note_path.read_text())
    new_header, _ = _add_skills_to_frontmatter(header, skill_slugs)
    if new_header != header:
        note_path.write_text(new_header + body)

    skills_path = vault_path / "skills.md"
    if not skills_path.exists():
        return 0

    skills_text = skills_path.read_text()
    registry = _skills_registry(skills_text)
    added = 0
    for slug in skill_slugs:
        if slug in registry:
            continue
        category = _resolve_skill_category(registry, category_hint)
        skills_text = _add_skill_to_inventory(skills_text, category, slug)
        registry[slug] = category
        added += 1

    if added:
        skills_path.write_text(skills_text)
    return added
