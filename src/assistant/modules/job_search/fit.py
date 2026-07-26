"""The fit-analysis pipeline: two typed agent calls over one deterministic
posting parse, code-orchestrated per ADR-0002 (no tool loop). `run_fit_analysis`
is the seam tests exercise directly, with `TestModel`/`FunctionModel` swapped
into the agents `create_fit_agents` returns.
"""

from dataclasses import dataclass

from pydantic_ai import Agent

from assistant.core import ExperienceStore, Settings, usage_limits
from assistant.modules.job_search.agents import (
    FitMatchDeps,
    create_fit_extract_agent,
    create_fit_match_agent,
)
from assistant.modules.job_search.models import FitReport, JobPosting, RequirementSet


@dataclass(frozen=True, slots=True)
class FitAgents:
    """The fit pipeline's two agents, built together so callers - CLI or
    tests - construct and override them as one unit."""

    extract: Agent[None, RequirementSet]
    match: Agent[FitMatchDeps, FitReport]


def create_fit_agents(settings: Settings) -> FitAgents:
    return FitAgents(
        extract=create_fit_extract_agent(settings),
        match=create_fit_match_agent(settings),
    )


def _match_prompt(posting: JobPosting, requirements: RequirementSet) -> str:
    lines = [
        f"Title: {posting.title}",
        f"Company: {posting.company}",
        f"Market: {posting.market}",
        "",
        "Requirements:",
    ]
    for requirement in requirements.requirements:
        lines.append(
            f"- [{requirement.kind}/{requirement.firmness}] {requirement.text} "
            f"(category: {requirement.category}; firmness reason: {requirement.firmness_reason})"
        )
    return "\n".join(lines)


async def run_fit_analysis(
    agents: FitAgents,
    *,
    store: ExperienceStore,
    posting: JobPosting,
    posting_text: str,
    settings: Settings,
) -> FitReport:
    """Run extract then match. The match stage's evidence citations are
    validated against `store` before this returns; an invalid ref exhausts
    the agent's retries and raises rather than yielding an unverified report.
    """
    limits = usage_limits(settings)
    extract_result = await agents.extract.run(posting_text, usage_limits=limits)
    requirements = extract_result.output
    match_result = await agents.match.run(
        _match_prompt(posting, requirements),
        deps=FitMatchDeps(store=store, requirements=requirements),
        usage_limits=limits,
    )
    return match_result.output
