"""`tripwire ui` — start the Tripwire dashboard.

Heavy imports (FastAPI, uvicorn) happen inside the command body so that
``tripwire --help`` works even on a minimal ``tripwire[projects]`` install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

# Modules whose absence indicates a minimal [projects] install.
_UI_MODULES = frozenset({"fastapi", "uvicorn", "watchdog", "websockets"})


def _find_project_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a directory containing ``project.yaml``."""
    for candidate in (start, *start.parents):
        if (candidate / "project.yaml").is_file():
            return candidate
    return None


@click.command(name="ui")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=None,
    help="Open directly to this project [default: auto-discover].",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    show_default=True,
    help="HTTP port.",
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't auto-open the browser.",
)
@click.option(
    "--dev",
    is_flag=True,
    help="Dev mode (expects Vite on :3000 proxying /api).",
)
def ui_cmd(
    project_dir: Path | None,
    port: int,
    no_browser: bool,
    dev: bool,
) -> None:
    """Start the Tripwire dashboard (localhost only)."""
    # 1. Import check — graceful degradation on minimal installs.
    try:
        from tripwire.ui.server import start_server
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "") or ""
        if any(mod in missing for mod in _UI_MODULES):
            click.echo(
                "The UI requires the full tripwire install.\n"
                "Run:\n"
                "  pip install tripwire-pm\n"
                "(You appear to have tripwire-pm[projects] "
                "— a minimal install without web deps.)"
            )
            sys.exit(1)
        raise

    # 2. Load user config.
    from tripwire.ui.config import load_user_config

    config = load_user_config()

    # 3. Resolve project directories.
    #
    # `pin` controls whether the resolved project_dirs *restrict* discovery
    # (the --project-dir case — user explicitly scoped this run to one
    # project) or merely *augment* it (cwd / wide-discovery cases — the
    # user wants the dropdown to show everything they have).
    from tripwire.ui.services.project_service import discover_projects

    if project_dir is not None:
        project_dirs = [project_dir.expanduser().resolve()]
        pin = True
    else:
        # Wide discovery first — surfaces every project under
        # `config.project_roots` and the fallback locations.
        discovered = discover_projects(config)
        project_dirs = [Path(p.dir) for p in discovered]

        # Augment with cwd's project if we're inside one and it didn't
        # already show up in discovery.
        cwd_project = _find_project_root(Path.cwd())
        if cwd_project is not None:
            cwd_resolved = cwd_project.resolve()
            if cwd_resolved not in {p.resolve() for p in project_dirs}:
                project_dirs.append(cwd_resolved)

        if not project_dirs:
            click.echo(
                "No projects found.\n"
                "Hint: run `tripwire init` in a project directory, or add paths\n"
                "to ~/.tripwire/config.yaml under `project_roots`\n"
                "(see `tripwire config --help`)."
            )
            sys.exit(1)
        pin = False

    # 4. Launch the server.
    start_server(
        host="127.0.0.1",
        port=port,
        project_dirs=project_dirs,
        dev_mode=dev,
        open_browser=not no_browser,
        pin=pin,
    )
