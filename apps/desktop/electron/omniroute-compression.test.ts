import { describe, expect, it } from 'vitest'

import {
  compressionBridgeArgs,
  getOmniRouteCompressionStatus,
  parseCompressionStatus,
  setOmniRouteCompressionMode
} from './omniroute-compression'

describe('OmniRoute compression control', () => {
  it('parses Caveman standard mode after harmless startup logs', () => {
    expect(parseCompressionStatus('Loaded local env\n{\n  "strategy": "standard",\n  "settings": {}\n}')).toEqual({
      available: true,
      enabled: true,
      mode: 'caveman',
      strategy: 'standard'
    })
  })

  it('maps the explicit off strategy to a disabled state', () => {
    expect(parseCompressionStatus('{"strategy":"off"}')).toEqual({
      available: true,
      enabled: false,
      mode: 'off',
      strategy: 'off'
    })
  })

  it('uses a fixed allowlist for CLI mutations and verifies the resulting state', async () => {
    const calls: string[][] = []

    const run = async (args: string[]) => {
      calls.push(args)

      return {
        stderr: '',
        stdout: args.includes('--compression-status') ? '{"enabled":false,"strategy":"off"}' : '{"success":true}'
      }
    }

    expect(await setOmniRouteCompressionMode('off', run)).toMatchObject({ enabled: false, mode: 'off' })
    expect(calls).toEqual([compressionBridgeArgs('set', 'off'), compressionBridgeArgs('get')])
    expect(await getOmniRouteCompressionStatus(run)).toMatchObject({ available: true })
  })

  it('rejects unknown modes before starting a process', () => {
    expect(() => compressionBridgeArgs('set', 'ultra' as never)).toThrow(/Unsupported/)
  })
})
