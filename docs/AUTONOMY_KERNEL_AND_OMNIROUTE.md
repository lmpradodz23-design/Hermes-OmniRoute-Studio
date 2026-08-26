# Autonomy Kernel & OmniRoute Provider System

This document describes the shared **Autonomy Kernel** (one core powering both an
autonomous general agent and an autonomous software factory) and the **OmniRoute
Provider Catalog + Free-First** configuration system layered on top of it.

Everything here is built as a **pure, additive** layer (standard library only, no new
parallel runtime, no duplicated provider transport). It is exercised by unit, contract,
and source-integration tests. Anything that requires the packaged Windows app —
Electron build, NSIS installer, the running GUI, installed-app E2E — is **not** validated
in-tree and is tracked in [`../audit/WINDOWS_NATIVE_EXECUTOR_HANDOFF.md`](../audit/WINDOWS_NATIVE_EXECUTOR_HANDOFF.md).

## Design invariants

- **Reuse and extend — never fork a parallel system.** The provider layer selects which
  existing `ProviderProfile` (`providers/`) the existing transport
  (`agent/transports/chat_completions.py`) runs; it does not replace either.
- **Source ≠ runtime.** IMPLEMENTATION / UNIT / CONTRACT / source-INTEGRATION are kept
  strictly separate from REAL_RUNTIME / E2E. No runtime PASS is ever claimed without the
  real host.
- **No invented facts.** Provider quotas and prices are `UNKNOWN` until verified live —
  never fabricated.
- **Secrets never leak.** API keys live only in OS-backed secret storage
  (`agent/secret_sources/`). No key touches the repo, renderer, `localStorage`, logs,
  task reports, or screenshots. The renderer receives only `{configured, status, metadata}`.
- **LOCAL_ONLY is absolute.** In local-only mode, cloud providers are ineligible even if
  free and top-scoring; cloud egress is zero.
- **ASK_BEFORE_PAID.** A paid provider is never called without explicit authorization.

## Autonomy Kernel — modules

| Concern | Modules |
|---|---|
| Mission model & scheduling | `agent/mission.py`, `mission_dag.py`, `mission_store.py`, `mission_runtime.py`, `progress_signal.py` |
| Policy & budget | `mission_policy.py`, `autonomy_levels.py`, `budget_state.py`, `failure_taxonomy.py`, `idempotency.py` |
| Evidence & observability | `mission_evidence.py`, `mission_trace.py` |
| Learning & routing | `route_history.py`, `benchmark_arena.py` |
| Capability acquisition | `capability_acquisition.py` |
| Software factory | `product_spec.py`, `mission_class.py`, `code_graph.py`, `impact_selection.py`, `project_model.py`, `debug_session.py`, `security_gate.py`, `safe_repair.py`, `release_pipeline.py`, `mcp_control_plane.py`, `self_heal.py`, `doctor_model.py`, `flaky_ledger.py`, `skill_lifecycle.py`, `creative_contract.py`, `eyes_hands_contracts.py` |

Canary guards live in `tests/canary/` (fail-closed; real LOCAL_ONLY and destructive-pattern checks).

## OmniRoute Provider System — modules

| Layer | Module | Role |
|---|---|---|
| Metadata | `agent/provider_catalog.py` | Curated provider metadata; no invented quotas. |
| Selection | `agent/provider_routing.py` | Free-first / local-first / quality / balanced routing + cost guard. |
| Adapter | `agent/provider_adapter.py` | Connection-state vocabulary, key-format validation, secret sanitization. |
| Link | `agent/provider_catalog_link.py` | Reconcile catalog ↔ live `providers/` registry; flag drift (anti-parallel guard). |
| UX view | `agent/provider_settings_view.py` | Renderer-safe Settings → AI & Models view-model + guided steps. |
| Bridge | `agent/provider_omniroute_bridge.py` | Routing decision → real `ProviderProfile`; fail-closed; LOCAL_ONLY/ASK_BEFORE_PAID. |
| Secrets | `agent/provider_secret_bridge.py` | Provider keys via `secret_sources`; non-secret handles only. |
| Probes | `agent/provider_probe.py` | Injected HTTP; health check, model discovery, local auto-detect. |
| Service | `agent/provider_settings_service.py` | Settings service + guided connect state machine + IPC handlers. |
| Kernel hooks | `agent/provider_runtime_hooks.py` | Record outcomes → `route_history`; arena quality feedback; trace/evidence; `route_for_mission`. |
| Real injections | `agent/provider_runtime.py` | `UrllibHttpClient` (stdlib), `SecretSourcesResolver`, `default_service()`. |

See the honest, source-generated provider table in
[`provider-catalog.md`](./provider-catalog.md).

## How selection flows at runtime

```
ProviderCatalog + live state (configured? healthy? quota? benchmark score?)
        │  build_candidates()
        ▼
provider_routing.select_provider()      # free-first, LOCAL_ONLY absolute, cost guard
        │  RoutingDecision
        ▼
provider_omniroute_bridge.route_and_resolve()
        │  reconcile() → real ProviderProfile (providers/get_provider_profile)
        │  re-validate capability + privacy (fail-closed)
        ▼
existing transport  agent/transports/chat_completions.py::_build_kwargs_from_profile()
        ▼
real provider
```

`provider_runtime_hooks.route_for_mission()` is the single integrated entry point a
mission-node dispatch calls: it routes, resolves, and emits a correlated trace event in
one step, then `record_route_outcome()` feeds `route_history`, which
`benchmark_arena` turns into the quality scores that flow back into the next
`build_candidates()` — closing the learning loop.

## Running the tests

```bash
python -m pytest tests/agent/test_provider_layer.py \
                 tests/agent/test_provider_link_view.py \
                 tests/agent/test_provider_omniroute_bridge.py \
                 tests/agent/test_provider_secret_bridge.py \
                 tests/agent/test_provider_probe.py \
                 tests/agent/test_provider_settings_service.py \
                 tests/agent/test_provider_runtime_hooks.py \
                 tests/agent/test_provider_runtime_integration.py \
                 tests/canary/test_real_guards.py -q
```

The integration test starts a real local HTTP server and drives the full probe chain
(health check + model discovery) through the real `UrllibHttpClient` — no transport fakes.

## Activating on the host (remaining runtime work)

The layer is complete and tested as source. To make it live in the desktop app, the
host wires the real injections and UI (all mapped in the executor handoff):

1. Inject `provider_runtime.UrllibHttpClient` (or an app HTTP client) and a
   `SecretSourcesResolver` bound to the app's `HERMES_HOME` and config.
2. Add an OS-keychain `SecretSource` (Windows Credential Manager / DPAPI, or keytar) and
   a `secret_writer` that stores the key and returns a `ProviderKeyRef`.
3. Render `apps/desktop/src/app/settings/ai-models-settings.tsx` from
   `ProviderSettingsService.build_view()` / `ipc_get_view`, and drive the connect flow
   via `ProviderSettingsService.connect`.
4. Call `route_for_mission()` from the real mission dispatch.

None of these require changing the modules above — only wiring and, then, real-host
validation (build / install / E2E).
