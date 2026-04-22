"""TmuxRuntime — manages an interactive claude inside a tmux session.

Uses tmux for the live-attach story. Launches
``claude --name <slug> --session-id <uuid>`` (no ``-p``) inside
``tmux new-session -d -s tw-<id>``, polls for claude's ready prompt
via ``tmux capture-pane``, then delivers the kickoff prompt with
``tmux send-keys``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime, timezone

import click

from tripwire.core.spawn_config import build_claude_args
from tripwire.models.session import AgentSession
from tripwire.runtimes.base import (
    AttachCommand,
    AttachExec,
    AttachInstruction,
    PreppedSession,
    RuntimeStartResult,
    RuntimeStatus,
)

# Default marker that signals claude's interactive prompt is ready to
# receive input. Must be empirically verified against the claude
# version you're running — the prompt UI has shifted between releases
# (past values include "> ", "│ ", and box-drawing prefixes). Override
# at launch time via TRIPWIRE_TMUX_READY_MARKER.
#
# Note: ``tmux capture-pane`` strips trailing whitespace per line, so
# a marker ending with a space won't match — prefer a distinctive
# non-whitespace-terminated substring.
#
# To verify locally:
#   tmux new-session -d -s probe -- claude
#   sleep 5
#   tmux capture-pane -pt probe | tail -3
#   tmux kill-session -t probe
#
# Pick the trailing substring of the prompt line that's stable
# (appearing on every ready prompt), without trailing whitespace.
_DEFAULT_READY_MARKER = "> "
_DEFAULT_READY_POLL_INTERVAL = 0.25
_DEFAULT_READY_TIMEOUT = 10.0

# Module-level binds kept for tests that monkeypatch these names
# directly (e.g. tests/unit/test_runtimes_tmux.py patches
# ``tripwire.runtimes.tmux._READY_TIMEOUT`` for fast-timeout tests).
# Runtime lookups below prefer the env var, falling back to these.
_READY_MARKER = _DEFAULT_READY_MARKER
_READY_POLL_INTERVAL = _DEFAULT_READY_POLL_INTERVAL
_READY_TIMEOUT = _DEFAULT_READY_TIMEOUT


def _current_ready_marker() -> str:
    return os.environ.get("TRIPWIRE_TMUX_READY_MARKER") or _READY_MARKER


def _current_poll_interval() -> float:
    env = os.environ.get("TRIPWIRE_TMUX_READY_POLL_INTERVAL")
    return float(env) if env else _READY_POLL_INTERVAL


def _current_timeout() -> float:
    env = os.environ.get("TRIPWIRE_TMUX_READY_TIMEOUT")
    return float(env) if env else _READY_TIMEOUT


def _tmux_session_name(session_id: str) -> str:
    return f"tw-{session_id}"


def _wait_for_ready(session_name: str) -> None:
    """Poll `tmux capture-pane` until claude's ready prompt appears.
    Raises RuntimeError on timeout. Env vars TRIPWIRE_TMUX_READY_MARKER
    / TRIPWIRE_TMUX_READY_POLL_INTERVAL / TRIPWIRE_TMUX_READY_TIMEOUT
    are read on each invocation."""
    marker = _current_ready_marker()
    poll_interval = _current_poll_interval()
    timeout = _current_timeout()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            out = subprocess.run(
                ["tmux", "capture-pane", "-pt", session_name],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except subprocess.SubprocessError:
            out = None
        if out is not None and marker in out.stdout:
            return
        time.sleep(poll_interval)
    raise RuntimeError(
        "claude did not reach ready prompt within "
        f"{int(timeout)}s. tmux session is still running — "
        "attach with 'tripwire session attach <id>' and paste the "
        "prompt from <code-worktree>/.tripwire/kickoff.md."
    )


class TmuxRuntime:
    name = "tmux"

    def validate_environment(self) -> None:
        if shutil.which("tmux") is None:
            raise click.ClickException(
                "tmux runtime requires tmux on PATH. "
                "Install tmux or set spawn_config.invocation.runtime: manual."
            )

    def start(self, prepped: PreppedSession) -> RuntimeStartResult:
        session_name = _tmux_session_name(prepped.session_id)

        # Kill any pre-existing tmux session with the same name (e.g. a
        # previous spawn that was paused at the tmux layer). Idempotent.
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            check=False,
            capture_output=True,
        )

        claude_args = build_claude_args(
            prepped.spawn_defaults,
            prompt=None,
            interactive=True,
            system_append=prepped.system_append,
            session_id=prepped.session_id,
            claude_session_id=prepped.claude_session_id,
            resume=prepped.resume,
        )

        subprocess.run(
            [
                "tmux", "new-session", "-d",
                "-s", session_name,
                "-c", str(prepped.code_worktree),
                "--",
                *claude_args,
            ],
            check=True,
        )

        _wait_for_ready(session_name)

        # Deliver the prompt via tmux paste-buffer, not send-keys. Embedded
        # newlines in send-keys are interpreted as Enter keystrokes and
        # would submit partial prompts to claude. load-buffer + paste-buffer
        # injects the whole string into the pane verbatim; a separate
        # send-keys Enter submits at the end.
        subprocess.run(
            ["tmux", "load-buffer", "-"],
            input=prepped.prompt.encode("utf-8"),
            check=True,
        )
        subprocess.run(
            ["tmux", "paste-buffer", "-t", session_name],
            check=True,
        )
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            check=True,
        )

        return RuntimeStartResult(
            claude_session_id=prepped.claude_session_id,
            worktrees=prepped.worktrees,
            started_at=datetime.now(tz=timezone.utc).isoformat(),
            tmux_session_name=session_name,
        )

    def pause(self, session: AgentSession) -> None:
        name = session.runtime_state.tmux_session_name
        if not name:
            raise RuntimeError(
                f"Session '{session.id}' has no tmux_session_name in runtime_state."
            )
        subprocess.run(
            ["tmux", "send-keys", "-t", name, "C-c"],
            check=False,
        )

    def abandon(self, session: AgentSession) -> None:
        name = session.runtime_state.tmux_session_name
        if not name:
            return
        subprocess.run(
            ["tmux", "kill-session", "-t", name],
            check=False,
        )

    def status(self, session: AgentSession) -> RuntimeStatus:
        name = session.runtime_state.tmux_session_name
        if not name:
            return "unknown"
        rc = subprocess.run(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
        ).returncode
        return "running" if rc == 0 else "exited"

    def attach_command(self, session: AgentSession) -> AttachCommand:
        name = session.runtime_state.tmux_session_name
        if not name:
            return AttachInstruction(
                message=(
                    f"Session '{session.id}' has no tmux session recorded. "
                    "The tmux session may not have been created, or "
                    "'tripwire session cleanup' has removed the runtime state."
                )
            )
        return AttachExec(argv=["tmux", "attach", "-t", name])
