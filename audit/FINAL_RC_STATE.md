# Hermes OmniRoute Studio — Final RC State (pre-publish)

Baseline: `275dad4` · Branch target: `oss/develop` · **NOT yet re-published** (run the `.bat`).

Two adversarial review rounds (Security + QA/Concurrency), every real finding
verified against source, fixed at root cause, retested with canaries. GitHub is
source of truth; SOURCE_PASS ≠ RUNTIME_PASS (runtime items deferred to the
Windows executor).

## Meta gates

| Gate | State |
|---|---|
| `P0_SOURCE_OPEN` | 0 |
| `P1_SOURCE_OPEN` | 0 |
| `P2_SOURCE_OPEN` | 0 |
| `LOCAL_ONLY_EMBEDDINGS` | SOURCE_PASS |
| `LOCAL_ONLY_MEMORY_EGRESS` | SOURCE_PASS |
| `LOCAL_ONLY_MEM0` | SOURCE_PASS |
| `LOCAL_ONLY_SUPERMEMORY` | SOURCE_PASS |
| `LOCAL_ONLY_HINDSIGHT` | SOURCE_PASS |
| `LOCAL_ONLY_CONFIG_FAIL_CLOSED` | SOURCE_PASS |
| `UPDATER_ATOMIC_LOCK` | SOURCE_PASS |
| `UPDATER_STALE_LOCK` | SOURCE_PASS |
| `UPDATER_OWNER_TRANSFER` | SOURCE_PASS |
| `UPDATER_PID_REUSE_PROTECTION` | BOUNDED (20-min age ceiling; RUNTIME) |
| `UPDATER_CRASH_RECOVERY` | SOURCE_PASS |
| `UPDATER_RELEASE_FAILURE_HANDLING` | SOURCE_PASS |

## Round 2/3 findings — verified and fixed

Updater lock (QA/Concurrency):
- **M1 (P1, CONFIRMED): claimUpdateMarker two-winner TOCTOU** — the self-heal
  unlink-by-path (and a later rename-reap attempt) let a 3rd claimant slip into
  an absent window and double-acquire. Proven with a REAL multi-process test.
  FIXED by serializing the whole read-decide-write behind an atomic
  critical-section spinlock (`enterClaimCs`, O_EXCL); inside the CS the marker is
  inspected non-destructively (`peekMarker`) and written via temp+rename. CS is
  token-scoped on release and self-heals a crashed holder after 30s.
  **Re-audit: CLOSED.**
- **M2 (P3): future/negative startedAt never expired** — FIXED (>5min-future →
  stale; unlink now mtime-guarded). **CLOSED.**
- N2 empty-CS wedge on write failure — FIXED (unlink + fail-closed).

LOCAL_ONLY (Security):
- **A1 (P2, CONFIRMED): config_local_only_enabled fails OPEN on corrupt/dropped
  state** — FIXED: cross-checks the raw persisted file; corrupt/unreadable →
  deny (fail closed), fresh install → off, cache keyed by st_mtime_ns.
- **P1 (CONFIRMED regression): empty mem0 embedder/llm `{}` → OpenAI cloud
  default egress** — FIXED: the empty-block skip is scoped to graph_store/reranker
  only; empty embedder/llm/vector_store deny. **CLOSED at gate + _create_backend.**
- **A2/P2 (CONFIRMED): account-usage egress under local-only** —
  `fetch_account_usage`, `redeem_codex_reset_credit` (/usage reset GET+POST), and
  `get_nous_portal_account_info` (/usage, /topup portal GET) all now suppressed
  under local-only. **CLOSED.**
- Supermemory: explicit gate — remote/cloud denied, loopback self-hosted allowed;
  activation-deny stops all its egress hooks. **CLOSED.**
- mem0 graph_store/reranker gated (defense-in-depth); telemetry forced off.

Accepted residuals (P3, non-blocking, not egress/double-update): managed-only
local_only source not cross-checked (needs an abnormal managed-overlay drop;
normal managed deploys are already ON); CS busy-spin only under multi-process
contention; PID reuse bounded by the 20-min ceiling.

## Verification (all green)

- Python: **201 passed** across LOCAL_ONLY (aux/loopback/memory-egress/dispatch/
  config-failclosed/supermemory/account-usage/proxy) + mem0 backend/providers/v3/
  setup + nous_account + account_usage suites.
- Electron: **1593 passed / 8 skipped / 0 failed**; `tsc -p tsconfig.electron.json` clean.
- Concurrency: REAL multi-process race (6 procs × 15 iters, holding winners) →
  exactly 1 winner every iteration; companion CANARY proves the old
  exists→unlink→write shape yields >1 (harness is load-bearing).
- Canaries: mem0 denial load-bearing; proxy guard neuter-canary; atomic-lock
  concurrency canary.
- Secret scan: clean (no secrets in the 33-file diff). No new project deps.

## Deferred to Windows executor (RUNTIME, not source)

Electron P1 token-in-URL, P1 fs-read scope; all RUNTIME_PASS validation on the
real product (boot-loop reproduction, live local-only egress canaries).

## Publish

Source is synced to the PC working tree. Publish with
`PUBLICAR-HERMES-OMNIROUTE.bat` (portable gh + gitleaks, unshallow, no force,
`git push -u oss HEAD:develop`). SOURCE_FINAL_SHA is the commit that push creates.
