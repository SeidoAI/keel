"""Station registry — what runs at each workflow station.

Three sub-registries co-live here so the well-formedness validator can
ask one module for the union of all known refs:

- :func:`known_validator_ids` — populated by the ``@registers_at``
  decorator on validator check functions (KUI-120).
- :func:`known_jit_prompt_ids` — populated by the ``at = (...)`` class
  attribute on :class:`JitPrompt` subclasses (KUI-121).
- :func:`known_prompt_check_ids` — populated by the ``fires_at:``
  frontmatter on PM-skill slash command files (KUI-122).

The validator-id channel is module-import-time (decorator runs when
the check module is loaded). JIT prompts are instance-time (registry
loaded when the manifest is parsed). Prompt-checks are
filesystem-time (the slash command directory is enumerated).

Each accessor is safe to call before its source has populated — it
returns an empty set, which the schema validator treats as "no known
refs declared yet, skip the ref-existence check".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

# ----------------------------------------------------------------------
# Validator station registry (KUI-120)
# ----------------------------------------------------------------------

_validator_stations: dict[str, list[tuple[str, str]]] = {}
"""Maps validator id (`v_<slug>`) → list of (workflow, station) pairs."""

_station_validators: dict[tuple[str, str], list[str]] = defaultdict(list)
"""Inverse: (workflow, station) → list of validator ids registered there."""

F = TypeVar("F", bound=Callable[..., object])


def registers_at(workflow: str, station: str) -> Callable[[F], F]:
    """Decorator marking a validator check function as registered at a station.

    Idempotent across module reloads — a re-import just refreshes the
    registry entry. The decorator returns the function unchanged; only
    side effect is the registry insertion.

    Usage:

    .. code-block:: python

        @registers_at("coding-session", "executing")
        def check_uuid_present(ctx): ...
    """

    def _decorator(fn: F) -> F:
        slug = fn.__name__.removeprefix("check_")
        validator_id = f"v_{slug}"
        pairs = _validator_stations.setdefault(validator_id, [])
        pair = (workflow, station)
        if pair not in pairs:
            pairs.append(pair)
        if validator_id not in _station_validators[pair]:
            _station_validators[pair].append(validator_id)
        # Stash the metadata on the function for introspection.
        try:
            fn.__tripwire_workflow_station__ = pair  # type: ignore[attr-defined]
        except AttributeError:  # pragma: no cover — function-likes
            pass
        return fn

    return _decorator


def known_validator_ids() -> set[str]:
    """Return the set of validator ids registered against any station.

    Empty before KUI-120 wires the decorator on existing check
    functions. The schema validator treats an empty set as "skip the
    ref-existence check".
    """
    return set(_validator_stations.keys())


def validators_for_station(workflow: str, station: str) -> list[str]:
    """Return the validator ids declared at ``(workflow, station)``."""
    return list(_station_validators.get((workflow, station), []))


# ----------------------------------------------------------------------
# JIT prompt station registry (KUI-121)
# ----------------------------------------------------------------------

_jit_prompt_stations: dict[str, tuple[str, str]] = {}
"""Maps JIT prompt id to (workflow, station) declared via class ``at`` attr."""

_station_jit_prompts: dict[tuple[str, str], list[str]] = defaultdict(list)


def register_jit_prompt_station(
    jit_prompt_id: str, workflow: str, station: str
) -> None:
    """Record that ``jit_prompt_id`` is registered at ``(workflow, station)``.

    Called by the JIT prompt loader when it instantiates a JitPrompt whose
    class declares ``at = ("workflow", "station")``. Re-registration
    overwrites the previous mapping (last loader wins) so reloads work.
    """
    _jit_prompt_stations[jit_prompt_id] = (workflow, station)
    pair = (workflow, station)
    if jit_prompt_id not in _station_jit_prompts[pair]:
        _station_jit_prompts[pair].append(jit_prompt_id)


def known_jit_prompt_ids() -> set[str]:
    """Return the set of JIT prompt ids registered against any station."""
    return set(_jit_prompt_stations.keys())


def jit_prompts_for_station(workflow: str, station: str) -> list[str]:
    return list(_station_jit_prompts.get((workflow, station), []))


# ----------------------------------------------------------------------
# Prompt-check station registry (KUI-122)
# ----------------------------------------------------------------------


def known_prompt_check_ids(project_dir: Path) -> set[str]:
    """Return the prompt-check ids declared via slash-command frontmatter.

    Walks the packaged ``templates/commands/`` directory plus the
    project-local ``.tripwire/commands/`` override directory, parses
    each ``*.md`` file's YAML frontmatter, and collects every command
    name that declares a ``fires_at:`` field.

    Empty before KUI-122 adds frontmatter to the existing slash
    commands.
    """
    from tripwire.core.workflow.prompt_checks import collect_prompt_checks

    return {pc.id for pc in collect_prompt_checks(project_dir)}


def prompt_checks_for_station(project_dir: Path, station: str) -> list[str]:
    """Return the prompt-check ids whose ``fires_at:`` matches ``station``.

    Resolution mirrors :func:`known_prompt_check_ids`: project-local
    overrides win over packaged defaults.
    """
    from tripwire.core.workflow.prompt_checks import collect_prompt_checks

    out: list[str] = []
    for pc in collect_prompt_checks(project_dir):
        if pc.fires_at == station and pc.id not in out:
            out.append(pc.id)
    return out


__all__ = [
    "jit_prompts_for_station",
    "known_jit_prompt_ids",
    "known_prompt_check_ids",
    "known_validator_ids",
    "prompt_checks_for_station",
    "register_jit_prompt_station",
    "registers_at",
    "validators_for_station",
]
