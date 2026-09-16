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
function closeNativeHud() {
  const api = nativeHudApi()
  if (!api || typeof api.close !== 'function') return false
  try {
    api.close()
    return true
  } catch {
    return false
  }
}
function openHudSurface() {
  try { host.navigate(HUD_PATH) } catch { /* noop */ }
  return 'in-app'
}
function closeHudSurface() {
  if (closeNativeHud()) return 'native'
  try { host.navigate(HOME_PATH) } catch { /* noop */ }
  return 'in-app'
}
function goHomeSurface() {
  closeNativeHud()
  try { host.navigate(HOME_PATH) } catch { /* noop */ }
}
function transcriptPath() {
  try {
    const stored = host.state.focusedStoredSessionId && host.state.focusedStoredSessionId.get
      ? host.state.focusedStoredSessionId.get()
      : null
    const pinned = stored || (typeof localStorage !== 'undefined' ? localStorage.getItem('neewa.personalSessionId') : null)
    if (pinned) return '/' + encodeURIComponent(String(pinned))
  } catch { /* noop */ }
  return HOME_PATH
}
function openTranscript() {
  closeNativeHud()
  try { host.navigate(transcriptPath()) } catch { /* noop */ }
}
function markVoiceTrace(stage) {
  try {
    const w = window
    if (!w.__NEEWA_VOICE_TRACE__) w.__NEEWA_VOICE_TRACE__ = { stages: [] }
    const stages = w.__NEEWA_VOICE_TRACE__.stages
    stages.push({ stage, at: Date.now() })
    if (stages.length > 40) stages.splice(0, stages.length - 40)
  } catch { /* noop */ }
}

function voiceApi() {
  try {
    return typeof window !== 'undefined' ? window.__NEEWA_VOICE__ : null
  } catch {
    return null
  }
}

function voiceSnapshot() {
  const api = voiceApi()
  if (!api) return null
  try {
    return typeof api.snapshot === 'function' ? api.snapshot() : api
  } catch {
    return api
  }
}

function useVoiceController() {
  const [snap, setSnap] = useState(() => voiceSnapshot())
  useEffect(() => {
    const on = () => setSnap(voiceSnapshot())
    try { window.addEventListener('hermes:neewa-voice', on) } catch { /* noop */ }
    const t = window.setInterval(on, 400)
    on()
    return () => {
      try { window.removeEventListener('hermes:neewa-voice', on) } catch { /* noop */ }
      window.clearInterval(t)
    }
  }, [])
  return snap
}

function resolveSessionId(focused, stored) {
  try {
    const voice = voiceSnapshot()
    const fromVoice = voice && (voice.storedSessionId || voice.sessionId)
    if (fromVoice) return String(fromVoice)
  } catch { /* noop */ }
  if (stored) return String(stored)
  if (focused) return String(focused)
  try {
    const pinned = typeof localStorage !== 'undefined' ? localStorage.getItem('neewa.personalSessionId') : null
    if (pinned) return String(pinned)
  } catch { /* noop */ }
  return null
}

function derivePersona(gateway, busy, waiting, phase, wake, probe, voice) {
  if (gateway === 'connecting') return 'connecting'
  if (!ONLINE.has(gateway)) return 'offline'
  const vp = voice && voice.phase
  if (vp === 'ERROR') return 'error'
  if (vp === 'PLAYING_AUDIO') return 'speaking'
  if (vp === 'AGENT_WORKING') return waiting ? 'thinking' : 'working'
  if (vp === 'TRANSCRIBING') return 'transcribing'
  if (vp === 'RECORDING' || (voice && voice.recording === true)) return 'listening'
  if (vp === 'WAKE_DETECTED') return 'detected'
  if (vp === 'STOPPING') return 'starting'
  if (phase === 'error') return 'error'
  if (waiting) return 'thinking'
  if (busy) return 'working'
  if (phase === 'approval') return 'approval'
  if (phase === 'speaking') return 'speaking'
  if (phase === 'transcribing') return 'transcribing'
  if (phase === 'detected') return voice && voice.recording === true ? 'listening' : 'detected'
  if (phase === 'listening' && voice && voice.recording === true) return 'listening'
  if (probe && probe.permission === 'denied') return 'mic_denied'
  if (probe && probe.wrongDevice) return 'device_unavailable'
  if (!wake || wake.status === 'loading') return 'starting'
  if (wake.status === 'unavailable') return 'wake_unavailable'
  if (wake.status === 'ok' && wake.available === false) return 'wake_unavailable'
  if (wake.status === 'ok' && (wake.enabled === false || wake.listening === false)) return 'muted'
  if (wake.status === 'ok' && wake.listening) {
    // Server audio_silent is authoritative for client-capture health.
    // Never open a second getUserMedia probe — it steals the Windows mic
    // from Desktop's wake.feed and makes the detector go deaf.
    // Missing audio_silent is UNKNOWN, never READY.
    if (wake.audioSilent === true) return 'stream_inactive'
    if (wake.audioSilentKnown !== true && !(wake.pcmFrames > 0)) return 'unknown'
    if (wake.armedAt && (Date.now() - wake.armedAt) < 2500) return 'starting'
    if (wake.audioSilentKnown === true && wake.audioSilent === false) return 'stream_active'
    if (wake.pcmFrames > 0) return 'stream_active'
    return 'unknown'
  }
  return 'unknown'
}

