import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  activateCustomEndpoint,
  deleteCustomEndpoint,
  getCustomEndpoints,
  getHermesConfigRecord,
  saveCustomEndpoint,
  saveHermesConfig,
  validateCustomEndpoint
} from '@/hermes'
import { useI18n } from '@/i18n'
import { triggerHaptic } from '@/lib/haptics'
import { Check, Globe, Loader2, Network, Plus, RefreshCw, Save, Trash2, Zap } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { confirm } from '@/store/confirm'
import { notify, notifyError } from '@/store/notifications'
import type { CustomEndpoint, CustomEndpointUpdate } from '@/types/hermes'

import { buildOmniRouteStudioConfig, OMNIROUTE_ENDPOINT } from './omniroute-preset'
import { EmptyState, Pill, SectionHeading, SettingsContent, SettingsSkeleton } from './primitives'

interface CustomEndpointsSettingsProps {
  onConfigSaved?: () => void
  onMainModelChanged?: (provider: string, model: string) => void
}

interface EndpointForm {
  apiKey: string
  baseUrl: string
  contextLength: string
  discoverModels: boolean
  id: string
  makeDefault: boolean
  model: string
  name: string
}

const EMPTY_FORM: EndpointForm = {
  apiKey: '',
  baseUrl: '',
  contextLength: '',
  discoverModels: true,
  id: '',
  makeDefault: true,
  model: '',
  name: ''
}

type OmniRouteStatus =
  { kind: 'checking'; models: string[] } | { kind: 'offline'; models: string[] } | { kind: 'online'; models: string[] }

interface CompressionStatus {
  available: boolean
  enabled: boolean
  mode: 'caveman' | 'off'
  strategy: string
}

function omniRoutePayload(models?: string[]): CustomEndpointUpdate {
  return {
    id: OMNIROUTE_ENDPOINT.id,
    name: OMNIROUTE_ENDPOINT.name,
    base_url: OMNIROUTE_ENDPOINT.baseUrl,
    model: OMNIROUTE_ENDPOINT.model,
    discover_models: true,
    make_default: true,
    models
  }
}

function formFromEndpoint(endpoint: CustomEndpoint): EndpointForm {
  return {
    apiKey: '',
    baseUrl: endpoint.base_url,
    contextLength: endpoint.context_length ? String(endpoint.context_length) : '',
    discoverModels: endpoint.discover_models,
    id: endpoint.id,
    makeDefault: Boolean(endpoint.is_current),
    model: endpoint.model,
    name: endpoint.name
  }
}

function toPayload(form: EndpointForm, models?: string[]): CustomEndpointUpdate {
  const contextLength = Number.parseInt(form.contextLength, 10)

  return {
    id: form.id.trim() || undefined,
    name: form.name.trim(),
    base_url: form.baseUrl.trim(),
    model: form.model.trim(),
    api_key: form.apiKey.trim() || undefined,
    context_length: Number.isFinite(contextLength) && contextLength > 0 ? contextLength : undefined,
    discover_models: form.discoverModels,
    make_default: form.makeDefault,
    models: models?.length ? models : undefined
  }
}

