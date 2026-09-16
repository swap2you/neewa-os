import { cn, haptic, host, Tip, useValue } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

// NEEWA Home + compact HUD + Command Center (native Desktop plugin).
//
// Supported SDK only: ROUTES_AREA, SIDEBAR_NAV_AREA, PALETTE_AREA, KEYBINDS_AREA,
// panes, statusBar, host.state / host.request / host.navigate / host.onEvent.
// Native Electron HUD (Ctrl+Shift+H) is opened via the installed Desktop bridge
// when present — not a Hermes core patch. No public listener, no secrets.
const ID = 'neewa-command-center'
const ROUTES = 'routes'
const SIDEBAR_NAV = 'sidebar.nav'
const PALETTE = 'palette'
const KEYBINDS = 'keybinds'
const HOME_PATH = '/neewa-home'
const HUD_PATH = '/neewa-hud'
const ONLINE = new Set(['open', 'connected', 'ready'])

function connLabel(g) {
  if (ONLINE.has(g)) return 'ONLINE'
  if (g === 'connecting') return 'CONNECTING'
  return 'OFFLINE'
}
function turnLabel(g, busy, waiting) {
  if (!ONLINE.has(g)) return connLabel(g)
  if (waiting) return 'THINKING'
  if (busy) return 'WORKING'
  return 'READY'
}
function ago(ts) {
  if (!ts) return 'never'
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000))
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)}m ago`
}
function prefersReducedMotion() {
  try {
    return typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}
function nativeHudApi() {
  try {
    const api = typeof window !== 'undefined' && window.hermesDesktop && window.hermesDesktop.hud
    return api && typeof api.open === 'function' ? api : null
  } catch {
    return null
  }
}
function openNativeHud() {
  const api = nativeHudApi()
  if (!api) return false
  try {
    api.open({})
    return true
  } catch {
    return false
  }
}
function openHudSurface() {
  if (openNativeHud()) return 'native'
  try { host.navigate(HUD_PATH) } catch { /* noop */ }
  return 'in-app'
}

function usePersonaState(wake) {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const [phase, setPhase] = useState('armed') // armed | listening | transcribing | speaking | muted | approval | error

  useEffect(() => {
    let off = () => {}
    try {
      off = host.onEvent('*', (e) => {
        const t = e && e.type ? String(e.type).toLowerCase() : ''
        if (t.indexOf('wake.detected') !== -1) setPhase('listening')
        else if (t.indexOf('stt') !== -1 || t.indexOf('transcript') !== -1 || t.indexOf('asr') !== -1) setPhase('transcribing')
        else if (t.indexOf('tts') !== -1 || t.indexOf('audio.play') !== -1 || t.indexOf('speaking') !== -1) setPhase('speaking')
        else if (t.indexOf('approval') !== -1) setPhase('approval')
        else if (t.indexOf('wake.pause') !== -1) setPhase('listening')
        else if (t.indexOf('wake.resume') !== -1 || t.indexOf('wake.start') !== -1) setPhase('armed')
        else if (t.indexOf('wake.stop') !== -1) setPhase('muted')
        else if (t.indexOf('error') !== -1 && t.indexOf('parse') === -1) setPhase('error')
      })
    } catch { /* onEvent unavailable */ }
    return () => { try { off() } catch { /* noop */ } }
  }, [])

  if (!ONLINE.has(gateway)) return 'disconnected'
  if (waiting) return 'thinking'
  if (busy) return 'working'
  if (phase === 'listening' || phase === 'transcribing' || phase === 'speaking' || phase === 'approval' || phase === 'error') return phase
  if (wake && wake.status === 'ok' && (wake.enabled === false || wake.listening === false)) return 'muted'
  return 'armed'
}

const STATE_META = {
  disconnected: { label: 'Disconnected', hue: '#6b7785', ring: '#3a444d' },
  armed: { label: 'Ready · listening for “Hey Neewa”', hue: '#4FD1C5', ring: '#2C7A7B' },
  listening: { label: 'Listening', hue: '#63E6E2', ring: '#4FD1C5' },
  transcribing: { label: 'Transcribing', hue: '#9AE6B4', ring: '#2F855A' },
  thinking: { label: 'Thinking', hue: '#F6C85F', ring: '#B7902F' },
  working: { label: 'Working', hue: '#81E6D9', ring: '#2C7A7B' },
  speaking: { label: 'Speaking', hue: '#E6FFFA', ring: '#4FD1C5' },
  muted: { label: 'Muted · listener off', hue: '#FC8181', ring: '#9B2C2C' },
  approval: { label: 'Approval required', hue: '#F6AD55', ring: '#C05621' },
  error: { label: 'Error', hue: '#FC8181', ring: '#9B2C2C' },
}

function PersonaCanvas({ state }) {
  const ref = useRef(null)
  const stateRef = useRef(state)
  stateRef.current = state

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const reduced = prefersReducedMotion()
    let raf = 0
    let running = true
    let t = 0
    let lastW = 0
    let lastH = 0
    let lastDpr = 0

    const resize = () => {
      const dpr = Math.min(2, (window.devicePixelRatio || 1))
      const w = canvas.clientWidth || 360
      const h = canvas.clientHeight || 360
      if (w === lastW && h === lastH && dpr === lastDpr) return
      lastW = w
      lastH = h
      lastDpr = dpr
      canvas.width = Math.round(w * dpr)
      canvas.height = Math.round(h * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    let ro
    try {
      ro = new ResizeObserver(resize)
      ro.observe(canvas)
    } catch { /* older runtime */ }

    const draw = () => {
      const w = canvas.clientWidth || 360
      const h = canvas.clientHeight || 360
      const cx = w / 2
      const cy = h / 2
      const meta = STATE_META[stateRef.current] || STATE_META.armed
      const breath = reduced ? 0.5 : (Math.sin(t / 45) + 1) / 2
      const active = stateRef.current === 'listening' || stateRef.current === 'working' || stateRef.current === 'speaking'
      const fast = stateRef.current === 'thinking' || stateRef.current === 'transcribing'
      ctx.clearRect(0, 0, w, h)

      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) / 1.2)
      bg.addColorStop(0, 'rgba(9,30,38,0.0)')
      bg.addColorStop(1, 'rgba(4,12,16,0.35)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, w, h)

      const base = Math.min(w, h) * 0.16
      const rings = 4
      for (let i = rings; i >= 1; i--) {
        const spread = active ? 0.9 : 0.6
        const pulse = reduced ? 0 : Math.sin(t / (fast ? 12 : 30) + i) * (active ? 6 : 3)
        const r = base + i * (base * spread) + pulse + breath * 6
        ctx.beginPath()
        ctx.arc(cx, cy, r, 0, Math.PI * 2)
        ctx.strokeStyle = meta.ring
        ctx.globalAlpha = 0.10 + (rings - i) * 0.05
        ctx.lineWidth = 1.5
        ctx.stroke()
      }
      ctx.globalAlpha = 1

      if (fast && !reduced) {
        ctx.beginPath()
        ctx.arc(cx, cy, base * 2.2, t / 10, t / 10 + Math.PI / 2)
        ctx.strokeStyle = meta.hue
        ctx.lineWidth = 3
        ctx.stroke()
      }

      const coreR = base * (0.9 + breath * 0.12)
      const grad = ctx.createRadialGradient(cx, cy - coreR * 0.2, coreR * 0.2, cx, cy, coreR)
      grad.addColorStop(0, '#E6FFFA')
      grad.addColorStop(0.35, meta.hue)
      grad.addColorStop(1, 'rgba(9,30,38,0.15)')
      ctx.beginPath()
      ctx.arc(cx, cy, coreR, 0, Math.PI * 2)
      ctx.fillStyle = grad
      ctx.shadowColor = meta.hue
      ctx.shadowBlur = active ? 40 : 22
      ctx.fill()
      ctx.shadowBlur = 0

      if (reduced) return
      t += 1
    }

    const loop = () => {
      if (!running) return
      draw()
      const idle = stateRef.current === 'armed' || stateRef.current === 'disconnected' || stateRef.current === 'muted'
      raf = window.setTimeout(() => { if (running) requestAnimationFrame(loop) }, idle ? 80 : 33)
    }
    if (reduced) draw()
    else requestAnimationFrame(loop)

    const onVis = () => { running = !document.hidden; if (running && !reduced) requestAnimationFrame(loop) }
    try { document.addEventListener('visibilitychange', onVis) } catch { /* noop */ }

    return () => {
      running = false
      try { window.clearTimeout(raf) } catch { /* noop */ }
      try { if (ro) ro.disconnect() } catch { /* noop */ }
      try { document.removeEventListener('visibilitychange', onVis) } catch { /* noop */ }
    }
  }, [])

  return jsx('canvas', { ref, className: 'h-full w-full', 'aria-hidden': 'true' })
}

function useCron() {
  const [state, setState] = useState({ status: 'loading', jobs: [], at: 0 })
  const load = useCallback(async () => {
    try {
      const data = await host.request('cron.manage', { action: 'list', include_disabled: true })
      const jobs = data && Array.isArray(data.jobs) ? data.jobs : []
      setState({ status: 'ok', jobs, at: Date.now() })
    } catch {
      setState((s) => ({ status: 'unavailable', jobs: s.jobs, at: s.at }))
    }
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [load])
  return [state, load]
}

function useWake() {
  const [state, setState] = useState({
    status: 'loading', listening: false, enabled: false, available: false,
    phrase: 'hey neewa', capture: '', at: 0,
  })
  const load = useCallback(async () => {
    try {
      const data = await host.request('wake.status', { client_capture: true, surface: 'gui' })
      setState({
        status: 'ok',
        listening: !!(data && data.listening),
        enabled: !(data && data.enabled === false),
        available: !(data && data.available === false),
        phrase: String((data && (data.phrase || data.wake_phrase)) || 'hey neewa'),
        capture: String((data && data.capture) || ''),
        at: Date.now(),
      })
    } catch {
      setState((s) => ({ ...s, status: 'unavailable' }))
    }
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [load])
  return [state, load]
}

// config.get in 0.21.3 only allowlists keys like provider/skin/full — NOT tts.provider
// or voice.voice_chat_mode. Never call config.get full (it returns the whole YAML).
function useVoiceRuntime() {
  const [state, setState] = useState({
    status: 'loading',
    speech: 'telemetry unavailable',
    mode: 'telemetry unavailable',
    stt: 'telemetry unavailable',
    at: 0,
  })
  const load = useCallback(async () => {
    try {
      const data = await host.request('voice.toggle', { action: 'status' })
      const speechOn = !!(data && data.tts)
      const modeOn = !!(data && data.enabled)
      const stt = data && data.stt_available
      setState({
        status: 'ok',
        speech: speechOn ? 'on · verified' : 'off · verified',
        mode: modeOn ? 'voice mode on · verified' : 'chained wake · verified',
        stt: stt === false ? 'service unavailable' : stt === true ? 'verified working' : 'telemetry unavailable',
        at: Date.now(),
      })
    } catch {
      setState((s) => ({
        ...s,
        status: 'telemetry',
        speech: 'telemetry unavailable',
        mode: 'telemetry unavailable',
        stt: 'telemetry unavailable',
      }))
    }
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])
  return [state, load]
}

function useApprovals(sessionId) {
  const [state, setState] = useState({ status: 'loading', label: '…', at: 0 })
  const load = useCallback(async () => {
    if (!sessionId) {
      setState({ status: 'ok', label: 'none (no focused session)', at: Date.now() })
      return
    }
    try {
      const data = await host.request('approval.pending', { session_id: sessionId })
      const list = data && Array.isArray(data.approvals) ? data.approvals : []
      setState({
        status: 'ok',
        label: list.length ? `${list.length} pending · verified` : '0 pending · verified',
        at: Date.now(),
      })
    } catch {
      setState({ status: 'telemetry', label: 'telemetry unavailable', at: Date.now() })
    }
  }, [sessionId])
  useEffect(() => {
    load()
    const t = setInterval(load, 20000)
    return () => clearInterval(t)
  }, [load])
  return [state, load]
}

function Grid(rows) {
  return jsx('div', {
    className: 'grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-(--ui-text-tertiary)',
    children: rows.flatMap(([k, v], i) => [
      jsx('span', { children: k }, `k${i}`),
      jsx('span', { className: 'truncate text-foreground', children: v }, `v${i}`),
    ]),
  })
}
function Section(title, child) {
  return jsxs('div', {
    className: 'flex flex-col gap-1.5',
    children: [
      jsx('div', { className: 'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)', children: title }),
      child,
    ],
  })
}
function Btn({ children, onClick, danger }) {
  return jsx('button', {
    className: cn(
      'rounded-full border px-4 py-2 hover:bg-(--chrome-action-hover)',
      danger ? 'border-[#9B2C2C] text-[#FC8181]' : 'border-(--ui-stroke-secondary)',
    ),
    type: 'button',
    onClick,
    children,
  })
}

async function muteListener(refresh) {
  try {
    await host.request('wake.stop', {})
    host.notify({ kind: 'info', message: 'Microphone muted (wake listener off)' })
  } catch {
    host.notify({ kind: 'error', message: 'Mute failed — wake.stop not accepted' })
  }
  if (refresh) refresh()
}
async function rearmListener(refresh) {
  try {
    await host.request('wake.start', { surface: 'gui', client_capture: true })
    host.notify({ kind: 'info', message: 'Wake listener re-armed' })
  } catch {
    host.notify({ kind: 'error', message: 'Rearm failed — wake.start not accepted' })
  }
  if (refresh) refresh()
}
async function stopConversation(sessionId, refresh) {
  // Distinct from mute: end voice mode + audio, interrupt the turn, then rearm.
  try {
    await host.request('voice.toggle', { action: 'off' })
  } catch { /* voice mode may already be off */ }
  if (sessionId) {
    try {
      await host.request('session.interrupt', { session_id: sessionId })
    } catch { /* no running turn is fine */ }
    try {
      await host.request('voice.record', { action: 'stop', session_id: sessionId })
    } catch { /* no capture is fine */ }
  }
  host.notify({ kind: 'info', message: 'Conversation and audio stop requested. Re-arming wake…' })
  window.setTimeout(() => { void rearmListener(refresh) }, 400)
}
async function cancelTask(sessionId) {
  if (!sessionId) {
    host.notify({ kind: 'info', message: 'No focused session to cancel' })
    return
  }
  try {
    const result = await host.request('session.interrupt', { session_id: sessionId })
    const status = result && result.status ? String(result.status) : 'interrupted'
    host.notify({ kind: 'info', message: status === 'not_interrupted' ? 'No active task to cancel' : 'Active task cancelled' })
  } catch {
    host.notify({ kind: 'error', message: 'Cancel not accepted for this session' })
  }
}

function PrivacyBadge({ persona, wake }) {
  const muted = persona === 'muted' || (wake && wake.status === 'ok' && !wake.listening)
  const live = persona === 'listening' || persona === 'transcribing'
  const label = muted ? 'MIC OFF' : live ? 'MIC LIVE' : wake && wake.listening ? 'MIC ARMED' : 'MIC UNKNOWN'
  const color = muted ? '#FC8181' : live ? '#68D391' : '#4FD1C5'
  return jsx('span', {
    className: 'rounded-full border px-3 py-1 text-[0.6875rem] tracking-wide',
    style: { borderColor: color, color },
    children: label,
  })
}

function CommandRail({ variant }) {
  const compact = variant !== 'home'
  const heading = variant === 'hud' ? 'NEEWA HUD' : 'Command Center'
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const model = useValue(host.state.model)
  const profile = useValue(host.state.focusedSessionProfile)
  const connectionId = useValue(host.state.connectionId)
  const sessionId = useValue(host.state.focusedSessionId)
  const usage = useValue(host.state.focusedUsage)
  const [cron, refreshCron] = useCron()
  const [wake, refreshWake] = useWake()
  const [voiceRt] = useVoiceRuntime()
  const [approvals] = useApprovals(sessionId)
  const persona = usePersonaState(wake)
  const meta = STATE_META[persona] || STATE_META.armed
  const ctxPct = usage && usage.context_percentage != null ? `${usage.context_percentage}%` : '—'
  const activeJobs = cron.jobs.filter((j) => j && j.enabled !== false && j.paused !== true)
  const source = connectionId ? String(connectionId) : 'local/primary'
  const isRemote = source !== 'local/primary' && source.toLowerCase().indexOf('local') === -1

  return jsxs('div', {
    className: cn('flex flex-col gap-4 overflow-y-auto p-4 text-sm', compact ? 'h-full' : ''),
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('span', { className: 'font-semibold tracking-wide', children: heading }),
          jsx('span', { className: 'text-(--ui-accent)', children: turnLabel(gateway, busy, waiting) }),
        ],
      }),
      Section('Connection', Grid([
        ['Gateway', connLabel(gateway)],
        ['Socket', String(gateway || 'unknown')],
        ['Source', isRemote ? source : `${source} (not neewa-core-01)`],
        ['Profile', String(profile || 'default')],
      ])),
      Section('Voice', Grid([
        ['State', meta.label],
        ['Wake', wake.status === 'ok' ? (wake.listening ? `armed · ${wake.phrase}` : 'off') : wake.status],
        ['Capture', wake.capture || '—'],
        ['Speech', voiceRt.speech],
        ['Mode', voiceRt.mode],
        ['STT', voiceRt.stt],
        ['TTS provider', 'telemetry unavailable (no tts.provider RPC)'],
        ['Privacy', persona === 'muted' ? 'MIC OFF' : (persona === 'listening' ? 'MIC LIVE' : 'MIC ARMED')],
      ])),
      Section('Assistant', Grid([
        ['Model', String(model || 'unknown')],
        ['Context', ctxPct],
        ['Approvals', approvals.label],
      ])),
      Section('Scheduled jobs', jsxs('div', {
        className: 'flex flex-col gap-1.5',
        children: [
          Grid([
            ['Jobs', cron.status === 'loading' ? 'loading…' : cron.status === 'unavailable' ? 'unavailable' : `${activeJobs.length} active / ${cron.jobs.length} total`],
            ['Updated', cron.status === 'ok' ? ago(cron.at) : '—'],
          ]),
          !compact && cron.status === 'ok' && cron.jobs.length
            ? jsx('div', {
                className: 'flex flex-col gap-1',
                children: cron.jobs.slice(0, 6).map((j, i) => jsxs('div', {
                  className: 'flex items-center justify-between gap-2',
                  children: [
                    jsx('span', { className: 'truncate text-foreground', children: String(j.name || j.job_id || 'job') }),
                    jsx('span', { className: 'shrink-0 text-(--ui-text-tertiary)', children: String(j.schedule || '') }),
                  ],
                }, j.job_id || i)),
              })
            : null,
          cron.status === 'unavailable'
            ? jsx('div', { className: 'text-(--ui-text-tertiary)', children: 'Unavailable (gateway RPC).' })
            : null,
        ],
      })),
      jsxs('div', {
        className: 'mt-1 flex flex-wrap gap-2',
        children: [
          jsx(Btn, { children: 'Mute', danger: true, onClick: () => { haptic('tap'); void muteListener(refreshWake) } }),
          jsx(Btn, { children: 'Stop', danger: true, onClick: () => { haptic('tap'); void stopConversation(sessionId, refreshWake) } }),
          jsx(Btn, { children: 'Cancel task', danger: true, onClick: () => { haptic('tap'); void cancelTask(sessionId) } }),
          jsx(Btn, { children: 'Rearm', onClick: () => { haptic('tap'); void rearmListener(refreshWake) } }),
          compact
            ? jsx(Btn, { children: 'Open Home', onClick: () => host.navigate(HOME_PATH) })
            : jsx(Btn, { children: 'Open HUD', onClick: () => { haptic('tap'); openHudSurface() } }),
          jsx(Btn, { children: 'Chat', onClick: () => host.navigate('/') }),
          jsx(Btn, { children: 'Jobs', onClick: () => host.navigate('/cron') }),
          jsx(Btn, { children: 'Refresh', onClick: () => { haptic('tap'); refreshCron(); refreshWake() } }),
        ],
      }),
      jsx('div', {
        className: 'mt-auto pt-2 text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: 'Host health and morning brief are snapshot-backed. TTS provider is CLI/host config (no plugin RPC). Native HUD: Ctrl+Shift+H.',
      }),
    ],
  })
}

function NeewaHome() {
  const gateway = useValue(host.state.gateway)
  const sessionId = useValue(host.state.focusedSessionId)
  const [wake, refreshWake] = useWake()
  const persona = usePersonaState(wake)
  const meta = STATE_META[persona] || STATE_META.armed

  return jsxs('div', {
    className: 'flex h-full w-full flex-col items-center justify-center gap-4 bg-[#050f14] p-6 text-sm text-foreground',
    children: [
      jsxs('div', {
        className: 'flex w-full max-w-4xl items-center justify-between gap-2',
        children: [
          jsxs('div', {
            className: 'flex items-center gap-2',
            children: [
              jsx('span', { className: 'text-lg font-semibold tracking-[0.2em] text-(--ui-accent)', children: 'NEEWA' }),
              jsx('span', { className: 'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)', children: connLabel(gateway) }),
            ],
          }),
          jsx(PrivacyBadge, { persona, wake }),
        ],
      }),
      jsx('div', {
        className: 'relative flex items-center justify-center',
        style: { width: 'min(52vh, 480px)', height: 'min(52vh, 480px)' },
        children: jsx(PersonaCanvas, { state: persona }),
      }),
      jsx('div', { className: 'text-base font-medium', style: { color: meta.hue }, children: meta.label }),
      jsx('div', {
        className: 'text-[0.75rem] text-(--ui-text-tertiary)',
        children: persona === 'disconnected'
          ? 'Reconnecting to NEEWA on neewa-core-01…'
          : persona === 'muted'
            ? 'Microphone is off. Click Rearm, then say “Hey Neewa”.'
            : 'Say “Hey Neewa”, then speak. No click needed when the listener is armed.',
      }),
      jsxs('div', {
        className: 'mt-2 flex flex-wrap justify-center gap-2',
        children: [
              jsx(Btn, { children: 'Mute', danger: true, onClick: () => { haptic('tap'); void muteListener(refreshWake) } }),
              jsx(Btn, { children: 'Stop', danger: true, onClick: () => { haptic('tap'); void stopConversation(sessionId, refreshWake) } }),
              jsx(Btn, { children: 'Cancel task', danger: true, onClick: () => { haptic('tap'); void cancelTask(sessionId) } }),
              jsx(Btn, { children: 'Rearm', onClick: () => { haptic('tap'); void rearmListener(refreshWake) } }),
          jsx(Btn, { children: 'Open HUD', onClick: () => { haptic('tap'); openHudSurface() } }),
          jsx(Btn, { children: 'Conversation', onClick: () => host.navigate('/') }),
        ],
      }),
    ],
  })
}

function NeewaHud() {
  const [wake] = useWake()
  const persona = usePersonaState(wake)
  const meta = STATE_META[persona] || STATE_META.armed
  const gateway = useValue(host.state.gateway)
  return jsxs('div', {
    className: 'flex h-full w-full flex-col bg-[#050f14] text-sm text-foreground',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-4 border-b border-(--ui-border) px-4 py-3',
        children: [
          jsx('div', { style: { width: 72, height: 72 }, children: jsx(PersonaCanvas, { state: persona }) }),
          jsxs('div', {
            className: 'flex min-w-0 flex-1 flex-col gap-1',
            children: [
              jsxs('div', {
                className: 'flex items-center gap-2',
                children: [
                  jsx('span', { className: 'font-semibold tracking-[0.2em] text-(--ui-accent)', children: 'NEEWA' }),
                  jsx('span', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: connLabel(gateway) }),
                  jsx(PrivacyBadge, { persona, wake }),
                ],
              }),
              jsx('div', { style: { color: meta.hue }, children: meta.label }),
              jsx('div', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: 'Compact HUD. Native overlay: Ctrl+Shift+H (movable, always-on-top).' }),
            ],
          }),
        ],
      }),
      jsx('div', { className: 'min-h-0 flex-1', children: jsx(CommandRail, { variant: 'hud' }) }),
    ],
  })
}

function Pane() {
  return jsx(CommandRail, { variant: 'pane' })
}

function Chip() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const value = turnLabel(gateway, busy, waiting)
  return jsx(Tip, {
    label: `NEEWA ${value} — open Home`,
    children: jsx('button', {
      className: cn('inline-flex h-full items-center gap-1.5 px-2 text-[0.6875rem]', 'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover)'),
      type: 'button',
      onClick: () => { haptic('tap'); host.navigate(HOME_PATH) },
      children: `NEEWA · ${value}`,
    }),
  })
}

function maybeOpenHomeOnStartup() {
  try {
    const hash = (typeof window !== 'undefined' && window.location ? window.location.hash : '') || ''
    const path = hash.replace(/^#/, '')
    if (path === '' || path === '/') {
      setTimeout(() => {
        try {
          const now = (window.location.hash || '').replace(/^#/, '')
          if (now === '' || now === '/') host.navigate(HOME_PATH)
        } catch { /* noop */ }
      }, 1200)
    }
  } catch { /* noop */ }
}

export default {
  id: ID,
  name: 'NEEWA Command Center',
  register(ctx) {
    ctx.register({ id: 'home', area: ROUTES, title: 'NEEWA', data: { path: HOME_PATH }, render: () => jsx(NeewaHome, {}) })
    ctx.register({ id: 'hud', area: ROUTES, title: 'NEEWA HUD', data: { path: HUD_PATH }, render: () => jsx(NeewaHud, {}) })
    ctx.register({ id: 'home-nav', area: SIDEBAR_NAV, order: 5, data: { codicon: 'hubot', label: 'NEEWA Home', path: HOME_PATH } })
    ctx.register({ id: 'hud-nav', area: SIDEBAR_NAV, order: 6, data: { codicon: 'window', label: 'NEEWA HUD', path: HUD_PATH } })
    ctx.register({ id: 'pane', area: 'panes', title: 'NEEWA', data: { placement: 'right', width: '300px' }, render: () => jsx(Pane, {}) })
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 110, render: () => jsx(Chip, {}) })
    ctx.register({
      id: 'open-home',
      area: PALETTE,
      data: { id: 'neewa.openHome', label: 'NEEWA: Open Home', keywords: ['neewa', 'home', 'jarvis', 'assistant'], run: () => host.navigate(HOME_PATH) },
    })
    ctx.register({
      id: 'open-hud',
      area: PALETTE,
      data: { id: 'neewa.openHud', label: 'NEEWA: Open HUD', keywords: ['neewa', 'hud', 'overlay'], run: () => openHudSurface() },
    })
    ctx.register({
      id: 'open-home-key',
      area: KEYBINDS,
      data: { id: 'neewa.openHome', category: 'view', defaults: ['mod+alt+n'], label: 'NEEWA: Open Home', run: () => host.navigate(HOME_PATH) },
    })
    maybeOpenHomeOnStartup()
  },
}
