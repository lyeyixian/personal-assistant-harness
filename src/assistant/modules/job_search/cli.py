"""`pa jobs` sub-app: posting intake (`add`) and the frontmatter listing (`list`)."""

import sys
from pathlib import Path
from typing import Annotated

import click
import typer
from rich.console import Console
from rich.table import Table

from assistant.core import get_settings
from assistant.modules.job_search.models import Market
from assistant.modules.job_search.notes import list_job_notes, mint_job_note
from assistant.modules.job_search.parsing import PostingParseError, parse_posting

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
