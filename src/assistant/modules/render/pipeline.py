"""`pa render <dir>`: the two mechanical gates and the write step, per ADR-0005.

Neither gate is the model grading itself, and both run on every invocation -
including a re-render of a hand-edited `resume.yaml`, so a human's own edits
cannot silently break provenance either.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from assistant.core import ExperienceStore, ProvenanceResult, load_store, validate_provenance
from assistant.modules.render.models import ResumeContent
from assistant.modules.render.pdf import render_resume_pdf

YAML_FILENAME = "resume.yaml"
PDF_FILENAME = "resume.pdf"


class ShapeError(ValueError):
    """Raised when `resume.yaml` doesn't parse into the `ResumeContent` IR."""


def _format_validation_error(exc: ValidationError) -> str:
    lines = [
        f"  {'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in exc.errors(include_url=False)
    ]
    return f"{YAML_FILENAME} failed the shape gate:\n" + "\n".join(lines)


def load_resume_content(directory: Path) -> ResumeContent:
    """The shape gate: parse `resume.yaml` in `directory` into the IR.

    A missing file, invalid YAML, and a document that doesn't match the IR
    (unknown fields included, per `_ResumeModel`) are all legible failures -
    never a traceback.
    """
    path = directory / YAML_FILENAME
    if not path.exists():
        raise FileNotFoundError(f"No {YAML_FILENAME} in {directory}")

    try:
        document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ShapeError(f"{YAML_FILENAME} is not valid YAML:\n  {exc}") from exc

    try:
        return ResumeContent.model_validate(document)
    except ValidationError as exc:
        raise ShapeError(_format_validation_error(exc)) from exc


class ProvenanceError(ValueError):
    """Raised when a bullet's source ref doesn't resolve in the Experience Store."""

    def __init__(self, failures: tuple[ProvenanceResult, ...]) -> None:
        self.failures = failures
        detail = "\n".join(f"  {failure.ref} ({failure.reason})" for failure in failures)
        super().__init__(f"{len(failures)} bullet source ref(s) do not resolve:\n{detail}")


def unresolved_refs(store: ExperienceStore, content: ResumeContent) -> tuple[ProvenanceResult, ...]:
    """Every bullet source ref that doesn't resolve to a real note and heading."""
    return tuple(
        result
        for bullet in content.bullets()
        if not (result := validate_provenance(store, bullet.source)).valid
    )


def validate_resume_provenance(store: ExperienceStore, content: ResumeContent) -> None:
    """The provenance gate: every bullet must trace to a real note and heading."""
    failures = unresolved_refs(store, content)
    if failures:
        raise ProvenanceError(failures)


def render(directory: Path, vault_path: Path) -> Path:
    """Read `resume.yaml` from `directory`, run both gates, and write `resume.pdf`
    beside it. Either gate failing, or content overflowing the two-page cap,
    leaves no PDF behind.
    """
    content = load_resume_content(directory)
    store = load_store(vault_path)
    validate_resume_provenance(store, content)

    pdf_path = directory / PDF_FILENAME
    pdf_path.write_bytes(render_resume_pdf(content))
    return pdf_path
