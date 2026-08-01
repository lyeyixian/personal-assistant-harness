"""The root `pa` CLI, per ADR-0005.

Mounts no commands yet: the render command that will fill it - a shape gate,
a provenance gate, and Typst compilation behind `pa render <dir>` - lands in
a later ticket.
"""

import typer

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """pa - the personal assistant harness."""
