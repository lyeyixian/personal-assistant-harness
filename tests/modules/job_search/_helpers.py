from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from assistant.modules.job_search.agents import ResumeDeps
from assistant.modules.job_search.models import (
    JobPosting,
    Market,
    ResumeBullet,
    ResumeContent,
    ResumeEducation,
    ResumeExperience,
    ResumeHeader,
    ResumeProject,
    ResumeSkillGroup,
)


def stub_resume_agent(content: ResumeContent) -> Agent[ResumeDeps, ResumeContent]:
    """A resume agent whose model always returns `content` - no provider, no network."""
    return Agent(
        TestModel(custom_output_args=content.model_dump()),
        output_type=ResumeContent,
        deps_type=ResumeDeps,
    )


def job_note_body(content: str) -> str:
    """The verbatim posting body of a rendered job note, stripped of its frontmatter."""
    _, _, body = content.partition("---\n")
    _, _, body = body.partition("---\n")
    return body


def make_resume_content(
    *,
    market: Market = "sg",
    work_authorization: str | None = "Singapore Citizen — no work pass required",
    experience_source: str = "acme-payments-rotation#partner-bank-onboarding-automation",
    project_source: str = "oss-contribution#accessible-date-picker-component",
) -> ResumeContent:
    """A `ResumeContent` whose every source ref resolves in the fixture vault."""
    return ResumeContent(
        market=market,
        header=ResumeHeader(
            name="Jamie Rivera",
            title_line="Backend Engineer",
            location="Singapore",
            email="jamie.rivera@example.com",
            linkedin="linkedin.com/in/jamie-rivera",
            work_authorization=work_authorization,
        ),
        summary=(
            "Backend engineer who builds payment and platform services, "
            "with a bias for integration tests over manual verification."
        ),
        skills=[
            ResumeSkillGroup(category="Languages", skills=["Python", "C#", "TypeScript"]),
            ResumeSkillGroup(category="Infra", skills=["PostgreSQL", "Docker", "Testcontainers"]),
        ],
        experience=[
            ResumeExperience(
                company="Acme Corp",
                title="Software Engineer",
                location="Singapore",
                start="2025-03",
                end=None,
                bullets=[
                    ResumeBullet(
                        text=(
                            "Automated partner-bank reconciliation, projected to remove "
                            "roughly 500 manual transactions a month."
                        ),
                        source=experience_source,
                    ),
                    ResumeBullet(
                        text=(
                            "Collapsed several settlement microservices into one service and "
                            "gave the codebase its first integration tests."
                        ),
                        source="acme-payments-rotation#settlement-service-refactor",
                    ),
                    ResumeBullet(
                        text=(
                            "Built the queue consumer feeding the nightly reporting pipeline, "
                            "retiring a manual CSV export."
                        ),
                        source="acme-platform-team#queue-integration-for-the-reporting-pipeline",
                    ),
                ],
            )
        ],
        projects=[
            ResumeProject(
                name="Angular component library",
                link="github.com/example/project",
                bullets=[
                    ResumeBullet(
                        text=(
                            "Contributed a keyboard-navigable date picker adopted by "
                            "three downstream consumers."
                        ),
                        source=project_source,
                    )
                ],
            )
        ],
        education=[
            ResumeEducation(
                institution="University of Nowhere",
                qualification="BSc Computer Science",
                period="2020 – 2024",
            )
        ],
        certifications=["AWS Certified Cloud Practitioner (2025)"],
    )


POSTING = JobPosting(
    title="AI Engineer",
    company="Anthropic",
    market="sg",
    requirements=["5+ years of Python", "Experience with agent frameworks"],
    keywords=["Python", "Agent"],
)
"""The parsed posting every offline resume test tailors against."""
