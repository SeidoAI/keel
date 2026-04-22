"""Tests for TmuxRuntime."""

from unittest.mock import patch

import pytest

from tripwire.models.session import (
    AgentSession,
    RuntimeState,
    WorktreeEntry,
)
from tripwire.models.spawn import SpawnDefaults
from tripwire.runtimes.base import (
    AttachExec,
    AttachInstruction,
    PreppedSession,
)


def _prepped(tmp_path) -> PreppedSession:
    wt = WorktreeEntry(
        repo="SeidoAI/code",
        clone_path=str(tmp_path / "clone"),
        worktree_path=str(tmp_path / "wt"),
        branch="feat/s1",
    )
    (tmp_path / "wt").mkdir()
    return PreppedSession(
        session_id="s1",
        session=AgentSession(id="s1", name="test", agent="a"),
        project_dir=tmp_path,
        code_worktree=tmp_path / "wt",
        worktrees=[wt],
        claude_session_id="uuid-1",
        prompt="DO THE THING",
        system_append="",
        spawn_defaults=SpawnDefaults.model_validate({
            "prompt_template": "{plan}",
            "system_prompt_append": "",
        }),
    )


def test_validate_environment_missing_tmux_raises(monkeypatch):
    from tripwire.runtimes import TmuxRuntime

    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(Exception, match="tmux"):
        TmuxRuntime().validate_environment()


def test_validate_environment_with_tmux_present(fake_tmux_on_path):
    from tripwire.runtimes import TmuxRuntime

    TmuxRuntime().validate_environment()


def test_start_creates_tmux_session_and_sends_keys(
    fake_tmux_on_path, tmp_path
):
    from tripwire.runtimes import TmuxRuntime

    prepped = _prepped(tmp_path)
    fake_tmux_on_path.set_pane_text("Welcome to claude\n> ")

    result = TmuxRuntime().start(prepped)

    calls = fake_tmux_on_path.calls()
    commands = [c[0] for c in calls]
    assert "new-session" in commands
    assert "load-buffer" in commands
    assert "paste-buffer" in commands

    new_session = next(c for c in calls if c[0] == "new-session")
    assert "-s" in new_session
    session_name = new_session[new_session.index("-s") + 1]
    assert session_name.startswith("tw-s1")

    # Prompt is injected via the tmux buffer, not via send-keys.
    assert fake_tmux_on_path.buffer_contents() == "DO THE THING"

    # Final Enter submit after paste.
    enter_call = next(
        c for c in calls if c[0] == "send-keys" and "Enter" in c
    )
    assert enter_call == ["send-keys", "-t", session_name, "Enter"]

    assert result.tmux_session_name == session_name
    assert result.claude_session_id == "uuid-1"


def test_start_timeout_when_ready_prompt_never_appears(
    fake_tmux_on_path, tmp_path
):
    from tripwire.runtimes import TmuxRuntime

    prepped = _prepped(tmp_path)
    fake_tmux_on_path.set_pane_text("still starting...")

    with patch("tripwire.runtimes.tmux._READY_POLL_INTERVAL", 0.01), \
         patch("tripwire.runtimes.tmux._READY_TIMEOUT", 0.05):
        with pytest.raises(Exception, match="did not reach ready prompt"):
            TmuxRuntime().start(prepped)

    calls = fake_tmux_on_path.calls()
    assert any(c[0] == "new-session" for c in calls)
    assert not any(c[0] == "send-keys" for c in calls)


def _session_in_runtime(tmp_path, tmux_name: str = "tw-s1") -> AgentSession:
    return AgentSession(
        id="s1",
        name="test",
        agent="a",
        runtime_state=RuntimeState(
            claude_session_id="uuid-1",
            tmux_session_name=tmux_name,
            worktrees=[
                WorktreeEntry(
                    repo="SeidoAI/code",
                    clone_path=str(tmp_path / "clone"),
                    worktree_path=str(tmp_path / "wt"),
                    branch="feat/s1",
                ),
            ],
        ),
    )


def test_status_running_when_session_exists(fake_tmux_on_path, tmp_path):
    from tripwire.runtimes import TmuxRuntime

    fake_tmux_on_path.mark_session_exists("tw-s1")
    session = _session_in_runtime(tmp_path)

    assert TmuxRuntime().status(session) == "running"


