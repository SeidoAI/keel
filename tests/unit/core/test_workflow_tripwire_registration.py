"""Tripwire station registration (KUI-121).

Each Tripwire subclass declares its workflow + station via a class-level
``at = ("workflow", "station")`` attribute. The loader registers the
mapping with the workflow registry at instantiation time, so the gate
runner (KUI-159) and drift detector (KUI-124) can ask "what tripwires
should fire at this station?"
"""

from __future__ import annotations

from pathlib import Path

from tripwire._internal.tripwires import Tripwire
from tripwire._internal.tripwires.self_review import SelfReviewTripwire


def test_self_review_tripwire_declares_at() -> None:
    """The first canonical tripwire — self-review — declares its station."""
    assert hasattr(SelfReviewTripwire, "at")
    workflow, station = SelfReviewTripwire.at
    assert workflow == "coding-session"
    assert station == "verified"


def test_loading_registry_populates_tripwire_station(tmp_path: Path) -> None:
    """Loading the manifest must call ``register_tripwire_station`` for
    each Tripwire whose class declares ``at``."""
    from tripwire._internal.tripwires.loader import load_registry
    from tripwire.core.workflow.registry import (
        known_tripwire_ids,
        tripwires_for_station,
    )

    # Minimal project.yaml so load_registry's load_project succeeds.
    (tmp_path / "project.yaml").write_text(
        "name: test\nkey_prefix: TST\nbase_branch: main\nstatuses: [planned]\n"
        "status_transitions:\n  planned: []\nrepos: {}\nnext_issue_number: 1\n"
        "next_session_number: 1\n",
        encoding="utf-8",
    )
    load_registry(tmp_path)
    assert "self-review" in known_tripwire_ids()
    assert "self-review" in tripwires_for_station("coding-session", "verified")


def test_tripwire_base_class_accepts_at_attribute() -> None:
    """Subclasses can declare ``at = (workflow, station)`` without
    triggering the missing-attr check (id, fires_on still required)."""

    class StationTripwire(Tripwire):
        id = "station-test"
        fires_on = "test.event"
        at = ("test-workflow", "test-station")

        def fire(self, ctx):
            return "test"

        def is_acknowledged(self, ctx):
            return True

    instance = StationTripwire()
    assert instance.at == ("test-workflow", "test-station")
