# Remaining NEEWA Backlog

Prioritized after JOB-20260916-002.

P0 — resilience and persistence
- Securely authenticate Codex OAuth through the owner device.
- Securely provide OPENAI_API_KEY through the protected environment and run direct API validation.
- Add controlled delegated-worker and cron fallback simulations for each authenticated cloud provider.

P1 — Windows one-action acceptance
- Run the packaged `16_WINDOWS_CLIENT/dist/NEEWA-Windows-Bootstrap.zip` on the personal Windows PC.
- Complete Tailscale/SSH trust and Hermes Desktop remote connection Test.
- Validate microphone permission, TTS playback, sherpa wake phrase, and barge-in.

P2 — private connectivity
- If Desktop SSH mode is insufficient, configure authenticated loopback `hermes serve` plus tailnet-private Tailscale Serve. Never use Funnel.

P3 — model governor
- Measure Luna/Terra/Sol latency and cost once each provider is independently authenticated.
- Add provider capacity observations without conflating subscriptions, API billing, or context meters.

P4 — morning briefing
- Refine the deterministic brief after the first real overnight Windows connection and owner feedback.

P5 — UI and project visibility
- Add active-job/project summaries to the Command Center after the Desktop plugin is running on Windows.

Deferred by owner
- NemoClaw/OpenShell/K3s;
- global Docker network disable;
- UFW/Lightsail firewall changes;
- public exposure/Funnel;
- new paid services;
- employer integrations.
