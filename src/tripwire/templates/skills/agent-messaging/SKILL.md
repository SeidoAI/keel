---
name: agent-messaging
description: >-
  How to communicate with the human operator (and other agents) via the
  MCP messaging server. Covers when to send each message type, priority
  semantics, the mandatory status heartbeat, and anti-patterns. Loaded
  by default into every agent-containers session regardless of agent
  type — all agents in containerised execution need this.
license: MIT
metadata:
  author: tripwire
  version: "1.0"
compatibility: >-
  Agents running in agent-containers with the MCP agent-messaging server
  mounted. The server exposes `send_message` and `check_messages` tools.
---

# Agent Messaging

The `agent-messaging` MCP server exposes:

- **`send_message`** — post to the human via the project dashboard.
- **`check_messages`** — read pending responses.

Messages are ephemeral; the full log persists to
`sessions/<id>/messages.yaml` when the session completes.

## Type catalogue

| Type | Priority | After | Use when |
|---|---|---|---|
| `status` | informational | keep working | heartbeat every ~5 min, every state transition |
| `progress` | informational | keep working | milestone reached |
| `fyi` | informational | keep working | found something interesting / out of scope |
| `plan_approval` | blocking | STOP | before implementation (if gate enabled) |
| `question` | blocking | STOP | ambiguity blocks correct work |
| `stuck` | blocking | STOP | tried 3+ approaches, can't proceed |
| `escalation` | blocking | STOP | need elevated permissions or scope change |
| `handover` | blocking | STOP | passing to human; no response expected |

After any blocking message, exit the agent loop — the orchestrator
re-engages you with the response.

## Mandatory messages

**Status heartbeat.** Every ~5 min of active work and every state
transition. Body: `{state, summary}` — `state` from
`<project>/enums/agent_state.yaml` (`investigating`, `planning`,
`awaiting_plan_approval`, `implementing`, `testing`, `debugging`,
`refactoring`, `documenting`, `self_verifying`, `blocked`,
`handed_off`, `done`). `summary` is 1-2 plain sentences. Priority is
always `informational`.

```json
{"type": "status", "priority": "informational",
 "body": {"state": "implementing",
          "summary": "Wired JWT middleware. Now writing validation tests."}}
```

**Plan approval.** If `manifest.yaml` has `approval_gate: true` on the
`plan` artifact, send a `plan_approval` (priority `blocking`, body =
plan content) after writing `plan.md` and before implementing. Then
exit. This corresponds to the `plan_approval` JIT prompt on
`coding-session.executing` (see workflow.yaml and PM skill's
`WORKFLOWS_CODE_REVIEW.md`).

**Blocking questions.** Genuine ambiguity that blocks correct work.
Good questions have specific options, reference the ambiguous source,
and include your preferred answer with reasoning. Don't ask "what
should I do?".

```json
{"type": "question", "priority": "blocking",
 "body": "Should /auth/refresh rotate the refresh token? Contract in [[contract-auth-token]] doesn't specify. A: rotate (safer, complex). B: reuse (simpler, less safe). I lean A."}
```

## Reading responses

After re-engagement, call `check_messages` first — responses don't
appear inline. Result shape:

```
[{"in_reply_to": "msg-123", "body": "Go with option A", "author": "maia"}]
```

## Anti-patterns

1. Spamming `status` (every 5 minutes, not every 5 seconds).
2. Using `blocking` when `informational` would do.
3. Sending `plan_approval` when the manifest doesn't require it.
4. Asking questions without specific options + preferred answer.
5. Forgetting `check_messages` after re-engagement.

Full discussion: `references/ANTI_PATTERNS.md`.

## See also

- `references/MESSAGE_TYPES.md` — full catalogue with examples
- `references/EXAMPLES.md` — worked examples per type
- `references/ANTI_PATTERNS.md` — common mistakes
