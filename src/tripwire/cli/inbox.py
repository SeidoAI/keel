"""Inbox CLI — read-only inspection of the PM-agent attention queue.

Authoring stays in YAML (the PM agent writes inbox/<id>.md directly,
matching the existing "agents create entities by writing files" rule).
Resolving lives in the dashboard UI. The CLI is purely a way to
inspect the queue from a terminal.

Subcommands:
    tripwire inbox list [--bucket blocked|fyi] [--resolved/--unresolved]
    tripwire inbox show <entry_id>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from tripwire.ui.services.inbox_service import (
    get_inbox_entry,
    list_inbox,
)


@click.group(name="inbox")
def inbox_cmd() -> None:
    """Inspect the PM-agent attention queue."""


@inbox_cmd.command("list")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
)
@click.option(
    "--bucket",
    type=click.Choice(["blocked", "fyi"]),
    default=None,
    help="Filter by bucket.",
)
@click.option(
    "--resolved/--unresolved",
    "resolved",
    default=None,
    help="Filter by resolved state. Omit to show both.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
def inbox_list_cmd(
    project_dir: Path,
    bucket: str | None,
    resolved: bool | None,
    fmt: str,
) -> None:
    """List inbox entries."""
    project = project_dir.expanduser().resolve()
    items = list_inbox(project, bucket=bucket, resolved=resolved)
    if fmt == "json":
        click.echo(
            json.dumps(
                [
                    {
                        "id": i.id,
                        "bucket": i.bucket,
                        "title": i.title,
                        "author": i.author,
                        "created_at": i.created_at.isoformat(),
                        "resolved": i.resolved,
                    }
                    for i in items
                ],
                indent=2,
            )
        )
        return
    if not items:
        click.echo("(no inbox entries)")
        return
    for item in items:
        marker = "✓" if item.resolved else ("!" if item.bucket == "blocked" else "·")
        click.echo(f"{marker} [{item.bucket:7s}] {item.id}  {item.title}")


@inbox_cmd.command("show")
@click.argument("entry_id")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
def inbox_show_cmd(entry_id: str, project_dir: Path, fmt: str) -> None:
    """Show one inbox entry by id."""
    project = project_dir.expanduser().resolve()
    item = get_inbox_entry(project, entry_id)
    if item is None:
        click.echo(f"inbox entry {entry_id!r} not found", err=True)
        sys.exit(1)
    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "id": item.id,
                    "bucket": item.bucket,
                    "title": item.title,
                    "body": item.body,
                    "author": item.author,
                    "created_at": item.created_at.isoformat(),
                    "references": item.references,
                    "escalation_reason": item.escalation_reason,
                    "resolved": item.resolved,
                    "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
                    "resolved_by": item.resolved_by,
                },
                indent=2,
            )
        )
        return
    click.echo(f"id:       {item.id}")
    click.echo(f"bucket:   {item.bucket}")
    click.echo(f"title:    {item.title}")
    click.echo(f"author:   {item.author}")
    click.echo(f"created:  {item.created_at.isoformat()}")
    if item.references:
        click.echo("refs:")
        for ref in item.references:
            click.echo(f"  - {ref}")
    if item.escalation_reason:
        click.echo(f"reason:   {item.escalation_reason}")
    click.echo(f"resolved: {item.resolved}")
    if item.resolved_at:
        click.echo(f"  at:     {item.resolved_at.isoformat()}")
        click.echo(f"  by:     {item.resolved_by}")
    if item.body.strip():
        click.echo("\n" + item.body.rstrip())
