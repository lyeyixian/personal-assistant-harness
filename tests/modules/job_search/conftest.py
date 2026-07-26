from pathlib import Path

import pytest

from assistant.core import ExperienceStore, load_store


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated vault + config for `pa jobs` CLI tests: no ambient machine state."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PA_CONFIG_FILE", str(tmp_path / "unwritten-config.toml"))
    vault = tmp_path / "vault"
    monkeypatch.setenv("VAULT_PATH", str(vault))
    for env_var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(env_var, raising=False)
    return vault


@pytest.fixture
def store(fixture_vault_path: Path) -> ExperienceStore:
    """The fictional vault, loaded - what every offline resume test reads against."""
    return load_store(fixture_vault_path)
