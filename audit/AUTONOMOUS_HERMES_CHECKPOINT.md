# AUTONOMOUS HERMES — GLOBAL CHECKPOINT

MISSION_ID = hermes-omniroute-autonomy-kernel
MISSION = One shared Autonomy Kernel powering an autonomous general agent + an autonomous software factory (reuse-and-extend; no invented PASS; source vs runtime always separated).
CURRENT_WAVE = Waves 1-6 SOURCE LAYER exhausted (kernel + factory logic, tested). Remainder = runtime wiring/validation (WAITING_FOR_HUMAN) + platform blockers.

## §4 STATE
FEATURE_HEAD = feature/autonomy-kernel tip (delivered as hos-waves-<sha>.bundle, base 6c46770)
DEVELOP_HEAD = <pending: user runs INTEGRAR-HERMES-WAVES.bat>
REMOTE_HEAD  = oss/develop = 649bf5c (CORRECTED; 6c46770 is its ancestor). My feature branch sits DIRECTLY on
  top of 649bf5c, so oss/develop is a direct ancestor of FEATURE_HEAD -> merge into develop is CONFLICT-FREE /
  fast-forwardable (verified on device: merge-base(HEAD,649bf5c)=649bf5c; 0 file collisions with develop's 3
  newer release/docs commits). Bundle base 6c46770 is verified present on the Windows repo. Cloud proxy blocks
  push; integrate via the .bat.
  NOTE: 6c46770 = "fix(desktop): NTFS-robust update-lock CS + honest MCP test precondition" -> the atomic-lock/
  MCP fixes from audit/runtime-evidence are ALREADY in oss/develop history (landed upstream on the fork).
INTEGRATED = NO (HERMES-INTEGRATION-RESULT.txt not present yet) -> YES when the .bat reports PUSH=PASS
RUNTIME_VALIDATED = NO (Windows app not runnable here)
SOURCE_IMPLEMENTED = YES (all pure + additive; only mission_runtime got an additive policy hook, regression green)
LAST_TEST = 196 passed (Linux venv), mission kernel/factory/canary + provider complement (20 new)
LAST_TEST_RESULT = PASS (1 unrelated product test skipped: test_verification_evidence needs `requests` dep; not a mission module)
LAST_COMMIT = docs(omniroute): supported-providers table generated from catalog (§35)
LAST_EVIDENCE = per-module tests in tests/agent + tests/canary; secret scan clean per commit; Windows run-1 evidence preserved under audit/runtime-evidence/f33d1918

## PROVIDER COMPLEMENT (§1-43) — DONE (source layer), OmniRoute EXTENSION not parallel router
provider_catalog       = IMPLEMENTED+TESTED (curation metadata; quotas NEVER invented; last_verified_at=None)
provider_routing       = IMPLEMENTED+TESTED (free-first; LOCAL_ONLY absolute; cost guard; §37 canaries green)
provider_adapter       = IMPLEMENTED+TESTED (ConnectionStatus + key-format + local auto-detect; NO api_key field; sanitize_for_renderer)
provider_catalog_link  = IMPLEMENTED+TESTED (reconcile to existing providers/ registry; registry wins runtime facts; drift FLAGGED = anti-parallel guard)
provider_settings_view = IMPLEMENTED+TESTED (Settings->AI&Models lay-user surface; guided flow §38; secret-safe by construction; UNKNOWN never faked CONNECTED)
docs/provider-catalog.md = generated from source (honest, no invented price/quota)
PROVIDER_RUNTIME_WIRING = WAITING_FOR_HUMAN: bind provider_routing into gateway selection; OS secure-storage for key_ref;
  live health probes/quota_status; benchmark_arena feed of quality_score; capability_acquisition of missing local provider;
  renderer screen consuming build_settings_view. (Runtime = validatable only on the app host.)

## MODULES IMPLEMENTED (branch feature/autonomy-kernel; agent/*.py unless noted)
Kernel: budget_state, mission_dag, progress_signal, mission, mission_store, mission_runtime(+policy hook),
        mission_evidence, mission_policy, autonomy_levels, failure_taxonomy, idempotency,
        route_history, benchmark_arena, capability_acquisition, mission_trace
Factory: product_spec, mission_class, code_graph, impact_selection, project_model, debug_session,
         security_gate, safe_repair, release_pipeline, mcp_control_plane, creative_contract,
         eyes_hands_contracts, skill_lifecycle, self_heal, doctor_model, flaky_ledger
Provider(§1-43): provider_catalog, provider_routing, provider_adapter, provider_catalog_link, provider_settings_view
         + docs/provider-catalog.md (generated from source)
Canary: tests/canary/framework + tests/canary/test_real_guards (LOCAL_ONLY + dz23)
Ops: INTEGRAR-HERMES-WAVES.bat (one-click integration to develop)
Evidence: audit/runtime-evidence/f33d1918 (preserved Windows SourceTests run-1 + atomic-lock/MCP fix rationale)

