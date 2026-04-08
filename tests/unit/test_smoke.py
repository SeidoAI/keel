"""Smoke test — verifies the package is importable and reports its version.

Replaced/supplemented by real unit tests in subsequent steps.
"""

import agent_project


def test_package_imports() -> None:
    assert agent_project.__version__ == "0.1.0"