function usePersonaState(wake, probe) {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const voice = useVoiceController()
  const [phase, setPhase] = useState('unknown')

  useEffect(() => {
    let off = () => {}
    try {
      off = host.onEvent('*', (e) => {
        const t = e && e.type ? String(e.type).toLowerCase() : ''
        if (t.indexOf('wake.detected') !== -1) {
          setPhase('detected')
          markVoiceTrace('wake.detected')
          // ChatView stays mounted under Home (Desktop keep-mounted patch).
          // Do NOT navigate to '/' — that is NEW_CHAT_ROUTE and mints sessions.
          // Listening is owned by window.__NEEWA_VOICE__, not this event.
        } else if (t.indexOf('stt') !== -1 || t.indexOf('transcript') !== -1 || t.indexOf('asr') !== -1) {
          setPhase('transcribing')
          markVoiceTrace('stt')
        } else if (t.indexOf('tts') !== -1 || t.indexOf('audio.play') !== -1 || t.indexOf('speaking') !== -1) {
          setPhase('speaking')
          markVoiceTrace('tts')
        } else if (t.indexOf('approval') !== -1) setPhase('approval')
        else if (t.indexOf('wake.pause') !== -1) {
          markVoiceTrace('wake.pause')
        } else if (t.indexOf('wake.resume') !== -1 || t.indexOf('wake.start') !== -1) setPhase('unknown')
        else if (t.indexOf('wake.stop') !== -1) setPhase('muted')
        else if (t.indexOf('error') !== -1 && t.indexOf('parse') === -1) setPhase('error')
      })
    } catch { /* onEvent unavailable */ }
    return () => { try { off() } catch { /* noop */ } }
  }, [])

  return derivePersona(gateway, busy, waiting, phase, wake, probe, voice)
}

function usePinPersonalSession() {
  const stored = useValue(host.state.focusedStoredSessionId)
  useEffect(() => {
    if (!stored) return
    try { localStorage.setItem('neewa.personalSessionId', String(stored)) } catch { /* noop */ }
  }, [stored])
}

