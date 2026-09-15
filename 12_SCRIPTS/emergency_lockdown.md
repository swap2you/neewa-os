# Emergency Lockdown — Operator Card

If the UI is responsive:
1. Set NEEWA Governor to LOCKDOWN.
2. Disable LiteLLM virtual worker keys.
3. Stop active GPU workers.
4. Snapshot/preserve logs.

If the UI is not trustworthy:
1. Connect to NEEWA-Core through the private admin path.
2. Stop the Hermes/NemoClaw sandbox.
3. Stop LiteLLM worker access or revoke scoped keys.
4. Rotate exposed provider credentials.
5. Preserve evidence.
6. Do not return to RUN until reviewed.
