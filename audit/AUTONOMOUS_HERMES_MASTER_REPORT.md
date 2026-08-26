# AUTONOMOUS HERMES — MASTER REPORT (WAVE ZERO)

Baseline: `/root/hos-frozen` @ `649bf5c` (release/hygiene-cleanup lineage over public `oss/develop = 6c46770`). Method: 8 independent read-only auditors over the REAL source; every classification below is backed by cited files in the per-cluster audits. Runtime is **not** validated here (Windows-only desktop app on a Linux host) — "works" means source + real tests, never a runtime PASS.

## Headline

Hermes OmniRoute Studio is **not** "a fork with many features." It already contains most of an Autonomy Kernel and a software factory as **real, tested, runtime-wired code**. The correct strategy is **reuse-and-extend**; a green-field rebuild of any subsystem below would be duplication. The gaps are specific and mostly *integration* gaps (compose existing parts) rather than *missing* engines.

## Capability matrix (27, per §4)

| # | Capability | Classification | Primary existing implementation (reuse target) |
|---|---|---|---|
| 1 | Mission orchestration | SOURCE_ONLY (engines exist) | `hermes_cli/goals.py` GoalManager (per-session loop) + Kanban dispatcher; `mission-control/` UI is read-only |
| 2 | Mission DAG / deps / parallel | PARTIAL (DAG+parallel real; critical-path MISSING) | `hermes_cli/kanban_db.py` parent edges + claim dispatcher; `kanban_decompose.py` |
| 3 | Watchdog | EXISTS_NEEDS_IMPROVEMENT | `gateway/shutdown_watchdog.py`, `session_stall.py`, `goals.classify_progress()`, kanban claim-TTL reclaim |
| 4 | Checkpoint / resume | SOURCE_ONLY | `GoalState` in `state.db state_meta`; kanban SQLite; `test_goal_resume_restart.py` |
| 5 | Evidence engine | EXISTS_AND_WORKS | `agent/verification_evidence.py` (PASS = exit-code + HTTP readiness, not prose) |
| 6 | Computer use | SOURCE_ONLY (ext. cua-driver) | `tools/computer_use/*` gated adapter (modes/approval/blocked-combos/manifest) |
| 7 | Browser automation | SOURCE_ONLY (ext. agent-browser) | `tools/browser_tool.py` + CDP/camofox; profile-scoped storage |
| 8 | Visual QA | PARTIAL / not composed | `apps/desktop/src/lib/preview-act/*`, `visual-snapshot.ts`, TUI `scripts/visual` |
| 9 | Creative / image gen | EXISTS_NEEDS_IMPROVEMENT | `agent/image_gen_provider.py` + 7 providers; LOCAL_ONLY blocks `image_generate` (tested) |
| 10 | Product Studio | SOURCE_ONLY (skill+installer) | `skills/software-development/product-studio/` + `bundled-product-studio.ts` |
| 11 | Project intake / ProductSpec | MISSING (structured) | intake prose only; `contracts.yaml` is the place to add a schema |
| 12 | Repo intelligence | PARTIAL (shallow) | `agent/coding_context.py detect_project_facts()`; `projects_db.py` |
| 13 | Code / knowledge graph | MISSING (code); learning-graph exists | build on `agent/lsp/*` (diagnostics-only today) |
| 14 | Impact analysis | MISSING | blocked on #13 |
| 15 | Worktree isolation | EXISTS (tested) | `kanban_db` per-task worktrees, `tools/subagent_worktree.py`, `worktree_gc.py` |
| 16 | Test intelligence | PARTIAL (lane-level) | `.github/actions/detect-changes`, `scripts/run_tests_parallel.py` |
| 17 | Debugging | IMPLEMENTED_NOT_INTEGRATED | `skills/.../systematic-debugging`, `agent/error_classifier.py` |
| 18 | RAPTOR / security gate | IMPLEMENTED_NOT_INTEGRATED | `security_research/*` primitives + 45 tests; **`engine.py` MISSING**, binary not vendored |
| 19 | Doctor / repair | EXISTS_NEEDS_IMPROVEMENT | `hermes_cli/doctor.py` (20+ sections) + `hermes_state.repair_state_db_schema` (textbook safe-repair) |
| 20 | Release pipeline | EXISTS_NEEDS_IMPROVEMENT | decomposed `.github/workflows/*`; no SBOM, no single orchestrator |
| 21 | Mobile testing | Android PARTIAL / iOS BLOCKED_BY_PLATFORM | `apps/mobile/` Capacitor wrapper (never built; not wired to gateway) |
| 22 | Model benchmarking / routing | PARTIAL (static MoA) | `agent/moa_loop.py` + `moa_trace.py` (records cost; nothing learns) |
| 23 | Skill evolution | EXISTS_NEEDS_IMPROVEMENT | `tools/skill_manager_tool.py`, `agent/background_review.py`, `skill_usage.py` |
| 24 | MCP registry / control plane | PARTIAL | `capabilities_lock.py` (id/version/sha256), `mcp_security.py`, subagent `allowed_toolsets` |
| 25 | Observability / mission trace | PARTIAL | `session_recording.py`, `moa_trace.py`, kanban `task_runs`; no shared `mission_id` |
| 26 | Resource / cost governance | PARTIAL -> **increment landed** | `spend_ceiling.py`, `iteration_budget.py`, `credits_tracker.py`; unified by new `agent/budget_state.py` |
| 27 | Self-healing | PARTIAL (bounded) | `background_review.py` (memory/skills only, code self-patch MISSING); worktree isolation exists |

