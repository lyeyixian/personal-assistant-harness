from typer.testing import CliRunner

from assistant.cli import app

runner = CliRunner()


def test_help_runs_without_a_vault_path_or_api_key() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
