"""Slash command bodies must not reference removed commands or CLI verbs.

The pre-v0.7 forwarder commands (`/pm-handoff`, `/pm-close`, `/pm-update`,
`/pm-plan`) were removed in the v0.9 prune (KUI-158). This test guards
against regressions where prose in any current `pm-*` command mentions
those names again.
"""

from pathlib import Path

COMMANDS_DIR = (
    Path(__file__).parent.parent.parent / "src" / "tripwire" / "templates" / "commands"
)

FORBIDDEN_IN_REGULAR = {
    "tripwire workspace new-project",  # replaced by tripwire init --workspace (v0.6b)
    "/pm-handoff",
    "/pm-close",
    "/pm-update",
    "/pm-plan",
}


def test_no_command_references_deprecated_tokens():
    for path in COMMANDS_DIR.glob("pm-*.md"):
        text = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_IN_REGULAR:
            assert forbidden not in text, (
                f"{path.name}: references deprecated token {forbidden!r}"
            )
