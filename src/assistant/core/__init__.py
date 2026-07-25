"""The core facade's public API - the only surface modules may import from.

Per ADR-0002: modules import only from here; core never imports from modules
except the single CLI-mounting line in `assistant.cli`.
"""

from assistant.core.agents import create_agent, usage_limits
from assistant.core.config import Settings, get_settings

__all__ = [
    "Settings",
    "create_agent",
    "get_settings",
    "usage_limits",
]
