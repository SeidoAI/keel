#!/usr/bin/env bash
# Real-claude smoke test for the subprocess runtime.
#
# Exercises the full happy path: queue + spawn a trivial session,
# wait for the agent to finish, verify it created a file and made a
# commit. Requires `claude` + `tripwire` + `git` + `gh` on PATH.
#
# Usage:  bash scripts/smoke-subprocess-runtime.sh
# Env:    TW_SMOKE_TIMEOUT  seconds to wait for agent exit (default 240)

set -euo pipefail

TIMEOUT="${TW_SMOKE_TIMEOUT:-240}"

for bin in claude tripwire git; do
  if ! command -v "$bin" >/dev/null; then
    echo "FAIL: $bin not on PATH" >&2
    exit 1
  fi
done

tmp_root="$(mktemp -d -t tripwire-smoke-XXXXXX)"
project_dir="$tmp_root/project"
clone_dir="$tmp_root/clone"
mkdir -p "$project_dir" "$clone_dir"

cleanup() {
  local exit_code=$?
  if [[ -n "${SESSION_ID:-}" ]]; then
    tripwire session abandon "$SESSION_ID" \
      --project-dir "$project_dir" 2>/dev/null || true
  fi
  if (( exit_code != 0 )); then
    echo "--- FAIL (exit=$exit_code). Tree: $tmp_root" >&2
    if [[ -n "${LOG_PATH:-}" && -f "$LOG_PATH" ]]; then
      echo "--- Last 50 lines of $LOG_PATH ---" >&2
      tail -n 50 "$LOG_PATH" >&2 || true
    fi
  else
    rm -rf "$tmp_root"
  fi
}
trap cleanup EXIT

# 1. Seed the clone with an empty commit on main.
(
  cd "$clone_dir"
  git init -q -b main
  git -c user.name=smoke -c user.email=smoke@example.com \
    commit --allow-empty -q -m "smoke root"
)

# 2. Write tripwire project scaffolding.
cat > "$project_dir/project.yaml" <<YAML
name: smoke
key_prefix: SMK
next_issue_number: 1
next_session_number: 1
repos:
  SeidoAI/smoke-code:
    local: $clone_dir
YAML
mkdir -p "$project_dir"/{issues,nodes,sessions,docs,plans,agents,templates/artifacts}

# 3. Agent definition (no sub-agent tools, matches subprocess default).
cat > "$project_dir/agents/backend-coder.yaml" <<YAML
id: backend-coder
context:
  skills: []
YAML

# 4. Session + plan.
SESSION_ID="smk-smoke-1"
mkdir -p "$project_dir/sessions/$SESSION_ID"
cat > "$project_dir/sessions/$SESSION_ID/session.yaml" <<YAML
id: $SESSION_ID
name: Smoke subprocess
agent: backend-coder
issues: []
status: planned
repos:
  - repo: SeidoAI/smoke-code
    base_branch: main
YAML
cat > "$project_dir/sessions/$SESSION_ID/plan.md" <<'MD'
# Smoke plan

Create a file named `hello.txt` with the single-line contents `hi`
in the repo root. Commit it with the message `smoke: hello`. Do not
push and do not open a PR — this is a local-only smoke test. When
done, simply exit.
MD
cat > "$project_dir/sessions/$SESSION_ID/handoff.yaml" <<YAML
session_id: $SESSION_ID
branch: feat/$SESSION_ID
YAML

# 5. Queue + spawn.
tripwire session queue "$SESSION_ID" --project-dir "$project_dir"
tripwire session spawn "$SESSION_ID" --project-dir "$project_dir"

# Capture log path for cleanup-on-error.
LOG_PATH="$(
  tripwire session show "$SESSION_ID" --project-dir "$project_dir" 2>/dev/null \
    | awk -F': ' '/log_path/ {print $2; exit}'
)"
LOG_PATH="${LOG_PATH%\"}"
LOG_PATH="${LOG_PATH#\"}"

# 6. Poll until process exits (or timeout).
deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  status="$(
    tripwire session show "$SESSION_ID" --project-dir "$project_dir" 2>/dev/null \
      | awk -F': ' '/^status/ {print $2; exit}'
  )"
  if [[ "$status" != "executing" ]]; then
    echo "smoke: session transitioned to '$status'"
    break
  fi
  if (( $(date +%s) > deadline )); then
    echo "FAIL: timed out after ${TIMEOUT}s" >&2
    exit 1
  fi
  sleep 2
done

# 7. Assertions — worktree contains the expected artifact.
worktree="$(
  find "$clone_dir" -maxdepth 4 -name "hello.txt" 2>/dev/null | head -n1
)"
# Fall back to the tripwire-managed worktree location if the find
# traversal missed it (git worktrees may live outside the clone).
if [[ -z "$worktree" ]]; then
  worktree="$(find "$tmp_root" -maxdepth 6 -name "hello.txt" 2>/dev/null | head -n1)"
fi

if [[ -z "$worktree" ]]; then
  echo "FAIL: hello.txt not created anywhere under $tmp_root" >&2
  exit 1
fi
if ! grep -q "^hi$" "$worktree"; then
  echo "FAIL: hello.txt does not contain 'hi': $(cat "$worktree")" >&2
  exit 1
fi

worktree_dir="$(dirname "$worktree")"
if ! (cd "$worktree_dir" && git log --oneline -n 5 | grep -q "smoke: hello"); then
  echo "FAIL: no 'smoke: hello' commit in $worktree_dir" >&2
  exit 1
fi

# Summary is nice-to-have; failure here doesn't fail the smoke.
tripwire session summary "$SESSION_ID" --project-dir "$project_dir" || true

echo "PASS: subprocess-runtime smoke"
