# Prepared Approval Boundaries

The A0/A1 bootstrap stops before the following consequential actions.

## A2 — Install and onboard NemoClaw/OpenShell for Hermes

Exact prepared action:
1. Re-download the official installer from `https://www.nvidia.com/nemoclaw.sh` immediately before execution and verify it still matches the reviewed SHA-256 `d6d8b3f4fe9298efae4a0ddce3d1f256f75e5c5ea33c91b41dfb274ef350c335` (staged 2026-09-16, 16,318 bytes, `bash -n` passed).
2. Run the staged script with `NEMOCLAW_AGENT=hermes` and sandbox name `neewa-core`; select Hermes Provider/Nous OAuth, no public dashboard bind, no messaging, and the Restricted or Balanced reviewed network policy.
3. Verify `nemohermes neewa-core status`, loopback-only dashboard/API forwards, provider route, sandbox policy, and snapshot support.

Why approval is required: the installer adds a security boundary, OpenShell gateway, k3s/container resources, downloads an approximately 2.4 GB compressed image, may request administrator access, creates a sandbox, and receives authentication through a protected flow.

Impact/cost: no planned new subscription; disk, memory, and network consumption on NEEWA-Core. Onboarding may interrupt or duplicate the current host Hermes runtime unless migration is staged carefully.

Rollback: export secret-free config and snapshot first; stop and uninstall only receipt-owned NemoClaw resources using its verified lifecycle commands; restore the current host Hermes configuration backup and gateway.

## A2 — Enforce deny-by-default network for the current Hermes Docker backend

Exact prepared action: after confirming required offline tooling, run `hermes config set terminal.docker_network false`, recreate only the disposable Hermes tool sandbox, and verify an external connection fails while the approved repository mount still works.

Why approval is required: this changes a security control and can break tools that require network access.

Impact/cost: no financial cost; network-dependent terminal jobs fail until explicitly routed through an approved boundary.

Rollback: `hermes config set terminal.docker_network true`, recreate the disposable tool sandbox, and verify connectivity. The timestamped pre-bootstrap Hermes config backup remains available under `~/.hermes/`.

## A2 — Enable the host firewall

Observed state: SSH uses socket activation on all interfaces, password authentication is explicitly disabled, and UFW is inactive. The AWS Lightsail firewall could not be verified from the host.

Exact prepared action: verify the Lightsail firewall and current admin path, add explicit OpenSSH and Tailscale-safe rules, set default deny incoming, then enable UFW while retaining the current SSH session and testing a second connection before disconnecting.

Why approval is required: firewall changes are A2 and can lock out the owner.

Impact/cost: no financial cost; incorrectly scoped rules can interrupt remote administration.

Rollback: use the retained session or Lightsail console to run `sudo ufw disable`; restore the exported UFW rule set.

## A2/A3 — External providers, observability, voice, and workers

OpenAI, OpenRouter, Langfuse, RunPod, OpenHands/Codex/Claude/Gemini, GPT-Live voice, and NEEWA-EDGE-01 remain prepared but unconfigured. Each requires some combination of account identity, credentials, access grants, paid limits, data disclosure, or host permissions.

Before any integration, NEEWA will present its exact scoped credential, budget, data boundary, network destinations, tests, and rollback. No secret should be pasted into chat or Git.