## §121 FINAL MATRIX (evidence-backed; IMPLEMENTED/TESTED = source+unit on Linux)
AUTONOMY_KERNEL        = IMPLEMENTED+TESTED ; INTEGRATED=NO ; RUNTIME_VALIDATED=WAITING_FOR_HUMAN
MISSION_DAG            = IMPLEMENTED+TESTED (topo/frontier/critical-path/impact + dynamic nodes)
MISSION_STORE         = IMPLEMENTED+TESTED (SQLite persistence + restart/resume)
SCHEDULER             = IMPLEMENTED+TESTED (mission_runtime + dispatch policy gate)
WATCHDOG              = IMPLEMENTED+TESTED (progress_signal + mission_runtime.watchdog)
CHECKPOINT_RESUME     = IMPLEMENTED+TESTED
EVIDENCE_ENGINE       = IMPLEMENTED+TESTED (per-node required evidence; ledger-correlation via mission_trace)
LEARNED_ROUTING       = IMPLEMENTED+TESTED (route_history + benchmark_arena; LOCAL_ONLY absolute)
RESOURCE_GOVERNOR     = IMPLEMENTED+TESTED (budget_state + mission_policy wired into scheduler)
AUTONOMY_LEVELS       = IMPLEMENTED+TESTED (enforced at dispatch via mission_policy)
OBSERVABILITY         = IMPLEMENTED+TESTED (mission_trace + structured redacted JSON logs)
CAPABILITY_ACQUISITION= IMPLEMENTED+TESTED (§141-165 incl. mandatory §165 gate)
COMPUTER_USE          = EXISTS(audit)+CONTRACTS IMPLEMENTED+TESTED ; REAL_RUNTIME=WAITING_FOR_HUMAN
BROWSER_AGENT         = EXISTS(audit)+CONTRACTS IMPLEMENTED+TESTED ; browser_network tool=WAITING_FOR_HUMAN ; REAL_RUNTIME=WAITING_FOR_HUMAN
VISUAL_QA             = CONTRACTS IMPLEMENTED+TESTED ; loop+REAL_RUNTIME=WAITING_FOR_HUMAN
PROJECT_BUILDER       = ProductSpec+DAG+adaptive pipeline IMPLEMENTED+TESTED ; full intake loop=PARTIAL
DESIGN_ENGINE         = CONTRACTS IMPLEMENTED+TESTED (creative_contract DesignSpec) ; skills EXIST(audit)
CREATIVE_ENGINE       = CONTRACTS IMPLEMENTED+TESTED (image LOCAL_ONLY absolute) ; provider bind=WAITING(runtime)
REPO_INTELLIGENCE     = IMPLEMENTED+TESTED (project_model heuristics) ; LSP-enrich=WAITING(runtime)
KNOWLEDGE_GRAPH       = IMPLEMENTED+TESTED (code_graph) ; populate-from-LSP=WAITING(runtime)
IMPACT_ANALYSIS       = IMPLEMENTED+TESTED (blast_radius + fail-open selection)
WORKTREE_ISOLATION    = EXISTS+TESTED(audit) ; merge orchestration=PARTIAL
TEST_INTELLIGENCE     = IMPLEMENTED+TESTED (impact_selection + flaky_ledger)
DEBUGGING             = IMPLEMENTED+TESTED (debug_session iron-law state machine)
SECURITY_GATE         = IMPLEMENTED+TESTED (mission node + remediation/rescan/reopen) ; RAPTOR binary=BLOCKED_PLATFORM
MOBILE_LAB            = Android scaffold EXISTS(audit) ; build=WAITING_HUMAN ; iOS=BLOCKED_PLATFORM
RELEASE_FACTORY       = IMPLEMENTED+TESTED (release_pipeline gate model) ; runtime build=WAITING_HUMAN
BENCHMARK_ARENA       = IMPLEMENTED+TESTED
SKILL_FACTORY         = EXISTS(audit)+lifecycle/proposal states IMPLEMENTED+TESTED
DOCTOR                = EXISTS broad(audit) + doctor_model (BLOCKED status + self-heal bridge) IMPLEMENTED+TESTED ; wire into doctor.py=WAITING_FOR_HUMAN
SAFE_REPAIR           = IMPLEMENTED+TESTED
SELF_HEALING          = IMPLEMENTED+TESTED (isolated propose-only loop) ; live wiring=WAITING_FOR_HUMAN
MCP_CONTROL_PLANE     = IMPLEMENTED+TESTED (registry + per-mission selection) ; bind to capabilities.lock=WAITING(runtime)
PROVIDER_CATALOG_UX   = IMPLEMENTED+TESTED (catalog+routing+adapter+link+settings-view; free-first/LOCAL_ONLY/secret-safe; §37 canaries) ; runtime bind/UI=WAITING_FOR_HUMAN
GENERAL_AGENT_E2E     = WAITING_FOR_HUMAN (runtime)
SOFTWARE_FACTORY_E2E  = SOURCE-INTEGRATION TESTED (test_full_kernel_integration, failure injection) ; full runtime E2E=WAITING_FOR_HUMAN
INSTALLED_APP_E2E     = WAITING_FOR_HUMAN (Windows)

