import { cn, haptic, host, Tip, useValue } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

// NEEWA Command Center — real, supported-API data only. No fabricated values;
// every panel shows an explicit unavailable/loading state and data freshness.
// Server host-health, morning brief, and project summaries are host/repo facts
// not exposed to a renderer plugin through a supported read RPC, so instead of
// faking numbers we surface the authoritative path (NEEWA chat + host snapshot)
// as a working control. Conversation/voice/connection/model/context and the
// real scheduled-jobs list ARE available via host.state + host.request.
const ID = 'neewa-command-center'
const ONLINE = new Set(['open', 'connected', 'ready'])

function connLabel(gateway) {
  if (ONLINE.has(gateway)) return 'ONLINE'
  if (gateway === 'connecting') return 'CONNECTING'
  return 'OFFLINE'
}
function turnLabel(gateway, busy, waiting) {
  if (!ONLINE.has(gateway)) return connLabel(gateway)
  if (waiting) return 'THINKING'
  if (busy) return 'WORKING'
  return 'READY'
}
function ago(ts) {
  if (!ts) return 'never'
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000))
  if (s < 60) return `${s}s ago`
  const m = Math.round(s / 60)
  return `${m}m ago`
}

// Real scheduled jobs via the same RPC the core cron UI uses.
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

function Section(title, children) {
  return jsxs('div', {
    className: 'flex flex-col gap-1.5',
    children: [
      jsx('div', { className: 'text-[0.6875rem] uppercase tracking-wide text-(--ui-text-tertiary)', children: title }),
      children,
    ],
  })
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

function Pane() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const model = useValue(host.state.model)
  const profile = useValue(host.state.focusedSessionProfile)
  const connectionId = useValue(host.state.connectionId)
  const usage = useValue(host.state.focusedUsage)
  const [cron, refreshCron] = useCron()

  const ctxPct = usage && usage.context_percentage != null ? `${usage.context_percentage}%` : '—'
  const activeJobs = cron.jobs.filter((j) => j && (j.enabled !== false) && (j.paused !== true))
  const jobsValue =
    cron.status === 'loading'
      ? 'loading…'
      : cron.status === 'unavailable'
        ? 'unavailable'
        : `${activeJobs.length} active / ${cron.jobs.length} total`

  const jobList =
    cron.status === 'ok' && cron.jobs.length
      ? jsx('div', {
          className: 'flex flex-col gap-1',
          children: cron.jobs.slice(0, 6).map((j, i) =>
            jsxs('div', {
              className: 'flex items-center justify-between gap-2',
              children: [
                jsx('span', { className: 'truncate text-foreground', children: String(j.name || j.job_id || 'job') }),
                jsx('span', { className: 'shrink-0 text-(--ui-text-tertiary)', children: String(j.schedule || '') }),
              ],
            }, j.job_id || i),
          ),
        })
      : jsx('div', {
          className: 'text-(--ui-text-tertiary)',
          children: cron.status === 'unavailable' ? 'Scheduled jobs unavailable (gateway RPC).' : 'No scheduled jobs.',
        })

  return jsxs('div', {
    className: 'flex h-full flex-col gap-3 overflow-y-auto p-4 text-sm',
    children: [
      // Header / identity + live status
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx('span', { className: 'font-semibold tracking-wide', children: 'NEEWA' }),
          jsx('span', { className: 'text-(--ui-accent)', children: turnLabel(gateway, busy, waiting) }),
        ],
      }),

      Section(
        'Connection',
        Grid([
          ['Gateway', connLabel(gateway)],
          ['Socket', String(gateway || 'unknown')],
          ['Source', connectionId ? String(connectionId) : 'local/primary'],
          ['Profile', String(profile || 'default')],
        ]),
      ),

      Section(
        'Assistant',
        Grid([
          ['State', turnLabel(gateway, busy, waiting)],
          ['Model', String(model || 'unknown')],
          ['Context', ctxPct],
        ]),
      ),

      Section(
        'Scheduled jobs',
        jsxs('div', {
          className: 'flex flex-col gap-1.5',
          children: [
            Grid([['Jobs', jobsValue], ['Updated', cron.status === 'ok' ? ago(cron.at) : '—']]),
            jobList,
          ],
        }),
      ),

      // Working controls (real navigations), not decorative.
      jsxs('div', {
        className: 'mt-1 flex flex-col gap-2',
        children: [
          jsx('button', {
            className: 'rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--chrome-action-hover)',
            type: 'button',
            onClick: () => host.navigate('/cron'),
            children: 'Open scheduled jobs',
          }),
          jsx('button', {
            className: 'rounded border border-(--ui-stroke-secondary) px-3 py-2 text-left hover:bg-(--chrome-action-hover)',
            type: 'button',
            onClick: () => {
              haptic('tap')
              refreshCron()
              host.notify({ kind: 'info', message: 'NEEWA Command Center refreshed' })
            },
            children: 'Refresh data',
          }),
        ],
      }),

      // Honest note: host health / morning brief / projects come from the
      // authoritative host snapshot and the NEEWA chat, not fabricated here.
      jsx('div', {
        className: 'mt-auto pt-2 text-[0.6875rem] leading-relaxed text-(--ui-text-tertiary)',
        children:
          'Server health, morning brief and project status are host-snapshot backed. Ask NEEWA in chat (e.g. “system status” or “morning brief”) for the authoritative, timestamped report.',
      }),
    ],
  })
}

function Chip() {
  const gateway = useValue(host.state.gateway)
  const busy = useValue(host.state.busy)
  const waiting = useValue(host.state.awaitingResponse)
  const value = turnLabel(gateway, busy, waiting)
  return jsx(Tip, {
    label: `NEEWA ${value}`,
    children: jsx('button', {
      className: cn(
        'inline-flex h-full items-center gap-1.5 px-2 text-[0.6875rem]',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover)',
      ),
      type: 'button',
      onClick: () => {
        haptic('tap')
        host.notify({ kind: 'info', message: `NEEWA ${value}` })
      },
      children: `NEEWA · ${value}`,
    }),
  })
}

export default {
  id: ID,
  name: 'NEEWA Command Center',
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'NEEWA',
      data: { placement: 'right', width: '300px' },
      render: () => jsx(Pane, {}),
    })
    ctx.register({ id: 'chip', area: 'statusBar.right', order: 110, render: () => jsx(Chip, {}) })
  },
}
