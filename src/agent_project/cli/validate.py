"""`agent-project validate` — run the validation gate against a project.

Thin CLI wrapper over `core.validator.validate_project`. Exits with the
report's exit code so shell pipelines and orchestrators can branch on the
result:

- 0 → clean
- 1 → warnings only
- 2 → one or more errors

Output formats:
- `text` (default): human-readable rendering with rich styling
- `json`: the full report serialised to the spec's JSON schema, for
  agents that parse errors programmatically
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console

from agent_project.core.validator import (
    CheckResult,
    ValidationReport,
    validate_project,
)

console = Console()


@click.command(name="validate")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Path to the project root (contains project.yaml).",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors (the agent's normal mode).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Auto-fix the defined subset of issues (timestamps, UUIDs, etc.).",
)
def validate_cmd(
    project_dir: Path, strict: bool, output_format: str, fix: bool
) -> None:
    """Run the validation gate.

    The gate the agent runs after every batch of file writes. Always
    rebuilds `graph/index.yaml` as a side effect. Run with `--fix` to
    auto-repair trivial issues, `--strict` to treat warnings as errors.
    """
    resolved = project_dir.expanduser().resolve()
    report = validate_project(resolved, strict=strict, fix=fix)

    if output_format == "json":
        click.echo(json.dumps(report.to_json(), indent=2))
    else:
        _render_text(report)

    sys.exit(report.exit_code)


def _render_text(report: ValidationReport) -> None:
    """Render the validation report as styled text via rich."""
    # Header line
    if report.exit_code == 0:
        console.print("[bold green]validate passed[/bold green]")
    elif report.exit_code == 1:
        console.print(
            f"[bold yellow]validate: {len(report.warnings)} warning(s)[/bold yellow]"
        )
    else:
        console.print(
            f"[bold red]validate: {len(report.errors)} error(s), "
            f"{len(report.warnings)} warning(s)[/bold red]"
        )

    # Summary line
    console.print(
        f"  [dim]duration: {report.duration_ms}ms  "
        f"cache rebuilt: {str(report.cache_rebuilt).lower()}[/dim]"
    )

    if report.fixed:
        console.print(f"\n[bold cyan]Fixed ({len(report.fixed)}):[/bold cyan]")
        for fix in report.fixed:
            _render_finding(fix, severity_color="cyan")

    if report.errors:
        console.print(f"\n[bold red]Errors ({len(report.errors)}):[/bold red]")
        for err in report.errors:
            _render_finding(err, severity_color="red")

    if report.warnings:
        console.print(
            f"\n[bold yellow]Warnings ({len(report.warnings)}):[/bold yellow]"
        )
        for warn in report.warnings:
            _render_finding(warn, severity_color="yellow")


def _render_finding(finding: CheckResult, severity_color: str) -> None:
    """Render one CheckResult as two to three lines of styled text."""
    location = finding.file or ""
    if finding.field:
        location = f"{location}:{finding.field}" if location else finding.field
    if finding.line is not None:
        location = f"{location}:{finding.line}"

    header = f"  [{severity_color}]{finding.code}[/{severity_color}]"
    if location:
        header = f"{header}  [dim]{location}[/dim]"
    console.print(header)
    console.print(f"    {finding.message}")
    if finding.fix_hint:
        console.print(f"    [dim]hint: {finding.fix_hint}[/dim]")
