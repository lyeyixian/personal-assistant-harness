import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from assistant.core.config import Settings

SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY")


@pytest.fixture
def make_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Settings]:
    """An isolated `Settings` factory: no real config.toml, .env, or ambient secrets."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PA_CONFIG_FILE", str(tmp_path / "unwritten-config.toml"))
    for env_var in SECRET_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    def _make(
        *,
        default_model: str = "test",
        agent_retries: int = 3,
        usage_request_limit: int | None = 50,
        usage_total_tokens_limit: int | None = None,
        vault_path: Path | None = None,
    ) -> Settings:
        return Settings(
            vault_path=vault_path if vault_path is not None else tmp_path / "vault",
            default_model=default_model,
            agent_retries=agent_retries,
            usage_request_limit=usage_request_limit,
            usage_total_tokens_limit=usage_total_tokens_limit,
        )

    return _make


@pytest.fixture
def fold_vault(tmp_path: Path, fixture_vault_path: Path) -> Path:
    """A writable copy of the fixture vault with an empty `journal/` - Fold
    tests populate their own pending entries rather than reusing the
    read-path fixtures' sentinel journal file."""
    vault_path = tmp_path / "vault"
    shutil.copytree(fixture_vault_path, vault_path)
    shutil.rmtree(vault_path / "journal")
    return vault_path
