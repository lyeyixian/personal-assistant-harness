from pathlib import Path

import pytest
import typer
import yaml
from pydantic_ai import Agent
from typer.testing import CliRunner

from assistant.core import ExperienceStore, Settings
from assistant.modules.job_search.agents import ResumeDeps, generate_resume_content
from assistant.modules.job_search.cli import (
    _read_posting_text,  # pyright: ignore[reportPrivateUsage]
    app,
)
from assistant.modules.job_search.models import JobPosting, ResumeContent
from tests.modules.job_search._helpers import job_note_body, make_resume_content, stub_resume_agent


def stub_agent(monkeypatch: pytest.MonkeyPatch, content: ResumeContent) -> None:
    """Point the CLI's agent factory at a stub model that always returns `content`."""

    def factory(settings: Settings) -> Agent[ResumeDeps, ResumeContent]:
        return stub_resume_agent(content)

    monkeypatch.setattr("assistant.modules.job_search.cli.create_resume_agent", factory)


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
        assert job_note_body(note) == POSTING_TEXT

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
        assert job_note_body(note) == POSTING_TEXT

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


class TestResume:
    @pytest.fixture(autouse=True)
    def resume_environment(
        self, tmp_path: Path, fixture_vault_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Path:
        """The fixture vault as the store, a throwaway directory as the output root."""
        monkeypatch.setenv("VAULT_PATH", str(fixture_vault_path))
        output_root = tmp_path / "pa-output"
        monkeypatch.setenv("OUTPUT_DIR", str(output_root))
        return output_root

    @pytest.fixture
    def posting_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "posting.txt"
        path.write_text("AI Engineer at Anthropic\n\nRequirements:\n- 5+ years of Python\n")
        return path

    @pytest.fixture(autouse=True)
    def offline_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stub_agent(monkeypatch, make_resume_content())

    @pytest.fixture
    def recorded_postings(self, monkeypatch: pytest.MonkeyPatch) -> list[JobPosting]:
        """The postings the CLI actually handed the agent."""
        postings: list[JobPosting] = []

        def spy(
            agent: Agent[ResumeDeps, ResumeContent],
            *,
            store: ExperienceStore,
            posting: JobPosting,
            settings: Settings,
        ) -> ResumeContent:
            postings.append(posting)
            return generate_resume_content(agent, store=store, posting=posting, settings=settings)

        monkeypatch.setattr("assistant.modules.job_search.cli.generate_resume_content", spy)
        return postings

    def test_one_run_writes_yaml_and_pdf_under_the_output_root(
        self, posting_file: Path, resume_environment: Path
    ) -> None:
        result = runner.invoke(app, ["resume", str(posting_file)])

        assert result.exit_code == 0, result.output
        directory = resume_environment / "anthropic-ai-engineer"
        assert (directory / "resume.yaml").exists()
        assert (directory / "resume.pdf").read_bytes().startswith(b"%PDF")

    def test_reports_where_the_artifacts_landed(
        self, posting_file: Path, resume_environment: Path
    ) -> None:
        result = runner.invoke(app, ["resume", str(posting_file)])

        assert "resume.yaml" in result.output
        assert "resume.pdf" in result.output

    def test_outputs_stay_outside_the_vault(
        self, posting_file: Path, fixture_vault_path: Path
    ) -> None:
        runner.invoke(app, ["resume", str(posting_file)])

        assert not list(fixture_vault_path.glob("**/resume.yaml"))

    def test_out_overrides_the_output_directory(self, posting_file: Path, tmp_path: Path) -> None:
        destination = tmp_path / "somewhere-else"

        result = runner.invoke(app, ["resume", str(posting_file), "--out", str(destination)])

        assert result.exit_code == 0, result.output
        assert (destination / "resume.pdf").exists()

    def test_market_override_reaches_the_agent(
        self, posting_file: Path, recorded_postings: list[JobPosting]
    ) -> None:
        result = runner.invoke(app, ["resume", str(posting_file), "--market", "sg"])

        assert result.exit_code == 0, result.output
        assert recorded_postings[0].market == "sg"

    def test_a_remote_posting_drops_the_work_authorization_line(
        self, posting_file: Path, resume_environment: Path
    ) -> None:
        result = runner.invoke(app, ["resume", str(posting_file), "--market", "remote"])

        assert result.exit_code == 0, result.output
        directory = resume_environment / "anthropic-ai-engineer"
        # The rendered toggle itself is covered at the render seam; what the CLI
        # owns is that the posting's market - not the model's - lands in the IR.
        assert yaml.safe_load((directory / "resume.yaml").read_text())["market"] == "remote"

    def test_a_second_run_overwrites_in_place(
        self, posting_file: Path, resume_environment: Path
    ) -> None:
        runner.invoke(app, ["resume", str(posting_file)])

        result = runner.invoke(app, ["resume", str(posting_file)])

        assert result.exit_code == 0, result.output
        directory = resume_environment / "anthropic-ai-engineer"
        assert sorted(path.name for path in directory.iterdir()) == ["resume.pdf", "resume.yaml"]

    def test_an_unresolvable_source_ref_fails_before_a_pdf_exists(
        self, posting_file: Path, resume_environment: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stub_agent(
            monkeypatch,
            make_resume_content(experience_source="acme-payments-rotation#invented-win"),
        )

        result = runner.invoke(app, ["resume", str(posting_file)])

        assert result.exit_code == 1
        assert "acme-payments-rotation#invented-win" in result.output
        assert not (resume_environment / "anthropic-ai-engineer" / "resume.pdf").exists()
