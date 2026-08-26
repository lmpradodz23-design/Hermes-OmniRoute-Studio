# AUTONOMOUS HERMES — GLOBAL CHECKPOINT

MISSION_ID = hermes-omniroute-autonomy-kernel
MISSION = One shared Autonomy Kernel powering an autonomous general agent + an autonomous software factory (reuse-and-extend; no invented PASS; source vs runtime always separated).
CURRENT_WAVE = Waves 1-6 source layer landed (kernel + factory logic); runtime wiring + E2E = WAITING_FOR_HUMAN (Windows).

## §4 STATE
FEATURE_HEAD = feature/autonomy-kernel tip (delivered as hos-waves-<sha>.bundle, base 6c46770)
DEVELOP_HEAD = <pending: user runs INTEGRAR-HERMES-WAVES.bat>
REMOTE_HEAD  = oss/develop = 6c46770 (cloud proxy blocks push; integrate via the .bat)
INTEGRATED = NO (bundle = transport; becomes YES when the .bat reports PUSH=PASS)
RUNTIME_VALIDATED = NO (Windows app not runnable here)
SOURCE_IMPLEMENTED = YES (see modules below), all pure + additive, NO existing product file modified
LAST_TEST = 126 passed (Linux venv), all new kernel/factory/canary suites
LAST_TEST_RESULT = PASS
LAST_COMMIT = feat(waves 3/5/6): adaptive pipeline + safe repair + skill lifecycle + benchmark arena
LAST_EVIDENCE = tests/agent + tests/canary (per-module), secret scan clean per commit

## MODULES IMPLEMENTED THIS SESSION (branch feature/autonomy-kernel; agent/*.py unless noted)
Wave1: budget_state, mission_dag, progress_signal, mission, mission_store, mission_runtime,
       mission_evidence, autonomy_levels, failure_taxonomy, idempotency, route_history,
       capability_acquisition (+ kernel_pipeline coherence test)
Wave2: eyes_hands_contracts
Wave3: product_spec, mission_class
Wave4: code_graph, impact_selection
Wave5: security_gate, safe_repair
Wave6: tests/canary/framework + tests/canary/test_real_guards, skill_lifecycle, benchmark_arena
Plus one-click INTEGRAR-HERMES-WAVES.bat (integration to develop).

