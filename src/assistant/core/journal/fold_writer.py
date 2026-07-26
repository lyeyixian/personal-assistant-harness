"""Deterministic note-writing for the Fold: splices a `FoldedEntry`'s content
into the vault's markdown, preserving everything else in each file byte for
byte - frontmatter is edited via targeted regex/line surgery, never a full
YAML re-serialization, and body edits touch only the achievement (or
skills.md section) being written, so the human's `git diff` stays minimal.
"""

from pathlib import Path

from assistant.core.journal.fold_types import FoldedEntry
from assistant.core.store.loader import note_path
from assistant.core.store.models import Note
from assistant.core.store.parser import slugify

_ACHIEVEMENTS_HEADING = "## Achievements"
_SKILLS_FIELD_PREFIX = "skills:"


def _split_frontmatter_block(text: str) -> tuple[str, str]:
    """Split raw note text into its exact frontmatter block (fences included)
    and body, without going through YAML parsing - keeps every byte of the
    frontmatter untouched by body edits, and vice versa for `header` edits."""
    lines = text.split("\n")
    if lines[0] != "---":
        raise ValueError("note is missing its opening frontmatter fence (`---`)")
    end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    header = "\n".join(lines[: end + 1]) + "\n"
    body = "\n".join(lines[end + 1 :])
    return header, body


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


def append_achievement(vault_path: Path, note: Note, entry: FoldedEntry) -> None:
    path = note_path(vault_path, note)
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


def update_achievement(vault_path: Path, note: Note, entry: FoldedEntry) -> None:
    assert entry.existing_heading_slug is not None
    original = next((a for a in note.achievements if a.slug == entry.existing_heading_slug), None)
    if original is None:
        raise ValueError(
            f"note {note.slug!r} has no achievement matching {entry.existing_heading_slug!r}"
        )

    path = note_path(vault_path, note)
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


def create_story(vault_path: Path, entry: FoldedEntry, *, roles: list[str]) -> str:
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


def _add_skills_to_frontmatter(header: str, new_slugs: list[str]) -> str:
    """Append any `new_slugs` missing from the note's `skills:` list, leaving
    every other frontmatter line untouched."""
    lines = header.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith(_SKILLS_FIELD_PREFIX):
            continue
        value = line.removeprefix(_SKILLS_FIELD_PREFIX).strip().removeprefix("[").removesuffix("]")
        existing = [s.strip() for s in value.split(",") if s.strip()]
        added = [s for s in new_slugs if s not in existing]
        if not added:
            return header
        lines[i] = f"skills: [{', '.join([*existing, *added])}]"
        return "\n".join(lines)
    return header


def skills_registry(skills_body: str) -> dict[str, str]:
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


def propagate_skills(
    vault_path: Path, note: Note, skill_slugs: list[str], category_hint: str | None
) -> int:
    """Add any skills unknown to `note`'s frontmatter, and any skills unknown
    to the registry to `skills.md`. Returns the count of registry additions -
    skills already known to the registry but new to this note's frontmatter
    don't count, since the registry (not any one note) is the source of
    truth for "is this a new skill"."""
    path = note_path(vault_path, note)
    header, body = _split_frontmatter_block(path.read_text())
    new_header = _add_skills_to_frontmatter(header, skill_slugs)
    if new_header != header:
        path.write_text(new_header + body)

    skills_path = vault_path / "skills.md"
    if not skills_path.exists():
        return 0

    skills_text = skills_path.read_text()
    registry = skills_registry(skills_text)
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
