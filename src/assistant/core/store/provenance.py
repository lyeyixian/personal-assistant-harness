"""The shared deterministic provenance validator - the honesty gate both the
fit-analysis and resume-generation features reuse (per the schema spec's
retrieval contract and ADR-0002). Resolves a `<note-slug>#<achievement-heading>`
ref against the vault; never calls an LLM.
"""

from dataclasses import dataclass
from typing import Literal

from assistant.core.store.models import ExperienceStore

ProvenanceReason = Literal["malformed-ref", "unknown-note", "unknown-heading"]


@dataclass(frozen=True, slots=True)
class ProvenanceResult:
    ref: str
    valid: bool
    reason: ProvenanceReason | None = None


def validate_provenance(store: ExperienceStore, ref: str) -> ProvenanceResult:
    """Check that `ref` resolves to a real note and achievement heading."""
    if "#" not in ref:
        return ProvenanceResult(ref=ref, valid=False, reason="malformed-ref")

    note_slug, _, heading_slug = ref.partition("#")
    note = store.note(note_slug)
    if note is None:
        return ProvenanceResult(ref=ref, valid=False, reason="unknown-note")

    if not any(achievement.slug == heading_slug for achievement in note.achievements):
        return ProvenanceResult(ref=ref, valid=False, reason="unknown-heading")

    return ProvenanceResult(ref=ref, valid=True)
