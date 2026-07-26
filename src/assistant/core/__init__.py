"""The core facade's public API - the only surface modules may import from.

Per ADR-0002: modules import only from here; core never imports from modules
except the single CLI-mounting line in `assistant.cli`.
"""

from assistant.core.agents import create_agent, usage_limits
from assistant.core.config import Settings, get_settings
from assistant.core.journal.capture import JournalEntry, add_entry, list_entries
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
    "JournalEntry",
    "Note",
    "NoteType",
    "ProvenanceReason",
    "ProvenanceResult",
    "Settings",
    "add_entry",
    "create_agent",
    "get_settings",
    "list_entries",
    "load_store",
    "usage_limits",
    "validate_provenance",
]
