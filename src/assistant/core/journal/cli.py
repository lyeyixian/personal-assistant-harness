"""`pa journal add` / `pa journal list` — the CLI surface over journal capture."""

from datetime import datetime

import typer

from assistant.core.config import get_settings
from assistant.core.journal.capture import add_entry, list_entries

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
