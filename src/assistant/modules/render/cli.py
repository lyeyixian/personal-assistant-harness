"""The `render` command: `pa render <dir>` mounted at the CLI root (ADR-0005).

The only command `pa` has - no `jobs` noun, no schema-emitting verb. This
command *is* the schema's only authority: there is no separate schema
document to drift from what actually renders.
"""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from assistant.core import get_settings
from assistant.modules.render.pdf import ResumeOverflowError
from assistant.modules.render.pipeline import ProvenanceError, ShapeError
from assistant.modules.render.pipeline import render as render_resume


def _resolve_vault_path(vault_path: Path | None) -> Path:
    if vault_path is not None:
        return vault_path
    try:
        return get_settings().vault_path
    except ValidationError as exc:
        raise typer.BadParameter("VAULT_PATH is not set and no --vault-path was given.") from exc


def render(
    directory: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=False,
            readable=True,
            help="Directory containing resume.yaml.",
        ),
    ],
    vault_path: Annotated[
        Path | None,
        typer.Option(
            "--vault-path",
            help="Path to the Experience Store vault; overrides VAULT_PATH.",
        ),
    ] = None,
) -> None:
    """Render `resume.yaml` in DIRECTORY into `resume.pdf` beside it.

    Runs the shape gate and the provenance gate first - a gate failure or a
    two-page overflow exits non-zero with a legible reason and writes no PDF.
    """
    resolved_vault_path = _resolve_vault_path(vault_path)

    try:
        pdf_path = render_resume(directory, resolved_vault_path)
    except (FileNotFoundError, ShapeError, ProvenanceError, ResumeOverflowError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote {pdf_path}")
