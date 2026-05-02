"""JitPrompt station registration (KUI-121).

Each JitPrompt subclass declares its workflow + station via a class-level
``at = ("workflow", "station")`` attribute. The loader registers the
mapping with the workflow registry at instantiation time, so the gate
runner (KUI-159) and drift detector (KUI-124) can ask "what JIT prompts
should fire at this station?"
"""

from __future__ import annotations

from pathlib import Path

from tripwire._internal.jit_prompts import JitPrompt
from tripwire._internal.jit_prompts.self_review import SelfReviewJitPrompt


def test_self_review_jit_prompt_declares_at() -> None:
    """The first canonical JIT prompt — self-review — declares its station."""
    assert hasattr(SelfReviewJitPrompt, "at")
    workflow, station = SelfReviewJitPrompt.at
    assert workflow == "coding-session"
    assert station == "verified"


def test_loading_registry_populates_jit_prompt_station(tmp_path: Path) -> None:
    """Loading the manifest must call ``register_jit_prompt_status`` for
    each JitPrompt whose class declares ``at``."""
    from tripwire._internal.jit_prompts.loader import load_jit_prompt_registry
    from tripwire.core.workflow.registry import (
        jit_prompts_for_status,
        known_jit_prompt_ids,
    )

    # Minimal project.yaml so load_jit_prompt_registry's load_project succeeds.
    (tmp_path / "project.yaml").write_text(
        "name: test\nkey_prefix: TST\nbase_branch: main\nstatuses: [planned]\n"
        "status_transitions:\n  planned: []\nrepos: {}\nnext_issue_number: 1\n"
        "next_session_number: 1\n",
        encoding="utf-8",
    )
    load_jit_prompt_registry(tmp_path)
    assert "self-review" in known_jit_prompt_ids()
    assert "self-review" in jit_prompts_for_status("coding-session", "verified")


def test_jit_prompt_base_class_accepts_at_attribute() -> None:
    """Subclasses can declare ``at = (workflow, station)`` without
    triggering the missing-attr check (id, fires_on still required)."""

    class StationJitPrompt(JitPrompt):
        id = "station-test"
        fires_on = "test.event"
        at = ("test-workflow", "test-station")

        def fire(self, ctx):
            return "test"

        def is_acknowledged(self, ctx):
            return True

    instance = StationJitPrompt()
    assert instance.at == ("test-workflow", "test-station")
