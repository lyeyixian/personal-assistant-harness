"""`pa jobs` sub-app: posting intake (`add`), the frontmatter listing (`list`),
and resume generation (`resume`).
"""

import sys
from pathlib import Path
from typing import Annotated

import click
import typer
from rich.console import Console
from rich.table import Table

from assistant.core import get_settings, load_store
from assistant.modules.job_search.agents import create_resume_agent, generate_resume_content
from assistant.modules.job_search.models import Market
from assistant.modules.job_search.notes import list_job_notes, mint_job_note
from assistant.modules.job_search.parsing import PostingParseError, parse_posting
from assistant.modules.job_search.render import ResumeOverflowError
from assistant.modules.job_search.resume import (
    ProvenanceError,
    resume_output_dir,
    write_resume,
)

app = typer.Typer(
    add_completion=False, help="Job-search: posting intake, fit analysis, resume generation."
)


def _read_posting_text(file: Path | None) -> str:
    """A posting's raw text: `file` if given, else piped stdin, else `$EDITOR`."""
    if file is not None:
        return file.read_text()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    text = click.edit("")
    if not text:
        raise typer.BadParameter("No posting text provided (editor closed without saving).")
    return text


@app.command()
def add(
    file: Annotated[
        Path | None,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="A file containing the pasted posting; omit to read stdin or open $EDITOR.",
        ),
    ] = None,
    url: Annotated[
        str | None, typer.Option("--url", help="The posting's URL, stored as metadata only.")
    ] = None,
    market: Annotated[
        Market | None, typer.Option("--market", help="Override the inferred market.")
    ] = None,
) -> None:
    """Ingest a job posting (file, stdin, or $EDITOR) and mint a job note; prints the slug."""
    settings = get_settings()
    raw_text = _read_posting_text(file)

    try:
        posting = parse_posting(raw_text, market=market)
    except PostingParseError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    slug = mint_job_note(settings.vault_path, posting, raw_text, url=url)
    typer.echo(slug)


@app.command("list")
def list_jobs() -> None:
    """Render an at-a-glance table of captured postings from job-note frontmatter."""
    settings = get_settings()
    notes = list_job_notes(settings.vault_path)

    if not notes:
        typer.echo("No job postings captured yet.")
        return

    table = Table()
    for column in ("Company", "Title", "Verdict", "Direction", "Analyzed"):
        table.add_column(column)
    for note in notes:
        table.add_row(
            note.company or "",
            note.title or "",
            note.verdict or "",
            note.direction or "",
            note.analyzed or "",
        )
    Console().print(table)


def _exit_with_error(exc: Exception) -> typer.Exit:
    typer.echo(str(exc), err=True)
    return typer.Exit(code=1)


@app.command()
def resume(
    posting_file: Annotated[
        Path,
        typer.Argument(
            exists=True, dir_okay=False, readable=True, help="A file containing the job posting."
        ),
    ],
    market: Annotated[
        Market | None, typer.Option("--market", help="Override the inferred market.")
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Write the artifacts here instead of under the output root."),
    ] = None,
) -> None:
    """Generate a tailored resume: parse the posting, run the agent, write YAML + PDF.

    Outputs overwrite in place - they are generated, never versioned.
    """
    settings = get_settings()

    try:
        posting = parse_posting(posting_file.read_text(), market=market)
    except PostingParseError as exc:
        raise _exit_with_error(exc) from exc

    store = load_store(settings.vault_path)
    content = generate_resume_content(
        create_resume_agent(settings), store=store, posting=posting, settings=settings
    )

    try:
        artifacts = write_resume(
            out or resume_output_dir(settings.output_dir, posting), content, store
        )
    except (ProvenanceError, ResumeOverflowError) as exc:
        raise _exit_with_error(exc) from exc

    typer.echo(f"Wrote {artifacts.yaml_path}")
    typer.echo(f"Wrote {artifacts.pdf_path}")
