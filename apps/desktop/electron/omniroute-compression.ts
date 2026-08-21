import { execFile } from 'node:child_process'

import { hiddenWindowsChildOptions } from './windows-child-options'

export type OmniRouteCompressionMode = 'caveman' | 'off'

export interface OmniRouteCompressionStatus {
  available: boolean
  enabled: boolean
  mode: OmniRouteCompressionMode
  strategy: string
}

interface CompressionCliResult {
  stderr: string
  stdout: string
}

type RunCompressionCli = (args: string[]) => Promise<CompressionCliResult>

const ANSI_PATTERN = new RegExp(`${String.fromCharCode(27)}\\[[0-9;]*m`, 'g')

export function compressionBridgeArgs(action: 'get' | 'set', mode?: OmniRouteCompressionMode): string[] {
  if (action === 'get') {
    return ['--compression-status']
  }

  if (mode !== 'caveman' && mode !== 'off') {
    throw new Error('Unsupported OmniRoute compression mode')
  }

  return ['--compression-set', mode]
}

export function parseCompressionStatus(output: string): OmniRouteCompressionStatus {
  const clean = String(output || '').replace(ANSI_PATTERN, '')
  const start = clean.lastIndexOf('\n{')
  const jsonText = (start >= 0 ? clean.slice(start + 1) : clean).trim()

  const parsed = JSON.parse(jsonText) as {
    enabled?: unknown
    settings?: { defaultMode?: unknown }
    strategy?: unknown
  }

  const rawStrategy = parsed.settings?.defaultMode ?? parsed.strategy ?? 'off'
  const strategy = typeof rawStrategy === 'string' ? rawStrategy.toLowerCase() : 'off'
  const globallyEnabled = typeof parsed.enabled === 'boolean' ? parsed.enabled : strategy !== 'off'
  const enabled = globallyEnabled && (strategy === 'caveman' || strategy === 'standard')

  return {
    available: true,
    enabled,
    mode: enabled ? 'caveman' : 'off',
    strategy
  }
}

export function createOmniRouteCompressionRunner(options: {
  bridgePath: string
  nodeCommand: string
}): RunCompressionCli {
  return args =>
    new Promise((resolve, reject) => {
      execFile(
        options.nodeCommand,
        [options.bridgePath, ...args],
        hiddenWindowsChildOptions({
          encoding: 'utf8',
          env: { ...process.env, NO_COLOR: '1' },
          timeout: 45_000,
          windowsHide: true
        }),
        (error, stdout, stderr) => {
          if (error) {
            const message = String(stderr || error.message || 'OmniRoute CLI failed')
              .replace(ANSI_PATTERN, '')
              .trim()

            reject(new Error(message || 'OmniRoute CLI failed'))

            return
          }

          resolve({ stderr: String(stderr || ''), stdout: String(stdout || '') })
        }
      )
    })
}

export async function getOmniRouteCompressionStatus(run: RunCompressionCli): Promise<OmniRouteCompressionStatus> {
  const result = await run(compressionBridgeArgs('get'))

  return parseCompressionStatus(result.stdout)
}

export async function setOmniRouteCompressionMode(
  mode: OmniRouteCompressionMode,
  run: RunCompressionCli
): Promise<OmniRouteCompressionStatus> {
  await run(compressionBridgeArgs('set', mode))
  const status = await getOmniRouteCompressionStatus(run)

  if (status.mode !== mode) {
    throw new Error(`OmniRoute reported compression mode ${status.strategy} after requesting ${mode}`)
  }

  return status
}

export function unavailableCompressionStatus(): OmniRouteCompressionStatus {
  return { available: false, enabled: false, mode: 'off', strategy: 'unavailable' }
}
