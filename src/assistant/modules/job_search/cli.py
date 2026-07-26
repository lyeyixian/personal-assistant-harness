"""`pa jobs` sub-app: posting intake (`add`), fit analysis (`fit`), and the
frontmatter listing (`list`).
"""

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

import click
import typer
from pydantic_ai.exceptions import AgentRunError
from rich.console import Console
from rich.table import Table

from assistant.core import get_settings, load_store
from assistant.modules.job_search.fit import create_fit_agents, run_fit_analysis
from assistant.modules.job_search.models import JobPosting, Market
from assistant.modules.job_search.notes import (
    job_note_exists,
    list_job_notes,
    mint_job_note,
    read_job_note,
    write_fit_report,
)
from assistant.modules.job_search.parsing import PostingParseError, parse_posting
from assistant.modules.job_search.render.fit import print_fit_report, render_fit_section

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


def _resolve_posting(
    vault_path: Path, target: str, market: Market | None
) -> tuple[str, JobPosting, str]:
    """Resolve `pa jobs fit`'s `<slug|file>` argument: an existing file mints
    a job note first; otherwise `target` must be an existing note's slug."""
    path = Path(target)
    if path.is_file():
        raw_text = path.read_text()
        posting = parse_posting(raw_text, market=market)
        slug = mint_job_note(vault_path, posting, raw_text)
        return slug, posting, raw_text

    if not job_note_exists(vault_path, target):
        raise typer.BadParameter(f"'{target}' is neither a file nor a known job-note slug.")

    note = read_job_note(vault_path, target)
    posting = parse_posting(note.posting_text, market=market or note.frontmatter.get("market"))
    return target, posting, note.posting_text


@app.command()
def fit(
    target: Annotated[str, typer.Argument(help="A job-note slug, or a posting file to add first.")],
    market: Annotated[
        Market | None, typer.Option("--market", help="Override the inferred/stored market.")
    ] = None,
) -> None:
    """Run (or re-run) fit analysis; a file path mints the job note first."""
    settings = get_settings()

    try:
        slug, posting, posting_text = _resolve_posting(settings.vault_path, target, market)
    except PostingParseError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    store = load_store(settings.vault_path)
    agents = create_fit_agents(settings)
    try:
        report = asyncio.run(
            run_fit_analysis(
                agents,
                store=store,
                posting=posting,
                posting_text=posting_text,
                settings=settings,
            )
        )
    except AgentRunError as exc:
        typer.echo(f"Fit analysis failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    write_fit_report(
        settings.vault_path,
        slug,
        render_fit_section(report),
        verdict=report.verdict.tier,
        direction=report.direction.axis,
        analyzed=date.today(),
    )
    print_fit_report(report, slug=slug)


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
