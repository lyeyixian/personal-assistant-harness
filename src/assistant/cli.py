"""The root `pa` CLI, per ADR-0002: mounts core commands and module sub-apps.

Mounting a module is one explicit line, e.g.:

    from assistant.modules.job_search.cli import app as job_search_app
    app.add_typer(job_search_app, name="jobs")
"""

import tomli_w
import typer

from assistant.core.config import Settings, config_file_path

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """pa - the personal assistant harness."""


@app.command()
def init() -> None:
    """Interactively scaffold the per-machine config file."""
    path = config_file_path()

    if path.exists() and not typer.confirm(f"{path} already exists. Overwrite?", default=False):
        raise typer.Exit()

    default_model_default = Settings.model_fields["default_model"].get_default()
    output_dir_default = Settings.model_fields["output_dir"].get_default()

    vault_path = typer.prompt("Experience Store vault path")
    default_model = typer.prompt("Default model", default=default_model_default)
    output_dir = typer.prompt("Output directory", default=str(output_dir_default))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        tomli_w.dumps(
            {
                "vault_path": vault_path,
                "default_model": default_model,
                "output_dir": output_dir,
            }
        ).encode()
    )

    typer.echo(f"Wrote {path}")
    typer.echo("Set your provider's API key (e.g. ANTHROPIC_API_KEY) in env or .env")