export function CustomEndpointsSettings({ onConfigSaved, onMainModelChanged }: CustomEndpointsSettingsProps) {
  const { t } = useI18n()
  const omni = t.settings.omniroute
  const endpointCopy = t.settings.customEndpoints
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [activating, setActivating] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [endpoints, setEndpoints] = useState<CustomEndpoint[]>([])
  const [form, setForm] = useState<EndpointForm>(EMPTY_FORM)
  const [discoveredModels, setDiscoveredModels] = useState<string[]>([])
  const [omniRouteStatus, setOmniRouteStatus] = useState<OmniRouteStatus>({ kind: 'checking', models: [] })
  const [compression, setCompression] = useState<CompressionStatus | null>(null)
  const [compressionBusy, setCompressionBusy] = useState(false)

  async function refresh() {
    const data = await getCustomEndpoints()
    setEndpoints(data.endpoints)
  }

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const [data, omniRouteProbe] = await Promise.all([
          getCustomEndpoints(),
          validateCustomEndpoint(omniRoutePayload()).catch(() => null)
        ])

        if (cancelled) {
          return
        }

        setEndpoints(data.endpoints)
        setOmniRouteStatus(
          omniRouteProbe?.ok
            ? { kind: 'online', models: omniRouteProbe.models }
            : { kind: 'offline', models: omniRouteProbe?.models ?? [] }
        )
        const current = data.endpoints.find(endpoint => endpoint.is_current) ?? data.endpoints[0]

        if (current) {
          setForm(formFromEndpoint(current))
          setDiscoveredModels(current.models)
        }
      } catch (err) {
        notifyError(err, endpointCopy.loadFailed)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()

    const compressionController = window.hermesDesktop.omniRouteCompression

    if (compressionController) {
      void compressionController
        .get()
        .then(status => {
          if (!cancelled) {
            setCompression(status)
          }
        })
        .catch(() => {
          if (!cancelled) {
            setCompression({ available: false, enabled: false, mode: 'off', strategy: 'unavailable' })
          }
        })
    } else {
      setCompression({ available: false, enabled: false, mode: 'off', strategy: 'unavailable' })
    }

    return () => {
      cancelled = true
    }
  }, [endpointCopy.loadFailed])

  async function handleCheckOmniRoute() {
    setOmniRouteStatus(current => ({ kind: 'checking', models: current.models }))

    try {
      const response = await validateCustomEndpoint(omniRoutePayload())
      setOmniRouteStatus({ kind: response.ok ? 'online' : 'offline', models: response.models })

      if (!response.ok) {
        notify({ kind: response.reachable ? 'warning' : 'error', message: response.message })
      }
    } catch (err) {
      setOmniRouteStatus({ kind: 'offline', models: [] })
      notifyError(err, omni.configureFailed)
    }
  }

  async function handleConfigureOmniRoute() {
    setSaving(true)
    setOmniRouteStatus(current => ({ kind: 'checking', models: current.models }))

    try {
      const validation = await validateCustomEndpoint(omniRoutePayload())

      if (!validation.ok) {
        setOmniRouteStatus({ kind: 'offline', models: validation.models })
        throw new Error(validation.message || omni.offline)
      }

      const response = await saveCustomEndpoint(omniRoutePayload(validation.models))
      const config = await getHermesConfigRecord()
      const mcpConfig = await window.hermesDesktop.omniRouteMcp?.getConfig()

      if (!mcpConfig) {
        throw new Error('OmniRoute MCP bridge is unavailable')
      }

      await saveHermesConfig(buildOmniRouteStudioConfig(config, mcpConfig))

      const saved = response.endpoints.find(endpoint => endpoint.id === OMNIROUTE_ENDPOINT.id)
      setEndpoints(response.endpoints)
      setOmniRouteStatus({ kind: 'online', models: validation.models })

      if (saved) {
        setForm(formFromEndpoint(saved))
        setDiscoveredModels(saved.models)
      }

      onConfigSaved?.()
      onMainModelChanged?.(OMNIROUTE_ENDPOINT.id, OMNIROUTE_ENDPOINT.model)
      triggerHaptic('success')
      notify({ kind: 'success', message: omni.configureSuccess })
    } catch (err) {
      notifyError(err, omni.configureFailed)
    } finally {
      setSaving(false)
    }
  }

  async function handleCavemanToggle(checked: boolean) {
    const controller = window.hermesDesktop.omniRouteCompression

    if (!controller) {
      return
    }

    try {
      setCompressionBusy(true)
      const status = await controller.set(checked ? 'caveman' : 'off')
      setCompression(status)
      triggerHaptic('success')
      notify({ kind: 'success', message: status.enabled ? omni.cavemanEnabled : omni.cavemanDisabled })
    } catch (err) {
      notifyError(err, omni.cavemanFailed)
    } finally {
      setCompressionBusy(false)
    }
  }

  async function handleSave() {
    try {
      setSaving(true)
      const response = await saveCustomEndpoint(toPayload(form, discoveredModels))
      setEndpoints(response.endpoints)
      const saved = response.endpoints.find(endpoint => endpoint.id === response.id)

      if (saved) {
        setForm(formFromEndpoint(saved))
        setDiscoveredModels(saved.models)
      }

      if (saved && saved.is_current) {
        onMainModelChanged?.(saved.id, saved.model)
      }

      triggerHaptic('success')
      onConfigSaved?.()
      notify({ kind: 'success', message: endpointCopy.saved })
    } catch (err) {
      notifyError(err, endpointCopy.saveFailed)
    } finally {
      setSaving(false)
    }
  }

  async function handleValidate() {
    try {
      setTesting(true)
      const response = await validateCustomEndpoint(toPayload(form))
      setDiscoveredModels(response.models)

      if (response.ok) {
        if (!form.model && response.models[0]) {
          setForm(current => ({ ...current, model: response.models[0] }))
        }

        notify({
          kind: 'success',
          message: response.models.length
            ? endpointCopy.reachableModels(response.models.length)
            : endpointCopy.reachable
        })
      } else {
        notify({
          kind: response.reachable ? 'warning' : 'error',
          message: response.message || endpointCopy.validationFailed
        })
      }
    } catch (err) {
      notifyError(err, endpointCopy.validationFailed)
    } finally {
      setTesting(false)
    }
  }

  async function handleActivate(endpoint: CustomEndpoint) {
    try {
      setActivating(endpoint.id)
      const response = await activateCustomEndpoint(endpoint.id)
      await refresh()
      onConfigSaved?.()
      onMainModelChanged?.(response.provider, response.model)
      triggerHaptic('success')
    } catch (err) {
      notifyError(err, endpointCopy.activationFailed)
    } finally {
      setActivating(null)
    }
  }

  async function handleDelete(endpoint: CustomEndpoint) {
    if (!(await confirm({ destructive: true, title: endpointCopy.deleteTitle(endpoint.name) }))) {
      return
    }

    try {
      setDeleting(endpoint.id)
      const response = await deleteCustomEndpoint(endpoint.id)
      setEndpoints(response.endpoints)

      if (form.id === endpoint.id) {
        setForm(EMPTY_FORM)
        setDiscoveredModels([])
      }

      onConfigSaved?.()
      triggerHaptic('success')
    } catch (err) {
      notifyError(err, endpointCopy.deleteFailed)
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return <SettingsSkeleton sections={[{ heading: true, rows: 3 }]} />
  }

  const allModelOptions = Array.from(new Set([...discoveredModels, form.model].filter(Boolean)))
  const canSave = form.name.trim() && form.baseUrl.trim() && form.model.trim()

  return (
    <SettingsContent>
      <div className="space-y-6">
        <section>
          <SectionHeading icon={Network} title={omni.title} />
          <div className="grid gap-3 border-b border-(--ui-stroke-tertiary) pb-5">
            <p className="text-sm text-muted-foreground">{omni.description}</p>
            <div className="flex flex-wrap items-center gap-2">
              <Pill tone={omniRouteStatus.kind === 'online' ? 'primary' : 'muted'}>
                {omniRouteStatus.kind === 'checking' ? (
                  <Loader2 className="animate-spin" />
                ) : omniRouteStatus.kind === 'online' ? (
                  <Check />
                ) : (
                  <Network />
                )}
                {omniRouteStatus.kind === 'checking'
                  ? omni.checking
                  : omniRouteStatus.kind === 'online'
                    ? omni.online
                    : omni.offline}
              </Pill>
              {endpoints.some(endpoint => endpoint.id === OMNIROUTE_ENDPOINT.id) && <Pill>{omni.configured}</Pill>}
              {omniRouteStatus.models.length > 0 && <Pill>{omni.modelsFound(omniRouteStatus.models.length)}</Pill>}
            </div>
            <div className="font-mono text-[0.72rem] text-muted-foreground">
              {omni.endpoint}: {OMNIROUTE_ENDPOINT.baseUrl}
            </div>
            <p className="text-xs text-muted-foreground">{omni.fallbackDescription}</p>
            <div className="flex items-center justify-between gap-4 rounded-md border border-border/50 p-3">
              <div className="min-w-0">
                <div className="text-sm font-medium">{omni.cavemanTitle}</div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {compression?.available === false ? omni.cavemanUnavailable : omni.cavemanDescription}
                </p>
              </div>
              {compression === null || compressionBusy ? (
                <Loader2 className="size-4 shrink-0 animate-spin text-muted-foreground" />
              ) : (
                <Switch
                  aria-label={omni.cavemanTitle}
                  checked={compression.enabled}
                  disabled={!compression.available}
                  onCheckedChange={checked => void handleCavemanToggle(checked)}
                />
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={omniRouteStatus.kind === 'checking'}
                onClick={() => void handleCheckOmniRoute()}
                variant="outline"
              >
                <RefreshCw className={cn(omniRouteStatus.kind === 'checking' && 'animate-spin')} />
                {omni.check}
              </Button>
              <Button disabled={saving} onClick={() => void handleConfigureOmniRoute()}>
                {saving ? <Loader2 className="animate-spin" /> : <Zap />}
                {saving ? omni.configuring : omni.configure}
              </Button>
            </div>
          </div>
        </section>

        <section>
          <SectionHeading icon={Globe} meta={`${endpoints.length}`} title={endpointCopy.title} />
          <div className="divide-y divide-border/40 rounded-md border border-border/50">
            {endpoints.length ? (
              endpoints.map(endpoint => (
                <div className="grid gap-3 p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center" key={endpoint.id}>
                  <button
                    className="min-w-0 text-left"
                    onClick={() => {
                      setForm(formFromEndpoint(endpoint))
                      setDiscoveredModels(endpoint.models)
                    }}
                    type="button"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="truncate text-sm font-medium">{endpoint.name}</span>
                      {endpoint.is_current && (
                        <Pill tone="primary">
                          <Check className="size-3" />
                          {endpointCopy.active}
                        </Pill>
                      )}
                      {endpoint.source === 'direct-config' && <Pill>config.yaml</Pill>}
                    </div>
                    <div className="mt-1 truncate font-mono text-[0.7rem] text-muted-foreground">
                      {endpoint.base_url}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      <span>{endpoint.model}</span>
                      {endpoint.has_api_key && <span>{endpoint.api_key_preview ?? endpointCopy.apiKeySet}</span>}
                    </div>
                  </button>
                  <div className="flex items-center gap-2 sm:justify-end">
                    <Button
                      disabled={endpoint.is_current || activating === endpoint.id}
                      onClick={() => void handleActivate(endpoint)}
                      size="sm"
                      variant="outline"
                    >
                      {activating === endpoint.id ? <Loader2 className="animate-spin" /> : <Zap />}
                      {endpointCopy.use}
                    </Button>
                    {endpoint.source !== 'direct-config' && (
                      <Button
                        aria-label={endpointCopy.deleteAria(endpoint.name)}
                        className="hover:text-destructive"
                        disabled={deleting === endpoint.id}
                        onClick={() => void handleDelete(endpoint)}
                        size="icon-sm"
                        variant="ghost"
                      >
                        {deleting === endpoint.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
                      </Button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <EmptyState description={endpointCopy.emptyDescription} title={endpointCopy.emptyTitle} />
            )}
          </div>
        </section>

        <section>
          <SectionHeading icon={Plus} title={form.id ? endpointCopy.editTitle : endpointCopy.addTitle} />
          <div className="grid gap-3 rounded-md border border-border/50 p-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                {endpointCopy.name}
                <Input
                  onChange={event => setForm(current => ({ ...current, name: event.target.value }))}
                  placeholder="Axet Proxy"
                  value={form.name}
                />
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                {endpointCopy.providerId}
                <Input
                  onChange={event => setForm(current => ({ ...current, id: event.target.value }))}
                  placeholder="axet-proxy"
                  value={form.id}
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              {endpointCopy.endpointUrl}
              <Input
                onChange={event => setForm(current => ({ ...current, baseUrl: event.target.value }))}
                placeholder="http://127.0.0.1:8081/v1"
                value={form.baseUrl}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                {endpointCopy.defaultModel}
                <Input
                  list="custom-endpoint-models"
                  onChange={event => setForm(current => ({ ...current, model: event.target.value }))}
                  placeholder="gpt-5.4"
                  value={form.model}
                />
                <datalist id="custom-endpoint-models">
                  {allModelOptions.map(model => (
                    <option key={model} value={model} />
                  ))}
                </datalist>
              </label>
              <label className="grid gap-1.5 text-xs text-muted-foreground">
                {endpointCopy.context}
                <Input
                  inputMode="numeric"
                  onChange={event => setForm(current => ({ ...current, contextLength: event.target.value }))}
                  placeholder={endpointCopy.auto}
                  value={form.contextLength}
                />
              </label>
            </div>
            <label className="grid gap-1.5 text-xs text-muted-foreground">
              {endpointCopy.apiKey}
              <Input
                onChange={event => setForm(current => ({ ...current, apiKey: event.target.value }))}
                placeholder={form.id ? endpointCopy.keepKeyPlaceholder : endpointCopy.optional}
                type="password"
                value={form.apiKey}
              />
            </label>
            <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={form.makeDefault}
                  onCheckedChange={checked => setForm(current => ({ ...current, makeDefault: checked === true }))}
                />
                {endpointCopy.useForNewChats}
              </label>
              <label className="flex items-center gap-2">
                <Checkbox
                  checked={form.discoverModels}
                  onCheckedChange={checked => setForm(current => ({ ...current, discoverModels: checked === true }))}
                />
                {endpointCopy.discoverModels}
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={testing || !form.baseUrl.trim()}
                onClick={() => void handleValidate()}
                variant="outline"
              >
                {testing ? <Loader2 className="animate-spin" /> : <Zap />}
                {endpointCopy.test}
              </Button>
              <Button disabled={saving || !canSave} onClick={() => void handleSave()}>
                {saving ? <Loader2 className="animate-spin" /> : <Save />}
                {endpointCopy.save}
              </Button>
              <Button
                className={cn(!form.id && 'hidden')}
                onClick={() => {
                  setForm(EMPTY_FORM)
                  setDiscoveredModels([])
                }}
                type="button"
                variant="ghost"
              >
                {endpointCopy.newEndpoint}
              </Button>
            </div>
          </div>
        </section>
      </div>
    </SettingsContent>
  )
}
