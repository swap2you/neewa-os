# Development worker registry

Canonical machine file: `11_CONFIG/workers.json`.
Default development worker: **cursor-agent-cli**.

| Worker | Executable | Version | Auth | Noninteractive | Routable |
| --- | --- | --- | --- | --- | --- |
| cursor-agent-cli | `%LOCALAPPDATA%\cursor-agent\agent.cmd` | 2026.09.15-d2fe57e | official `agent login` (browser) | `agent --print --output-format json --workspace <repo> --sandbox enabled` | yes, after AUTH |
| neewa-windows-worker | `Start-NeewaWindowsWorker.ps1` | existing | Tailscale SSH | outbound poll | yes |
| cua-driver | local 0.28.2 | 0.28.2 | local session | not an inbox worker | interactive only |
| Cursor IDE `cursor.cmd` | IDE launcher | 3.17.x | IDE login | not the agent CLI | no |
| Codex | `codex` on PATH | 0.154.0 | ChatGPT logged in | `codex exec` smoke pong | no |
| Grok CLI | `grok` on PATH | 1.0.34 | grok.com logged in | `grok -p` smoke pong | no |
| Claude Code | `%USERPROFILE%\.local\bin\claude.exe` | 2.1.274 | Claude Pro logged in | `claude -p` smoke pong | no |
| Gemini CLI | `gemini` on PATH | 0.60.0 | Google login present | individual Code Assist client rejected | no |
| Antigravity CLI `agy` | `%LOCALAPPDATA%\agy\bin\agy.exe` | 1.2.5 | Google / Gemini Pro | `agy -p` smoke pong | no |
| GitHub Copilot CLI | `%LOCALAPPDATA%\GitHubCopilotCLI\copilot.exe` | 1.0.65 | `copilot login` pending | `copilot -p` | no |
| Claude Cowork | Claude Desktop 2.110.0 + CoworkVMService | — | desktop GUI | no programmable CLI | no |
| Antigravity IDE `antigravity.cmd` | IDE launcher | 1.107.x | IDE login | not a NEEWA worker | no |

Do not copy tokens between products.
Do not install extra paid CLIs just to demonstrate orchestration.
If a worker is unavailable, NEEWA returns the missing capability and records
a BLOCKED job instead of pretending.
