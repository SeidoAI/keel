"""Tests for `tripwire.ui.services.role_gate`.

KUI-100 — see `docs/specs/2026-04-26-v08-handoff.md` §2.5 for the
PM-mode header check + redaction contract.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from tripwire.ui.services.role_gate import (
    PROMPT_REDACTED_PLACEHOLDER,
    is_pm,
    redact_tripwire_prompt,
    role_from_headers,
)


def _request_with_headers(headers: dict[str, str]) -> Request:
    """Build a minimal Starlette Request with the given headers."""
    encoded = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": encoded,
        "query_string": b"",
    }
    return Request(scope)


def test_role_from_headers_returns_pm_when_header_set() -> None:
    req = _request_with_headers({"X-Tripwire-Role": "pm"})
    assert role_from_headers(req) == "pm"


def test_role_from_headers_is_case_insensitive_value() -> None:
    req = _request_with_headers({"X-Tripwire-Role": "PM"})
    assert role_from_headers(req) == "pm"


def test_role_from_headers_default_executor_when_missing() -> None:
    req = _request_with_headers({})
    assert role_from_headers(req) == "executor"


def test_role_from_headers_default_executor_for_unknown_role() -> None:
    req = _request_with_headers({"X-Tripwire-Role": "anonymous"})
    assert role_from_headers(req) == "executor"


def test_is_pm_true_for_pm_header() -> None:
    req = _request_with_headers({"X-Tripwire-Role": "pm"})
    assert is_pm(req) is True


def test_is_pm_false_when_no_header() -> None:
    req = _request_with_headers({})
    assert is_pm(req) is False


def test_redact_tripwire_prompt_returns_none_for_non_pm() -> None:
    revealed, redacted = redact_tripwire_prompt(
        prompt="full secret prompt body",
        is_pm_role=False,
    )
    assert revealed is None
    assert redacted == PROMPT_REDACTED_PLACEHOLDER


def test_redact_tripwire_prompt_reveals_for_pm() -> None:
    revealed, redacted = redact_tripwire_prompt(
        prompt="full secret prompt body",
        is_pm_role=True,
    )
    assert revealed == "full secret prompt body"
    assert redacted == PROMPT_REDACTED_PLACEHOLDER


def test_redact_tripwire_prompt_handles_none_input() -> None:
    revealed, redacted = redact_tripwire_prompt(prompt=None, is_pm_role=False)
    assert revealed is None
    assert redacted == PROMPT_REDACTED_PLACEHOLDER


@pytest.mark.parametrize(
    "header_name",
    ["X-Tripwire-Role", "x-tripwire-role", "X-TRIPWIRE-ROLE"],
)
def test_role_from_headers_header_name_case_insensitive(header_name: str) -> None:
    req = _request_with_headers({header_name: "pm"})
    assert role_from_headers(req) == "pm"
