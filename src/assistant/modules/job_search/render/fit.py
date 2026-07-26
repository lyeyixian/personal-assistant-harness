"""Rendering a `FitReport`: the `## Fit analysis` markdown section written
into the job note, and the terminal pretty-print - per the spec, "the same
report pretty-prints to the terminal on every run."
"""

from rich.console import Console
from rich.table import Table

from assistant.modules.job_search.models import FitReport, RequirementGrade
from assistant.modules.job_search.notes import FIT_SECTION_HEADING


def _gaps(report: FitReport) -> list[RequirementGrade]:
    """Requirements graded `partial`/`gap`, must-haves first - derived from
    `grades` rather than a second model-authored list, so the table and the
    gaps section can never disagree."""
    gaps = [grade for grade in report.grades if grade.grade != "met"]
    return sorted(gaps, key=lambda grade: grade.requirement.kind != "must-have")


def _evidence_text(grade: RequirementGrade) -> str:
    return "; ".join(f"{evidence.ref} — {evidence.note}" for evidence in grade.evidence) or "—"


def _bridging_action_text(grade: RequirementGrade) -> str:
    action = grade.bridging_action
    return f"{action.kind}: {action.action}" if action else "—"


def _row_cells(grade: RequirementGrade) -> tuple[str, str, str, str, str]:
    """The five requirements-table cells, shared by the markdown table and
    the terminal one so a column can't drift between the two renderers."""
    return (
        grade.requirement.text,
        grade.requirement.kind,
        grade.requirement.firmness,
        grade.grade,
        _evidence_text(grade),
    )


def render_fit_section(report: FitReport) -> str:
    """The `## Fit analysis` markdown section, in the spec's rendered order:
    verdict + rationale, direction check, per-requirement table, gaps."""
    lines = [
        FIT_SECTION_HEADING,
        "",
        f"**Verdict:** {report.verdict.tier}",
        "",
        report.verdict.rationale,
        "",
        f"**Direction:** {report.direction.axis}",
        "",
        report.direction.reasons,
        "",
        "### Requirements",
        "",
        "| Requirement | Kind | Firmness | Grade | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for grade in report.grades:
        lines.append("| " + " | ".join(_row_cells(grade)) + " |")

    lines += ["", "### Gaps", ""]
    gaps = _gaps(report)
    if not gaps:
        lines.append("None.")
    else:
        lines.extend(
            f"- **{grade.requirement.text}** ({grade.grade}) — {_bridging_action_text(grade)}"
            for grade in gaps
        )

    return "\n".join(lines)


def print_fit_report(report: FitReport, *, slug: str, console: Console | None = None) -> None:
    """Pretty-print the same report to the terminal."""
    console = console or Console()

    console.print(
        f"[bold]{slug}[/bold] — verdict: [bold]{report.verdict.tier}[/bold], "
        f"direction: [bold]{report.direction.axis}[/bold]"
    )
    console.print(report.verdict.rationale)
    console.print()
    console.print(report.direction.reasons)
    console.print()

    table = Table(title="Requirements")
    for column in ("Requirement", "Kind", "Firmness", "Grade", "Evidence"):
        table.add_column(column)
    for grade in report.grades:
        table.add_row(*_row_cells(grade))
    console.print(table)

    gaps = _gaps(report)
    if gaps:
        console.print("[bold]Gaps[/bold]")
        for grade in gaps:
            action_text = _bridging_action_text(grade)
            console.print(f"- {grade.requirement.text} ({grade.grade}) — {action_text}")
