# Keel backlog

Features evaluated in the v0.1 planning cycle but deferred.
See `docs/similar-tools.md` for the full analysis behind each.

## Future (revisit with evidence)

### F3: `keel timeline` — Fossil-style interleaved log
Chronological interleaving of git commits + issue/node/session
changes. Needs git-diff correlation work. Ship when corpus scale
justifies it.

### F17: Skill/methodology registry
Versioned reusable PM methodologies (startup-lean, enterprise-
compliance). Revisit after at least one external team uses Keel
in production.

### Selector grammar extensions (F9 v2)
Unions, negations, parenthesized expressions, cross-entity selectors.
Revisit after v0.1 selector usage patterns emerge.

### Container-native execution + verification skills
Full container delegation with execution/verification skills loaded
per-container. Depends on `keel.containers` infrastructure. See
SKILL.md delegation model section for the design intent.

### `keel plan` full workflow intent abstraction (F15 v2)
Refactor all PM workflows to separate intent from I/O via a
WorkflowIntent dataclass. Allows plan/apply for any workflow, not
just brief. Revisit when multiple workflows need dry-run support.

## Explicitly skipped

### F1: Property drawers (arbitrary metadata on entities)
Weakens the strict-schema bet. No user has requested it. If a
concrete use case emerges, model it as a new typed field on the
relevant entity kind instead of a generic drawer.

### F16: Explicit drift category in validator
Subsumed by F11 (named validator categories). Not a separate feature.
