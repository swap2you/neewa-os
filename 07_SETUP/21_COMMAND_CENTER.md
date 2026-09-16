# Step 21 — NEEWA Command Center (Desktop plugin)

The Command Center is a Hermes Desktop plugin (`16_WINDOWS_CLIENT/assets/neewa-command-center/plugin.js`,
installed to `<HERMES_HOME>/desktop-plugins/neewa-command-center/plugin.js`). It uses only
supported extension APIs — `host.state`, `host.request` (gateway JSON-RPC), `host.navigate`,
`host.notify` — and adds no network listener or public endpoint.

## What it shows (real data only)

- **Identity + live status** — NEEWA branding and turn state (READY / THINKING / WORKING /
  OFFLINE) from `host.state`.
- **Connection** — gateway socket state, registry source, and profile.
- **Assistant** — turn state, active model, context usage — from `host.state`.
- **Scheduled jobs** — live via `host.request('cron.manage', { action: 'list', include_disabled: true })`,
  with a data-freshness stamp and an explicit "unavailable" state on RPC failure.
- **Controls** — "Open scheduled jobs" navigates to `/cron`; "Refresh data" re-fetches.

Every panel shows loading / unavailable explicitly and never renders `undefined` or a
placeholder as if it were real.

## Deliberate limitation (no fabrication)

Server host-health, the morning brief, and project summaries are **host/repository facts**.
A renderer plugin cannot read the host filesystem or the read-only status snapshot through a
supported read RPC without introducing a backend plugin half or a new listener — which the
privacy constraints forbid. Rather than fabricate numbers, the pane points the owner to the
authoritative, timestamped source: ask NEEWA in chat ("system status" / "morning brief"),
which is backed by `/opt/neewa/status/latest.json` and `12_SCRIPTS/neewa_host_status.sh`.

## Identity vs the Hermes landing screen

The large "HERMES" landing is the pre-chat empty-state wordmark. The `neewa` skin recolors the
chrome (midnight teal / cyan) but does not replace that wordmark; replacing it would require
forking Hermes, which is out of scope. NEEWA identity is expressed through the skin, the
Command Center chip + right pane, and the agent's own identity (`SOUL.md`: "You are NEEWA").

## Runtime verification

Plugin file presence is necessary but not sufficient. Confirm on the owner PC that the teal
skin is applied, the "NEEWA" status-bar chip is visible, and the right-side "NEEWA" pane renders
the sections above. A renderer plugin's load state is not written to a host log, so a screenshot
is the practical runtime evidence.
