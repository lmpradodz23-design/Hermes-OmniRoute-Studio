# AUTONOMOUS HERMES — GLOBAL CHECKPOINT

MISSION = Hermes OmniRoute Studio -> autonomous general agent + autonomous software factory on ONE shared Autonomy Kernel (reuse-and-extend, never duplicate; no invented PASS).

CURRENT_WAVE = WAVE_1 (Autonomy Kernel) in progress — 4 pure kernel primitives landed + tested.

COMPLETED =
  - WAVE ZERO: evidence-based source audit of all 27 capabilities (§4), 8 independent read-only auditors, every claim file-cited. See AUTONOMOUS_HERMES_MASTER_REPORT.md.
  - Release-hygiene lineage on release/hygiene-cleanup (649bf5c) unchanged; wave work isolated on branch feature/autonomy-kernel.
  - WAVE 1 increment #1: agent/budget_state.py (Resource Governor / §39 BudgetState) implemented + unit-tested on Linux.

IN_PROGRESS =
  - WAVE 1: unify Goal loop + Kanban DAG under a thin Mission reference (no new engine); thread one correlation id (run_id/mission_id) through the 4 evidence sinks.

IMPLEMENTED (this session, Linux, source+unit only; branch feature/autonomy-kernel; all pure + additive, NO existing file modified) =
  - agent/budget_state.py — Resource Governor (§39) worst-state-wins roll-up; adapters reuse IterationBudget + SpendCeilingConfig/SpendStatus.
  - agent/mission_dag.py — Mission DAG (§7): topo order, ready/blocked frontier, critical path (longest weighted), ancestors/descendants, cycle+unknown-parent guards. Feedable by kanban parent edges OR goal sub-nodes.
  - agent/progress_signal.py — unified Watchdog stuck signal (§8): PROGRESSING/HEARTBEAT_ONLY/STRATEGY_CHANGE_REQUIRED/ESCALATE_TO_DIAGNOSTIC_AGENT/STALLED_NO_HEARTBEAT, thresholds mirror goals.classify_progress.
  - agent/mission.py — thin Mission entity (§6): MissionState DRAFT..CANCELLED, Mission references goal_key + kanban_board_id, Checkpoint reference tuple (§9), derive_state() composes DAG+budget+progress. Persist via to_dict/from_dict on the existing state_meta path.
  - agent/product_spec.py — structured ProductSpec (§11/§16, WAVE 3): validated dataclass (name/audience/roles/features/journeys/design/backend/db/auth/integrations/platforms/acceptance_criteria/assumptions/risks), to_dict/from_mapping, and to_mission_dag() that lowers a spec into a schedulable build graph (features -> QA -> release). This is the machine-readable spec the factory was missing.
  - tests/canary/framework.py — reusable break->RED->restore->GREEN canary driver (§25/§116), fail-closed.
  - agent/route_history.py — learned routing (§6/§7): per-(task_type,model) ledger + eligibility-gated scoring. LOCAL_ONLY is an ABSOLUTE eligibility gate (remote provider ELIGIBLE=false regardless of history); history does not solely dominate (neutral prior for unbenchmarked models).
  - agent/mission_store.py — durable Mission persistence (§4): SQLite store for mission/nodes/deps/status/attempts/checkpoint/events. No secrets persisted.
  - agent/mission_runtime.py — orchestration (§3/§5): MissionRuntime scheduler over the DAG frontier + pluggable NodeExecutor (delegates to Goals/kanban/subagents in real runtime), bounded RecoveryPolicy (NO infinite retry), MissionWatchdog (HEALTHY/SLOW/STUCK/FAILED/RECOVERABLE/BLOCKED + action), create/tick/run/resume with checkpoint-after-every-step.
  - tests/canary/test_real_guards.py — REAL guards registered through the canary framework: LOCAL_ONLY egress (_ALWAYS_REMOTE_TOOL_MARKERS) + DZ23 destructive guardrail (_DESTRUCTIVE_PATTERNS), break in-memory only (never the working tree).
  - Still NOT wired into the live gateway/goals/kanban (that's a Windows-runtime-validatable edit). The orchestration + persistence LOGIC is proven with real SQLite restart/resume tests here; no runtime PASS claimed for the shipped Windows app.

VALIDATED =
  - Full kernel/factory/canary suite = 68 passed (Linux venv): budget_state, mission_dag, progress_signal, mission, product_spec, kernel_pipeline, route_history, mission_runtime (persistence + restart/resume + bounded recovery + watchdog), canary framework + real-guard canaries.
  - NO runtime validation of the Windows app. NO PASS claimed for any Windows runtime gate.

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

LAST_TEST = full kernel/factory/canary suite -> 68 passed (Linux).
LAST_COMMIT = feature/autonomy-kernel: orchestration (MissionStore/Runtime/Watchdog) + learned routing + real-guard canaries.

INTEGRATION_STATUS (§15) =
  FEATURE_HEAD = feature/autonomy-kernel tip (see delivered bundle name hos-waves-<sha>.bundle)
  DEVELOP_HEAD = <pending — user runs INTEGRAR-HERMES-WAVES.bat on Windows>
  REMOTE_HEAD  = oss/develop still at 6c46770 until the one-click integrator pushes (cloud proxy blocks push here)
  INTEGRATED   = NO (bundle is transport, not merged/pushed) -> becomes YES after INTEGRAR-HERMES-WAVES.bat reports PUSH=PASS
  RUNTIME_VALIDATED = NO (Windows app gates = WAITING_FOR_HUMAN)
NEXT_ACTION = Continue WAVE 1 -> WAVE 2 with additive, Linux-testable increments (reuse-and-extend):
  - wire the primitives into runtime seams (gateway session-status read for BudgetState; a Mission reference row alongside GoalState) — small edits, Windows-validatable.
  - WAVE 2: browser_network tool (alongside browser_console); compose a visual-QA loop from preview-act + screenshot + browser_vision.
  External/human (do not block cloud work): user pushes bundles + runs P0/runtime gates on Windows per PUBLIC_PREVIEW_RUNBOOK.md.

REMAINING_INTERNAL_EXECUTABLE_WORK (Linux-testable, additive; the loop continues on these) =
  - Wave 4/6: route-history ledger + learned selection policy (§30/§31) — pure, reuses moa_trace concept.
  - Wave 5: security_research/engine.py composing the existing primitives (§27) — pure orchestration, unit-testable with fakes; RAPTOR binary itself = BLOCKED_BY_PLATFORM.
  - Wave 6: register the real guards (LOCAL_ONLY / dz23-guardrail) through tests/canary/framework.py.
  - Wave 3: ProductSpec schema block into product-studio contracts.yaml (doc reuse).
  - Runtime wiring of all kernel primitives (small edits to gateway/goals/kanban) — authored here, but their PASS is WINDOWS-runtime and therefore WAITING_FOR_HUMAN to validate.

BLOCKED (not internal-executable here) =
  - Wave 2 browser_network / visual-QA loop runtime (external agent-browser + Windows app) = WAITING_FOR_HUMAN.
  - Wave 4 code graph / impact analysis = large LSP engine (buildable but not one-turn-testable; queued).
  - Wave 5 installers / clean-install / rollback / mobile Android build = WAITING_FOR_HUMAN (Windows/SDK); iOS = BLOCKED_BY_PLATFORM.
