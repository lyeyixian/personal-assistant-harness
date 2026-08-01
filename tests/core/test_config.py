from pathlib import Path

import pytest
from pydantic import ValidationError

from assistant.core.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAULT_PATH", raising=False)


def test_vault_path_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VAULT_PATH", "/vault")

    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.vault_path == Path("/vault")


def test_missing_vault_path_raises() -> None:
    with pytest.raises(ValidationError):
        Settings()  # pyright: ignore[reportCallIssue]
