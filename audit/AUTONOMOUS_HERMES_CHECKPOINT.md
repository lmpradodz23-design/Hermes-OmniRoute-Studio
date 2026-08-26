# AUTONOMOUS HERMES — GLOBAL CHECKPOINT

MISSION = Hermes OmniRoute Studio -> autonomous general agent + autonomous software factory on ONE shared Autonomy Kernel (reuse-and-extend, never duplicate; no invented PASS).

CURRENT_WAVE = WAVE_ZERO complete -> WAVE_1 (Autonomy Kernel) started.

COMPLETED =
  - WAVE ZERO: evidence-based source audit of all 27 capabilities (§4), 8 independent read-only auditors, every claim file-cited. See AUTONOMOUS_HERMES_MASTER_REPORT.md.
  - Release-hygiene lineage on release/hygiene-cleanup (649bf5c) unchanged; wave work isolated on branch feature/autonomy-kernel.
  - WAVE 1 increment #1: agent/budget_state.py (Resource Governor / §39 BudgetState) implemented + unit-tested on Linux.

IN_PROGRESS =
  - WAVE 1: unify Goal loop + Kanban DAG under a thin Mission reference (no new engine); thread one correlation id (run_id/mission_id) through the 4 evidence sinks.

IMPLEMENTED (this session, Linux, source+unit only) =
  - agent/budget_state.py — worst-state-wins roll-up (WITHIN_BUDGET/NEAR_LIMIT/LIMIT_REACHED/OVERRIDE_REQUIRED); adapters reuse IterationBudget + SpendCeilingConfig/SpendStatus. NOT yet wired into the gateway status RPC (next step).

VALIDATED =
  - tests/agent/test_budget_state.py = 17 passed (Linux venv). Adapters exercised against the REAL enforcer types.
  - NO runtime validation (Windows app not runnable here). NO PASS claimed for any runtime gate.

EXTERNAL_BLOCKERS =
  - WAITING_FOR_HUMAN (Windows): P0 updater runtime gates; all install/cold-start/backend-READY/restart/LOCAL_ONLY-runtime/U1 gates; native build.
  - BLOCKED_BY_PROXY: cannot push from cloud container (git proxy 403 on the fork). Push happens from the user's Windows box via delivered bundle. develop/tag/release unchanged.
  - BLOCKED_BY_PLATFORM: iOS (needs macOS/Xcode). RAPTOR runtime binary not vendored/installed.

OPEN_INTERNAL_FIXABLE (from audit; none block the Public Preview) =
  - Autonomy Kernel: no unifying Mission entity; no critical-path over the Kanban DAG.
  - Observability: no mission_id correlation across session_recording/moa_trace/verification_evidence/kanban; logs are line-text not JSON.
  - Repo intelligence: no code/knowledge graph; no impact-analysis (both blocked on the graph).
  - RAPTOR: primitives + 45 tests exist but security_research/engine.py is MISSING and unwired.
  - Product Studio: no structured ProductSpec schema (prose only).
  - Visual QA: stations exist, no stitched critique->fix loop. browser_network tool missing.
  - Routing: MoA is static; moa_trace records cost but nothing learns from it.
  - Skill factory: ACTIVE/STALE/ARCHIVED only (no DRAFT/QUARANTINED authoring states, no ImprovementProposal); agent-created security scan off by default.
  - Doctor: vocabulary OK/WARN/FAIL/INFO (no BLOCKED); transactional safe-repair envelope exists only for state.db.

LAST_TEST = tests/agent/test_budget_state.py -> 17 passed (Linux).
LAST_COMMIT = feature/autonomy-kernel: "feat(autonomy): Resource Governor budget-state roll-up (§39)".
NEXT_ACTION = (1) user runs the delivered bundle push + P0/runtime gates on Windows; (2) next cloud increment: wire BudgetState into the gateway session-status read path and add the thin Mission reference linking GoalState <-> kanban board id (both additive, Linux-unit-testable). Continue reuse-and-extend per wave; declare PASS only with evidence.
