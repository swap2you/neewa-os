# Step 20 — System Status Reporting (Sandbox vs Host)

NEEWA runs its agent tools inside an isolated Docker sandbox on `neewa-core-01`.
The sandbox is deliberately not the host: its filesystem, CPU, RAM, and disk are
container-scoped. Reporting container stats as if they were the server is wrong.

## Four distinct layers

- **A. Sandbox health** — the Docker execution container. `/workspace` is scratch;
  `/root` is the container home. Use only to describe the tool sandbox itself.
- **B. Actual NEEWA server health** — the `neewa-core-01` host: uptime, CPU/RAM,
  disk, gateway, Docker, Tailscale, Ollama, failed units. Source of truth is the
  read-only snapshot at `/opt/neewa/status/latest.json` (also `.txt`), produced by
  `12_SCRIPTS/neewa_host_status.sh` on the host and mounted read-only into the sandbox.
- **C. NEEWA application / repository health** — the repo at `/opt/neewa/neewa-os`
  (branch, HEAD, clean/dirty) plus `neewa_ops.py validate`. The repo is mounted
  read-only into the sandbox for inspection.
- **D. Windows client health** — Hermes Desktop, microphone, wake listener, and the
  private SSH/Tailscale connection. Reported from the Windows side.

## Agent directive

When asked for "system status" / "server health" / "are you up":

1. Read `/opt/neewa/status/latest.json` for **host (layer B)** facts and quote the
   `generated_at` timestamp. Never substitute container `df`/`free`/`uptime`.
2. If `/opt/neewa/status/latest.json` is absent or stale, say so and fall back to a
   host-authorized run of `neewa_host_status.sh` (via the scheduled refresh), rather
   than reporting the empty sandbox.
3. The absence of `/opt/neewa/neewa-os` or an empty `/workspace` inside the sandbox is
   **normal sandbox isolation**, not a server outage. Do not report it as a blocker.
4. Always label each fact with its layer: sandbox vs server vs repo vs Windows client.

## Voice pipeline status

Voice readiness and the most recent OBSERVED voice events (wake armed, wake detected,
real speech transcription, voice→agent turn, TTS generation) are published to
`/opt/neewa/status/voice.json` by the read-only host probe `12_SCRIPTS/neewa_voice_readiness.sh`.
The live gateway logs, venv, and model caches are intentionally not mounted into the
sandbox, so voice facts must come from this host-side snapshot, not from the sandbox.
For any voice question, read `/opt/neewa/status/voice.json` and cite `generated_at`.

## Refresh mechanism

- Host scripts: `12_SCRIPTS/neewa_host_status.sh` and `12_SCRIPTS/neewa_voice_readiness.sh`
  → `~/.hermes/scripts/`.
- Scheduled no-agent Hermes cron jobs: `neewa-host-status` (every 10 min) and
  `neewa-voice-readiness` (every 15 min) refresh the read-only snapshots on the host.
- Sandbox mounts (read-only): `/opt/neewa/neewa-os` and `/opt/neewa/status`.

No public exposure, no secrets, no host mutation — the probe is read-only.
