"""`tripwire migrate` — schema/layout migrations for existing projects.

Currently ships one subcommand: ``tripwire migrate templates``, which
moves a pre-v0.10.0 flat-layout project to the consolidated
``templates/`` layout via ``git mv`` (or plain ``shutil.move`` if
the project isn't a git repo).

Idempotent — running it twice is a no-op.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click

from tripwire.core import paths

# Source (flat) → destination (under templates/) mapping for the v0.10.0
# layout migration. Mirrors the canonical/legacy pairs in
# ``core/paths.py``'s ``_LEGACY_TEMPLATE_PATHS``.
_TEMPLATE_RENAMES: tuple[tuple[str, str], ...] = (
    ("agents", paths.AGENTS_DIR),                       # → templates/agents
    ("enums", paths.ENUMS_DIR),                          # → templates/enums
    ("issue_templates", paths.ISSUE_TEMPLATES_DIR),     # → templates/issues
    ("session_templates", paths.SESSION_TEMPLATES_DIR), # → templates/sessions
    ("comment_templates", paths.COMMENT_TEMPLATES_DIR), # → templates/comments
    ("orchestration", paths.ORCHESTRATION_DIR),         # → templates/orchestration
)


@click.group(name="migrate")
def migrate_cmd() -> None:
    """Run a one-shot schema/layout migration on the project at cwd."""


@migrate_cmd.command("templates")
@click.option(
    "--project-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    default=".",
    show_default=True,
    help="Project root to migrate.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the moves without performing them.",
)
def migrate_templates_cmd(project_dir: Path, dry_run: bool) -> None:
    """Migrate a pre-v0.10.0 project to the consolidated templates/ layout.

    Moves these flat-layout directories into ``templates/``:

      \b
      agents/             → templates/agents/
      enums/              → templates/enums/
      issue_templates/    → templates/issues/
      session_templates/  → templates/sessions/
      comment_templates/  → templates/comments/
      orchestration/      → templates/orchestration/

    Uses ``git mv`` when the project is a git repo (preserves history);
    falls back to ``shutil.move`` otherwise. Idempotent — directories
    that don't exist (already migrated) are skipped silently.
    """
    project_dir = project_dir.expanduser().resolve()
    if not (project_dir / "project.yaml").is_file():
        raise click.ClickException(
            f"{project_dir} doesn't look like a tripwire project "
            "(no project.yaml at the root)."
        )

    is_git_repo = (project_dir / ".git").exists()

    moved: list[tuple[str, str]] = []
    skipped: list[str] = []

    for src_rel, dest_rel in _TEMPLATE_RENAMES:
        src = project_dir / src_rel
        dest = project_dir / dest_rel

        if not src.exists():
            skipped.append(f"{src_rel} (not present — already migrated or never created)")
            continue

        if dest.exists():
            raise click.ClickException(
                f"Cannot migrate {src_rel}/ → {dest_rel}/ — destination "
                f"already exists. Manual cleanup required: inspect "
                f"{dest} and merge or remove before retrying."
            )

        # Ensure parent (templates/) exists.
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dry_run:
            click.echo(f"[dry-run] would move: {src_rel}/ → {dest_rel}/")
            moved.append((src_rel, dest_rel))
            continue

        if is_git_repo:
            try:
                subprocess.run(
                    ["git", "mv", str(src), str(dest)],
                    cwd=project_dir,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as exc:
                raise click.ClickException(
                    f"git mv {src_rel} {dest_rel} failed: "
                    f"{exc.stderr.decode('utf-8', errors='replace').strip()}"
                ) from exc
        else:
            shutil.move(str(src), str(dest))

        moved.append((src_rel, dest_rel))
        click.echo(f"moved {src_rel}/ → {dest_rel}/")

    # Summary
    if not moved and not skipped:
        click.echo("Nothing to migrate.")
        return

    if dry_run:
        click.echo(f"\n{len(moved)} dir(s) would be moved (dry run — no changes).")
        return

    if moved:
        click.echo(f"\nMigrated {len(moved)} dir(s).")
        if is_git_repo:
            click.echo(
                "Review with `git status` and commit when satisfied. "
                "Run `tripwire validate` to confirm the project loads."
            )
        else:
            click.echo("Run `tripwire validate` to confirm the project loads.")
    if skipped:
        click.echo(f"\nSkipped {len(skipped)} dir(s):")
        for s in skipped:
            click.echo(f"  - {s}")


__all__ = ["migrate_cmd"]
