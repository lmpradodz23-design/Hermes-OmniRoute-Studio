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
  - tests/canary/framework.py — reusable break->RED->restore->GREEN canary driver (§25/§116), fail-closed (a too-weak break can never green-wash). Generalizes the update-marker canary so every guard can ship an automated break-proof.
  - NOT yet wired into runtime (gateway status RPC / goals.py / kanban_db.py / product-studio skill), and the canary driver is not yet registered against the real guards (LOCAL_ONLY / dz23-guardrail / update-lock). Wiring/registration is the next step; no runtime PASS claimed.

VALIDATED =
  - tests/agent/{test_budget_state,test_mission_dag,test_progress_signal,test_mission,test_product_spec,test_kernel_pipeline}.py + tests/canary/test_canary_framework.py = 52 passed (Linux venv). Adapters exercised against the REAL enforcer types; kernel coherence proven end-to-end (INTENT->SPEC->DAG->STATE); canary driver proven fail-closed.
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

LAST_TEST = 6 kernel/factory modules + canary framework -> 52 passed (Linux).
LAST_COMMIT = feature/autonomy-kernel: canary framework (§25/§116).
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
