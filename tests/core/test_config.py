import os
from pathlib import Path

import pytest

from assistant.core.config import Settings, get_settings


def _load_settings() -> Settings:
    # vault_path is populated from env/config.toml, not the constructor -
    # pyright's pydantic-derived `__init__` can't see that.
    return Settings()  # pyright: ignore[reportCallIssue]


def _write_toml(path: Path, **fields: object) -> Path:
    lines: list[str] = []
    for key, value in fields.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        else:
            lines.append(f"{key} = {value}")
    path.write_text("\n".join(lines) + "\n")
    return path


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.toml"
    monkeypatch.setenv("PA_CONFIG_FILE", str(path))
    monkeypatch.delenv("VAULT_PATH", raising=False)
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return path


def test_code_defaults_apply_when_nothing_else_is_set(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULT_PATH", "/vault")

    settings = _load_settings()

    assert settings.default_model == "anthropic:claude-sonnet-5"
    assert settings.output_dir == Path.home() / "pa-output"


def test_config_file_overrides_code_defaults(config_file: Path) -> None:
    _write_toml(config_file, vault_path="/from-toml", default_model="openai:gpt-5")

    settings = _load_settings()

    assert settings.vault_path == Path("/from-toml")
    assert settings.default_model == "openai:gpt-5"


def test_dotenv_overrides_config_file(config_file: Path, tmp_path: Path) -> None:
    _write_toml(config_file, vault_path="/from-toml", default_model="openai:gpt-5")
    (tmp_path / ".env").write_text("DEFAULT_MODEL=gemini:gemini-3-flash\n")

    settings = _load_settings()

    assert settings.vault_path == Path("/from-toml")
    assert settings.default_model == "gemini:gemini-3-flash"


def test_env_overrides_dotenv_and_config_file(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(config_file, vault_path="/from-toml", default_model="openai:gpt-5")
    (tmp_path / ".env").write_text("DEFAULT_MODEL=gemini:gemini-3-flash\n")
    monkeypatch.setenv("DEFAULT_MODEL", "anthropic:claude-opus-4-8")

    settings = _load_settings()

    assert settings.default_model == "anthropic:claude-opus-4-8"


def test_secret_in_config_file_is_never_read(config_file: Path) -> None:
    _write_toml(config_file, vault_path="/from-toml", anthropic_api_key="leaked-from-toml")

    settings = _load_settings()

    assert settings.anthropic_api_key is None


def test_secret_from_env_is_read_even_when_config_file_sets_it(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(config_file, vault_path="/from-toml", anthropic_api_key="leaked-from-toml")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-secret")

    settings = _load_settings()

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "real-secret"


def test_secret_from_dotenv_alone_is_read(config_file: Path, tmp_path: Path) -> None:
    _write_toml(config_file, vault_path="/from-toml")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=from-dotenv-secret\n")

    settings = _load_settings()

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "from-dotenv-secret"


def test_get_settings_bridges_a_dotenv_only_secret_into_the_process_environment(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(config_file, vault_path="/from-toml")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=from-dotenv-secret\n")

    get_settings()

    assert os.environ["ANTHROPIC_API_KEY"] == "from-dotenv-secret"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_get_settings_never_overwrites_a_real_env_secret(
    config_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_toml(config_file, vault_path="/from-toml")
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=from-dotenv-secret\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "real-env-secret")

    get_settings()

    assert os.environ["ANTHROPIC_API_KEY"] == "real-env-secret"


def test_missing_config_file_falls_back_to_defaults(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VAULT_PATH", "/vault")

    settings = _load_settings()

    assert settings.vault_path == Path("/vault")
