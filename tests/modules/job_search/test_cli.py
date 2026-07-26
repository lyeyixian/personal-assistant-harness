import shutil
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
import typer
import yaml
from pydantic_ai.models.test import TestModel
from typer.testing import CliRunner

from assistant.core import ExperienceStore, Settings
from assistant.modules.job_search import cli as job_search_cli
from assistant.modules.job_search.cli import (
    _read_posting_text,  # pyright: ignore[reportPrivateUsage]
    app,
)
from assistant.modules.job_search.fit import FitAgents, create_fit_agents
from assistant.modules.job_search.models import (
    DirectionCheck,
    Evidence,
    FitReport,
    JobPosting,
    Requirement,
    RequirementGrade,
    RequirementSet,
    Verdict,
)
from tests.modules.job_search._helpers import job_note_body

runner = CliRunner()

POSTING_TEXT = "AI Engineer at Anthropic\n\nRequirements:\n- 5+ years of Python\n"

FIT_REPORT = FitReport(
    verdict=Verdict(tier="strong-fit", rationale="Great alignment across the board."),
    direction=DirectionCheck(axis="aligned", reasons="Matches direction.md target roles."),
    grades=[
        RequirementGrade(
            requirement=Requirement(
                text="5+ years of Python",
                kind="must-have",
                firmness="likely-flexible",
                firmness_reason="years-of-experience number",
                category="language",
            ),
            grade="met",
            evidence=[
                Evidence(
                    ref="acme-payments-rotation#partner-bank-onboarding-automation",
                    note="Built Python automation.",
                )
            ],
        ),
    ],
)


def _stub_agent_factory(monkeypatch: pytest.MonkeyPatch, agents: FitAgents) -> None:
    """Make `create_fit_agents` return one already-built `FitAgents`, so a
    test can `.override()` its models before the CLI command builds its own.
    """

    def fake_create_fit_agents(settings: Settings) -> FitAgents:
        return agents

    monkeypatch.setattr(job_search_cli, "create_fit_agents", fake_create_fit_agents)


def _stub_fit_pipeline(monkeypatch: pytest.MonkeyPatch, report: FitReport = FIT_REPORT) -> None:
    """Stub out the agent pipeline: `pa jobs fit` CLI tests are thin per the
    Testing Decisions - the pipeline itself is covered at its own seam in
    `test_fit.py`. Setting `DEFAULT_MODEL=test` keeps `create_fit_agents`
    (still called for real) from requiring a live provider API key.
    """
    monkeypatch.setenv("DEFAULT_MODEL", "test")

    async def fake_run_fit_analysis(
        agents: FitAgents,
        *,
        store: ExperienceStore,
        posting: JobPosting,
        posting_text: str,
        settings: Settings,
    ) -> FitReport:
        return report

    monkeypatch.setattr(job_search_cli, "run_fit_analysis", fake_run_fit_analysis)


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


