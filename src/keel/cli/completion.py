"""`keel completion <shell>` — print shell completion install instructions.

Click ships with a built-in tab-completion mechanism that works for any
Click command. The user just needs to source the right snippet in their
shell rc file. This subcommand prints the snippet for `bash`, `zsh`, or
`fish` so the user can pipe it into their config or eval it in-place.

Once installed, completing a partial command (e.g. `keel val<TAB>`)
will offer the matching subcommands, and option completion works for
flags too.
"""

from __future__ import annotations

import click

SHELL_INSTRUCTIONS: dict[str, str] = {
    "bash": """\
# Bash completion for keel.
#
# To enable in your current shell, run:
#
#     eval "$(keel completion bash | tail -n 1)"
#
# To enable permanently, append the following line to ~/.bashrc:

eval "$(_KEEL_COMPLETE=bash_source keel)"
""",
    "zsh": """\
# Zsh completion for keel.
#
# To enable in your current shell, run:
#
#     eval "$(keel completion zsh | tail -n 1)"
#
# To enable permanently, append the following line to ~/.zshrc:

eval "$(_KEEL_COMPLETE=zsh_source keel)"
""",
    "fish": """\
# Fish completion for keel.
#
# To enable, save the snippet to your fish completions directory:
#
#     keel completion fish > ~/.config/fish/completions/keel.fish

_KEEL_COMPLETE=fish_source keel | source
""",
}


@click.command(name="completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion_cmd(shell: str) -> None:
    """Print instructions for installing shell tab completion.

    \b
    Examples:
        # Enable bash completion in the current shell
        eval "$(keel completion bash | tail -n 1)"

        # Permanently install zsh completion
        keel completion zsh >> ~/.zshrc

        # Install fish completion
        keel completion fish > ~/.config/fish/completions/keel.fish
    """
    click.echo(SHELL_INSTRUCTIONS[shell], nl=False)


__all__ = ["SHELL_INSTRUCTIONS", "completion_cmd"]