const STATE_META = {
  offline: { label: 'Offline', hue: '#6b7785', ring: '#3a444d' },
  connecting: { label: 'Connecting', hue: '#A0AEC0', ring: '#4A5568' },
  unknown: { label: 'Unknown · waiting for wake telemetry', hue: '#A0AEC0', ring: '#4A5568' },
  starting: { label: 'Listener starting…', hue: '#76E4F7', ring: '#2C7A7B' },
  armed: { label: 'Ready · say “Hey Neewa”', hue: '#4FD1C5', ring: '#2C7A7B' },
  stream_active: { label: 'Ready · say “Hey Neewa”', hue: '#4FD1C5', ring: '#2C7A7B' },
  stream_inactive: { label: 'Listener on · mic audio not reaching NEEWA', hue: '#F6AD55', ring: '#C05621' },
  detected: { label: 'Wake detected · starting capture', hue: '#68D391', ring: '#276749' },
  listening: { label: 'Listening to you…', hue: '#63E6E2', ring: '#4FD1C5' },
  transcribing: { label: 'Transcribing…', hue: '#9AE6B4', ring: '#2F855A' },
  thinking: { label: 'Thinking…', hue: '#F6C85F', ring: '#B7902F' },
  working: { label: 'Working…', hue: '#81E6D9', ring: '#2C7A7B' },
  speaking: { label: 'Speaking…', hue: '#E6FFFA', ring: '#4FD1C5' },
  muted: { label: 'Muted · tap Rearm', hue: '#FC8181', ring: '#9B2C2C' },
  wake_unavailable: { label: 'Wake unavailable', hue: '#FC8181', ring: '#9B2C2C' },
  mic_denied: { label: 'Microphone permission denied', hue: '#FC8181', ring: '#9B2C2C' },
  device_unavailable: { label: 'Wrong capture device (not Realtek)', hue: '#F6AD55', ring: '#C05621' },
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
      const meta = STATE_META[stateRef.current] || STATE_META.unknown
      const breath = reduced ? 0.5 : (Math.sin(t / 45) + 1) / 2
      const active = stateRef.current === 'listening' || stateRef.current === 'working' || stateRef.current === 'speaking' || stateRef.current === 'detected' || stateRef.current === 'stream_active'
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
      const idle = stateRef.current === 'armed' || stateRef.current === 'offline' || stateRef.current === 'muted' || stateRef.current === 'unknown' || stateRef.current === 'stream_inactive'
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
    audioSilent: false, audioSilentKnown: false, pcmFrames: 0, phrase: 'hey neewa', capture: '', hint: '', owner: '',
    at: 0, armedAt: 0,
  })
  const armedAtRef = useRef(0)
  const wasListeningRef = useRef(false)
  const load = useCallback(async () => {
    try {
      const data = await host.request('wake.status', { client_capture: true, surface: 'gui' })
      const listening = !!(data && data.listening)
      if (listening && !wasListeningRef.current) armedAtRef.current = Date.now()
      if (!listening) armedAtRef.current = 0
      wasListeningRef.current = listening
      const silentKnown = !!(data && Object.prototype.hasOwnProperty.call(data, 'audio_silent'))
      let pcmFrames = 0
      try {
        const health = window.__NEEWA_WAKE_HEALTH__
        if (health && typeof health.frames === 'number') pcmFrames = health.frames
      } catch { /* noop */ }
      setState({
        status: 'ok',
        listening,
        enabled: !(data && data.enabled === false),
        available: !(data && data.available === false),
        audioSilent: !!(data && data.audio_silent),
        audioSilentKnown: silentKnown,
        pcmFrames,
        phrase: String((data && (data.phrase || data.wake_phrase)) || 'hey neewa'),
        capture: String((data && data.capture) || ''),
        hint: String((data && data.hint) || ''),
        owner: String((data && data.owner_surface) || ''),
        at: Date.now(),
        armedAt: armedAtRef.current,
      })
    } catch {
      setState((s) => ({ ...s, status: 'unavailable' }))
    }
  }, [])
  useEffect(() => {
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [load])
  return [state, load]
}

// Device label only — NEVER open getUserMedia here. A second mic stream on
// Windows steals the device from Desktop's wake.feed and the server logs
// "mic delivers only silence" while Conversation PTT still works.
function useCaptureProbe() {
  const [state, setState] = useState({
    status: 'unknown', permission: 'unknown', device: 'unknown',
    label: '', level: 'unknown', rms: 0, wrongDevice: false, at: 0,
  })
  useEffect(() => {
    let stopped = false
    const sample = async () => {
      if (stopped) return
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        setState((s) => ({ ...s, status: 'unavailable', device: 'unavailable' }))
        return
      }
      try {
        const devices = await navigator.mediaDevices.enumerateDevices()
        const inputs = devices.filter((d) => d.kind === 'audioinput')
        const labeled = inputs.find((d) => d.label) || inputs[0]
        const label = labeled && labeled.label ? String(labeled.label) : ''
        const wrongDevice = /iriun/i.test(label) && !/realtek/i.test(label)
        setState({
          status: 'ok',
          permission: label ? 'granted' : 'unknown',
          device: wrongDevice ? 'unavailable' : (label ? 'ok' : 'unknown'),
          label: label || 'Windows default input',
          level: 'unknown',
          rms: 0,
          wrongDevice,
          at: Date.now(),
        })
      } catch {
        setState((s) => ({ ...s, status: 'unavailable' }))
      }
    }
    void sample()
    const t = window.setInterval(() => { void sample() }, 15000)
    return () => {
      stopped = true
      try { window.clearInterval(t) } catch { /* noop */ }
    }
  }, [])
  return state
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

let controlLock = false

