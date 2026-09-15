# Kill Switch Runbook

## Immediate owner action
1. Set Governor state to `LOCKDOWN`.
2. Stop/disable NEEWA sandbox execution.
3. Disable LiteLLM virtual keys.
4. Stop RunPod workers.
5. Block/rotate affected provider credentials if compromise suspected.
6. Preserve logs and snapshots.
7. Do not delete evidence.

## Recovery
- identify trigger;
- inspect audit trail;
- rotate secrets if needed;
- restore known-good snapshot/config;
- run security regression;
- require owner approval to return to RUN.

Test this procedure during initial acceptance.
