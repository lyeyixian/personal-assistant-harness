"""The Fold agent's typed I/O - shared between `fold.py` (the pipeline) and
`fold_writer.py` (the deterministic note-writing helpers) so neither imports
the other.
"""

from typing import Literal

from pydantic import BaseModel, Field


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
