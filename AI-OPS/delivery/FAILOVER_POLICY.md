# Failover policy

Tested with injected empty worker registries in `13_TESTS/test_neewa_autonomy.py`.

| Failure | Behavior |
| --- | --- |
| No verified coding worker | `WAITING`; resume when a worker is routable |
| Budget ceiling `<= 0` | `BLOCKED` / `BUDGET_EXHAUSTED`; no implementation |
| Cursor AUTH_REQUIRED | existing inbox `BLOCKED`; do not bypass login |
| Unauthorized repo | existing cursor_call path `BLOCKED` |
| Validator missing files | inbox `FAILED`, never `COMPLETED` |

Fallback must not open a new paid account. Codex/Claude are not used.
A configured fallback is not claimed verified until a live CLI test exists.
