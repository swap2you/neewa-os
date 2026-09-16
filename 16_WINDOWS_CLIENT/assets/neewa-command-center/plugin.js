import { cn, haptic, host, Tip, useValue } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

// NEEWA Command Center + NEEWA Home (native Desktop plugin).
//
// Registers, using only supported APIs:
//   - a full-page route  /neewa-home  (ROUTES_AREA value 'routes')  — the product Home
//   - a sidebar nav entry (SIDEBAR_NAV_AREA value 'sidebar.nav')     — discoverable entry
//   - a status-bar chip and a right-side Command Center pane (unchanged, working)
//   - a best-effort cold-start navigation to /neewa-home
//
// The persona animation is driven by REAL host.state + host.onEvent gateway
// events (not decorative timers beyond a gentle idle breath). No fabricated
// system metrics, no lip-sync claim. Every data panel shows real values with a
// freshness stamp or an explicit "unavailable" state.
const ID = 'neewa-command-center'
// Literal area ids (stable in the installed SDK; avoids import-availability risk).
const ROUTES = 'routes'
const SIDEBAR_NAV = 'sidebar.nav'
const HOME_PATH = '/neewa-home'
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

// Derived persona state from real signals. Wake transitions come from gateway
// events; idle/thinking/working from host.state; disconnected from the socket.
function usePersonaState() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const [wakePhase, setWakePhase] = useState('armed') // armed | listening | active

  useEffect(() => {
    let off = () => {}
    try {
      off = host.onEvent('*', (e) => {
        const t = e && e.type ? String(e.type) : ''
        if (t.indexOf('wake.detected') !== -1) setWakePhase('listening')
        else if (t.indexOf('wake.pause') !== -1) setWakePhase('active')
        else if (t.indexOf('wake.resume') !== -1 || t.indexOf('wake.start') !== -1) setWakePhase('armed')
      })
    } catch {
      /* onEvent unavailable: fall back to host.state only */
    }
    return () => {
      try { off() } catch { /* noop */ }
    }
  }, [])

  if (!ONLINE.has(gateway)) return 'disconnected'
  if (waiting) return 'thinking'
  if (busy) return 'working'
  if (wakePhase === 'listening') return 'listening'
  return 'armed'
}

const STATE_META = {
  disconnected: { label: 'Disconnected', hue: '#6b7785', ring: '#3a444d' },
  armed: { label: 'Ready · listening for “Hey Neewa”', hue: '#4FD1C5', ring: '#2C7A7B' },
  listening: { label: 'Listening', hue: '#63E6E2', ring: '#4FD1C5' },
  thinking: { label: 'Thinking', hue: '#F6C85F', ring: '#B7902F' },
  working: { label: 'Working', hue: '#81E6D9', ring: '#2C7A7B' },
}

