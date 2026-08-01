from pathlib import Path
from typing import Any

import yaml

from assistant.modules.render.models import (
    Market,
    ResumeBullet,
    ResumeContent,
    ResumeEducation,
    ResumeExperience,
    ResumeHeader,
    ResumeProject,
    ResumeSkillGroup,
)


def write_resume_yaml(directory: Path, document: ResumeContent | dict[str, Any]) -> Path:
    """Write `resume.yaml` as a session or a human would - the pipeline's only input."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "resume.yaml"
    payload = document.model_dump() if isinstance(document, ResumeContent) else document
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    return path


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