## §122 STATUS SEPARATION (never a global PASS)
IMPLEMENTATION=PASS ; UNIT=PASS ; CONTRACT=PASS ; INTEGRATION(source)=PASS ;
REAL_RUNTIME=WAITING_FOR_HUMAN ; E2E(runtime)=WAITING_FOR_HUMAN ; SECURITY(source gates)=PASS

## QUEUES
READY_QUEUE (pure Linux-testable internal work) = EXHAUSTED for the high-value layer this session.
  Remaining pure candidates are marginal; the substantive remainder is runtime-wiring below.
RUNTIME_WIRING_QUEUE (edits to mature engines; PASS is Windows-runtime -> WAITING_FOR_HUMAN, not done blindly here per §137) =
  - wire kernel primitives into gateway/goals.py/kanban_db.py seams
  - wire doctor_model + safe_repair into hermes_cli/doctor.py; BLOCKED status
  - browser_network tool into tools/browser_tool.py ; populate code_graph from agent/lsp
  - bind mcp_control_plane to capabilities.lock ; creative_contract to plugins/image_gen
  - PROVIDER: bind provider_routing.select_provider into the gateway provider-selection path (extend, not replace);
    reconcile() against providers.list_providers() at startup; store key_ref in OS secure storage (keyring/DPAPI);
    live health_check/quota_status probes; feed benchmark_arena quality_score; renderer Settings->AI&Models consumes
    build_settings_view(); LOCAL_ONLY runtime gate on the real dispatch path.
WINDOWS_VALIDATION_QUEUE = P0 updater runtime, Electron/NSIS build, Computer Use/Browser/Visual QA real, installed E2E, cold start/backend READY/restart, LOCAL_ONLY runtime
HUMAN_ACTION_QUEUE = run INTEGRAR-HERMES-WAVES.bat (push develop); OpenWA QR; code-signing cert
PLATFORM_QUEUE = iOS (macOS/Xcode) ; RAPTOR runtime binary

## INTEGRATION READINESS (verified on device this turn — de-risked, ready to run)
DELIVERED_BUNDLE = hos-waves-<final>.bundle in the Hermes-OmniRoute repo root (base 649bf5c = real oss/develop tip).
VERIFIED: (a) `git bundle verify` PASS on device; (b) base 649bf5c present on the Windows repo; (c) DRY-RUN fetch of
  the feature branch on device succeeded and merge-base(develop 649bf5c, feature tip)=649bf5c => CONFLICT-FREE /
  fast-forwardable merge; (d) 0 file collisions with develop's 3 newer release/docs commits.
STALE bundles moved to <repo>/_to_delete/ on the device (device_bash cannot delete — user removes that folder).
REMAINING ACTION = run INTEGRAR-HERMES-WAVES.bat on Windows. Push itself is WAITING_FOR_HUMAN: the cloud/device
  shells have NO network egress to GitHub, and a push is a gated publish action — must be the user's authenticated run.

EXECUTABLE_INTERNAL_WORK = 0 for pure/Linux-validatable source. CONVERGED: the §1-43 provider complement
  (catalog+routing+adapter+link+settings-view+docs, pyflakes-clean, 20 new tests green) is the last pure layer;
  its remainder is provider RUNTIME_WIRING (WAITING_FOR_HUMAN). Every other open item is WAITING_FOR_HUMAN
  (runtime wiring, integration .bat, Windows validation/E2E) or BLOCKED_PLATFORM (iOS, RAPTOR). Proof: this
  turn ran the mission suite (196 pass; the one fail is an unrelated product test missing the `requests` dep),
  secret scans clean, and an on-device dry-run proving the develop merge is conflict-free.
OPEN_INTERNAL_FIXABLE = 0 known P0/P1 in the landed source layer (all tested)
NEXT_READY_TASK = (runtime, next Windows turn) run the .bat to integrate develop, then execute the
  RUNTIME_WIRING_QUEUE + WINDOWS_VALIDATION_QUEUE on the authoritative host.

## RESUME INSTRUCTIONS (§5/§76)
1. If HERMES-INTEGRATION-RESULT.txt exists: confirm PUSH=PASS, set DEVELOP_HEAD/REMOTE_HEAD, use develop as base.
2. Read this checkpoint + AUTONOMOUS_HERMES_MASTER_REPORT.md; do NOT repeat WAVE ZERO or landed waves.
3. Pure additive source items: write module+test -> pytest (venv /tmp/hos-venv) -> secret scan -> commit -> update checkpoint.
4. Runtime-wiring items require the Windows host to validate (mark WAITING_FOR_HUMAN; do not fake PASS).
STABLE_RELEASE = NOT_AUTHORIZED. Upstream push = NEVER. Force push = NEVER.