// Canvas persona: an original, abstract feminine-coded luminous presence
// (concentric light rings around a soft core). Not a real person, not a movie
// character. Motion derives from state; idle is a slow breath. Reduced-motion
// renders a single static frame. Throttled + paused when hidden for low CPU.
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

    const resize = () => {
      const dpr = Math.min(2, (window.devicePixelRatio || 1))
      const w = canvas.clientWidth || 360
      const h = canvas.clientHeight || 360
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
      const breath = reduced ? 0.5 : (Math.sin(t / 45) + 1) / 2 // 0..1 slow
      const active = stateRef.current === 'listening' || stateRef.current === 'working'
      const fast = stateRef.current === 'thinking'
      ctx.clearRect(0, 0, w, h)

      // background vignette (graphite)
      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.max(w, h) / 1.2)
      bg.addColorStop(0, 'rgba(9,30,38,0.0)')
      bg.addColorStop(1, 'rgba(4,12,16,0.35)')
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, w, h)

      const base = Math.min(w, h) * 0.16
      // concentric rings react to state
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

      // thinking arc (only in thinking state, real busy signal)
      if (fast && !reduced) {
        ctx.beginPath()
        ctx.arc(cx, cy, base * 2.2, t / 10, t / 10 + Math.PI / 2)
        ctx.strokeStyle = meta.hue
        ctx.lineWidth = 3
        ctx.stroke()
      }

      // core
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

      if (reduced) return // single frame
      t += 1
    }

    const loop = () => {
      if (!running) return
      draw()
      // ~30fps active, ~12fps idle for low CPU
      const idle = stateRef.current === 'armed' || stateRef.current === 'disconnected'
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

// The product Home: persona center stage + live state + real widgets + controls.
function NeewaHome() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const model = useValue(host.state.model)
  const profile = useValue(host.state.focusedSessionProfile)
  const connectionId = useValue(host.state.connectionId)
  const usage = useValue(host.state.focusedUsage)
  const persona = usePersonaState()
  const [cron, refreshCron] = useCron()
  const meta = STATE_META[persona] || STATE_META.armed

  const ctxPct = usage && usage.context_percentage != null ? `${usage.context_percentage}%` : '—'
  const activeJobs = cron.jobs.filter((j) => j && j.enabled !== false && j.paused !== true)

  const openChat = () => host.navigate('/')
  const openJobs = () => host.navigate('/cron')

  return jsxs('div', {
    className: 'grid h-full w-full grid-cols-[1fr_320px] bg-[#050f14] text-sm text-foreground',
    children: [
      // Center stage: persona + state label
      jsxs('div', {
        className: 'flex min-h-0 min-w-0 flex-col items-center justify-center gap-4 p-6',
        children: [
          jsxs('div', {
            className: 'flex items-center gap-2 self-start',
            children: [
              jsx('span', { className: 'text-lg font-semibold tracking-[0.2em] text-(--ui-accent)', children: 'NEEWA' }),
              jsx('span', { className: 'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)', children: connLabel(gateway) }),
            ],
          }),
          jsx('div', {
            className: 'relative flex items-center justify-center',
            style: { width: 'min(46vh, 440px)', height: 'min(46vh, 440px)' },
            children: jsx(PersonaCanvas, { state: persona }),
          }),
          jsx('div', { className: 'text-base font-medium', style: { color: meta.hue }, children: meta.label }),
          jsx('div', {
            className: 'text-[0.75rem] text-(--ui-text-tertiary)',
            children: persona === 'disconnected'
              ? 'Reconnecting to NEEWA on neewa-core-01…'
              : 'Say “Hey Neewa”, then speak. No click needed when the listener is armed.',
          }),
          jsxs('div', {
            className: 'mt-2 flex gap-2',
            children: [
              jsx('button', {
                className: 'rounded-full border border-(--ui-stroke-secondary) px-4 py-2 hover:bg-(--chrome-action-hover)',
                type: 'button', onClick: openChat, children: 'Open conversation',
              }),
              jsx('button', {
                className: 'rounded-full border border-(--ui-stroke-secondary) px-4 py-2 hover:bg-(--chrome-action-hover)',
                type: 'button',
                onClick: () => { haptic('tap'); refreshCron(); host.notify({ kind: 'info', message: 'NEEWA Home refreshed' }) },
                children: 'Refresh',
              }),
            ],
          }),
        ],
      }),
      // Right rail: real Command Center data
      jsxs('div', {
        className: 'flex w-[320px] shrink-0 flex-col gap-4 overflow-y-auto border-l border-(--ui-border) bg-[#071318] p-4',
        children: [
          jsxs('div', {
            className: 'flex items-center justify-between',
            children: [
              jsx('span', { className: 'font-semibold tracking-wide', children: 'Command Center' }),
              jsx('span', { className: 'text-(--ui-accent)', children: turnLabel(gateway, busy, waiting) }),
            ],
          }),
          Section('Connection', Grid([
            ['Gateway', connLabel(gateway)],
            ['Socket', String(gateway || 'unknown')],
            ['Source', connectionId ? String(connectionId) : 'local/primary'],
            ['Profile', String(profile || 'default')],
          ])),
          Section('Assistant', Grid([
            ['State', meta.label],
            ['Model', String(model || 'unknown')],
            ['Context', ctxPct],
          ])),
          Section('Scheduled jobs', jsxs('div', {
            className: 'flex flex-col gap-1.5',
            children: [
              Grid([
                ['Jobs', cron.status === 'loading' ? 'loading…' : cron.status === 'unavailable' ? 'unavailable' : `${activeJobs.length} active / ${cron.jobs.length} total`],
                ['Updated', cron.status === 'ok' ? ago(cron.at) : '—'],
              ]),
              cron.status === 'ok' && cron.jobs.length
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
                : jsx('div', { className: 'text-(--ui-text-tertiary)', children: cron.status === 'unavailable' ? 'Unavailable (gateway RPC).' : 'No scheduled jobs.' }),
              jsx('button', {
                className: 'mt-1 rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--chrome-action-hover)',
                type: 'button', onClick: openJobs, children: 'Open scheduled jobs',
              }),
            ],
          })),
          jsx('div', {
            className: 'mt-auto pt-2 text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
            children: 'Server health, morning brief and project status are host-snapshot backed. Ask NEEWA (“system status” / “morning brief”) for the authoritative, timestamped report. Voice output and cost are shown when measured; unsupported fields read “Unavailable”.',
          }),
        ],
      }),
    ],
  })
}

