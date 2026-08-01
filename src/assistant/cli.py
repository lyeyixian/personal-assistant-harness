"""The root `pa` CLI, per ADR-0005.

One command, mounted at the root: `pa render <dir>` - a shape gate, a
provenance gate, and Typst compilation. No noun-verb grammar, no `jobs` noun.
"""

import typer

from assistant.modules.render.cli import render

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """pa - the personal assistant harness."""


app.command()(render)
