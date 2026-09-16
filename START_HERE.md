# NEEWA — Start Here

NEEWA is Swapnil's private personal AI Chief of Staff. Hermes runs the brain on neewa-core-01; the Windows PC is the face, microphone, speakers, and normal user interface.

Current state
- Server runtime, persistence, schedules, memory, registries, voice stack, local fallback, and governance are operational.
- Routine model default is Nous GPT-5.6 Luna; Sol is an escalation tier.
- Nous primary and local Qwen fallback are verified.
- Windows package is ready for the one-time personal-PC install.
- Direct OpenAI API and Codex OAuth are prepared but await secure owner authentication.

One-time Windows action
1. Download/run `16_WINDOWS_CLIENT/dist/NEEWA-Windows-Bootstrap.zip` contents on the personal Windows PC.
2. Complete the generated Hermes Desktop SSH connection to `ubuntu@neewa-core-01:22` over Tailscale.
3. Test the connection, microphone, speaker, and wake phrase.

Normal use
1. Open Hermes Desktop (auto-starts at login; NEEWA is the primary SSH gateway to `neewa-core-01`).
2. Type or speak. Push-to-talk / the ear (wake) icon capture the Windows mic and stream it to NEEWA on the server.
3. Say the wake phrase `Hey Neewa`, pause for the visible listening state, then speak your request.
4. Ask: `Neewa, check your server health and tell me what you completed overnight.`

System status is truthful and layered: NEEWA reads a read-only host snapshot
(`/opt/neewa/status/latest.json`, refreshed every 10 min by `12_SCRIPTS/neewa_host_status.sh`)
for real server facts and never reports its Docker sandbox as the server. See
`07_SETUP/20_SYSTEM_STATUS_REPORTING.md`.

Morning handoff
Read `MORNING_REPORT.md`.

Technical operation
- Run `./12_SCRIPTS/bootstrap.sh` for deterministic repository checks.
- Run `python3 12_SCRIPTS/neewa_ops.py validate` for semantic validation.
- Run `hermes gateway status` and `hermes fallback list` for runtime status.
- Daily health: 06:00. Morning brief: 06:15. Both are deterministic no-agent jobs.

Recovery
- Gateway: `hermes gateway restart`.
- Local model: `systemctl status ollama`; keep it loopback-only.
- Repository rollback: use Git revert of the relevant pushed checkpoint.
- Windows client rollback: run `16_WINDOWS_CLIENT/Uninstall-NEEWA-Client.ps1`; it preserves Hermes data and Tailscale.

Deferred by owner: NemoClaw/OpenShell/K3s, global Docker network disable, firewall changes, public exposure/Funnel, new paid services, and employer integrations.
