"""The shared `JobPosting` model, per the job-fit and resume-generation specs,
plus the typed outputs of the fit-analysis pipeline's two agent calls.

`JobPosting` is produced once by the deterministic posting parser and consumed
identically by `pa jobs fit` and `pa jobs resume` - both features read the
same parse. `RequirementSet` and `FitReport` are the extract and match stages'
typed outputs, per the job-fit-analysis spec.
"""

from typing import Literal

from pydantic import BaseModel

Market = Literal["sg", "remote"]


class JobPosting(BaseModel):
    """The deterministic parse of a pasted job posting."""

    title: str
    company: str
    market: Market
    requirements: list[str]
    keywords: list[str]


RequirementKind = Literal["must-have", "nice-to-have"]
Firmness = Literal["likely-firm", "likely-flexible"]


class Requirement(BaseModel):
    """One posting requirement, calibrated for wishlist inflation.

    `firmness` is the explicit calibration a raw posting lacks: classic
    flexible signals are years-of-experience numbers and laundry-list tech;
    classic firm signals are visa-tied degree requirements, clearance, and
    the role's named core stack.
    """

    text: str
    kind: RequirementKind
    firmness: Firmness
    firmness_reason: str
    category: str


class RequirementSet(BaseModel):
    """The extract stage's typed output: every requirement in the posting."""

    requirements: list[Requirement]


Grade = Literal["met", "partial", "gap"]
VerdictTier = Literal["strong-fit", "good-fit", "stretch", "skip"]
DirectionAxis = Literal["aligned", "caution", "conflict"]
BridgingActionKind = Literal["positioning", "learning"]


class Evidence(BaseModel):
    """A citation backing a `met`/`partial` grade - `ref` is a
    `<note-slug>#<achievement-heading>` checked by the shared provenance
    validator before the report is written.
    """

    ref: str
    note: str


class BridgingAction(BaseModel):
    """The concrete next move for a `partial`/`gap` requirement."""

    kind: BridgingActionKind
    action: str


class RequirementGrade(BaseModel):
    """One requirement's grade in the match stage's output.

    `bridging_action` is set for `partial`/`gap` grades and absent for `met` -
    the report's "gaps" view is derived from this list (must-haves first),
    not restated separately, so the two can't drift apart.
    """

    requirement: Requirement
    grade: Grade
    evidence: list[Evidence] = []
    bridging_action: BridgingAction | None = None


class Verdict(BaseModel):
    """The capability-only tier - never blended with the direction check."""

    tier: VerdictTier
    rationale: str


class DirectionCheck(BaseModel):
    """The alignment axis against `direction.md`, a separate axis from `Verdict`."""

    axis: DirectionAxis
    reasons: str


class FitReport(BaseModel):
    """The match stage's typed output: the full fit-analysis report."""

    verdict: Verdict
    direction: DirectionCheck
    grades: list[RequirementGrade]
