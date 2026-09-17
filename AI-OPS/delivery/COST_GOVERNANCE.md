# Cost governance

Chargeable steps require a remaining allowance.

- Measured `cost_usd` is used when a worker reports it.
- Otherwise Cursor invocations consume `conservative_estimates_usd.cursor_call`
  (currently 0.50) from `11_CONFIG/budgets.json`.
- Ceiling `<= 0` or remaining `<` next estimate → `BUDGET_EXHAUSTED` before submit.
- If the conservative estimate is missing, chargeable work is `COST_UNKNOWN` and blocked.

Subscription-included usage is not invented as an invoice. The conservative
figure is a gate, not a claim of billed dollars.
