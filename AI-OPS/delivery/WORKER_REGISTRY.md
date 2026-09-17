# Development worker registry

Canonical machine file: `11_CONFIG/workers.json`.
Default development worker: **cursor-agent-cli**.

| Worker | Executable | Version | Auth | Noninteractive | Routable |
| --- | --- | --- | --- | --- | --- |
| cursor-agent-cli | `%LOCALAPPDATA%\cursor-agent\agent.cmd` | 2026.09.15-d2fe57e | official `agent login` (browser) | `agent --print --output-format json --workspace <repo> --sandbox enabled` | yes, after AUTH |
| neewa-windows-worker | `Start-NeewaWindowsWorker.ps1` | existing | Tailscale SSH | outbound poll | yes |
| cua-driver | local 0.28.2 | 0.28.2 | local session | not an inbox worker | interactive only |
| Cursor IDE `cursor.cmd` | IDE launcher | 3.17.x | IDE login | not the agent CLI | no |
| Codex | not on PATH | unknown | `.codex` present | not verified | no |
| Claude Code | not on PATH | unknown | `%LOCALAPPDATA%\claude\Logs` only | not verified | no |
| Gemini CLI | not on PATH | unknown | `.gemini` present | not verified | no |
| Claude Cowork | not verified | — | — | no documented remote automation verified | no |

Do not copy tokens between products.
Do not install extra paid CLIs just to demonstrate orchestration.
If a worker is unavailable, NEEWA returns the missing capability and records
a BLOCKED job instead of pretending.