async function muteListener(refresh) {
  if (controlLock) {
    host.notify({ kind: 'error', message: 'Voice control is busy' })
    return
  }
  controlLock = true
  try {
    const api = voiceApi()
    if (api && typeof api.muteMic === 'function') {
      const result = await api.muteMic()
      if (!result || !result.ok) {
        host.notify({ kind: 'error', message: (result && result.error) || 'Mute was not accepted' })
        return
      }
    }
    await host.request('wake.stop', {})
    host.notify({ kind: 'info', message: 'Microphone muted' })
  } catch {
    host.notify({ kind: 'error', message: 'Mute failed — capture or wake.stop not accepted' })
  } finally {
    controlLock = false
    if (refresh) refresh()
  }
}
async function rearmListener(refresh) {
  if (controlLock) {
    host.notify({ kind: 'error', message: 'Voice control is busy' })
    return
  }
  controlLock = true
  try {
    await host.request('wake.start', { surface: 'gui', client_capture: true })
    host.notify({ kind: 'info', message: 'Wake listener re-armed' })
  } catch {
    host.notify({ kind: 'error', message: 'Rearm failed — wake.start not accepted' })
  } finally {
    controlLock = false
    if (refresh) refresh()
  }
}

// Backup path when Sherpa misses an accented wake. Starts the SAME NEEWA
// voice conversation Desktop uses after wake.detected — still remote NEEWA,
// not a different chatbot. voice.record start is NOT used (server PortAudio).
// Do NOT dispatch hermes:composer-voice-toggle: that toggles and can stop
// an already-started conversation. Do NOT navigate to '/'.
async function startListening(refresh) {
  if (controlLock) {
    host.notify({ kind: 'error', message: 'Voice control is busy' })
    return
  }
  controlLock = true
  markVoiceTrace('startListening')
  try {
    await host.request('wake.pause', {})
  } catch { /* listener may already be idle */ }
  try {
    const api = voiceApi()
    if (!api || typeof api.start !== 'function') {
      host.notify({ kind: 'error', message: 'Voice controller is not mounted. Relaunch packed Hermes on Home.' })
      try { await host.request('wake.start', { surface: 'gui', client_capture: true }) } catch { /* rearm best-effort */ }
      return
    }
    const result = await api.start()
    if (result && result.ok && result.recording) {
      host.notify({ kind: 'info', message: 'NEEWA is listening — speak now' })
    } else {
      host.notify({ kind: 'error', message: (result && result.error) || 'Recording did not start' })
      try { await host.request('wake.start', { surface: 'gui', client_capture: true }) } catch { /* rearm best-effort */ }
    }
  } catch {
    host.notify({ kind: 'error', message: 'Start listening failed' })
    try { await host.request('wake.start', { surface: 'gui', client_capture: true }) } catch { /* rearm best-effort */ }
  } finally {
    controlLock = false
    if (refresh) refresh()
  }
}
async function stopConversation(sessionId, refresh) {
  if (controlLock) {
    host.notify({ kind: 'error', message: 'Voice control is busy' })
    return
  }
  controlLock = true
  let rearm = false
  try {
    const api = voiceApi()
    if (!api || typeof api.stop !== 'function') {
      host.notify({ kind: 'error', message: 'Voice controller is not mounted; cannot stop capture' })
      return
    }
    const result = await api.stop()
    if (!result || !result.ok) {
      host.notify({ kind: 'error', message: (result && result.error) || 'Stop was not accepted' })
      return
    }
    const sid = sessionId || (api && (api.storedSessionId || api.sessionId))
    if (sid) {
      try {
        await host.request('session.interrupt', { session_id: sid })
      } catch { /* no running turn is fine */ }
    }
    host.notify({ kind: 'info', message: 'Voice conversation stopped' })
    rearm = true
  } catch {
    host.notify({ kind: 'error', message: 'Stop failed' })
  } finally {
    controlLock = false
  }
  if (rearm) window.setTimeout(() => { void rearmListener(refresh) }, 400)
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
  // After wake.detected the detector pauses (!wake.listening). That is NOT mute —
  // conversation capture owns the mic. Never treat pause as MIC OFF mid-turn.
  // MIC LIVE requires actual recording (persona listening/transcribing), not wake.detected.
  const conversational = persona === 'listening' || persona === 'transcribing' || persona === 'detected'
    || persona === 'speaking' || persona === 'thinking' || persona === 'working'
  const muted = persona === 'muted' || (!conversational && wake && wake.status === 'ok' && !wake.listening)
  let label = 'UNKNOWN'
  let color = '#A0AEC0'
  if (persona === 'listening' || persona === 'transcribing') { label = 'MIC LIVE'; color = '#68D391' }
  else if (persona === 'detected') { label = 'WAKE'; color = '#68D391' }
  else if (persona === 'speaking' || persona === 'thinking' || persona === 'working') { label = 'BUSY'; color = '#F6C85F' }
  else if (muted) { label = 'MIC OFF'; color = '#FC8181' }
  else if (persona === 'stream_active') { label = 'READY'; color = '#68D391' }
  else if (persona === 'stream_inactive') { label = 'NO AUDIO'; color = '#F6AD55' }
  else if (persona === 'starting' || persona === 'armed') { label = 'STARTING'; color = '#4FD1C5' }
  else if (persona === 'mic_denied') { label = 'MIC DENIED'; color = '#FC8181' }
  else if (persona === 'device_unavailable') { label = 'WRONG MIC'; color = '#F6AD55' }
  else if (persona === 'wake_unavailable') { label = 'WAKE OFF'; color = '#FC8181' }
  else if (persona === 'offline' || persona === 'connecting') { label = persona === 'connecting' ? 'CONNECTING' : 'OFFLINE'; color = '#A0AEC0' }
  return jsx('span', {
    className: 'rounded-full border px-3 py-1 text-[0.6875rem] tracking-wide',
    style: { borderColor: color, color },
    children: label,
  })
}

