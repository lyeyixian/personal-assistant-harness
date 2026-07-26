from pathlib import Path

import pytest

FIXTURE_VAULT_PATH = Path(__file__).parent / "fixtures" / "vault"


@pytest.fixture
def fixture_vault_path() -> Path:
    """The fictional Experience Store vault every offline test reads against."""
    return FIXTURE_VAULT_PATH
