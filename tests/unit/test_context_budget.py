"""Context budget tests — ensure keel-sourced content stays within bounds.

The PM skill is the single largest source of agent context. These tests
measure the total size of everything keel ships into a project and fail
if it exceeds a budget. This prevents accidental context bloat.

Budget rationale: the PM agent in v0.2 consumed ~160k tokens after
`keel init`, leaving ~40k for actual work in a 200k window. Planning
docs are user content (out of our control), but keel-sourced context
is ours to manage.
"""

from __future__ import annotations

from pathlib import Path

from keel.templates import get_templates_dir

TEMPLATES_DIR = get_templates_dir()


def _total_chars(directory: Path) -> int:
    """Sum of all text file sizes under a directory."""
    total = 0
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".yaml", ".j2", ".py"):
            total += len(f.read_text(encoding="utf-8"))
    return total


def _total_lines(directory: Path) -> int:
    """Sum of all text file lines under a directory."""
    total = 0
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".yaml", ".j2", ".py"):
            total += len(f.read_text(encoding="utf-8").splitlines())
    return total


# ============================================================================
# PM skill budget
# ============================================================================


def test_pm_skill_total_size_under_budget() -> None:
    """The PM skill (SKILL.md + references + examples) must stay under 130KB.

    v0.2 was ~106KB. Budget allows ~25% growth before alarm.
    """
    pm_dir = TEMPLATES_DIR / "skills" / "project-manager"
    total = _total_chars(pm_dir)
    assert total < 130_000, (
        f"PM skill is {total:,} chars ({total / 1024:.0f} KB). "
        f"Budget is 130KB. Consolidate or trim reference docs."
    )


def test_pm_skill_md_under_budget() -> None:
    """SKILL.md itself should stay under 20KB.

    It's the one file agents reliably read. Keep it focused.
    """
    skill_md = TEMPLATES_DIR / "skills" / "project-manager" / "SKILL.md"
    size = len(skill_md.read_text(encoding="utf-8"))
    assert size < 20_000, (
        f"SKILL.md is {size:,} chars ({size / 1024:.0f} KB). "
        f"Budget is 20KB. Move detail to reference docs."
    )


# ============================================================================
# Total init budget
# ============================================================================


def test_total_templates_under_budget() -> None:
    """Everything `keel init` copies must stay under 250KB total.

    v0.2 was ~217KB. Budget allows modest growth.
    """
    total = _total_chars(TEMPLATES_DIR)
    assert total < 250_000, (
        f"Total templates are {total:,} chars ({total / 1024:.0f} KB). Budget is 250KB."
    )


# ============================================================================
# Individual skill budgets
# ============================================================================


def test_each_non_pm_skill_under_budget() -> None:
    """Non-PM skills should each stay under 30KB."""
    skills_dir = TEMPLATES_DIR / "skills"
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name == "project-manager":
            continue
        total = _total_chars(skill_dir)
        assert total < 30_000, (
            f"Skill '{skill_dir.name}' is {total:,} chars ({total / 1024:.0f} KB). "
            f"Budget is 30KB."
        )
