"""Per-machine settings, per ADR-0005: the vault path alone, sourced from `VAULT_PATH`."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """The core facade's single settings surface: where the Experience Store vault lives."""

    vault_path: Path


def get_settings() -> Settings:
    # vault_path is populated from VAULT_PATH, not the constructor -
    # pyright's pydantic-derived `__init__` can't see that.
    return Settings()  # pyright: ignore[reportCallIssue]
