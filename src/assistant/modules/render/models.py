"""The `resume.yaml` IR: the seam of the resume contract (ADR-0005).

Whatever writes `resume.yaml` - a session today, an agent later - writes
content only. Nothing here describes layout - no fonts, sizes, ordering
hints, or page breaks - and the fixed Typst template never invents content.
Every field is either printed as written or (dates, the work-authorization
toggle) turned into display text by the deterministic render step.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Market = Literal["sg", "remote"]

MAX_BULLETS_PER_ENTRY = 5
"""The layout contract's ceiling. 3-5 bullets is the aim; there is no floor
because cutting bullets is how overflow gets fixed."""


class _ResumeModel(BaseModel):
    """Base for the IR: unknown keys are an error, so a typo in a hand-edited
    `resume.yaml` surfaces as a shape-gate failure instead of a silent drop."""

    model_config = ConfigDict(extra="forbid")


class ResumeBullet(_ResumeModel):
    """One achievement bullet and the store ref it must trace back to.

    `source` is `<note-slug>#<achievement-heading>`; the provenance gate
    checks it before any PDF exists, and it is never rendered.
    """

    text: str
    source: str


class ResumeSkillGroup(_ResumeModel):
    category: str
    skills: list[str]


class ResumeExperience(_ResumeModel):
    """One outward-facing position - team stints already regrouped by `programme`."""

    company: str
    title: str
    location: str | None = None
    start: str
    end: str | None = None
    bullets: list[ResumeBullet] = Field(min_length=1, max_length=MAX_BULLETS_PER_ENTRY)


class ResumeProject(_ResumeModel):
    name: str
    link: str | None = None
    bullets: list[ResumeBullet] = Field(min_length=1, max_length=MAX_BULLETS_PER_ENTRY)


class ResumeEducation(_ResumeModel):
    institution: str
    qualification: str
    period: str | None = None


class ResumeHeader(_ResumeModel):
    """Header facts. No photo, no date of birth - see the resume spec."""

    name: str
    title_line: str
    location: str
    email: str
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    work_authorization: str | None = None


class ResumeContent(_ResumeModel):
    """The typed IR `resume.yaml` deserializes into and the template renders.

    `market` rides along because it drives the work-authorization toggle and
    stays visible and editable in `resume.yaml`.
    """

    market: Market
    header: ResumeHeader
    summary: str
    skills: list[ResumeSkillGroup]
    experience: list[ResumeExperience]
    projects: list[ResumeProject] = []
    education: list[ResumeEducation] = []
    certifications: list[str] = []

    def bullets(self) -> list[ResumeBullet]:
        """Every experience and project bullet, in document order."""
        return [bullet for entry in (*self.experience, *self.projects) for bullet in entry.bullets]
