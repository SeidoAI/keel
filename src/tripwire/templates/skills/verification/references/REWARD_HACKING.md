# Reward Hacking Patterns

Reward hacking: implementation passes checks without meeting intent.
Catching it is the verification agent's highest-value job.

## Test-level

**1. Mocking the thing under test.**

```python
mocker.patch("src.api.auth.verify_password", return_value=True)
mocker.patch("src.api.auth.generate_jwt", return_value="fake-token")
response = client.post("/auth/token", json={...})
assert response.status_code == 200
```

Both verify and generate are mocked — test only checks the HTTP
layer returns what you told it to.

**2. Assertion-less tests.** `assert token is not None` checks
existence, not correctness. A buggy impl returning `"bogus"` passes.

**3. Circular expected values.** `assert hash_password("x") ==
hash_password("x")` proves determinism, not correctness. An identity
function passes.

**4. Broad exception handling in tests.** `try/except Exception:
pass` passes on `ImportError`, `NameError`, or a typo you introduced.
Use `pytest.raises(ExpectedError, match="..."`).

**5. Disabled / skipped tests.** A skipped test is a failing test you
aren't counting. Look for `@pytest.mark.skip[if]`, `@unittest.skip`,
commented-out test funcs, or tests moved into excluded paths.

**6. Tests that never ran.** New test file not picked up by
`pyproject.toml` / `pytest.ini` / `conftest.py` filters.

## Implementation-level

**7. Stub functions claiming success.** `return "pending-implementation"`
that satisfies type checks.

**8. Hardcoded test values in production paths.**

```python
if email == "test@example.com":
    return User(id="test-user", email=email)
# real lookup below
```

Test passes; production never exercises the real path.

**9. Silent error swallowing.**

```python
try:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
except Exception:
    return {}
```

Downstream `claims.get("sub")` returns `None` — treated as
unauthenticated, or worse, authenticated as user `None`.

**10. Always-true conditions.** `if user.tenant_id == resource.tenant_id
or True:` — any `or True` / `if True` in auth/authz is a critical
rejection.

## Review process

1. Read tests line by line, don't just run them.
2. For each test: "If the impl returned wrong data, would this catch
   it?"
3. Grep the diff for red flags:
   ```bash
   gh pr diff <number> | grep -E '(pytest.mark.skip|except Exception|or True|if True|TODO|FIXME|return None  #|assert.*is not None)'
   ```
4. Mutate one line of the impl to return wrong data; confirm tests
   fail. If they still pass, they're not testing what they claim.

## When you find it

Request changes with file:line references. Quote the problematic
code. Say what it should do. Don't rewrite — you're read-only.

If the coding agent has done this multiple times on one issue,
escalate via an `fyi` in your `verified.md` or directly to the PM
agent — likely a pattern needing human intervention.

## See also

- `SECURITY_CHECKLIST.md` — auth/authz specifically
- `SKILL.md` (verification) — full workflow
