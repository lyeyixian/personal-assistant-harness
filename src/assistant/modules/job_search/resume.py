"""The `pa jobs resume` pipeline: the honesty gate and the two artifacts one run
writes.

Nothing here knows about layout - that lives entirely in `render/` - and
nothing here writes into the vault: outputs are generated, not stored.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from assistant.core import ExperienceStore, ProvenanceResult, validate_provenance
from assistant.modules.job_search.models import JobPosting, ResumeContent
from assistant.modules.job_search.notes import job_slug
from assistant.modules.job_search.render import render_resume_pdf

YAML_FILENAME = "resume.yaml"
PDF_FILENAME = "resume.pdf"

_YAML_HEADER = f"""\
# The hand-editable half of `pa jobs resume`: fix phrasing, ordering, and cuts
# here. Each bullet's `source` is its provenance ref - never rendered, always
# validated before a {PDF_FILENAME} is written.
"""


class ProvenanceError(ValueError):
    """Raised when a bullet's source ref doesn't resolve in the Experience Store."""

    def __init__(self, failures: tuple[ProvenanceResult, ...]) -> None:
        self.failures = failures
        detail = "\n".join(f"  {failure.ref} ({failure.reason})" for failure in failures)
        super().__init__(f"{len(failures)} bullet source ref(s) do not resolve:\n{detail}")


def unresolved_refs(store: ExperienceStore, content: ResumeContent) -> tuple[ProvenanceResult, ...]:
    """Every bullet source ref that doesn't resolve to a real note and heading.

    The agent reads this to ask the model for a fix; the gate below reads it to
    stop a run.
    """
    return tuple(
        result
        for bullet in content.bullets()
        if not (result := validate_provenance(store, bullet.source)).valid
    )


def validate_resume_provenance(store: ExperienceStore, content: ResumeContent) -> None:
    """The honesty gate: every bullet must trace to a real note and heading."""
    failures = unresolved_refs(store, content)
    if failures:
        raise ProvenanceError(failures)


@dataclass(frozen=True)
class ResumeArtifacts:
    """Where one run's two artifacts landed."""

    directory: Path
    yaml_path: Path
    pdf_path: Path


def resume_output_dir(output_root: Path, posting: JobPosting) -> Path:
    """The per-posting output directory - outside the vault; outputs are generated."""
    return output_root / job_slug(posting)


def load_resume_content(directory: Path) -> ResumeContent:
    """Read `resume.yaml` back into the IR, validating whatever the human edited."""
    path = directory / YAML_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"No {YAML_FILENAME} in {directory}")

    document: Any = yaml.safe_load(path.read_text())
    return ResumeContent.model_validate(document)


def write_resume(
    directory: Path, content: ResumeContent, store: ExperienceStore
) -> ResumeArtifacts:
    """Write `resume.yaml` and `resume.pdf`, provenance gate first.

    An unresolvable ref fails the run before either artifact exists. A render
    that overflows the page cap leaves the YAML behind on purpose - it is the
    artifact the human edits to cut the overflow.
    """
    validate_resume_provenance(store, content)

    directory.mkdir(parents=True, exist_ok=True)
    yaml_path = directory / YAML_FILENAME
    yaml_path.write_text(
        _YAML_HEADER + yaml.safe_dump(content.model_dump(), sort_keys=False, allow_unicode=True)
    )

    pdf_path = directory / PDF_FILENAME
    pdf_path.write_bytes(render_resume_pdf(content))
    return ResumeArtifacts(directory=directory, yaml_path=yaml_path, pdf_path=pdf_path)
