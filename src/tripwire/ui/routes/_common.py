"""Shared error envelope + exception handler for v1 `/api/*` routes.

Every v1 route surfaces the same flat error body so the frontend's
`ApiError` helper can rely on it::

    {"detail": <human-readable string>,
     "code": <machine-parseable slash-namespaced code>,
     "hint": <optional guidance>}

Usage from a route::

    from tripwire.ui.routes._common import envelope_exception

    raise envelope_exception(404, code="project/not_found",
                             detail=f"Project {pid!r} not found")

The `install_error_handlers` function wires a Starlette-level handler
that flattens envelope-shaped `HTTPException.detail` dicts to top-level
JSON. Non-envelope exceptions (plain string details, v2 stub nested
envelopes with `extras`) pass through to FastAPI's default behaviour
so pre-existing shapes are preserved.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import http_exception_handler as _default_handler
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorEnvelope(BaseModel):
    """Canonical v1 error body: `{detail, code, hint?}`.

    Exposed mainly for OpenAPI docs — routes don't construct it directly;
    they raise via :func:`envelope_exception`.
    """

    detail: str
    code: str
    hint: str | None = None


class _V1Envelope(dict):
    """Marker dict subclass recognised by the handler as a flat-envelope body.

    The sentinel distinguishes v1 envelopes from the v2 stub's
    intentionally-nested `{detail, code, extras}` shape, so the handler
    flattens the former while leaving the latter untouched.
    """


def envelope_exception(
    status_code: int,
    *,
    code: str,
    detail: str,
    hint: str | None = None,
) -> HTTPException:
    """Build an :class:`HTTPException` carrying a flat v1 envelope body.

    The returned exception is meant to be ``raise``d from a route or
    dependency. The handler installed via :func:`install_error_handlers`
    serialises the envelope to the top-level response body.
    """
    body = _V1Envelope({"detail": detail, "code": code})
    if hint is not None:
        body["hint"] = hint
    return HTTPException(status_code=status_code, detail=body)


async def _handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Flatten v1 envelopes; delegate everything else to FastAPI's default.

    A v1 envelope is identified by the :class:`_V1Envelope` marker —
    not a key shape check — so dict details that happen to contain
    ``detail``/``code`` keys (e.g. v2 stubs with ``extras``) pass
    through to the default handler untouched.
    """
    if isinstance(exc.detail, _V1Envelope):
        return JSONResponse(
            status_code=exc.status_code,
            content=dict(exc.detail),
            headers=getattr(exc, "headers", None),
        )
    return await _default_handler(request, exc)


def install_error_handlers(app: FastAPI) -> None:
    """Register the envelope-flattening HTTPException handler on *app*.

    Idempotent — safe to call multiple times (the handler registry is
    a dict keyed by exception class).
    """
    app.add_exception_handler(StarletteHTTPException, _handler)


__all__ = [
    "ErrorEnvelope",
    "envelope_exception",
    "install_error_handlers",
]