## §121 FINAL MATRIX (status = evidence-backed; IMPLEMENTED/TESTED = source+unit on Linux)
AUTONOMY_KERNEL        = IMPLEMENTED+TESTED ; INTEGRATED=NO ; RUNTIME_VALIDATED=WAITING_FOR_HUMAN
MISSION_DAG            = IMPLEMENTED+TESTED (topo/frontier/critical-path/impact)
MISSION_STORE         = IMPLEMENTED+TESTED (SQLite persistence + restart/resume)
SCHEDULER             = IMPLEMENTED+TESTED (mission_runtime, DAG frontier)
WATCHDOG              = IMPLEMENTED+TESTED (progress_signal + mission_runtime.watchdog)
CHECKPOINT_RESUME     = IMPLEMENTED+TESTED (restart->reload->resume)
EVIDENCE_ENGINE       = IMPLEMENTED+TESTED (per-node required evidence; ledger-correlation = PARTIAL/next)
LEARNED_ROUTING       = IMPLEMENTED+TESTED (route_history + benchmark_arena; LOCAL_ONLY absolute)
COMPUTER_USE          = EXISTS(audit)+CONTRACTS IMPLEMENTED+TESTED ; REAL_RUNTIME=WAITING_FOR_HUMAN
BROWSER_AGENT         = EXISTS(audit)+CONTRACTS IMPLEMENTED+TESTED ; browser_network source-pending ; REAL_RUNTIME=WAITING_FOR_HUMAN
VISUAL_QA             = CONTRACTS IMPLEMENTED+TESTED ; loop-compose + REAL_RUNTIME=WAITING_FOR_HUMAN
PROJECT_BUILDER       = ProductSpec+DAG IMPLEMENTED+TESTED ; full intake loop = PARTIAL
DESIGN_ENGINE         = skills EXIST(audit) ; formal DesignSpec contract = READY (next)
CREATIVE_ENGINE       = EXISTS(audit: image_gen + LOCAL_ONLY block) ; provider-abstraction ext = PARTIAL
REPO_INTELLIGENCE     = shallow detect EXISTS(audit) ; project_model ext = READY (next)
KNOWLEDGE_GRAPH       = IMPLEMENTED+TESTED (code_graph) ; populate-from-LSP = WAITING/next
IMPACT_ANALYSIS       = IMPLEMENTED+TESTED (blast_radius + impact_selection fail-open)
WORKTREE_ISOLATION    = EXISTS+TESTED(audit) ; merge orchestration = PARTIAL
TEST_INTELLIGENCE     = IMPLEMENTED+TESTED (impact_selection) ; flaky-quarantine = next
DEBUGGING             = methodology+classifier EXIST(audit) ; debug_session engine = READY (next)
SECURITY_GATE         = IMPLEMENTED+TESTED (mission node + remediation/rescan/reopen) ; RAPTOR binary=BLOCKED_PLATFORM
MOBILE_LAB            = Android scaffold EXISTS(audit) ; build=WAITING_HUMAN ; iOS=BLOCKED_PLATFORM
RELEASE_FACTORY       = CI EXISTS(audit) ; orchestrator+SBOM=READY ; runtime=WAITING_HUMAN
BENCHMARK_ARENA       = IMPLEMENTED+TESTED
SKILL_FACTORY         = EXISTS(audit)+lifecycle/proposal states IMPLEMENTED+TESTED
DOCTOR                = EXISTS broad(audit) ; BLOCKED status + SafeRepair generalization IMPLEMENTED+TESTED ; wire into doctor.py=READY
SAFE_REPAIR           = IMPLEMENTED+TESTED
SELF_HEALING          = building blocks EXIST(audit)+safe_repair ; propose-only loop = READY (next)
CAPABILITY_ACQUISITION= IMPLEMENTED+TESTED (§141-165, incl. mandatory §165 gate)
GENERAL_AGENT_E2E     = WAITING_FOR_HUMAN (runtime)
SOFTWARE_FACTORY_E2E  = coherence pipeline TESTED (source) ; full E2E=WAITING_FOR_HUMAN
INSTALLED_APP_E2E     = WAITING_FOR_HUMAN (Windows)

## QUEUES
READY_QUEUE (Linux-testable, additive — loop continues here next) =
  1. observability/mission-trace correlation-id + JSON structured logs w/ redaction (§58/§59)
  2. self-healing propose-only loop composing doctor findings + worktree + safe_repair (§56/§57)
  3. DesignSpec contract + creative provider-abstraction contract w/ image LOCAL_ONLY (§35/§36/§37)
  4. project_model repo-intelligence extension (§40) ; debug_session engine (§45)
  5. release pipeline model + SBOM stage composition (§49) ; doctor BLOCKED wiring (§54)
WINDOWS_VALIDATION_QUEUE = P0 updater runtime, Electron/NSIS build, Computer Use real, Visual QA real, installed E2E, cold start/backend READY/restart, LOCAL_ONLY runtime
HUMAN_ACTION_QUEUE = run INTEGRAR-HERMES-WAVES.bat (push develop); OpenWA QR; code-signing cert
PLATFORM_QUEUE = iOS (needs macOS/Xcode) ; RAPTOR runtime binary
EXTERNAL_QUEUE = none currently

EXECUTABLE_INTERNAL_WORK = >0 (READY_QUEUE above)
OPEN_INTERNAL_FIXABLE = 0 known P0/P1 in the landed source layer (all tested)
NEXT_READY_TASK = observability correlation-id + structured JSON logging (§58/§59)

## RESUME INSTRUCTIONS (§5/§76)
1. git checkout feature/autonomy-kernel ; confirm clean tree.
2. Read this checkpoint + AUTONOMOUS_HERMES_MASTER_REPORT.md.
3. Continue from NEXT_READY_TASK; each increment: write module+test -> pytest (venv /tmp/hos-venv)
   -> secret scan -> commit -> update this checkpoint -> next READY.
4. Do NOT repeat WAVE ZERO. Do NOT modify existing product files (additive only) unless wiring,
   which is Windows-runtime-validatable (mark WAITING_FOR_HUMAN).
5. Integration to develop is via the delivered .bat (cloud proxy blocks push).
STABLE_RELEASE = NOT_AUTHORIZED. Upstream push = NEVER. Force push = NEVER.
