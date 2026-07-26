"""The two fit-analysis agents (extract, match), per ADR-0002's "one Agent
per task" rule and its "barely agentic" v1: no tool loop, so the match
agent's dynamic system prompt renders the full curated vault as context and
its output validator enforces the honesty gate deterministically before any
report reaches the caller.
"""

from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext

from assistant.core import ExperienceStore, Settings, create_agent, validate_provenance
from assistant.modules.job_search.models import FitReport, RequirementSet

_EXTRACT_SYSTEM_PROMPT = """\
You extract structured requirements from a pasted job posting.

For each requirement the posting states, produce:
- `text`: the requirement in the posting's own terms.
- `kind`: `must-have` or `nice-to-have`, as the posting frames it.
- `firmness`: `likely-firm` or `likely-flexible`, with a one-line `firmness_reason`.
  Postings are wishlists, not contracts - calibrate accordingly. Classic
  flexible signals: years-of-experience numbers, laundry-list tech, "expert
  in N frameworks". Classic firm signals: a degree tied to visa sponsorship,
  security clearance, or the role's named core stack.
- `category`: a short grouping label (e.g. language/framework, domain,
  seniority, practice).

Extract every distinct requirement; do not merge unrelated ones together."""

_MATCH_SYSTEM_PROMPT = """\
You judge job fit against a candidate's Experience Store, which will be
given to you in full below (roles, projects, stories, profile, skills, and
direction).

You will be given a job posting's title, company, market, and extracted
requirements. For each requirement, produce a grade:
- `met` or `partial`: cite at least one piece of `evidence`, each a
  `<note-slug>#<achievement-heading>` ref into the store (e.g.
  `acme-payments-rotation#partner-bank-onboarding-automation`) plus a
  one-line note. Only cite an achievement that actually entails the claim -
  never invent or approximate a ref.
- `partial` or `gap`: attach a `bridging_action` - `positioning` if evidence
  exists in the store but needs reframing or surfacing, `learning` if it's a
  real gap needing a project or course. Leave `bridging_action` unset for
  `met`.

Then produce:
- `verdict`: a capability-only tier - `strong-fit`, `good-fit`, `stretch`, or
  `skip` - with a 2-3 sentence `rationale` grounded in the grades above.
  Weigh gaps by firmness: a gap on a likely-flexible requirement should barely
  move the tier; a gap on a likely-firm must-have should move it decisively.
  Never let direction affect this tier.
- `direction`: a separate axis - `aligned`, `caution`, or `conflict` against
  the store's `direction.md` - with `reasons`. A strong capability fit that
  conflicts with direction is a legitimate, expected combination."""


def create_fit_extract_agent(settings: Settings) -> Agent[None, RequirementSet]:
    """The extract stage: posting text -> `RequirementSet`. No store access needed."""
    return create_agent(
        RequirementSet,
        deps_type=type(None),
        settings=settings,
        system_prompt=_EXTRACT_SYSTEM_PROMPT,
    )


@dataclass(frozen=True, slots=True)
class FitMatchDeps:
    """The match stage's injected deps, per ADR-0002 - the store is reached
    only through this, never fetched by a tool call. `requirements` lets the
    output validator confirm every extracted requirement got graded."""

    store: ExperienceStore
    requirements: RequirementSet


def _render_store(store: ExperienceStore) -> str:
    return "\n\n".join(f"# {note.slug} ({note.type})\n{note.body}" for note in store.notes)


def create_fit_match_agent(settings: Settings) -> Agent[FitMatchDeps, FitReport]:
    """The match stage: full vault + `RequirementSet` -> `FitReport`, gated by
    the shared provenance validator before the run can succeed."""
    agent = create_agent(
        FitReport,
        deps_type=FitMatchDeps,
        settings=settings,
        system_prompt=_MATCH_SYSTEM_PROMPT,
    )

    @agent.system_prompt
    def vault_context(ctx: RunContext[FitMatchDeps]) -> str:  # pyright: ignore[reportUnusedFunction]
        return _render_store(ctx.deps.store)

    @agent.output_validator
    def validate_report(  # pyright: ignore[reportUnusedFunction]
        ctx: RunContext[FitMatchDeps], report: FitReport
    ) -> FitReport:
        expected = {requirement.text for requirement in ctx.deps.requirements.requirements}
        graded = {grade.requirement.text for grade in report.grades}
        if graded != expected:
            missing, extra = sorted(expected - graded), sorted(graded - expected)
            raise ModelRetry(
                "Every extracted requirement must be graded exactly once. "
                f"Missing: {missing!r}. Unexpected: {extra!r}."
            )

        for grade in report.grades:
            if grade.grade in ("met", "partial") and not grade.evidence:
                raise ModelRetry(
                    f"Requirement {grade.requirement.text!r} is graded {grade.grade!r} but "
                    "cites no evidence. Cite at least one <note-slug>#<achievement-heading> ref."
                )
            for evidence in grade.evidence:
                result = validate_provenance(ctx.deps.store, evidence.ref)
                if not result.valid:
                    raise ModelRetry(
                        f"Evidence ref {evidence.ref!r} is invalid ({result.reason}). Cite a "
                        "real <note-slug>#<achievement-heading> from the store above."
                    )
            if grade.grade != "met" and grade.bridging_action is None:
                raise ModelRetry(
                    f"Requirement {grade.requirement.text!r} is graded {grade.grade!r} but has "
                    "no bridging_action. Every partial/gap grade needs one."
                )
        return report

    return agent
