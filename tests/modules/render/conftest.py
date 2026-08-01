from pathlib import Path

import pytest

from assistant.core import ExperienceStore, load_store


@pytest.fixture
def store(fixture_vault_path: Path) -> ExperienceStore:
    """The fictional vault, loaded - what every offline render test reads against."""
    return load_store(fixture_vault_path)
