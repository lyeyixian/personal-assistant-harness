"""The resume-content agent: full curated vault + `JobPosting` -> `ResumeContent`.

One agent, one pass, no tools (ADR-0002's "barely agentic" v1): selection and
phrasing happen in a single typed generation. The agent writes content only -
the typed output is the seam it can't cross into layout.

The provenance validator runs as an output validator too, so an unresolvable
source ref comes back to the model as a retry instead of failing the run: the
deterministic gate in `resume.py` is still the thing that stands between any
content and a PDF.
"""

from dataclasses import dataclass

from pydantic_ai import Agent, ModelRetry, RunContext

from assistant.core import ExperienceStore, Note, Settings, create_agent, usage_limits
from assistant.modules.job_search.models import MAX_BULLETS_PER_ENTRY, JobPosting, ResumeContent
from assistant.modules.job_search.resume import unresolved_refs

SYSTEM_PROMPT = f"""\
You write the content of a tailored one-page resume. You never make layout
decisions: a fixed template owns fonts, spacing, ordering and page breaks.

Rules, in priority order:

1. Rephrase, never originate. Every experience and project bullet must trace to
   a specific achievement, story, or frontmatter fact in the Experience Store
   below. Tailor the wording freely; invent nothing.
2. Every bullet carries `source` as `<note-slug>#<achievement-heading-slug>`,
   using the exact refs listed with each achievement below. The ref is checked
   against the vault and is never printed on the resume.
3. Metric qualifiers may be reworded, never removed. "~500 txns/month
   (projection, per go-live email)" becomes "projected to automate ~500
   transactions/month" - never "automated 500 transactions/month". If a
   qualifier leaves a bullet too weak to earn its place, drop the bullet; never
   the qualifier.
4. Select for this posting. One page is the target, two pages the hard cap, and
   overflow is fixed by cutting bullets or the whole projects section - never by
   cramming. 3 to {MAX_BULLETS_PER_ENTRY} bullets per entry.
5. Regroup team stints into outward-facing positions using each role note's
   `programme` frontmatter: stints sharing a programme become one entry, titled
   for the outward-facing position, with the full span of dates.
6. The summary is 2-3 lines carrying the fit narrative. Skills are short
   categorized lines: the pinned skills from `skills.md` plus posting-relevant
   picks, using the vault's canonical skill names.
7. Include a project only when it earns its place for this posting - the note's
   `on-profile` flag plus real relevance.
8. Header facts (name, contact, location, education, certifications) come from
   `profile.md` verbatim. Fill `work_authorization` from the profile when the
   posting's market is `sg`; leave it null for `remote`.
9. Dates are `YYYY-MM`; a current role has `end: null`.
"""


@dataclass(frozen=True)
class ResumeDeps:
    """What one resume generation reads: the curated corpus and the posting."""

    store: ExperienceStore
    posting: JobPosting


def _render_note(note: Note) -> str:
    frontmatter = "\n".join(f"{key}: {value}" for key, value in note.frontmatter.items())
    refs = "\n".join(
        f"- ref `{note.slug}#{achievement.slug}` -> {achievement.heading}"
        for achievement in note.achievements
    )
    sections = [f"## Note `{note.slug}` (type: {note.type})", frontmatter, note.body.strip()]
    if refs:
        sections.append(f"Provenance refs for this note:\n{refs}")
    return "\n\n".join(section for section in sections if section)


def render_corpus(store: ExperienceStore) -> str:
    """The whole curated vault as prompt text, each achievement tagged with its ref.

    Full-context retrieval per ADR-0004; the journal and captured postings are
    already outside what `load_store` reads.
    """
    return "\n\n".join(_render_note(note) for note in store.notes)


def build_task_prompt(deps: ResumeDeps) -> str:
    """The per-run task: the posting this resume is tailored for."""
    posting = deps.posting
    requirements = "\n".join(f"- {requirement}" for requirement in posting.requirements)
    sections = [
        "Write the resume content for this posting.",
        f"# Posting\n\nTitle: {posting.title}\nCompany: {posting.company}\n"
        f"Market: {posting.market}\nKeywords: {', '.join(posting.keywords)}",
        f"# Requirements\n\n{requirements}" if requirements else "",
    ]
    return "\n\n".join(section for section in sections if section)


def create_resume_agent(settings: Settings) -> Agent[ResumeDeps, ResumeContent]:
    """The module's one resume-content agent, wired to the store through deps."""
    agent = create_agent(
        ResumeContent,
        deps_type=ResumeDeps,
        settings=settings,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.system_prompt
    def experience_store(ctx: RunContext[ResumeDeps]) -> str:  # pyright: ignore[reportUnusedFunction]
        return f"# Experience Store\n\n{render_corpus(ctx.deps.store)}"

    @agent.output_validator
    def refs_resolve(  # pyright: ignore[reportUnusedFunction]
        ctx: RunContext[ResumeDeps], output: ResumeContent
    ) -> ResumeContent:
        failures = unresolved_refs(ctx.deps.store, output)
        if failures:
            listed = "; ".join(f"{failure.ref} ({failure.reason})" for failure in failures)
            raise ModelRetry(
                "These bullet source refs do not resolve to a note and achievement "
                f"heading in the Experience Store: {listed}. "
                "Cite the exact refs listed with each achievement, or drop the bullet."
            )
        return output

    return agent


def generate_resume_content(
    agent: Agent[ResumeDeps, ResumeContent],
    *,
    store: ExperienceStore,
    posting: JobPosting,
    settings: Settings,
) -> ResumeContent:
    """Run the one agent call that turns the vault and a posting into resume content.

    The posting's market is stamped onto the output afterwards: it comes from the
    deterministic parse (or the `--market` flag), not from the model, and it is
    what toggles the work-authorization line at render time.
    """
    deps = ResumeDeps(store=store, posting=posting)
    result = agent.run_sync(build_task_prompt(deps), deps=deps, usage_limits=usage_limits(settings))
    return result.output.model_copy(update={"market": posting.market})
