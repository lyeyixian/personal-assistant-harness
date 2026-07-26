"""The Experience Store document model, per the store schema spec.

A `Note` is the unit of the vault (role/project/story note, or one of the
singleton `profile.md`/`direction.md`/`skills.md` files); an `Achievement` is
a mini-arc subsection inside a role or project note's `## Achievements`
section. Both are read-only views over the vault - the write path (the Fold)
is out of scope for this ticket.
"""

from dataclasses import dataclass
from typing import Any, Literal

NoteType = Literal["profile", "direction", "skills", "role", "project", "story"]


@dataclass(frozen=True, slots=True)
class Achievement:
    """One `###` mini-arc subsection inside a note's `## Achievements` section."""

    heading: str
    slug: str
    body: str


@dataclass(frozen=True, slots=True)
class Note:
    """One vault file: a role/project/story note, or a singleton like `profile.md`."""

    slug: str
    type: NoteType
    frontmatter: dict[str, Any]
    body: str
    achievements: tuple[Achievement, ...]


@dataclass(frozen=True, slots=True)
class ExperienceStore:
    """The curated corpus: every note the retrieval contract allows into context.

    Journal and `jobs/` are excluded at load time (`load_store`), never
    filtered here - this type can only ever hold what full-context reads are
    allowed to see.
    """

    notes: tuple[Note, ...]

    def note(self, slug: str) -> Note | None:
        return next((note for note in self.notes if note.slug == slug), None)
