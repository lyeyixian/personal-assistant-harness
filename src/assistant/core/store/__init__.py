"""Experience Store I/O and document model - re-exported by `assistant.core`.

Per ADR-0002, modules should import from `assistant.core`, not this
subpackage directly; this file exists so the core facade has one place to
import the store's surface from.
"""

from assistant.core.store.loader import load_store, note_path
from assistant.core.store.models import Achievement, ExperienceStore, Note, NoteType
from assistant.core.store.provenance import ProvenanceReason, ProvenanceResult, validate_provenance

__all__ = [
    "Achievement",
    "ExperienceStore",
    "Note",
    "NoteType",
    "ProvenanceReason",
    "ProvenanceResult",
    "load_store",
    "note_path",
    "validate_provenance",
]
