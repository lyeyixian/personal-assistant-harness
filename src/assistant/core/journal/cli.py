"""`pa journal add/list/fold` — the CLI surface over journal capture and the Fold."""

from datetime import datetime

import typer

from assistant.core.config import get_settings
from assistant.core.journal.capture import add_entry, list_entries
from assistant.core.journal.fold import run_fold

app = typer.Typer(add_completion=False, help="Capture and browse Journal Entries.")


@app.command()
def add(text: str) -> None:
    """Append a timestamped bullet to today's journal file."""
    settings = get_settings()
    result = add_entry(settings.vault_path, text, now=datetime.now())

    typer.echo(f"Added to {result.path}")
    if result.reset_from_folded:
        typer.echo("Day was folded; reset to pending.")


@app.command(name="list")
def list_command(
    limit: int = typer.Option(20, "--limit", "-n", help="Max entries to show."),
) -> None:
    """Show recent Journal Entries and their pending/folded state."""
    settings = get_settings()
    entries = list_entries(settings.vault_path, limit=limit)

    if not entries:
        typer.echo("No journal entries yet.")
        return

    for entry in entries:
        status = "folded" if entry.folded else "pending"
        typer.echo(f"{entry.date}  [{status}]  {entry.text}")


@app.command()
def fold() -> None:
    """Fold every pending Journal Entry into curated notes.

    Nothing is committed - review the result with `git diff` in the vault
    before committing.
    """
    settings = get_settings()
    result = run_fold(settings.vault_path, settings)

    if not result.files:
        typer.echo("Nothing pending to fold.")
        return

    entry_word = "entry" if result.entry_count == 1 else "entries"
    file_word = "file" if len(result.files) == 1 else "files"
    typer.echo(f"Folded {result.entry_count} {entry_word} across {len(result.files)} {file_word}.")
    typer.echo(
        f"Achievements: {result.achievements_created} new, "
        f"{result.achievements_updated} updated. "
        f"Stories: {result.stories_created} new. "
        f"Skills added: {result.skills_added}."
    )
    typer.echo("Review the changes with `git diff` in your vault before committing.")
