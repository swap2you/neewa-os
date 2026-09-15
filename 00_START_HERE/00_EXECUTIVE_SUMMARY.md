# Executive Summary

## Outcome

By the end of Month 1, NEEWA should be able to:

- accept natural text and voice instructions;
- converse in the owner's normal English/Hindi/Marathi code-switching style;
- use a premium reasoning model when judgment matters;
- use cheaper/local workers for routine tasks;
- maintain structured memory for the owner and projects;
- perform "premium research" using a required evidence-coverage protocol;
- decompose goals into bounded jobs;
- delegate coding work to Codex, Claude Code, Gemini CLI, or another approved worker;
- route work to NEEWA-EDGE-01 when local repositories/tools are required;
- run independent review and validation;
- retry failed gates up to the configured limit;
- produce evidence before declaring work done;
- track model cost, token consumption, latency, retries, and provider failures;
- survive quota exhaustion by using approved fallbacks;
- allow the owner to RUN, PAUSE, or LOCKDOWN the system;
- produce daily executive briefs instead of requiring the owner to supervise individual agents.

## 30-day product definition

NEEWA OS v1.0 is accepted when one real project can move from owner objective to verified deliverable without manual prompt-copying between agents.

Minimum demonstration:

Owner -> NEEWA -> Research/Plan -> Worker -> Automated Tests -> Independent Review -> Automatic Rework -> Done Gate -> Council verdict -> Owner summary.

## 90-day business objective

Total owner funding ceiling: **$1,000 over the first 90 days**.

By the end of the 90-day proving period:

- infrastructure/subscriptions are measured and rationalized;
- NEEWA should produce at least **$300/month of attributable revenue or equivalent recurring cost savings** before the owner treats the system as self-funding;
- no claim of guaranteed revenue is permitted;
- NEEWA must maintain base / target / stretch revenue cases with assumptions and evidence.

## Architecture freeze

For 30 days, do not add another orchestration framework unless:
- a P0 security flaw makes the current design unsafe;
- a required integration is impossible;
- measured evidence demonstrates a clear material advantage.

No framework tourism during the first month.