// Compact right-side pane (kept for the chat view).
function Pane() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const model = useValue(host.state.model)
  const profile = useValue(host.state.focusedSessionProfile)
  const connectionId = useValue(host.state.connectionId)
  const usage = useValue(host.state.focusedUsage)
  const [cron] = useCron()
  const ctxPct = usage && usage.context_percentage != null ? `${usage.context_percentage}%` : '—'
  const activeJobs = cron.jobs.filter((j) => j && j.enabled !== false && j.paused !== true)
  return jsxs('div', {
    className: 'flex h-full flex-col gap-3 overflow-y-auto p-4 text-sm',
    children: [
      jsxs('div', { className: 'flex items-center justify-between', children: [
        jsx('span', { className: 'font-semibold tracking-wide', children: 'NEEWA' }),
        jsx('span', { className: 'text-(--ui-accent)', children: turnLabel(gateway, busy, waiting) }),
      ] }),
      Section('Connection', Grid([['Gateway', connLabel(gateway)], ['Source', connectionId ? String(connectionId) : 'local/primary'], ['Profile', String(profile || 'default')]])),
      Section('Assistant', Grid([['Model', String(model || 'unknown')], ['Context', ctxPct]])),
      Section('Scheduled jobs', Grid([['Jobs', cron.status === 'ok' ? `${activeJobs.length} active / ${cron.jobs.length} total` : cron.status === 'unavailable' ? 'unavailable' : 'loading…'], ['Updated', cron.status === 'ok' ? ago(cron.at) : '—']])),
      jsxs('div', { className: 'mt-1 flex flex-col gap-2', children: [
        jsx('button', { className: 'rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--chrome-action-hover)', type: 'button', onClick: () => host.navigate(HOME_PATH), children: 'Open NEEWA Home' }),
        jsx('button', { className: 'rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--chrome-action-hover)', type: 'button', onClick: () => host.navigate('/cron'), children: 'Open scheduled jobs' }),
      ] }),
      jsx('div', { className: 'mt-auto pt-2 text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)', children: 'Server health & morning brief are host-snapshot backed — ask NEEWA in chat for the timestamped report.' }),
    ],
  })
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

// Best-effort cold-start: land on NEEWA Home when the app opened at its default
// route (empty hash / root). Never override a deep link the user navigated to.
function maybeOpenHomeOnStartup() {
  try {
    const hash = (typeof window !== 'undefined' && window.location ? window.location.hash : '') || ''
    const path = hash.replace(/^#/, '')
    if (path === '' || path === '/' ) {
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
    ctx.register({ id: 'home-nav', area: SIDEBAR_NAV, order: 5, data: { codicon: 'hubot', label: 'NEEWA Home', path: HOME_PATH } })
    ctx.register({ id: 'pane', area: 'panes', title: 'NEEWA', data: { placement: 'right', width: '300px' }, render: () => jsx(Pane, {}) })
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 110, render: () => jsx(Chip, {}) })
    maybeOpenHomeOnStartup()
  },
}
