"""Corpus assembly: read the curated Experience Store vault into an
`ExperienceStore`, per the retrieval contract - journal and `jobs/` are never
read, not merely filtered afterwards.
"""

from pathlib import Path

from assistant.core.store.models import ExperienceStore, Note, NoteType
from assistant.core.store.parser import parse_achievements, parse_frontmatter

_SINGLETON_FILES: dict[str, NoteType] = {
    "profile.md": "profile",
    "direction.md": "direction",
    "skills.md": "skills",
}
_NOTE_DIRECTORIES: dict[str, NoteType] = {
    "roles": "role",
    "projects": "project",
    "stories": "story",
}


def _load_note(path: Path, note_type: NoteType) -> Note:
    frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Note(
        slug=path.stem,
        type=note_type,
        frontmatter=frontmatter,
        body=body,
        achievements=parse_achievements(body),
    )


def load_store(vault_path: Path) -> ExperienceStore:
    """Load every curated note in `vault_path` - the whole corpus, full-context.

    `journal/` and `jobs/` are outside the retrieval contract and are never
    listed or opened.
    """
    notes: list[Note] = []

    for filename, note_type in _SINGLETON_FILES.items():
        path = vault_path / filename
        if path.exists():
            notes.append(_load_note(path, note_type))

    for dirname, note_type in _NOTE_DIRECTORIES.items():
        directory = vault_path / dirname
        if directory.exists():
            for path in sorted(directory.glob("*.md")):
                notes.append(_load_note(path, note_type))

    return ExperienceStore(notes=tuple(notes))