def test_status_exited_when_session_absent(fake_tmux_on_path, tmp_path):
    from tripwire.runtimes import TmuxRuntime

    session = _session_in_runtime(tmp_path)

    assert TmuxRuntime().status(session) == "exited"


def test_pause_sends_ctrl_c(fake_tmux_on_path, tmp_path):
    from tripwire.runtimes import TmuxRuntime

    fake_tmux_on_path.mark_session_exists("tw-s1")
    session = _session_in_runtime(tmp_path)

    TmuxRuntime().pause(session)

    calls = fake_tmux_on_path.calls()
    send_keys = [c for c in calls if c[0] == "send-keys"]
    assert any("C-c" in c for c in send_keys)


def test_abandon_kills_session(fake_tmux_on_path, tmp_path):
    from tripwire.runtimes import TmuxRuntime

    fake_tmux_on_path.mark_session_exists("tw-s1")
    session = _session_in_runtime(tmp_path)

    TmuxRuntime().abandon(session)

    calls = fake_tmux_on_path.calls()
    assert any(c[0] == "kill-session" for c in calls)


def test_attach_command_returns_tmux_attach(fake_tmux_on_path, tmp_path):
    from tripwire.runtimes import TmuxRuntime

    session = _session_in_runtime(tmp_path)
    cmd = TmuxRuntime().attach_command(session)

    assert isinstance(cmd, AttachExec)
    assert cmd.argv[0] == "tmux"
    assert "attach" in cmd.argv
    assert "tw-s1" in cmd.argv


def test_attach_command_with_no_tmux_session_returns_instruction(tmp_path):
    from tripwire.runtimes import TmuxRuntime

    session = AgentSession(id="s1", name="t", agent="a")

    cmd = TmuxRuntime().attach_command(session)

    assert isinstance(cmd, AttachInstruction)
    assert (
        "no tmux session" in cmd.message.lower()
        or "not found" in cmd.message.lower()
    )


def test_start_delivers_multiline_prompt_via_paste_buffer(
    fake_tmux_on_path, tmp_path
):
    """Regression for B3: multi-line prompts (newlines in plan.md) must
    not be typed with send-keys — embedded newlines would submit
    partial prompts. Use load-buffer + paste-buffer + send-keys Enter."""
    from tripwire.runtimes import TmuxRuntime

    wt = WorktreeEntry(
        repo="SeidoAI/code",
        clone_path=str(tmp_path / "clone"),
        worktree_path=str(tmp_path / "wt"),
        branch="feat/s1",
    )
    (tmp_path / "wt").mkdir()
    multiline = "Line 1 of the plan\n\nLine 3 after a blank\nLine 4"
    prepped = PreppedSession(
        session_id="s1",
        session=AgentSession(id="s1", name="test", agent="a"),
        project_dir=tmp_path,
        code_worktree=tmp_path / "wt",
        worktrees=[wt],
        claude_session_id="uuid-1",
        prompt=multiline,
        system_append="",
        spawn_defaults=SpawnDefaults.model_validate({
            "prompt_template": "{plan}",
            "system_prompt_append": "",
        }),
    )
    fake_tmux_on_path.set_pane_text("> ")

    TmuxRuntime().start(prepped)

    calls = fake_tmux_on_path.calls()
    commands = [c[0] for c in calls]
    # load-buffer must be used, not a bare send-keys with the prompt.
    assert "load-buffer" in commands
    assert "paste-buffer" in commands

    # The buffer must contain the full multi-line prompt verbatim.
    assert fake_tmux_on_path.buffer_contents() == multiline

    # send-keys Enter is fired AFTER paste-buffer to submit.
    load_idx = commands.index("load-buffer")
    paste_idx = commands.index("paste-buffer")
    assert load_idx < paste_idx
    # Find the send-keys Enter call
    enter_calls = [
        i for i, c in enumerate(calls)
        if c[0] == "send-keys" and "Enter" in c
    ]
    assert enter_calls, "send-keys Enter must fire after paste-buffer"
    assert enter_calls[-1] > paste_idx

    # The prompt must NOT be passed to send-keys directly — that would
    # reintroduce the multi-line submission bug.
    for c in calls:
        if c[0] == "send-keys":
            assert "Line 3 after a blank" not in " ".join(c)