class TestFitFromFile:
    def test_mints_the_note_then_writes_the_fit_section(
        self, tmp_path: Path, isolated_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fit_pipeline(monkeypatch)
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        result = runner.invoke(app, ["fit", str(posting_file)])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert POSTING_TEXT in note
        assert "## Fit analysis" in note
        assert "verdict: strong-fit" in note
        assert "direction: aligned" in note
        assert "analyzed:" in note

    def test_prints_the_report_to_the_terminal(
        self, tmp_path: Path, isolated_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fit_pipeline(monkeypatch)
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)

        result = runner.invoke(app, ["fit", str(posting_file)])

        assert result.exit_code == 0, result.output
        assert "strong-fit" in result.output
        assert "aligned" in result.output


class TestFitFromSlug:
    def test_reruns_analysis_against_an_existing_note(
        self, tmp_path: Path, isolated_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)
        runner.invoke(app, ["add", str(posting_file)])
        _stub_fit_pipeline(monkeypatch)

        result = runner.invoke(app, ["fit", "anthropic-ai-engineer"])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert job_note_body(note).startswith(POSTING_TEXT)
        assert "verdict: strong-fit" in note

    def test_unknown_slug_or_file_fails_with_a_clear_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_fit_pipeline(monkeypatch)

        result = runner.invoke(app, ["fit", "no-such-slug"])

        assert result.exit_code != 0


class TestFitRerun:
    def test_replaces_the_fit_section_wholesale(
        self, tmp_path: Path, isolated_settings: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)
        runner.invoke(app, ["add", str(posting_file)])

        first_report = FIT_REPORT.model_copy(
            update={"verdict": Verdict(tier="stretch", rationale="First run rationale.")}
        )
        _stub_fit_pipeline(monkeypatch, report=first_report)
        runner.invoke(app, ["fit", "anthropic-ai-engineer"])

        second_report = FIT_REPORT.model_copy(
            update={"verdict": Verdict(tier="strong-fit", rationale="Second run rationale.")}
        )
        _stub_fit_pipeline(monkeypatch, report=second_report)
        runner.invoke(app, ["fit", "anthropic-ai-engineer"])

        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert note.count("## Fit analysis") == 1
        assert "First run rationale." not in note
        assert "Second run rationale." in note
        assert "verdict: strong-fit" in note
        assert job_note_body(note).startswith(POSTING_TEXT)


class TestFitAgainstTheFixtureVault:
    """Unlike the other `TestFit*` classes (which stub `run_fit_analysis` to
    keep the CLI seam thin), these drive the real pipeline - real agents,
    real system prompts, real output validator - against a copy of the
    fixture vault, with `TestModel` standing in for the provider."""

    def _agents_with_fixed_outputs(
        self, agents: FitAgents, *, requirement: Requirement, report: FitReport
    ) -> tuple[AbstractContextManager[None], AbstractContextManager[None]]:
        requirements = RequirementSet(requirements=[requirement])
        return (
            agents.extract.override(model=TestModel(custom_output_args=requirements.model_dump())),
            agents.match.override(model=TestModel(custom_output_args=report.model_dump())),
        )

    def test_file_mints_the_note_and_analyzes_it_end_to_end(
        self,
        tmp_path: Path,
        isolated_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
        fixture_vault_path: Path,
    ) -> None:
        shutil.copytree(fixture_vault_path, isolated_settings)
        monkeypatch.setenv("DEFAULT_MODEL", "test")
        settings = Settings(vault_path=isolated_settings, default_model="test", agent_retries=1)
        agents = create_fit_agents(settings)
        _stub_agent_factory(monkeypatch, agents)

        posting_file = tmp_path / "posting.txt"
        posting_file.write_text(POSTING_TEXT)
        requirement = FIT_REPORT.grades[0].requirement
        extract_override, match_override = self._agents_with_fixed_outputs(
            agents, requirement=requirement, report=FIT_REPORT
        )

        with extract_override, match_override:
            result = runner.invoke(app, ["fit", str(posting_file)])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert job_note_body(note).startswith(POSTING_TEXT)
        assert "## Fit analysis" in note
        assert "verdict: strong-fit" in note
        assert "acme-payments-rotation#partner-bank-onboarding-automation" in note
        assert "strong-fit" in result.output

    def test_slug_reruns_against_an_already_seeded_note(
        self,
        isolated_settings: Path,
        monkeypatch: pytest.MonkeyPatch,
        fixture_vault_path: Path,
    ) -> None:
        shutil.copytree(fixture_vault_path, isolated_settings)
        monkeypatch.setenv("DEFAULT_MODEL", "test")
        settings = Settings(vault_path=isolated_settings, default_model="test", agent_retries=1)
        agents = create_fit_agents(settings)
        _stub_agent_factory(monkeypatch, agents)

        requirement = FIT_REPORT.grades[0].requirement
        extract_override, match_override = self._agents_with_fixed_outputs(
            agents, requirement=requirement, report=FIT_REPORT
        )

        with extract_override, match_override:
            result = runner.invoke(app, ["fit", "anthropic-ai-engineer"])

        assert result.exit_code == 0, result.output
        note = (isolated_settings / "jobs" / "anthropic-ai-engineer.md").read_text()
        assert "SENTINEL-JOBS-CONTENT-MUST-NOT-APPEAR-IN-CORPUS" in note
        assert "verdict: strong-fit" in note
        assert "analyzed:" in note
        assert "strong-fit" in result.output


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
