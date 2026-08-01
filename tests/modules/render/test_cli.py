from pathlib import Path

import pytest
from typer.testing import CliRunner

from assistant.cli import app
from tests.modules.render._helpers import make_resume_content, write_resume_yaml

runner = CliRunner()


@pytest.fixture(autouse=True)
def no_ambient_vault_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test relies on whatever VAULT_PATH happens to be set on the machine."""
    monkeypatch.delenv("VAULT_PATH", raising=False)


class TestRenderCommand:
    def test_a_valid_yaml_writes_the_pdf_and_exits_zero(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(tmp_path, make_resume_content())

        result = runner.invoke(
            app, ["render", str(tmp_path), "--vault-path", str(fixture_vault_path)]
        )

        assert result.exit_code == 0, result.output
        assert (tmp_path / "resume.pdf").read_bytes().startswith(b"%PDF")

    def test_reports_where_the_pdf_landed(self, tmp_path: Path, fixture_vault_path: Path) -> None:
        write_resume_yaml(tmp_path, make_resume_content())

        result = runner.invoke(
            app, ["render", str(tmp_path), "--vault-path", str(fixture_vault_path)]
        )

        assert "resume.pdf" in result.output

    def test_vault_path_env_var_is_used_when_no_flag_is_given(
        self, tmp_path: Path, fixture_vault_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VAULT_PATH", str(fixture_vault_path))
        write_resume_yaml(tmp_path, make_resume_content())

        result = runner.invoke(app, ["render", str(tmp_path)])

        assert result.exit_code == 0, result.output

    def test_the_flag_overrides_the_env_var(
        self, tmp_path: Path, fixture_vault_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VAULT_PATH", str(tmp_path / "not-a-vault"))
        write_resume_yaml(tmp_path, make_resume_content())

        result = runner.invoke(
            app, ["render", str(tmp_path), "--vault-path", str(fixture_vault_path)]
        )

        assert result.exit_code == 0, result.output

    def test_no_vault_path_anywhere_fails_legibly(self, tmp_path: Path) -> None:
        write_resume_yaml(tmp_path, make_resume_content())

        result = runner.invoke(app, ["render", str(tmp_path)])

        assert result.exit_code != 0
        assert "VAULT_PATH" in result.output

    def test_a_missing_directory_fails(self, fixture_vault_path: Path) -> None:
        result = runner.invoke(
            app, ["render", "/no/such/directory", "--vault-path", str(fixture_vault_path)]
        )

        assert result.exit_code != 0

    def test_a_shape_gate_failure_exits_nonzero_and_writes_no_pdf(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(tmp_path, {"market": "sg"})

        result = runner.invoke(
            app, ["render", str(tmp_path), "--vault-path", str(fixture_vault_path)]
        )

        assert result.exit_code != 0
        assert "shape gate" in result.output
        assert not (tmp_path / "resume.pdf").exists()

    def test_a_provenance_gate_failure_names_the_ref_and_writes_no_pdf(
        self, tmp_path: Path, fixture_vault_path: Path
    ) -> None:
        write_resume_yaml(
            tmp_path,
            make_resume_content(experience_source="acme-payments-rotation#invented-win"),
        )

        result = runner.invoke(
            app, ["render", str(tmp_path), "--vault-path", str(fixture_vault_path)]
        )

        assert result.exit_code != 0
        assert "acme-payments-rotation#invented-win" in result.output
        assert not (tmp_path / "resume.pdf").exists()
