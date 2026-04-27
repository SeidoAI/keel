"""Tests for tripwire.ui.services.inbox_service."""

from __future__ import annotations

from pathlib import Path

from tripwire.core import paths
from tripwire.ui.services.inbox_service import (
    InboxItem,
    get_inbox_entry,
    list_inbox,
    resolve_inbox_entry,
)


def _write_entry(
    project_dir: Path,
    entry_id: str,
    *,
    bucket: str = "blocked",
    title: str = "test entry",
    body: str = "body text",
    references: str = "",
    resolved: bool = False,
    created_at: str = "2026-04-27T10:00:00Z",
) -> Path:
    """Drop a fixture inbox file under ``<project>/inbox/<id>.md``."""
    inbox = paths.inbox_dir(project_dir)
    inbox.mkdir(exist_ok=True)
    refs_yaml = f"\nreferences:\n{references}" if references else "\nreferences: []"
    text = (
        "---\n"
        f"id: {entry_id}\n"
        "uuid: 12345678-1234-4123-8123-123456789abc\n"
        f"created_at: {created_at}\n"
        "author: pm-agent\n"
        f"bucket: {bucket}\n"
        f"title: {title}\n"
        f"{refs_yaml}\n"
        f"resolved: {str(resolved).lower()}\n"
        "---\n"
        f"{body}\n"
    )
    path = inbox / f"{entry_id}.md"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# list_inbox
# ---------------------------------------------------------------------------


class TestListInbox:
    def test_empty_when_no_inbox_dir(self, tmp_path_project: Path):
        # Missing inbox/ directory is the normal case for a project
        # the PM agent hasn't escalated anything in yet.
        assert list_inbox(tmp_path_project) == []

    def test_returns_all_entries_newest_first(self, tmp_path_project: Path):
        _write_entry(
            tmp_path_project,
            "inb-old",
            title="older",
            created_at="2026-04-25T10:00:00Z",
        )
        _write_entry(
            tmp_path_project,
            "inb-new",
            title="newer",
            created_at="2026-04-27T10:00:00Z",
        )
        result = list_inbox(tmp_path_project)
        assert [i.id for i in result] == ["inb-new", "inb-old"]
        assert all(isinstance(i, InboxItem) for i in result)

    def test_filter_by_bucket(self, tmp_path_project: Path):
        _write_entry(tmp_path_project, "inb-a", bucket="blocked")
        _write_entry(tmp_path_project, "inb-b", bucket="fyi")
        assert [i.id for i in list_inbox(tmp_path_project, bucket="blocked")] == [
            "inb-a"
        ]
        assert [i.id for i in list_inbox(tmp_path_project, bucket="fyi")] == ["inb-b"]

    def test_filter_by_resolved(self, tmp_path_project: Path):
        _write_entry(tmp_path_project, "inb-open", resolved=False)
        _write_entry(tmp_path_project, "inb-done", resolved=True)
        assert [i.id for i in list_inbox(tmp_path_project, resolved=False)] == [
            "inb-open"
        ]
        assert [i.id for i in list_inbox(tmp_path_project, resolved=True)] == [
            "inb-done"
        ]

    def test_skips_unparseable_files(self, tmp_path_project: Path):
        # One bad file shouldn't take down the whole list.
        _write_entry(tmp_path_project, "inb-good")
        inbox = paths.inbox_dir(tmp_path_project)
        (inbox / "inb-bad.md").write_text(
            "not even close to valid yaml", encoding="utf-8"
        )
        result = list_inbox(tmp_path_project)
        assert [i.id for i in result] == ["inb-good"]


# ---------------------------------------------------------------------------
# get_inbox_entry
# ---------------------------------------------------------------------------


class TestGetInboxEntry:
    def test_returns_entry_when_exists(self, tmp_path_project: Path):
        _write_entry(tmp_path_project, "inb-x", title="hello")
        item = get_inbox_entry(tmp_path_project, "inb-x")
        assert item is not None
        assert item.id == "inb-x"
        assert item.title == "hello"

    def test_returns_none_when_missing(self, tmp_path_project: Path):
        assert get_inbox_entry(tmp_path_project, "inb-nope") is None


