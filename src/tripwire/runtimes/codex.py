"""CodexRuntime — launches OpenAI's ``codex exec --json`` via Popen.

Parallel adapter to :class:`ClaudeRuntime`: same ``SessionRuntime``
contract, same SIGTERM-then-SIGKILL pause/abandon semantics, same
log-tail attach mechanism. The differences are confined to:

  - the binary (``codex`` instead of ``claude``)
  - the argv shape (see :func:`tripwire.core.codex_args.build_codex_args`)
  - the auth gate (``OPENAI_API_KEY`` env var or a prior ``codex login``
    that wrote ``~/.codex/auth.json``)
  - the resume path (``codex exec resume <SESSION_ID>`` is a subcommand,
    not a flag)

Lifecycle mechanics live on :class:`BasePopenRuntime`; this file owns only
the auth check and the argv builder.
"""

from __future__ import annotations

import os
from pathlib import Path

from tripwire.runtimes.base import BasePopenRuntime, PreppedSession


def _has_codex_auth() -> bool:
    """Detect whether the host can authenticate to the Codex API.

    Two paths: ``OPENAI_API_KEY`` env var, or a prior ``codex login`` that
    persisted credentials under ``~/.codex/auth.json``. Either is enough."""
    if os.environ.get("OPENAI_API_KEY"):
        return True
    home = os.environ.get("HOME")
    if not home:
        return False
    return (Path(home) / ".codex" / "auth.json").is_file()


class CodexRuntime(BasePopenRuntime):
    name = "codex"

    def validate_environment(self) -> None:
        if not _has_codex_auth():
            raise RuntimeError(
                "Codex runtime requires authentication. Set OPENAI_API_KEY "
                "or run 'codex login --with-api-key' to persist credentials "
                "under ~/.codex/auth.json."
            )

    def _build_argv(self, prepped: PreppedSession) -> list[str]:
        # Imported here to avoid a cycle: codex_args lives under core/
        # and may eventually want to import from runtimes for shared
        # helpers. Keeping the import local sidesteps that risk.
        from tripwire.core.codex_args import build_codex_args

        return build_codex_args(
            prepped.spawn_defaults,
            prompt=prepped.prompt,
            interactive=False,
            system_append=prepped.system_append,
            session_id=prepped.session_id,
            codex_session_id=prepped.claude_session_id,
            resume=prepped.resume,
        )
