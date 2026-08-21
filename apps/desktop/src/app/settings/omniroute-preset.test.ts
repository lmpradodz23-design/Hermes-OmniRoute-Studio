import { describe, expect, it } from 'vitest'

import { buildOmniRouteStudioConfig, DZ23_MOA_PRESET, OMNIROUTE_DASHBOARD_URL } from './omniroute-preset'

describe('buildOmniRouteStudioConfig', () => {
  it('keeps the complete standalone OmniRoute dashboard reachable', () => {
    expect(OMNIROUTE_DASHBOARD_URL).toBe('http://127.0.0.1:20128/dashboard')
  })

  it('adds a virtual MoA model and bounded nested delegation', () => {
    const mcpConfig = {
      args: ['C:\\Hermes\\integrations\\omniroute-mcp-bridge.mjs'],
      command: 'C:\\Program Files\\nodejs\\node.exe',
      connect_timeout: 60,
      env: {
        OMNIROUTE_MCP_ENFORCE_SCOPES: 'true',
        OMNIROUTE_MCP_SCOPES: 'read:health,write:budget'
      },
      timeout: 120
    }

    const config = buildOmniRouteStudioConfig({}, mcpConfig)

    expect(config.delegation).toEqual({
      max_concurrent_children: 5,
      max_spawn_depth: 2,
      orchestrator_enabled: true,
      child_timeout_seconds: 1800
    })
    expect(config.goals).toEqual({ max_turns: 50 })
    expect(config.approvals).toMatchObject({
      cron_mode: 'deny',
      mode: 'smart',
      single_query_mode: 'deny'
    })
    const smartPolicy = (config.approvals as { smart_policy: string }).smart_policy

    expect(smartPolicy).toContain('lockfile-based dependency restores')
    expect(smartPolicy).toContain('explicit approval when a command names a new package')
    expect(smartPolicy).not.toContain('builds, dependency installation')
    expect(config.mcp_servers).toEqual({
      omniroute: mcpConfig
    })
    expect(config.moa).toMatchObject({
      default_preset: DZ23_MOA_PRESET,
      presets: {
        [DZ23_MOA_PRESET]: {
          aggregator: { provider: 'omniroute', model: 'auto/best-coding' },
          reference_models: [
            { provider: 'omniroute', model: 'auto/coding:free' },
            { provider: 'omniroute', model: 'auto/best-free' },
            { provider: 'omniroute', model: 'oc/deepseek-v4-flash-free' }
          ]
        }
      }
    })
  })

  it('does not inject a broken generic MCP command when the desktop bridge is unavailable', () => {
    const existing = { command: 'custom-node', args: ['custom-bridge.mjs'] }

    expect(buildOmniRouteStudioConfig({}).mcp_servers).toEqual({})
    expect(buildOmniRouteStudioConfig({ mcp_servers: { omniroute: existing } }).mcp_servers).toEqual({
      omniroute: existing
    })
  })

  it('enables local cross-chat memory and preserves existing configuration', () => {
    const fallbacks = [{ provider: 'nous', model: 'existing' }]

    const config = buildOmniRouteStudioConfig({
      fallback_providers: fallbacks,
      delegation: { max_iterations: 250 },
      memory: { memory_char_limit: 2200 },
      moa: { default_preset: 'personal', presets: { personal: { aggregator: { provider: 'x', model: 'y' } } } }
    })

    expect(config.fallback_providers).toBe(fallbacks)
    expect(config.delegation).toMatchObject({ max_iterations: 250, max_concurrent_children: 5 })
    expect(config.memory).toMatchObject({ memory_enabled: true, user_profile_enabled: true, memory_char_limit: 2200 })
    expect(config.moa).toMatchObject({ default_preset: 'personal', presets: { personal: expect.any(Object) } })
  })

  it('keeps unsafe or irrelevant toolsets disabled without deleting user exclusions', () => {
    const config = buildOmniRouteStudioConfig({ agent: { disabled_toolsets: ['video'] } })

    expect((config.agent as { disabled_toolsets: string[] }).disabled_toolsets).toEqual([
      'video',
      'spotify',
      'homeassistant',
      'yuanbao',
      'feishu_doc',
      'feishu_drive'
    ])
  })
})