function CommandRail({ variant }) {
  const compact = variant !== 'home'
  const heading = variant === 'hud' ? 'NEEWA HUD' : 'Command Center'
  usePinPersonalSession()
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const model = useValue(host.state.model)
  const profile = useValue(host.state.focusedSessionProfile)
  const connectionId = useValue(host.state.connectionId)
  const focused = useValue(host.state.focusedSessionId)
  const stored = useValue(host.state.focusedStoredSessionId)
  const sessionId = resolveSessionId(focused, stored)
  const usage = useValue(host.state.focusedUsage)
  const [cron, refreshCron] = useCron()
  const [wake, refreshWake] = useWake()
  const probe = useCaptureProbe()
  const [voiceRt] = useVoiceRuntime()
  const [approvals] = useApprovals(sessionId)
  const persona = usePersonaState(wake, probe)
  const meta = STATE_META[persona] || STATE_META.unknown
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
        ['Wake', wake.status === 'ok' ? (wake.listening ? `listener on · ${wake.phrase}` : 'off') : wake.status],
        ['Aliases', 'hey neewa · hey niva · hey neeva · hey neva · he neva'],
        ['Capture', wake.capture || '—'],
        ['Stream', wake.status === 'ok' ? (wake.audioSilent === true ? 'SILENT — Rearm (PCM not reaching detector)' : (wake.audioSilentKnown !== true && !(wake.pcmFrames > 0) ? 'UNKNOWN — no audio_silent/PCM proof' : (persona === 'stream_active' ? 'READY · wake audio flowing' : (persona === 'starting' ? 'starting…' : 'unknown')))) : 'unknown'],
        ['Windows mic', probe.label || (probe.permission === 'denied' ? 'permission denied' : probe.status)],
        ['Speech', voiceRt.speech],
        ['Mode', voiceRt.mode],
        ['STT', voiceRt.stt],
        ['TTS provider', 'telemetry unavailable (no tts.provider RPC) · live=nous coral + auto_tts'],
        ['Privacy', persona === 'muted' ? 'MIC OFF' : (persona === 'listening' || persona === 'transcribing' ? 'MIC LIVE (conversation)' : (persona === 'detected' ? 'WAKE' : (persona === 'speaking' || persona === 'thinking' || persona === 'working' ? 'BUSY' : (persona === 'stream_active' ? 'READY' : (persona === 'stream_inactive' ? 'NO AUDIO' : 'UNKNOWN')))))],
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
          jsx(Btn, { children: 'Start listening', onClick: () => { haptic('tap'); void startListening(refreshWake) } }),
          jsx(Btn, { children: 'Mute', danger: true, onClick: () => { haptic('tap'); void muteListener(refreshWake) } }),
          jsx(Btn, { children: 'Stop', danger: true, onClick: () => { haptic('tap'); void stopConversation(sessionId, refreshWake) } }),
          jsx(Btn, { children: 'Cancel task', danger: true, onClick: () => { haptic('tap'); void cancelTask(sessionId) } }),
          jsx(Btn, { children: 'Rearm', onClick: () => { haptic('tap'); void rearmListener(refreshWake) } }),
          compact
            ? jsx(Btn, { children: 'Open Home', onClick: () => { haptic('tap'); goHomeSurface() } })
            : jsx(Btn, { children: 'Open HUD', onClick: () => { haptic('tap'); openHudSurface() } }),
          variant === 'hud'
            ? jsx(Btn, { children: 'Close HUD', onClick: () => { haptic('tap'); closeHudSurface() } })
            : null,
          jsx(Btn, { children: 'Chat', onClick: () => { haptic('tap'); openTranscript() } }),
          jsx(Btn, { children: 'Jobs', onClick: () => host.navigate('/cron') }),
          jsx(Btn, { children: 'Refresh', onClick: () => { haptic('tap'); refreshCron(); refreshWake() } }),
        ],
      }),
      jsx('div', {
        className: 'mt-auto pt-2 text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children: 'Home = assistant. HUD = compact overlay. Conversation = optional transcript. Same NEEWA session. Unmute the speaker icon. Double-clap is off unless localStorage neewa.doubleClap=1.',
      }),
    ],
  })
}

