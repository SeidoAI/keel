"""`tripwire drift` — coherence reporting CLI (KUI-128 / A3).

The drift command surfaces a single 0-100 coherence score for a
project, computed from existing drift signals (stale pins,
unresolved references, stale concept-node freshness, recent
workflow-drift events). Higher = healthier.

Subcommands:

- ``tripwire drift report`` — current score with breakdown.

Future iterations will add ``--since`` for week-over-week deltas
once the events log substrate (KUI-123) lands.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from tripwire.core.drift import compute_coherence
from tripwire.core.store import ProjectNotFoundError, load_project


@click.group(name="drift")
def drift_cmd() -> None:
    """Coherence-score reporting for the project."""


@drift_cmd.command(name="report")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
def report_cmd(project_dir: Path, output_format: str) -> None:
    """Render the coherence score (0-100) plus per-signal breakdown."""
    resolved = project_dir.expanduser().resolve()
    try:
        load_project(resolved)
    except ProjectNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    result = compute_coherence(resolved)

    if output_format == "json":
        click.echo(
            json.dumps(
                {"score": result.score, "breakdown": result.breakdown},
                indent=2,
            )
        )
        return

    click.echo(f"Coherence score: {result.score}/100")
    click.echo("")
    click.echo("Breakdown:")
    for name, count in result.breakdown.items():
        click.echo(f"  {name}: {count}")


__all__ = ["drift_cmd"]
