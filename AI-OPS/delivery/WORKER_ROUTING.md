# Worker routing

Capability routing remains `12_SCRIPTS/neewa_orchestrate.py`.
Coding fallback order is in `select_coding_worker`:

1. `cursor-agent-cli` (verified)
2. `codex` (not routable)
3. `claude-code` (not routable)
4. `gemini-cli` (not routable)

If none are available the parent job is `WAITING`, not a fake completion.
Cursor stays the default development worker until another CLI is verified.

GUI apps (Claude Cowork) are inventoried and are not programmable workers.
