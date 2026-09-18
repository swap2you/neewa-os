import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { ipcMain } from 'electron'

const NEEWA_ROOT = 'C:\\Development\\Workspace\\NEEWA-OS'
const BRIDGE = path.join(NEEWA_ROOT, '12_SCRIPTS', 'neewa_home_bridge.py')

function pythonBin(): string {
  return process.env.NEEWA_PYTHON || 'python'
}

function invokeBridge(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
  return new Promise(resolve => {
    if (!fs.existsSync(BRIDGE)) {
      resolve({ status: 'BLOCKED', reason: 'HOME_BRIDGE_MISSING', authorization_bypass: false })
      return
    }
    const child = spawn(pythonBin(), [BRIDGE, '--json-stdin'], {
      cwd: NEEWA_ROOT,
      windowsHide: true,
      env: { ...process.env, PYTHONUTF8: '1' }
    })
    let stdout = ''
    let stderr = ''
    child.stdout.on('data', chunk => {
      stdout += String(chunk)
    })
    child.stderr.on('data', chunk => {
      stderr += String(chunk)
    })
    child.on('error', err => {
      resolve({
        status: 'BLOCKED',
        reason: 'HOME_BRIDGE_SPAWN_FAILED',
        detail: String(err),
        authorization_bypass: false
      })
    })
    child.on('close', () => {
      try {
        resolve(JSON.parse(stdout.trim() || '{}') as Record<string, unknown>)
      } catch {
        resolve({
          status: 'BLOCKED',
          reason: 'HOME_BRIDGE_INVALID_JSON',
          detail: (stdout || stderr).slice(0, 400),
          authorization_bypass: false
        })
      }
    })
    child.stdin.write(JSON.stringify(payload))
    child.stdin.end()
  })
}

export function registerNeewaMissionIpc(): void {
  ipcMain.handle('hermes:neewa:mission', async (_event, raw) => {
    const payload = raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {}
    const command = String(payload.command || '').trim().toLowerCase()
    if (command !== 'submit' && command !== 'status') {
      return { status: 'BLOCKED', reason: 'UNKNOWN_COMMAND', authorization_bypass: false }
    }
    return invokeBridge({
      command,
      objective: payload.objective,
      origin: payload.origin || 'home',
      workspace: payload.workspace,
      mission_id: payload.mission_id,
      project_id: payload.project_id
    })
  })
}
