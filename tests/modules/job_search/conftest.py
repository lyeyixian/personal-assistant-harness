from pathlib import Path

import pytest


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
