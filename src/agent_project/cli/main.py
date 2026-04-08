"""Click root group for `agent-project`.

Registers every v0 subcommand. The root group does nothing on its own —
all work happens inside the commands.
"""

from __future__ import annotations

import click

from agent_project import __version__
from agent_project.cli.artifacts import artifacts_cmd
from agent_project.cli.enums import enums_cmd
from agent_project.cli.graph import graph_cmd
from agent_project.cli.init import init_cmd
from agent_project.cli.next_key import next_key_cmd
from agent_project.cli.node import node_cmd
from agent_project.cli.refs import refs_cmd
from agent_project.cli.scaffold import scaffold_cmd
from agent_project.cli.status import status_cmd
from agent_project.cli.templates import templates_cmd
from agent_project.cli.validate import validate_cmd


@click.group(
    help=(
        "Git-native project management with a concept graph for AI agents. "
        "The primary user is Claude Code (or similar) loaded with the "
        "project-manager skill; humans interact through the agent."
    )
)
@click.version_option(version=__version__, prog_name="agent-project")
def cli() -> None:
    """Root command group. Does nothing on its own — see subcommands."""


cli.add_command(init_cmd)
cli.add_command(scaffold_cmd)
cli.add_command(next_key_cmd)
cli.add_command(validate_cmd)
cli.add_command(status_cmd)
cli.add_command(graph_cmd)
cli.add_command(refs_cmd)
cli.add_command(node_cmd)
cli.add_command(templates_cmd)
cli.add_command(enums_cmd)
cli.add_command(artifacts_cmd)


if __name__ == "__main__":
    cli()
