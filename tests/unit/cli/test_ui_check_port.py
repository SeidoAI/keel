"""Unit tests for `tripwire.cli.ui._check_port` — the single-instance probe.

Lives in its own file so the autouse stub in `test_ui_cmd.py` (which
patches `_check_port` for hermeticity in the CLI-flow tests) doesn't
interfere with calls to the real function.
"""

from __future__ import annotations

from unittest.mock import patch


class TestCheckPort:
    def test_connection_refused_returns_free(self):
        from tripwire.cli.ui import _check_port

        # Port 1 is reserved and almost certainly unbound on localhost,
        # so the probe should return "free" via the connection-refused
        # branch.
        verdict, url = _check_port("127.0.0.1", 1)
        assert verdict == "free"
        assert url == "http://127.0.0.1:1"

    def test_tripwire_response_returns_reuse(self):
        from tripwire.cli.ui import _check_port

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"status": "ok", "service": "tripwire", "version": "0.10.0"}'

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            verdict, _ = _check_port("127.0.0.1", 8000)
        assert verdict == "reuse"

    def test_non_tripwire_json_returns_conflict(self):
        from tripwire.cli.ui import _check_port

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b'{"app": "something-else"}'

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            verdict, _ = _check_port("127.0.0.1", 8000)
        assert verdict == "conflict"

    def test_non_json_response_returns_conflict(self):
        from tripwire.cli.ui import _check_port

        class _FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return b"<html>not us</html>"

        with patch("urllib.request.urlopen", return_value=_FakeResponse()):
            verdict, _ = _check_port("127.0.0.1", 8000)
        assert verdict == "conflict"
