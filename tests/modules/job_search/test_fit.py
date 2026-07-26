"""Pipeline-level tests for `run_fit_analysis`, per the Testing Decisions'
primary seam: a pipeline function called with an injected fixture store and
`TestModel` swapped into the agents `create_fit_agents` returns.
"""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

from assistant.core import ExperienceStore, Settings, load_store
from assistant.modules.job_search.fit import (
    FitAgents,
    _match_prompt,  # pyright: ignore[reportPrivateUsage]
    create_fit_agents,
    run_fit_analysis,
)
from assistant.modules.job_search.models import (
    BridgingAction,
    DirectionCheck,
    Evidence,
    FitReport,
    JobPosting,
    Requirement,
    RequirementGrade,
    RequirementSet,
    Verdict,
)

POSTING = JobPosting(
    title="AI Engineer",
    company="Anthropic",
    market="remote",
    requirements=["Strong Python", "Security clearance"],
    keywords=["Python"],
)
POSTING_TEXT = "AI Engineer at Anthropic\n\n- Strong Python\n- Security clearance\n"

REQUIREMENT = Requirement(
    text="Strong Python",
    kind="must-have",
    firmness="likely-firm",
    firmness_reason="named core stack",
    category="language",
)
REQUIREMENT_SET = RequirementSet(requirements=[REQUIREMENT])

VALID_REF = "acme-payments-rotation#partner-bank-onboarding-automation"


def _valid_report() -> FitReport:
    return FitReport(
        verdict=Verdict(tier="good-fit", rationale="Solid backend experience overall."),
        direction=DirectionCheck(axis="aligned", reasons="Matches direction.md target roles."),
        grades=[
            RequirementGrade(
                requirement=REQUIREMENT,
                grade="met",
                evidence=[Evidence(ref=VALID_REF, note="Built automation in Python.")],
            )
        ],
    )


@contextmanager
def _mock_outputs(
    agents: FitAgents, *, requirements: RequirementSet, report: FitReport
) -> Generator[None]:
    """Override both agents' models with fixed typed outputs for one run."""
    with (
        agents.extract.override(model=TestModel(custom_output_args=requirements.model_dump())),
        agents.match.override(model=TestModel(custom_output_args=report.model_dump())),
    ):
        yield


async def _run(agents: FitAgents, *, store: ExperienceStore, settings: Settings) -> FitReport:
    return await run_fit_analysis(
        agents, store=store, posting=POSTING, posting_text=POSTING_TEXT, settings=settings
    )


@pytest.fixture
def store(fixture_vault_path: Path) -> ExperienceStore:
    return load_store(fixture_vault_path)


@pytest.fixture
def settings(fixture_vault_path: Path) -> Settings:
    return Settings(vault_path=fixture_vault_path, default_model="test", agent_retries=1)


class TestRunFitAnalysis:
    async def test_returns_the_match_stages_typed_output(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        report = _valid_report()

        with _mock_outputs(agents, requirements=REQUIREMENT_SET, report=report):
            result = await _run(agents, store=store, settings=settings)

        assert result == report

    async def test_a_dropped_requirement_fails_the_run(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        two_requirements = RequirementSet(
            requirements=[
                REQUIREMENT,
                Requirement(
                    text="Security clearance",
                    kind="must-have",
                    firmness="likely-firm",
                    firmness_reason="named in the posting",
                    category="compliance",
                ),
            ]
        )
        report_missing_one = _valid_report()  # only grades REQUIREMENT

        with (
            _mock_outputs(agents, requirements=two_requirements, report=report_missing_one),
            pytest.raises(UnexpectedModelBehavior),
        ):
            await _run(agents, store=store, settings=settings)

    async def test_invalid_evidence_ref_fails_the_run(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        bad_report = FitReport(
            verdict=Verdict(tier="good-fit", rationale="x"),
            direction=DirectionCheck(axis="aligned", reasons="y"),
            grades=[
                RequirementGrade(
                    requirement=REQUIREMENT,
                    grade="met",
                    evidence=[Evidence(ref="no-such-note#no-such-heading", note="bad")],
                )
            ],
        )

        with (
            _mock_outputs(agents, requirements=REQUIREMENT_SET, report=bad_report),
            pytest.raises(UnexpectedModelBehavior),
        ):
            await _run(agents, store=store, settings=settings)

    async def test_met_grade_without_evidence_fails_the_run(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        bad_report = FitReport(
            verdict=Verdict(tier="good-fit", rationale="x"),
            direction=DirectionCheck(axis="aligned", reasons="y"),
            grades=[RequirementGrade(requirement=REQUIREMENT, grade="met", evidence=[])],
        )

        with (
            _mock_outputs(agents, requirements=REQUIREMENT_SET, report=bad_report),
            pytest.raises(UnexpectedModelBehavior),
        ):
            await _run(agents, store=store, settings=settings)

    async def test_gap_grade_without_bridging_action_fails_the_run(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        bad_report = FitReport(
            verdict=Verdict(tier="stretch", rationale="x"),
            direction=DirectionCheck(axis="aligned", reasons="y"),
            grades=[RequirementGrade(requirement=REQUIREMENT, grade="gap")],
        )

        with (
            _mock_outputs(agents, requirements=REQUIREMENT_SET, report=bad_report),
            pytest.raises(UnexpectedModelBehavior),
        ):
            await _run(agents, store=store, settings=settings)

    async def test_valid_gap_with_a_bridging_action_succeeds(
        self, store: ExperienceStore, settings: Settings
    ) -> None:
        agents = create_fit_agents(settings)
        report = FitReport(
            verdict=Verdict(tier="stretch", rationale="x"),
            direction=DirectionCheck(axis="conflict", reasons="y"),
            grades=[
                RequirementGrade(
                    requirement=REQUIREMENT,
                    grade="gap",
                    bridging_action=BridgingAction(kind="learning", action="Take a course."),
                )
            ],
        )

        with _mock_outputs(agents, requirements=REQUIREMENT_SET, report=report):
            result = await _run(agents, store=store, settings=settings)

        assert result == report


class TestMatchPrompt:
    def test_includes_posting_fields(self) -> None:
        prompt = _match_prompt(POSTING, REQUIREMENT_SET)

        assert "AI Engineer" in prompt
        assert "Anthropic" in prompt
        assert "remote" in prompt

    def test_includes_each_extracted_requirements_fields(self) -> None:
        prompt = _match_prompt(POSTING, REQUIREMENT_SET)

        assert "Strong Python" in prompt
        assert "must-have" in prompt
        assert "likely-firm" in prompt
        assert "language" in prompt
        assert "named core stack" in prompt
