"""Per-machine settings, per ADR-0005: the vault path alone, sourced from `VAULT_PATH`."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """The core facade's single settings surface: where the Experience Store vault lives."""

    vault_path: Path


def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
