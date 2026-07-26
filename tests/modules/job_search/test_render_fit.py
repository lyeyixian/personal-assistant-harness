from rich.console import Console

from assistant.modules.job_search.models import (
    BridgingAction,
    DirectionCheck,
    Evidence,
    FitReport,
    Requirement,
    RequirementGrade,
    Verdict,
)
from assistant.modules.job_search.render.fit import print_fit_report, render_fit_section

MUST_HAVE_GAP = RequirementGrade(
    requirement=Requirement(
        text="Security clearance",
        kind="must-have",
        firmness="likely-firm",
        firmness_reason="named in the posting as a hard requirement",
        category="compliance",
    ),
    grade="gap",
    bridging_action=BridgingAction(kind="learning", action="Pursue clearance eligibility."),
)
NICE_TO_HAVE_PARTIAL = RequirementGrade(
    requirement=Requirement(
        text="Kubernetes",
        kind="nice-to-have",
        firmness="likely-flexible",
        firmness_reason="laundry-list tech",
        category="infra",
    ),
    grade="partial",
    evidence=[
        Evidence(
            ref="acme-platform-team#queue-integration-for-the-reporting-pipeline",
            note="Adjacent infra work.",
        )
    ],
    bridging_action=BridgingAction(
        kind="positioning", action="Surface the platform-team infra work."
    ),
)
MET = RequirementGrade(
    requirement=Requirement(
        text="Strong Python",
        kind="must-have",
        firmness="likely-firm",
        firmness_reason="named core stack",
        category="language",
    ),
    grade="met",
    evidence=[
        Evidence(
            ref="acme-payments-rotation#partner-bank-onboarding-automation",
            note="Built automation in Python.",
        )
    ],
)

REPORT = FitReport(
    verdict=Verdict(tier="stretch", rationale="Strong on core skills, one firm gap."),
    direction=DirectionCheck(axis="aligned", reasons="Matches target roles in direction.md."),
    grades=[MET, NICE_TO_HAVE_PARTIAL, MUST_HAVE_GAP],
)


class TestRenderFitSection:
    def test_starts_with_the_fit_analysis_heading(self) -> None:
        section = render_fit_section(REPORT)

        assert section.startswith("## Fit analysis")

    def test_includes_verdict_and_rationale(self) -> None:
        section = render_fit_section(REPORT)

        assert "**Verdict:** stretch" in section
        assert "Strong on core skills, one firm gap." in section

    def test_includes_the_direction_check_separately_from_the_verdict(self) -> None:
        section = render_fit_section(REPORT)

        assert "**Direction:** aligned" in section
        assert "Matches target roles in direction.md." in section

    def test_requirements_table_has_a_row_per_grade_with_evidence(self) -> None:
        section = render_fit_section(REPORT)

        assert "| Strong Python | must-have | likely-firm | met |" in section
        assert "acme-payments-rotation#partner-bank-onboarding-automation" in section

    def test_gaps_section_orders_must_haves_before_nice_to_haves(self) -> None:
        section = render_fit_section(REPORT)

        gaps_section = section.split("### Gaps")[1]
        assert gaps_section.index("Security clearance") < gaps_section.index("Kubernetes")

    def test_gaps_carry_their_bridging_action(self) -> None:
        section = render_fit_section(REPORT)

        assert "learning: Pursue clearance eligibility." in section
        assert "positioning: Surface the platform-team infra work." in section

    def test_met_grade_is_not_listed_as_a_gap(self) -> None:
        section = render_fit_section(REPORT)

        gaps_section = section.split("### Gaps")[1]
        assert "Strong Python" not in gaps_section

    def test_no_gaps_renders_none(self) -> None:
        report = FitReport(verdict=REPORT.verdict, direction=REPORT.direction, grades=[MET])

        section = render_fit_section(report)

        assert "### Gaps\n\nNone." in section


class TestPrintFitReport:
    def test_prints_slug_verdict_and_direction(self) -> None:
        console = Console(record=True, width=120)

        print_fit_report(REPORT, slug="anthropic-ai-engineer", console=console)

        output = console.export_text()
        assert "anthropic-ai-engineer" in output
        assert "stretch" in output
        assert "aligned" in output

    def test_prints_the_gaps_and_their_bridging_actions(self) -> None:
        console = Console(record=True, width=120)

        print_fit_report(REPORT, slug="anthropic-ai-engineer", console=console)

        output = console.export_text()
        assert "Security clearance" in output
        assert "Pursue clearance eligibility." in output
