# Worker routing

Capability routing remains `12_SCRIPTS/neewa_orchestrate.py`.
Coding fallback order is in `select_coding_worker`:

1. `cursor-agent-cli` (verified)
2. `codex` (ChatGPT authenticated; `codex exec` smoke returned pong; not NEEWA-routable yet)
3. `claude-code` (Claude Pro authenticated; `claude -p` smoke returned pong; not NEEWA-routable yet)
4. `antigravity-cli` (Google authenticated; `agy -p` smoke returned pong; not NEEWA-routable yet)
5. `gemini-cli` (Google login present; individual Code Assist client rejected; do not use)

If none are available the parent job is `WAITING`, not a fake completion.
Cursor stays the default development worker until another CLI is verified.

GUI apps (Claude Cowork) are inventoried and are not programmable workers.