# ---------------------------------------------------------------------------
# resolve_inbox_entry
# ---------------------------------------------------------------------------


class TestResolveInboxEntry:
    def test_flips_resolved_flag(self, tmp_path_project: Path):
        _write_entry(tmp_path_project, "inb-x", resolved=False)
        result = resolve_inbox_entry(tmp_path_project, "inb-x", resolved_by="alice")
        assert result is not None
        assert result.resolved is True
        assert result.resolved_by == "alice"
        assert result.resolved_at is not None

    def test_persists_to_disk(self, tmp_path_project: Path):
        # Reload after resolve — the on-disk file must reflect the change
        # so a subsequent process sees it (and the file watcher will
        # pick up the modification → broadcast to UI clients).
        _write_entry(tmp_path_project, "inb-x", resolved=False)
        resolve_inbox_entry(tmp_path_project, "inb-x")
        reloaded = get_inbox_entry(tmp_path_project, "inb-x")
        assert reloaded is not None
        assert reloaded.resolved is True

    def test_returns_none_for_missing_entry(self, tmp_path_project: Path):
        assert resolve_inbox_entry(tmp_path_project, "inb-nope") is None

    def test_default_resolved_by_when_unset(self, tmp_path_project: Path):
        _write_entry(tmp_path_project, "inb-x", resolved=False)
        result = resolve_inbox_entry(tmp_path_project, "inb-x", resolved_by=None)
        assert result is not None
        # Defaults to "ui-user" so the field is never null on a
        # resolved entry — keeps audit trail consistent.
        assert result.resolved_by == "ui-user"


# ---------------------------------------------------------------------------
# References serialisation
# ---------------------------------------------------------------------------


class TestReferences:
    def test_references_round_trip_with_keys(self, tmp_path_project: Path):
        # Inline YAML for references — verifies the union-discriminator
        # serialises back to dicts the frontend can switch on.
        refs_yaml = (
            "  - issue: SEI-42\n"
            "  - session: storage-impl\n"
            "  - node: auth-token-endpoint\n"
            "    version: v3\n"
        )
        _write_entry(tmp_path_project, "inb-refs", references=refs_yaml)
        item = get_inbox_entry(tmp_path_project, "inb-refs")
        assert item is not None
        assert item.references == [
            {"issue": "SEI-42"},
            {"session": "storage-impl"},
            {"node": "auth-token-endpoint", "version": "v3"},
        ]

    def test_node_reference_without_version(self, tmp_path_project: Path):
        # Optional fields must be omitted (not null) so the wire shape
        # stays clean — frontend can branch on key presence.
        refs_yaml = "  - node: live-link-node\n"
        _write_entry(tmp_path_project, "inb-x", references=refs_yaml)
        item = get_inbox_entry(tmp_path_project, "inb-x")
        assert item is not None
        assert item.references == [{"node": "live-link-node"}]

    def test_artifact_and_comment_refs_are_nested(self, tmp_path_project: Path):
        # Per SCHEMA_INBOX.md: artifact and comment references nest
        # their fields under a single discriminator key, mirroring how
        # {issue: KEY}, {session: id}, etc. are also single-key shapes.
        # Frontend `describeReferenceDeep` reads `ref.artifact.session`
        # and `ref.comment.issue` — flat shapes would break that switch.
        refs_yaml = (
            "  - artifact:\n"
            "      session: storage-impl\n"
            "      file: plan.md\n"
            "  - comment:\n"
            "      issue: SEI-42\n"
            "      id: cmt-2026-04-26-x9k\n"
        )
        _write_entry(tmp_path_project, "inb-nested", references=refs_yaml)
        item = get_inbox_entry(tmp_path_project, "inb-nested")
        assert item is not None
        assert item.references == [
            {"artifact": {"session": "storage-impl", "file": "plan.md"}},
            {"comment": {"issue": "SEI-42", "id": "cmt-2026-04-26-x9k"}},
        ]
