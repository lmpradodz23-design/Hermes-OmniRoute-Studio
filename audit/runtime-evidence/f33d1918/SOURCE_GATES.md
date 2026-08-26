# Source-level gates @ f33d1918 (executed in cloud Linux)

Baseline SHA: `f33d1918aeebedbb6b69cbb65eadd6a27851d123` · branch `develop` · 10,798 files.
Verified: the frozen SHA contains every LOCAL_ONLY + updater-lock fix from rounds 1–3
(CS spinlock, config fail-closed, supermemory gate, mem0 empty-block P1 fix, account-usage
egress gates, real-multiprocess concurrency test).

These gates are platform-agnostic and were run against a pristine `git worktree` checked out
at exactly `f33d1918`. They prove SOURCE readiness for the Windows build; they are NOT a
substitute for the Windows RUNTIME gates (see GATE_MATRIX.md).

| Gate | Result | Evidence |
|---|---|---|
| Source baseline SHA | PASS | `git rev-parse HEAD` = f33d1918; 10,798 files |
| Compile stage (`npm run build`) | PASS | vite build ✓, electron-main.mjs (945 kb) ✓, preload ✓, native-dep staging ✓, assert-dist-built ✓, exit 0 |
| tsc electron (`tsconfig.electron.json`) | PASS | exit 0, 0 errors |
| Electron unit suite (full `electron/`) | PASS | 1593 passed / 8 skipped / 0 failed (117 files) |
| Updater suites (marker/backoff/decision/policy/worktree) | PASS | included above; 102 passed in the focused run |
| Atomic-lock REAL multi-process race | PASS | update-marker.concurrency.test.ts — 6 procs × 15 iters, holding winners → exactly 1 winner/iter |
| Atomic-lock CANARY (old exists→unlink→write) | PASS | same file — buggy shape yields >1 winner, harness is load-bearing |
| LOCAL_ONLY + memory Python suite | PASS | 143 passed (aux/loopback/memory-egress/dispatch/config-failclosed/supermemory/account-usage/proxy/nous/mem0-backend) |
| Secret scan (repo tree) | PASS | no real secrets; only a redaction-pattern comment in agent/redact.py |
| Dependency audit (`npm audit --omit=dev`) | PASS | found 0 vulnerabilities |

## What these gates do NOT prove (require the Windows host)

electron-builder NSIS/MSI packaging · installer inspection/hash · install · cold start ·
backend READY · restart · fork-guard runtime · update-backoff runtime · venv-blocker runtime ·
corrupt-backoff runtime · atomic-lock **Windows** file semantics · state.db of the real profile ·
LOCAL_ONLY **live network** inspection · all E2E (Agents/Goals/Memory/Computer Use/Product
Studio/RAPTOR/OpenWA/Terminal/Files/Preview) · token-URL & FS-boundary runtime · Electron
security runtime · pt-BR · accessibility · visual QA · first-run/offline/crash-recovery/process
hygiene · installer artifact security scan.

Run `windows-validation.ps1` on the Windows host to execute those.
