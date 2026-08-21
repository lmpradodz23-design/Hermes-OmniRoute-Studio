export const OMNIROUTE_ENDPOINT = {
  baseUrl: 'http://127.0.0.1:20128/v1',
  id: 'omniroute',
  model: 'auto/coding',
  name: 'OmniRoute'
} as const

export const DZ23_MOA_PRESET = 'dz23-moa'

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {}
}

export const OMNIROUTE_DASHBOARD_URL = 'http://127.0.0.1:20128/dashboard'

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string') : []
}

/**
 * Add the OmniRoute Studio capabilities without creating a second fallback
 * engine in Hermes. OmniRoute owns model retries and fallback selection; this
 * preset adds the virtual MoA model, bounded nested delegation, cross-chat
 * local memory, and explicit global toolset exclusions.
 */
export function buildOmniRouteStudioConfig(
  current: Record<string, unknown>,
  omniRouteMcp?: Record<string, unknown>
): Record<string, unknown> {
  const moa = record(current.moa)
  const presets = record(moa.presets)
  const delegation = record(current.delegation)
  const goals = record(current.goals)
  const approvals = record(current.approvals)
  const memory = record(current.memory)
  const mcpServers = record(current.mcp_servers)
  const agent = record(current.agent)
  const security = record(current.security)

  const disabledToolsets = Array.from(
    new Set([...strings(agent.disabled_toolsets), 'spotify', 'homeassistant', 'yuanbao', 'feishu_doc', 'feishu_drive'])
  )

  const nextMcpServers: Record<string, unknown> = { ...mcpServers }

  if (omniRouteMcp) {
    nextMcpServers.omniroute = {
      ...record(mcpServers.omniroute),
      ...omniRouteMcp
    }
  }

  return {
    ...current,
    agent: {
      ...agent,
      disabled_toolsets: disabledToolsets,
      max_verify_nudges: 3,
      verify_guidance: true
    },
    delegation: {
      ...delegation,
      max_concurrent_children: 5,
      max_spawn_depth: 2,
      orchestrator_enabled: true,
      child_timeout_seconds: 1800
    },
    goals: {
      ...goals,
      // A generous backstop for long autonomous product work. Goal mode still
      // stops early when its judge and deterministic gates agree it is done.
      max_turns: 50
    },
    approvals: {
      ...approvals,
      // Smart mode removes routine interruptions while preserving the native
      // hardline floor and the Studio plugin's deterministic policy gates.
      mode: 'smart',
      cron_mode: 'deny',
      single_query_mode: 'deny',
      smart_policy:
        'Auto-approve read-only inspection, tests, builds, dependency installation, and reversible writes inside the active workspace or an explicitly connected SSH workspace. Escalate secrets, credential changes, production deployment, external publication, writes outside the active workspace, and irreversible operations.'
    },
    memory: {
      ...memory,
      memory_enabled: true,
      user_profile_enabled: true
    },
    mcp_servers: nextMcpServers,
    moa: {
      ...moa,
      default_preset: typeof moa.default_preset === 'string' ? moa.default_preset : DZ23_MOA_PRESET,
      privacy_filter: typeof moa.privacy_filter === 'string' ? moa.privacy_filter : 'display',
      presets: {
        ...presets,
        [DZ23_MOA_PRESET]: {
          reference_models: [
            { provider: OMNIROUTE_ENDPOINT.id, model: 'auto/coding:free' },
            { provider: OMNIROUTE_ENDPOINT.id, model: 'auto/best-free' },
            { provider: OMNIROUTE_ENDPOINT.id, model: 'oc/deepseek-v4-flash-free' }
          ],
          aggregator: { provider: OMNIROUTE_ENDPOINT.id, model: 'auto/best-coding' },
          reference_fanout: 'user_turn',
          degraded_reference_policy: 'loud'
        }
      }
    },
    security: {
      ...security,
      redact_secrets: true
    }
  }
}
