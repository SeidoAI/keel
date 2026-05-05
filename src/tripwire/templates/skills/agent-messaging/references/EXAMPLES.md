# Message Examples

`body` accepts Markdown except `status`, which uses a structured
object.

## `status` — heartbeat

```json
{"type": "status", "priority": "informational",
 "body": {"state": "investigating",
          "summary": "Reading src/api/auth.py and [[contract-auth-token]] to confirm response shape."}}
```

Other examples by state: `testing` ("Running pytest tests/unit/test_auth.py"), `self_verifying` ("Walking verification-checklist.md before declaring done").

## `plan_approval` — before implementation

```json
{"type": "plan_approval", "priority": "blocking",
 "body": "## Plan for SEI-42\n## Goal\nPOST /auth/token per [[contract-auth-token]].\n## Approach\n1. Read [[user-model]] for lookup methods.\n2. Handler in src/api/auth.py.\n3. python-jose signing (see [[dec-003-session-tokens]]).\n4. Cookie via existing helpers.\n5. Tests: happy path, 401, 403, rate limit.\n## Out of scope\nRefresh flow (SEI-45), password reset."}
```

## `question` — ambiguity blocking work

```json
{"type": "question", "priority": "blocking",
 "body": "## SEI-42 acceptance criteria ambiguity\nTicket says 'expired → 403' but [[contract-auth-token]] uses code:invalid_credentials (semantically 401).\n**A**: 403 + code:token_expired (matches ticket, new code)\n**B**: 401 + code:invalid_credentials (matches contract)\n**C**: 403 + code:invalid_credentials (mixed)\n**Pref**: A — ticket newer; no other endpoint uses token_expired. Confirm?"}
```

## `stuck` — multiple attempts, no progress

```json
{"type": "stuck", "priority": "blocking",
 "body": "## Stuck on SEI-42 JWT verify\n**Goal**: jwt.decode() succeeds on a token we just signed.\n**Tried**:\n1. algorithms=['HS256'] → InvalidSignatureError\n2. algorithms=['HS512'] (matches signing) → same\n3. Confirmed JWT_SECRET matches sign + decode (32-char string)\n4. Payload decodes manually at jwt.io\n5. options={verify_signature: False} works → signature-specific\n**Suspicion**: byte-encoding (bytes vs str for the secret).\nCode: src/api/auth.py:45-82 on claude/SEI-42-auth."}
```

## `escalation` — scope change needed

```json
{"type": "escalation", "priority": "blocking",
 "body": "## Escalation: SEI-42 needs web-app-infrastructure\nTicket assumes [[config-jwt-secret]] is provisioned in test; it's not.\nFix requires a Terraform change in SeidoAI/web-app-infrastructure — out of scope for SEI-42 and outside agent permissions.\n**Need**: (a) expand SEI-42 scope, or (b) new infra issue SEI-X blocking SEI-42.\nStopped pending decision."}
```

## `handover` — giving up

```json
{"type": "handover", "priority": "blocking",
 "body": "## Handover: SEI-42 JWT impl\nThree libs (python-jose, pyjwt, authlib) all fail at the same verify step. Suspect JWT_SECRET encoding, can't confirm inside container.\n**State**:\n- Branch claude/SEI-42-auth @ abc123\n- src/api/auth.py:45-82 (signs OK, verify fails)\n- tests/unit/test_auth.py: 2/4 pass, 2 fail on signature\n- plan.md, task-checklist.md, verification-checklist.md committed\n**Next steps**:\n1. Inspect JWT_SECRET bytes in test env (Secret Manager not container-readable)\n2. Round-trip test outside container\n3. If env-level, escalate to infra\nMarked session handed_off."}
```

## `progress` — milestone

```json
{"type": "progress", "priority": "informational",
 "body": "Unit tests passing for SEI-42 (4/4). Moving to integration tests."}
```

## `fyi` — interesting finding

```json
{"type": "fyi", "priority": "informational",
 "body": "[[user-model]].find_by_email catches BaseException instead of FirestoreError — swallows KeyboardInterrupt/SystemExit. Out of scope for SEI-42; worth a follow-up."}
```