function NeewaHome() {
  const gateway = useValue(host.state.gateway)
  const focused = useValue(host.state.focusedSessionId)
  const stored = useValue(host.state.focusedStoredSessionId)
  const sessionId = resolveSessionId(focused, stored)
  usePinPersonalSession()
  const [wake, refreshWake] = useWake()
  const probe = useCaptureProbe()
  const persona = usePersonaState(wake, probe)
  const meta = STATE_META[persona] || STATE_META.unknown

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
        children: persona === 'offline' || persona === 'connecting'
          ? 'Reconnecting to NEEWA on neewa-core-01…'
          : persona === 'muted'
            ? 'Microphone listener is off. Tap Rearm, wait for READY, then say “Hey Neewa”.'
            : persona === 'stream_inactive'
              ? (wake.hint || 'Mic audio is not reaching the detector. Tap Rearm. Close other apps using the mic (Wispr, Zoom).')
              : persona === 'device_unavailable'
                ? (probe.wrongDevice
                  ? 'Wake capture may use Iriun Webcam. Set Communications default to Realtek, then restart NEEWA.'
                  : 'Capture device unavailable.')
            : persona === 'mic_denied'
              ? 'Windows denied microphone permission for Hermes Desktop.'
            : persona === 'stream_active'
              ? 'Stay on Home. Say “Hey Neewa”, then your request. Do not switch to Conversation — the orb is the assistant.'
            : persona === 'unknown'
              ? 'Listener is on but audio health is unproven. Wait for READY or tap Rearm.'
            : persona === 'listening'
              ? 'Listening — keep speaking your request.'
            : persona === 'detected'
              ? 'Wake heard — waiting for microphone capture to start.'
            : persona === 'thinking' || persona === 'working'
              ? 'NEEWA is working on your request…'
            : persona === 'speaking'
              ? 'NEEWA is speaking…'
            : persona === 'starting'
              ? 'Listener starting… wait for READY before speaking.'
            : 'Wait for READY (green). Do not assume the mic is live until then.',
      }),
      jsxs('div', {
        className: 'mt-2 flex flex-wrap justify-center gap-2',
        children: [
              jsx(Btn, { children: 'Start listening', onClick: () => { haptic('tap'); void startListening(refreshWake) } }),
              jsx(Btn, { children: 'Mute', danger: true, onClick: () => { haptic('tap'); void muteListener(refreshWake) } }),
              jsx(Btn, { children: 'Stop', danger: true, onClick: () => { haptic('tap'); void stopConversation(sessionId, refreshWake) } }),
              jsx(Btn, { children: 'Cancel task', danger: true, onClick: () => { haptic('tap'); void cancelTask(sessionId) } }),
              jsx(Btn, { children: 'Rearm', onClick: () => { haptic('tap'); void rearmListener(refreshWake) } }),
          jsx(Btn, { children: 'Open HUD', onClick: () => { haptic('tap'); openHudSurface() } }),
          jsx(Btn, { children: 'Conversation', onClick: () => { haptic('tap'); openTranscript() } }),
        ],
      }),
    ],
  })
}

