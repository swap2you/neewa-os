# Cost governance

Parent jobs record invocations with token fields when the worker reports them.
Cursor Agent JSON `usage` is copied from CLI stdout when parseable
(`Get-CursorUsage` in `Invoke-NeewaCursorCall.ps1`) onto the harvest record.

Subscription-included Cursor/Nous usage is **not** converted into invented
dollar amounts. `cost_usd` stays null with
`cost_basis=unavailable-subscription-included` unless a billed API invoice
is present.

Approved ceilings remain `11_CONFIG/budgets.json`
(`first_90_days_ceiling` 1000, job default `max_cost` 5).
`budget_ceiling=0` is the deterministic exhaustion test; it does not place
a real charge.
