# Hermes Desktop 0.21.3 — NEEWA keep-mounted patch

## Upstream limitation

Installed Hermes Desktop mounts `ChatView` (and the only `target: 'main'` composer) **inside** `<Routes>`. A plugin page such as `#/neewa-home` therefore **unmounts** the composer. `wake.detected` still calls `requestVoiceConversationStart()`, but `takeVoiceConversationStart` is a no-op until that composer remounts.

The previous plugin workaround navigated to `#/` (`NEW_CHAT_ROUTE`). That:

1. stole the visual from NEEWA Home;
2. nulled the selected session and minted extra chats.

Navigating back to Home after voice start would unmount the composer again and kill capture. Unsupported plugin APIs cannot keep that composer alive.

## Patch (narrow)

Workspace: `%LOCALAPPDATA%\hermes\hermes-agent` (Hermes 0.21.3 source that builds the packed `win-unpacked\Hermes.exe`).

| File | Change |
| --- | --- |
| `apps/desktop/src/app/contrib/surfaces.tsx` | Keep `ChatView` mounted for the workspace pane lifetime; overlay plugin pages with an opaque cover. **Do not use `visibility:hidden`** — Chromium can suspend AudioContext / MediaRecorder / HTMLAudio playback in a CSS-hidden subtree (Home stalled, Conversation worked). |
| `apps/desktop/src/lib/neewa-voice-bridge.ts` | Authoritative `window.__NEEWA_VOICE__` controller (IDLE → PLAYING_AUDIO). Home/HUD subscribe; MIC LIVE only when `recording === true`. |
| `apps/desktop/src/app/chat/composer/hooks/use-composer-voice.ts` | Main composer registers start/stop/mute and publishes real `conversation.status`. Start is idempotent (does not toggle). |
| `apps/desktop/src/app/routes.ts` | Document `RouteContribution.keepChatMounted`. |
| `apps/desktop/src/app/contrib/wiring.tsx` | Mint a new session on wake only when `start_new_session === true`; otherwise reuse/pin `neewa.personalSessionId`. `preserveRoute` so Home stays. |
| `apps/desktop/src/lib/wake-client-capture.ts` | Non-sensitive PCM counters on `window.__NEEWA_WAKE_HEALTH__`; optional double-clap on the **same** ScriptProcessor (no second getUserMedia). |
| `apps/desktop/src/store/wake-word.ts` | Dispatch `hermes:neewa-clap` from that stream. |

## Rebuild / apply

From `apps/desktop`:

```
npm run build
```

Then replace `release/win-unpacked/resources/app.asar` with a pack of the new `dist` (see `Apply-NeewaDesktopPatch.ps1`). Restart packed `Hermes.exe`.

## Rollback

Restore the previous `app.asar` and checkout the four files on Hermes `main` (`2cfb655` at patch time). Plugin-only rollback: copy the previous `plugin.js`.

## Upgrade maintenance

On each Hermes Desktop upgrade, re-apply this keep-mounted ChatView contract and re-test: stay on `#/neewa-home`, say Hey Neewa, confirm STT without a route change. If upstream adds a persistent composer, drop the overlay patch.
