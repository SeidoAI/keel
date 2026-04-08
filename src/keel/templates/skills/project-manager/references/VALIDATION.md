# Validation Gate

`keel validate` is the single most important command you run.
It's the gate you must pass after every batch of file writes before
declaring any work done.

## The one command

```bash
keel validate --strict --format=json
```

- `--strict` promotes warnings to errors (your normal mode)
- `--format=json` gives you a structured report you can parse

It always rebuilds `graph/index.yaml` as a side effect. No separate
`refs rebuild` needed.

## Exit codes

- **0** — clean
- **1** — warnings only (only possible without `--strict`)
- **2** — one or more errors

Your loop is: write files → validate → fix errors → validate → fix
errors → validate → exit 0 → commit.

## JSON output schema

```json
{
  "version": 1,
  "exit_code": 2,
  "summary": {
    "errors": 3,
    "warnings": 1,
    "fixed": 0,
    "cache_rebuilt": true,
    "duration_ms": 42
  },
  "errors": [
    {
      "code": "ref/dangling",
      "severity": "error",
      "file": "issues/SEI-42.yaml",
      "line": 18,
      "field": "body",
      "message": "Reference [[user-modle]] does not resolve to any node or issue.",
      "fix_hint": "Did you mean [[user-model]]? Or create a node 'user-modle' in graph/nodes/."
    }
  ],
  "warnings": [],
  "fixed": []
}
```

Parse the `errors` array. For each error:

1. `file` tells you which file has the problem
2. `field` tells you which frontmatter field (or `body`)
3. `message` is a human-readable description
4. `fix_hint` is a suggested fix (not always present)
5. `code` is the stable error identifier

Fix the file, re-run, continue.

## Error codes you'll see often

### Schema errors
- `schema/project_missing` — `project.yaml` not found. Run `init`.
- `schema/project_invalid` — `project.yaml` doesn't parse or match the model.
- `issue/parse_error` — frontmatter+body parser failed on an issue file.
- `issue/schema_invalid` — fields don't match the Issue model (wrong
  types, missing required, extra fields).
- `node/schema_invalid`, `session/schema_invalid` — same for nodes, sessions.

### UUID and ID errors
- `uuid/missing` — entity has no `uuid` field. Add a uuid4.
- `id/format` — issue id isn't in `<PREFIX>-<N>` form.
- `id/wrong_prefix` — issue id has the wrong prefix (compare with
  `project.yaml.key_prefix`).

### Enum errors
- `enum/issue_status`, `enum/priority`, `enum/executor`, `enum/verifier`,
  `enum/node_type`, `enum/node_status`, `enum/session_status`,
  `enum/agent_state`, `enum/comment_type` — value not in the active enum.
  Check `enums/<name>.yaml`.

### Reference errors
- `ref/dangling` — `[[reference]]` doesn't resolve to a node or issue.
- `ref/blocked_by` — `blocked_by: [X]` references a non-existent issue.
- `ref/parent` — `parent: X` references a non-existent issue.
- `ref/related` — node `related: [X]` references a non-existent node.
- `ref/repo` — a repo isn't declared in `project.yaml.repos`.
- `ref/session_issue` — session `issues: [X]` references a non-existent issue.
- `ref/session_agent` — session `agent: X` has no matching file in `agents/`.
- `ref/comment_issue` — comment `issue_key: X` references a non-existent issue.

### Body structure (warnings)
- `body/missing_heading` — required Markdown section missing.
- `body/no_acceptance_checkbox` — Acceptance criteria has no `- [ ]` items.
- `body/no_stop_and_ask` — body missing "stop and ask" guidance.
- `body/no_references` — issue has zero concept node references (coherence gap).

### Bi-directional (warnings)
- `bidi/related` — node A declares `related: [B]` but B doesn't
  reciprocate. Auto-fixable.

### Status, freshness, artifacts
- `status/unreachable` — issue status not reachable from `backlog` via
  declared transitions.
- `freshness/source_missing` — active node with a source, file can't
  be fetched.
- `freshness/stale` — node's `content_hash` doesn't match the live
  content (warning).
- `artifact/missing` — completed session missing a required artifact.

### Counters and timestamps
- `sequence/drift` — `next_issue_number` behind max existing key
  (warning, auto-fixable).
- `timestamp/missing` — `created_at` or `updated_at` missing (warning,
  auto-fixable from mtime).
- `timestamp/invalid` — timestamp isn't parseable as ISO datetime.

### Collisions
- `collision/id` — two files claim the same id with different uuids.

### Cache
- `cache/rebuild_failed` — the cache couldn't be rebuilt (warning).

## Auto-fix (`--fix`)

```bash
keel validate --strict --fix --format=json
```

Safely repairs:

- Missing `created_at` / `updated_at` — filled from file mtime
- Drifted `next_issue_number` — bumped past max existing key
- Missing `uuid` — uuid4 generated and added
- Bi-directional `related` mismatches — missing side added
- Sorted-list normalisation — `labels`, `related`, `tags` sorted
- Stale graph cache — rebuilt

Does NOT touch:

- Issue body content (no field invention)
- Reference targets (you decide what to reference)
- Anything that affects semantic intent

After a `--fix` pass, re-run `validate` without `--fix` to confirm
the project is clean.

## The iteration loop

```
write files
validate → N errors
fix errors based on JSON output
validate → M errors (M < N)
fix errors
validate → 0 errors
commit
```

If you find yourself stuck (same error recurring), you've probably
misread the schema. Re-read the relevant `SCHEMA_*.md` and the
matching example file.

## See also

- `SCHEMA_*.md` — the schemas the validator checks against
- `ANTI_PATTERNS.md` — common mistakes that trigger errors
- `REFERENCES.md` — `[[ref]]` resolution rules
