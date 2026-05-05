# Messaging Anti-patterns

## 1. Status spam

After every tool call instead of every ~5 min and every state
transition. Identical badges drown the UI; signal-to-noise collapses.
Just work between heartbeats — don't narrate every step.

## 2. Blocking when informational would do

`question` (blocking) for something the codebase answers. e.g.
"snake_case or camelCase?" when every existing field is `snake_case`.
Read the conventions first; save blocking for genuine ambiguity not
resolvable from the project.

## 3. Plan approval when not required

`plan_approval` regardless of manifest. If
`templates/artifacts/manifest.yaml` has `approval_gate: false` on
`plan`, you've halted yourself for nothing. Read the manifest first.

## 4. Questions without options

"What should I do?" forces the human into three round-trips. Always
present a choice menu with your preferred answer and reasoning:

```json
{"type": "question", "priority": "blocking",
 "body": "## Ambiguity in SEI-42\nTicket says X, contract says Y.\n**A**: do X (matches ticket).\n**B**: do Y (matches contract).\n**Pref**: A — ticket is newer. Confirm?"}
```

The human responds "A" in one line.

## 5. Skipping check_messages after re-engagement

Responses are never in your tool-call context automatically. Always
`check_messages()` first thing on re-engagement; then act.

```
[re-engaged] → check_messages() → [{"in_reply_to": "msg-123", "body": "Approved, also validate email format"}]
→ apply the email validation addendum
→ proceed with implementation
```

## 6. Conflating `status` and `progress`

`progress` for the heartbeat causes you to forget `status`, and the
UI loses the live state badge. `status` = 5-min heartbeat (always
`informational`); `progress` = discrete milestone ("unit tests
passing", "implementation complete").

## 7. Handover on first sign of trouble

`handover` is last resort, after multiple attempts. First try
`question` with specific options, or `stuck` after 3+ attempts with
per-attempt details. Handover gives the human nothing actionable.

## 8. Missing `[[references]]`

"About the user model" is ambiguous when several exist. Always link:

```json
{"type": "question", "body": "About [[user-model]] — add `last_login`?"}
```

## 9. Status with `blocking` priority

`status` is always `informational`. Setting it `blocking` halts the
session for no reason and confuses the human.