## Cross-cutting findings

1. **Two disjoint autonomy engines**, not one: a per-session Goal loop (durable, budgeted, stall-escalating, resumable) and a multi-task Kanban DAG (parent deps, claim-based parallel dispatch, TTL recovery). The single highest-leverage kernel move is a thin **Mission** record that *references* a `GoalState` key and a kanban board id — one checkpoint, one stuck-signal — **not** a third loop.
2. **No correlation id.** `mission_id` does not exist; `run_id` lives only inside kanban. Threading one id through `session_recording` + `moa_trace` + `verification_evidence` + kanban turns four silos into one mission timeline (§37) without a new store.
3. **The code graph is the keystone gap.** #13 code graph unlocks #14 impact analysis and a deterministic merge/integration lane on the (already solid) worktree substrate. Build it on `agent/lsp` + the per-edit delta-baseline seam.
4. **Enforcement is strong; orchestration is thin.** LOCAL_ONLY, spend ceiling, guardrail plugin, capability lock, worktree GC, safe state.db repair — all fail-closed and tested. What's missing is composing them into loops (visual-QA loop, self-heal loop, RAPTOR engine, learned router).

## Reuse-and-extend roadmap (smallest verifiable increment per wave)

- **WAVE 1 — Autonomy Kernel:** [DONE, tested] `budget_state.py` roll-up; `mission_dag.py` (topo/frontier/critical-path); `progress_signal.py` (unified stuck signal); `mission.py` (Mission entity + Checkpoint + `derive_state`). Coherence proven end-to-end in `test_kernel_pipeline.py`. [NEXT] wire into runtime seams (gateway status; a Mission row beside GoalState) — Windows-validatable.
- **WAVE 2 — Eyes & Hands:** [WAITING_FOR_HUMAN — external agent-browser + Windows app] compose `preview-act` + Electron/CDP screenshot + `browser_vision` into one visual-QA loop; add `browser_network` alongside `browser_console`.
- **WAVE 3 — Product Creation:** [DONE, tested] `product_spec.py` — structured, validated ProductSpec + `to_mission_dag()` bridge. [NEXT] mirror the schema into `contracts.yaml`; hand a DESIGN.md (design-md) to the design step.
- **WAVE 4 — Elite Coding:** [QUEUED — large] code graph on `agent/lsp` -> impact analysis -> deterministic integration/merge lane; fine-grained diff->test selection over `run_tests_parallel.py`.
- **WAVE 5 — Factory:** [PARTIAL-INTERNAL / rest WAITING_FOR_HUMAN] `security_research/engine.py` composing the existing primitives (unit-testable) + a `hermes doctor` "Security Research" section; SBOM job + tag-triggered release orchestrator; Android build/emulator CI (iOS BLOCKED_BY_PLATFORM; RAPTOR binary BLOCKED_BY_PLATFORM).
- **WAVE 6 — Self Evolution:** [DONE, tested] fail-closed canary framework (`tests/canary/framework.py`). [NEXT-INTERNAL] learned router over a promoted `moa_trace` ledger; DRAFT/QUARANTINED skill states + ImprovementProposal; register real guards through the canary framework; `SafeRepair` helper + `BLOCKED` doctor state; doctor FAIL -> worktree-isolated, propose-only self-heal.

## Changes made this session

- New (branch `feature/autonomy-kernel`, additive, non-bundled): `agent/budget_state.py`, `tests/agent/test_budget_state.py`. Reuses `IterationBudget` + `SpendCeilingConfig`/`SpendStatus`. No existing file modified; release candidate `649bf5c` untouched.

## Tests / evidence

- `tests/agent/test_budget_state.py` = **17 passed** (Linux venv), adapters run against the real enforcer types.
- All other capabilities: SOURCE-verified only; each per-cluster audit lists the existing test files. No runtime PASS asserted anywhere.

## Security / performance / runtime validation

- Security posture unchanged (no product/enforcer code touched). LOCAL_ONLY, guardrail, capability lock intact.
- Performance: N/A this session (additive read-only module).
- Runtime validation: **WAITING_FOR_HUMAN** for every Windows gate (P0 updater, install, cold start, backend READY, restart, LOCAL_ONLY runtime, U1). No inference-based PASS.

## Remaining blockers

- WAITING_FOR_HUMAN: Windows runtime gates + native build; git push (cloud proxy 403 -> use delivered bundle).
- BLOCKED_BY_PLATFORM: iOS; RAPTOR runtime binary.
- STABLE_RELEASE = NOT_AUTHORIZED.
