"""Per-machine settings, per ADR-0002: env -> .env -> config.toml -> defaults.

Secrets (API keys) are only ever sourced from env/.env - `config.toml` is
always safe to back up or commit. `_SecretSafeTomlSource` enforces that by
dropping any `SecretStr` field from what the config file is allowed to supply,
regardless of what the file actually contains.
"""

import os
from pathlib import Path
from typing import Any, get_args

from pydantic import SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

DEFAULT_CONFIG_FILE = Path.home() / ".config" / "pa" / "config.toml"


def config_file_path() -> Path:
    """The config.toml location, overridable via PA_CONFIG_FILE (tests, alt machines)."""
    override = os.environ.get("PA_CONFIG_FILE")
    return Path(override).expanduser() if override else DEFAULT_CONFIG_FILE


def _secret_field_names(settings_cls: type[BaseSettings]) -> set[str]:
    names: set[str] = set()
    for name, field in settings_cls.model_fields.items():
        annotation_args = get_args(field.annotation)
        candidate_types = annotation_args if annotation_args else (field.annotation,)
        if SecretStr in candidate_types:
            names.add(name)
    return names


class _SecretSafeTomlSource(TomlConfigSettingsSource):
    """A TOML source that never surfaces `SecretStr` fields, however the file spells them."""

    def __call__(self) -> dict[str, Any]:
        data = super().__call__()
        secret_fields = _secret_field_names(self.settings_cls)
        return {key: value for key, value in data.items() if key not in secret_fields}


class Settings(BaseSettings):
    """The core facade's single settings surface; modules nest their own config models."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # `pa init` prompts (durable, config.toml-backed)
    vault_path: Path
    default_model: str = "anthropic:claude-sonnet-5"
    output_dir: Path = Path.home() / "pa-output"

    # Agent factory knobs
    agent_retries: int = 3
    usage_request_limit: int | None = 50
    usage_total_tokens_limit: int | None = None

    # Secrets - env/.env only, never config.toml (enforced by _SecretSafeTomlSource below)
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_source = _SecretSafeTomlSource(settings_cls, toml_file=config_file_path())
        return (init_settings, env_settings, dotenv_settings, toml_source)


def export_secrets_to_environ(settings: Settings) -> None:
    """Put resolved secrets into the process environment for libraries that read it directly.

    Pydantic AI's provider classes (`AnthropicProvider`, etc.) read API keys from
    `os.environ` themselves rather than through `Settings` - this bridges a key that
    only came from `.env` (never real env) into `os.environ` so those providers still
    find it. Never overwrites a key already present in the real environment.
    """
    for env_var, secret in (
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ("OPENAI_API_KEY", settings.openai_api_key),
        ("GEMINI_API_KEY", settings.gemini_api_key),
    ):
        if secret is not None and env_var not in os.environ:
            os.environ[env_var] = secret.get_secret_value()


def get_settings() -> Settings:
    """Load Settings and bridge its secrets into the process environment."""
    # vault_path is populated from env/config.toml, not the constructor -
    # pyright's pydantic-derived `__init__` can't see that.
    settings = Settings()  # pyright: ignore[reportCallIssue]
    export_secrets_to_environ(settings)
    return settings
