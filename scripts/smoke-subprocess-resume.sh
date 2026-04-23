#!/usr/bin/env bash
# Real-claude smoke test for the subprocess resume flow.
#
# Forces a stop-and-ask (plan.md asks an unanswerable question),
# then adds a "## PM follow-up" section and re-spawns with --resume.
# Asserts the agent picks up prior context after resume.
#
# Usage: bash scripts/smoke-subprocess-resume.sh
# Env:   TW_SMOKE_TIMEOUT  seconds to wait for each spawn (default 180)

set -euo pipefail

TIMEOUT="${TW_SMOKE_TIMEOUT:-180}"

for bin in claude tripwire git; do
  if ! command -v "$bin" >/dev/null; then
    echo "FAIL: $bin not on PATH" >&2
    exit 1
  fi
done

tmp_root="$(mktemp -d -t tripwire-smoke-resume-XXXXXX)"
project_dir="$tmp_root/project"
clone_dir="$tmp_root/clone"
mkdir -p "$project_dir" "$clone_dir"

SESSION_ID="smk-resume-1"
cleanup() {
  local exit_code=$?
  tripwire session abandon "$SESSION_ID" \
    --project-dir "$project_dir" 2>/dev/null || true
  if (( exit_code != 0 )); then
    echo "--- FAIL (exit=$exit_code). Tree: $tmp_root" >&2
    tripwire session logs "$SESSION_ID" \
      --project-dir "$project_dir" --tail 80 2>/dev/null || true
  else
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

# Seed clone.
(
  cd "$clone_dir"
  git init -q -b main
  git -c user.name=smoke -c user.email=smoke@example.com \
    commit --allow-empty -q -m "smoke root"
)

# Project scaffold.
cat > "$project_dir/project.yaml" <<YAML
name: smoke-resume
key_prefix: SMK
next_issue_number: 1
next_session_number: 1
repos:
  SeidoAI/smoke-code:
    local: $clone_dir
YAML
mkdir -p "$project_dir"/{issues,nodes,sessions,docs,plans,agents,templates/artifacts}
cat > "$project_dir/agents/backend-coder.yaml" <<YAML
id: backend-coder
context:
  skills: []
YAML

# Session with an ambiguous plan that forces stop-and-ask.
mkdir -p "$project_dir/sessions/$SESSION_ID"
cat > "$project_dir/sessions/$SESSION_ID/session.yaml" <<YAML
id: $SESSION_ID
name: Smoke resume
agent: backend-coder
issues: []
status: planned
repos:
  - repo: SeidoAI/smoke-code
    base_branch: main
YAML
cat > "$project_dir/sessions/$SESSION_ID/plan.md" <<'MD'
# Resume smoke plan

Your task has two phases.

**Phase 1 (now):** Decide the magic password. The password must
meet a policy that isn't specified here. If you can't work it out
from context, **stop and ask in plain text** — do NOT invent one.
This is intentional.

**Phase 2 (on resume):** Once the PM supplies the password in a
`## PM follow-up` section, create `password.txt` containing
exactly the password string. Commit with message `smoke: password`.
MD
cat > "$project_dir/sessions/$SESSION_ID/handoff.yaml" <<YAML
session_id: $SESSION_ID
branch: feat/$SESSION_ID
YAML

# Phase 1: queue + spawn; expect the agent to stop-and-ask.
tripwire session queue "$SESSION_ID" --project-dir "$project_dir"
tripwire session spawn "$SESSION_ID" --project-dir "$project_dir"

deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  status="$(
    tripwire session show "$SESSION_ID" --project-dir "$project_dir" 2>/dev/null \
      | awk -F': ' '/^status/ {print $2; exit}'
  )"
  if [[ "$status" != "executing" ]]; then
    echo "phase 1: agent exited, status=$status"
    break
  fi
  if (( $(date +%s) > deadline )); then
    echo "FAIL: phase 1 timed out after ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 2
done

# Phase 1 should have stopped-to-ask: the summary heuristic flags this.
if ! tripwire session summary "$SESSION_ID" --project-dir "$project_dir" \
  | grep -qi "stopped to ask"; then
  echo "WARN: phase 1 did not obviously stop-to-ask — continuing anyway" >&2
fi

# Phase 2: supply the follow-up answer + pause→paused before --resume.
cat >> "$project_dir/sessions/$SESSION_ID/plan.md" <<'MD'

## PM follow-up

The magic password is `hunter2`. Proceed with Phase 2.
MD

# --resume requires status 'paused' or 'failed'. If the agent exited
# cleanly (status=executing → pause command won't apply), we need to
# coax the session into 'paused' first.
status="$(
  tripwire session show "$SESSION_ID" --project-dir "$project_dir" 2>/dev/null \
    | awk -F': ' '/^status/ {print $2; exit}'
)"
if [[ "$status" == "executing" ]]; then
  tripwire session pause "$SESSION_ID" --project-dir "$project_dir"
fi

tripwire session spawn "$SESSION_ID" --project-dir "$project_dir" --resume

deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  status="$(
    tripwire session show "$SESSION_ID" --project-dir "$project_dir" 2>/dev/null \
      | awk -F': ' '/^status/ {print $2; exit}'
  )"
  if [[ "$status" != "executing" ]]; then
    echo "phase 2: agent exited, status=$status"
    break
  fi
  if (( $(date +%s) > deadline )); then
    echo "FAIL: phase 2 timed out after ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 2
done

# Phase 2 assertion: password.txt exists with 'hunter2'.
password_file="$(
  find "$tmp_root" -maxdepth 6 -name "password.txt" 2>/dev/null | head -n1
)"
if [[ -z "$password_file" ]]; then
  echo "FAIL: password.txt was not created on resume" >&2
  exit 1
fi
if ! grep -q "^hunter2$" "$password_file"; then
  echo "FAIL: password.txt does not contain 'hunter2': $(cat "$password_file")" >&2
  exit 1
fi

tripwire session summary "$SESSION_ID" --project-dir "$project_dir" || true

echo "PASS: subprocess-resume smoke"
