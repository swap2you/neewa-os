# Step 21 — NEEWA Home, HUD, and Command Center

The product surface is a Hermes Desktop plugin
(`16_WINDOWS_CLIENT/assets/neewa-command-center/plugin.js`, installed to
`<HERMES_HOME>/desktop-plugins/neewa-command-center/plugin.js`). It uses only
supported native Desktop APIs. It adds no network listener or public endpoint.

## Surfaces

- **NEEWA Home** (`/neewa-home`) — primary full-page route. Original animated
  persona, live wake/privacy state, Mute / Stop / Rearm, Open HUD.
- **NEEWA HUD** (`/neewa-hud`) — compact in-app HUD. Native movable overlay is
  Hermes HUD (`Ctrl+Shift+H`), opened from Home when the Desktop bridge exists.
- **Sidebar** — NEEWA Home and NEEWA HUD. Palette: “NEEWA: Open Home”.
  Hotkey: `Ctrl+Alt+N`.
- **Status chip + right pane** — still present in chat/advanced view.

Cold-start navigates to `/neewa-home` when the app opened at `/`.

## Real data only

Connection, model, context, scheduled jobs (`cron.manage`), wake listener
(`wake.status` / start / stop), TTS provider (`config.get` of specific keys,
never `config.get full`), and pending approval count. Host health and the
morning brief remain snapshot-backed via chat (“system status” / “morning
brief”) because the renderer cannot read `/opt/neewa/status` through a
supported RPC without a new listener.

## Identity

The default owner-facing page is NEEWA Home, not the HERMES splash. Chat remains
the advanced/backup surface.
