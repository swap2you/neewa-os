# Risk register — autonomy v3

| ID | Risk | Control | Status |
| --- | --- | --- | --- |
| R-01 | False PASS from worker JSON | Require artifacts + TEST_JSON / citation validator | open-in-impl |
| R-02 | Forged owner approval | Do not trust job JSON owner_decision | open-in-impl |
| R-03 | Budget overrun | Reserve conservative estimate; fail closed | open-in-impl |
| R-04 | Duplicate dispatch | Lease + active_child_id | open-in-impl |
| R-05 | Invented scripture | Approved local source pack only; else SOURCE_PENDING | open-in-impl |
| R-06 | Cross-provider claim | Mark UNVERIFIED | accepted residual |
| R-07 | Same-session review | INDEPENDENCE_UNAVAILABLE | accepted residual |
| R-08 | Home voice confusion | PENDING_PHYSICAL; out of this delivery | accepted residual |
| R-09 | Secret leakage in evidence | Secret scan; redacted job JSON | control exists |
| R-10 | Public listener | Forbidden; Tailscale SSH poll only | control exists |
