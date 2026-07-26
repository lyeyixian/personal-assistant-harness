from pathlib import Path

import pytest
import typer
import yaml
from typer.testing import CliRunner

from assistant.modules.job_search.cli import (
    _read_posting_text,  # pyright: ignore[reportPrivateUsage]
    app,
)

runner = CliRunner()

POSTING_TEXT = "AI Engineer at Anthropic\n\nRequirements:\n- 5+ years of Python\n"


class TestAddFromFile:
    def test_prints_the_minted_slug(self, tmp_path: Path) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        result = runner.invoke(app, ["add", str(posting_file)])

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "anthropic-ai-engineer"

    def test_writes_a_job_note_with_verbatim_body(
        self, tmp_path: Path, isolated_settings: Path
    ) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        runner.invoke(app, ["add", str(posting_file)])

        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        _, _, body = note.partition("---\n")
        _, _, body = body.partition("---\n")
        assert body == POSTING_TEXT

    def test_market_override_is_stored_in_frontmatter(
        self, tmp_path: Path, isolated_settings: Path
    ) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        result = runner.invoke(app, ["add", str(posting_file), "--market", "sg"])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "market: sg" in note

    def test_url_is_stored_as_metadata_only(self, tmp_path: Path, isolated_settings: Path) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        result = runner.invoke(app, ["add", str(posting_file), "--url", "https://example.com/job"])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "url: https://example.com/job" in note
        _, _, body = note.partition("---\n")
        _, _, body = body.partition("---\n")
        assert body == POSTING_TEXT

    def test_missing_file_fails_with_a_clear_error(self) -> None:
        result = runner.invoke(app, ["add", "does-not-exist.txt"])

        assert result.exit_code != 0


class TestAddFromStdin:
    def test_reads_piped_stdin_when_no_file_given(self) -> None:
        result = runner.invoke(app, ["add"], input=POSTING_TEXT)

        assert result.exit_code == 0, result.output
        assert result.output.strip() == "anthropic-ai-engineer"


class TestReadPostingTextEditorIntake:
    def test_opens_editor_when_no_file_and_stdin_is_a_tty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_edit(text: str | None) -> str | None:
            return POSTING_TEXT

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("assistant.modules.job_search.cli.click.edit", fake_edit)

        assert _read_posting_text(None) == POSTING_TEXT

    def test_aborts_when_editor_is_closed_without_saving(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_edit(text: str | None) -> str | None:
            return None

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("assistant.modules.job_search.cli.click.edit", fake_edit)

        with pytest.raises(typer.BadParameter):
            _read_posting_text(None)


class TestListJobs:
    def test_reports_when_no_postings_captured(self) -> None:
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, result.output
        assert "No job postings" in result.output

    def test_renders_frontmatter_columns_for_each_note(self, isolated_settings: Path) -> None:
        jobs_dir = isolated_settings / "jobs"
        jobs_dir.mkdir(parents=True)
        frontmatter = {
            "type": "job",
            "company": "Anthropic",
            "title": "AI Engineer",
            "market": "remote",
            "url": None,
            "captured": "2026-07-19",
            "verdict": "strong-fit",
            "direction": "aligned",
            "analyzed": "2026-07-20",
        }
        (jobs_dir / "anthropic-ai-engineer.md").write_text(
            f"---\n{yaml.safe_dump(frontmatter, sort_keys=False)}---\nposting body\n"
        )

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0, result.output
        assert "Anthropic" in result.output
        assert "AI Engineer" in result.output
        assert "strong-fit" in result.output
        assert "aligned" in result.output
        assert "2026-07-20" in result.output
