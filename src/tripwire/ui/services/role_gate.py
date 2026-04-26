"""PM-mode role detection + redaction helpers.

The Tripwire UI surfaces the same `/api` endpoints to executor and PM
viewers. PM-mode unhides a small handful of fields (most notably
tripwire prompt bodies and private review comments). The check is *not*
security: it's the same posture as the rest of the app — semantic
separation, not authentication. The PM toggle is gated by the
`X-Tripwire-Role: pm` request header (with a `?role=pm` URL fallback
implemented at the route layer if needed).

See `docs/specs/2026-04-26-v08-handoff.md` §2.5.
"""

from __future__ import annotations

from typing import Literal

from starlette.requests import Request

ROLE_HEADER = "x-tripwire-role"
"""Lowercased canonical header name. Starlette normalises on lookup."""

PROMPT_REDACTED_PLACEHOLDER = "<<tripwire prompt — content hidden>>"
"""String returned in `prompt_redacted` for both PM and non-PM viewers."""

Role = Literal["pm", "executor"]


def role_from_headers(request: Request) -> Role:
    """Return the request's effective role.

    Currently only ``pm`` is recognised — every other value (including a
    missing header) defaults to ``executor``. Header lookup is
    case-insensitive in both name (Starlette normalises) and value (we
    lowercase before comparing) so `X-Tripwire-Role: PM` works.
    """
    raw = request.headers.get(ROLE_HEADER)
    if raw is None:
        return "executor"
    if raw.strip().lower() == "pm":
        return "pm"
    return "executor"


def is_pm(request: Request) -> bool:
    """Convenience predicate — true iff `role_from_headers(request) == "pm"`."""
    return role_from_headers(request) == "pm"


def redact_tripwire_prompt(
    *,
    prompt: str | None,
    is_pm_role: bool,
) -> tuple[str | None, str]:
    """Return ``(prompt_revealed, prompt_redacted)`` for one tripwire row.

    Mirrors the ``/api/workflow`` field shape: ``prompt_revealed`` is the
    full string when the caller is PM, ``None`` otherwise. The redacted
    placeholder is constant — frontends render it verbatim so the grid
    can show "[hidden]" without coupling to per-tripwire copy.
    """
    revealed = prompt if (is_pm_role and prompt is not None) else None
    return revealed, PROMPT_REDACTED_PLACEHOLDER


__all__ = [
    "PROMPT_REDACTED_PLACEHOLDER",
    "ROLE_HEADER",
    "Role",
    "is_pm",
    "redact_tripwire_prompt",
    "role_from_headers",
]
