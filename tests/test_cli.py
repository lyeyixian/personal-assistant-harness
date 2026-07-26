from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from assistant.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / "config.toml"
    monkeypatch.setenv("PA_CONFIG_FILE", str(config_path))
    return config_path


@pytest.fixture
def vault_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "vault"
    monkeypatch.setenv("VAULT_PATH", str(path))
    return path


def test_help_shows_the_command_surface() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output


def test_mounting_a_module_sub_app_is_one_line() -> None:
    dummy = typer.Typer()

    @dummy.command()
    def add() -> None:  # pyright: ignore[reportUnusedFunction] -- registered via the decorator, never called directly
        pass

    app.add_typer(dummy, name="dummy-module")
    try:
        result = runner.invoke(app, ["--help"])
    finally:
        app.registered_groups.pop()

    assert "dummy-module" in result.output


def test_init_writes_config_file(isolated_config: Path) -> None:
    result = runner.invoke(app, ["init"], input="/my/vault\n\n\n")

    assert result.exit_code == 0, result.output
    assert isolated_config.exists()
    content = isolated_config.read_text()
    assert 'vault_path = "/my/vault"' in content
    assert "default_model" in content
    assert "output_dir" in content


def test_init_prompts_before_overwriting_an_existing_config(isolated_config: Path) -> None:
    isolated_config.write_text('vault_path = "/old"\n')

    result = runner.invoke(app, ["init"], input="n\n")

    assert result.exit_code == 0
    assert isolated_config.read_text() == 'vault_path = "/old"\n'


def test_init_overwrites_when_confirmed(isolated_config: Path) -> None:
    isolated_config.write_text('vault_path = "/old"\n')

    result = runner.invoke(app, ["init"], input="y\n/new/vault\n\n\n")

    assert result.exit_code == 0, result.output
    assert 'vault_path = "/new/vault"' in isolated_config.read_text()


def test_journal_add_creates_todays_file(vault_path: Path) -> None:
    result = runner.invoke(app, ["journal", "add", "shipped the thing"])

    assert result.exit_code == 0, result.output
    journal_files = list((vault_path / "journal").glob("*.md"))
    assert len(journal_files) == 1
    assert "shipped the thing" in journal_files[0].read_text()


def test_journal_list_shows_an_added_entry(vault_path: Path) -> None:
    runner.invoke(app, ["journal", "add", "shipped the thing"])

    result = runner.invoke(app, ["journal", "list"])

    assert result.exit_code == 0, result.output
    assert "shipped the thing" in result.output
    assert "pending" in result.output


def test_journal_list_reports_when_empty(vault_path: Path) -> None:
    result = runner.invoke(app, ["journal", "list"])

    assert result.exit_code == 0, result.output
    assert "No journal entries" in result.output
