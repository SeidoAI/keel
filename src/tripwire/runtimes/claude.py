"""ClaudeRuntime — launches ``claude -p`` via Popen.

Headless by design: claude runs to completion (opens PR, exits) or stops
early with a plain-text question in the log. The human observes via
``tripwire session attach <id>``; there is no mid-run interactive channel.

Lifecycle mechanics (Popen, monitor fork, pause/abandon, attach) live on
:class:`tripwire.runtimes.base.BasePopenRuntime`. This file owns only the
runtime-specific argv builder — see :func:`build_claude_args`.
"""

from __future__ import annotations

from tripwire.core.spawn_config import build_claude_args
from tripwire.runtimes.base import BasePopenRuntime, PreppedSession


class ClaudeRuntime(BasePopenRuntime):
    name = "claude"

    def _build_argv(self, prepped: PreppedSession) -> list[str]:
        return build_claude_args(
            prepped.spawn_defaults,
            prompt=prepped.prompt,
            interactive=False,
            system_append=prepped.system_append,
            session_id=prepped.session_id,
            claude_session_id=prepped.claude_session_id,
            resume=prepped.resume,
            project_dir=prepped.project_dir,
        )