function NeewaHud() {
  const [wake, refreshWake] = useWake()
  const probe = useCaptureProbe()
  const persona = usePersonaState(wake, probe)
  const meta = STATE_META[persona] || STATE_META.unknown
  const gateway = useValue(host.state.gateway)
  const focused = useValue(host.state.focusedSessionId)
  const stored = useValue(host.state.focusedStoredSessionId)
  const sessionId = resolveSessionId(focused, stored)
  usePinPersonalSession()
  return jsxs('div', {
    className: 'relative flex h-full w-full flex-col overflow-hidden text-sm text-foreground',
    style: {
      background: 'radial-gradient(ellipse at 30% 20%, rgba(20,80,90,0.55) 0%, rgba(5,15,20,0.92) 45%, #030a0e 100%)',
    },
    children: [
      jsx('div', {
        className: 'pointer-events-none absolute inset-0 opacity-40',
        style: {
          backgroundImage: 'radial-gradient(circle at 70% 80%, rgba(79,209,197,0.12), transparent 40%), radial-gradient(circle at 10% 60%, rgba(104,211,145,0.08), transparent 35%)',
        },
      }),
      jsxs('div', {
        className: 'relative z-10 flex items-center gap-4 border-b border-white/10 px-4 py-3 backdrop-blur-sm',
        children: [
          jsx('div', { style: { width: 72, height: 72 }, children: jsx(PersonaCanvas, { state: persona }) }),
          jsxs('div', {
            className: 'flex min-w-0 flex-1 flex-col gap-1',
            children: [
              jsxs('div', {
                className: 'flex flex-wrap items-center gap-2',
                children: [
                  jsx('span', { className: 'font-semibold tracking-[0.2em] text-(--ui-accent)', children: 'NEEWA' }),
                  jsx('span', { className: 'text-[0.6875rem] text-(--ui-text-tertiary)', children: connLabel(gateway) }),
                  jsx(PrivacyBadge, { persona, wake }),
                ],
              }),
              jsx('div', { style: { color: meta.hue }, children: meta.label }),
              jsx('div', {
                className: 'text-[0.6875rem] text-(--ui-text-tertiary)',
                children: 'Compact overlay of the same NEEWA — not a second assistant. Go Home keeps this conversation.',
              }),
            ],
          }),
          jsxs('div', {
            className: 'flex shrink-0 flex-wrap gap-2',
            children: [
              jsx(Btn, { children: 'Go Home', onClick: () => { haptic('tap'); goHomeSurface() } }),
              jsx(Btn, { children: 'Conversation', onClick: () => { haptic('tap'); openTranscript() } }),
              jsx(Btn, { children: 'Close HUD', onClick: () => { haptic('tap'); closeHudSurface() } }),
            ],
          }),
        ],
      }),
      jsxs('div', {
        className: 'relative z-10 flex flex-wrap gap-2 border-b border-white/10 px-4 py-2',
        children: [
          jsx(Btn, { children: 'Start listening', onClick: () => { haptic('tap'); void startListening(refreshWake) } }),
          jsx(Btn, { children: 'Mute', danger: true, onClick: () => { haptic('tap'); void muteListener(refreshWake) } }),
          jsx(Btn, { children: 'Stop', danger: true, onClick: () => { haptic('tap'); void stopConversation(sessionId, refreshWake) } }),
          jsx(Btn, { children: 'Rearm', onClick: () => { haptic('tap'); void rearmListener(refreshWake) } }),
        ],
      }),
      jsx('div', { className: 'relative z-10 min-h-0 flex-1', children: jsx(CommandRail, { variant: 'hud' }) }),
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
      try { host.navigate(HOME_PATH) } catch { /* noop */ }
    }
  } catch { /* noop */ }
}

function bindClapToVoice() {
  const onClap = () => { void startListening(null) }
  try { window.addEventListener('hermes:neewa-clap', onClap) } catch { /* noop */ }
}

export default {
  id: ID,
  name: 'NEEWA Command Center',
  register(ctx) {
    ctx.register({ id: 'home', area: ROUTES, title: 'NEEWA', data: { path: HOME_PATH, keepChatMounted: true }, render: () => jsx(NeewaHome, {}) })
    ctx.register({ id: 'hud', area: ROUTES, title: 'NEEWA HUD', data: { path: HUD_PATH, keepChatMounted: true }, render: () => jsx(NeewaHud, {}) })
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
    bindClapToVoice()
  },
}
