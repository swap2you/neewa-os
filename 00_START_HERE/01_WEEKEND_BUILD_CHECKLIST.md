# Weekend Build Checklist

## Definition of success

By Sunday night, the owner can speak/type to NEEWA and NEEWA can complete a bounded real task using at least one worker and one independent validation path.

## Friday / Session 1 — Accounts + control plane
- [ ] Create/confirm dedicated password manager.
- [ ] Create unique password for every account.
- [ ] Enable MFA on email, AWS, OpenAI, GitHub, Tailscale, Nous, OpenRouter, RunPod.
- [ ] Create private `neewa-os` Git repository.
- [ ] Create AWS Lightsail Ubuntu server: 4 vCPU / 16 GB / 320 GB.
- [ ] Patch OS.
- [ ] Configure SSH key authentication.
- [ ] Configure host firewall.
- [ ] Join Tailscale.
- [ ] Take clean snapshot.

## Saturday AM — NemoClaw + Hermes
- [ ] Run read-only readiness checks.
- [ ] Install maintained current NemoClaw release.
- [ ] Create Hermes sandbox `neewa-core`.
- [ ] Verify dashboard/CLI through private access only.
- [ ] Create snapshot `baseline-hermes`.
- [ ] Configure provider credentials using reviewed secret mechanism.
- [ ] Verify deny-by-default sandbox networking.

## Saturday PM — model governor
- [ ] Deploy Postgres for LiteLLM state if required.
- [ ] Deploy LiteLLM proxy.
- [ ] Configure model aliases: `neewa-premium`, `neewa-routine`, `neewa-emergency`.
- [ ] Set monthly hard budget.
- [ ] Configure OpenAI direct.
- [ ] Configure OpenRouter with ZDR guardrails.
- [ ] Configure Nous.
- [ ] Create Langfuse project.
- [ ] Connect LiteLLM telemetry to Langfuse.
- [ ] Test simulated provider failure.

## Sunday AM — memory + constitution + voice
- [ ] Load NEEWA constitution.
- [ ] Load owner profile and authority matrix.
- [ ] Create project registry.
- [ ] Configure research protocol.
- [ ] Configure GPT-Live-1 test front end.
- [ ] Pick preferred female voice after audition.
- [ ] Confirm text fallback if voice fails.

## Sunday PM — worker + first real task
- [ ] Join ThinkPad to Tailscale as `neewa-edge-01`.
- [ ] Install/validate OpenHands Agent Canvas.
- [ ] Validate Codex login.
- [ ] Validate Claude Code login.
- [ ] Validate Gemini CLI login.
- [ ] Do NOT expose arbitrary remote desktop access.
- [ ] Run one bounded project task.
- [ ] Run independent review.
- [ ] Force one failure and prove automatic remediation.
- [ ] Verify Done Gate.
- [ ] Verify `PAUSE`.
- [ ] Verify `LOCKDOWN`.
- [ ] Produce first executive brief.

Do not onboard all projects during the weekend. Prove the operating model first.
