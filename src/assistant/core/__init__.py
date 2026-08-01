"""The core facade's public API - the only surface modules may import from.

Per ADR-0002: modules import only from here; core never imports from modules
except the single CLI-mounting line in `assistant.cli`.
"""

from assistant.core.config import Settings, get_settings
from assistant.core.store import (
    Achievement,
    ExperienceStore,
    Note,
    NoteType,
    ProvenanceReason,
    ProvenanceResult,
    load_store,
    validate_provenance,
)

__all__ = [
    "Achievement",
    "ExperienceStore",
    "Note",
    "NoteType",
    "ProvenanceReason",
    "ProvenanceResult",
    "Settings",
    "get_settings",
    "load_store",
    "validate_provenance",
]
