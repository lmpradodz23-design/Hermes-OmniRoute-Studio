# Release Gate Matrix — Hermes OmniRoute Studio

Baseline: `f33d1918aeebedbb6b69cbb65eadd6a27851d123` · branch `develop` · 10,798 files.

## Execution boundary (honest scope)

This validation ran in a **cloud Linux** session with an **isolated Linux VM** bridge to the
Windows host (folder-mounted, no Windows toolchain, no network). Platform-agnostic **source**
gates were executed here at the exact frozen SHA. The **native Windows** half (build → install →
runtime → E2E → live-network → visual/a11y) genuinely requires the Windows host and is delivered
as an automated + checklist runbook (`windows-validation.ps1`) rather than claimed. States use
the honest vocabulary from §61.

## Matrix

| Gate | Result | Evidence |
|---|---|---|
| Source baseline | PASS | HEAD f33d1918, 10,798 files; contains all rounds-1–3 fixes |
| Compile stage (`npm run build`) | PASS | vite+electron bundle+native-dep staging, exit 0 |
| Electron typecheck | PASS | `tsc -p tsconfig.electron.json` exit 0 |
| Electron tests | PASS | 1593 passed / 8 skipped / 0 failed |
| Atomic lock (source, real multi-process) | PASS | concurrency test 6×15 → 1 winner/iter; canary catches old shape |
| Python tests (LOCAL_ONLY + memory) | PASS | 143 passed |
| Secret scan (repo) | PASS | clean (only a redaction-pattern comment) |
| Dependency audit | PASS | `npm audit --omit=dev` = 0 vulnerabilities |
| Windows build (NSIS/MSI) | WAITING_FOR_HUMAN | needs Windows host; run `npm run dist:win` via runbook |
| Installer | WAITING_FOR_HUMAN | produced + hashed by the runbook |
| Install | WAITING_FOR_HUMAN | runbook step |
| Cold start | WAITING_FOR_HUMAN | runbook checklist |
| Backend READY | WAITING_FOR_HUMAN | runbook checklist (log-verified, not "window open") |
| Restart | WAITING_FOR_HUMAN | runbook checklist |
| Fork guard (runtime) | WAITING_FOR_HUMAN | runbook checklist (source logic proven by unit suite) |
| Update backoff (runtime) | WAITING_FOR_HUMAN | runbook checklist (source logic proven by unit suite) |
| Atomic lock (Windows runtime) | WAITING_FOR_HUMAN | runbook checklist (NTFS O_EXCL/link semantics) |
| state.db | WAITING_FOR_HUMAN | runbook runs PRAGMA quick_check/integrity_check non-destructively |
| LOCAL_ONLY (runtime + live network) | NOT_PROVEN | BLOCKER — must be PASS with observed traffic before RC; runbook has the capture procedure |
| Agents / Subagents | WAITING_FOR_HUMAN | runbook E2E |
| Goals | WAITING_FOR_HUMAN | runbook E2E |
| Memory / Starmap | WAITING_FOR_HUMAN | runbook E2E |
| Computer Use | WAITING_FOR_HUMAN | runbook E2E |
| Product Studio | WAITING_FOR_HUMAN | runbook E2E |
| Security Research / RAPTOR | WAITING_FOR_HUMAN (runtime may be BLOCKED_BY_EXTERNAL_DEPENDENCY) | runbook E2E |
| OpenWA | WAITING_FOR_HUMAN (up to WAITING_FOR_HUMAN_QR_SCAN) | runbook E2E |
| Terminal | WAITING_FOR_HUMAN | runbook E2E |
| Files / Artifacts / Diff | WAITING_FOR_HUMAN | runbook E2E |
| Preview | WAITING_FOR_HUMAN | runbook E2E |
| Electron security | WAITING_FOR_HUMAN | runbook checklist (source posture reviewable) |
| Token-in-URL (P1) | WAITING_FOR_HUMAN | needs runtime repro on Windows |
| FS boundaries (P1) | WAITING_FOR_HUMAN | needs runtime repro on Windows |
| pt-BR | WAITING_FOR_HUMAN | visual, needs running app |
| Accessibility | WAITING_FOR_HUMAN | needs running app |
| Visual QA | WAITING_FOR_HUMAN | needs running app + screenshots |
| Installer artifact secret scan | WAITING_FOR_HUMAN | runbook unpacks + scans the produced installer |

## §60 final result block (honest states)

```
BASELINE_SOURCE_SHA=f33d1918aeebedbb6b69cbb65eadd6a27851d123
FINAL_TESTED_SHA=f33d1918aeebedbb6b69cbb65eadd6a27851d123   (source-tested; no runtime defect found that required a new commit)
BRANCH=develop
BUILD_VERSION=0.17.0-omniroute.1
INSTALLER_PATH=WAITING_FOR_HUMAN (npm run dist:win on Windows)
INSTALLER_SIZE=WAITING_FOR_HUMAN
INSTALLER_SHA256=WAITING_FOR_HUMAN
WINDOWS_BUILD=WAITING_FOR_HUMAN (compile stage PASS in Linux; NSIS/MSI packaging needs Windows)
INSTALLATION=WAITING_FOR_HUMAN
TESTING_OLD_V0204=NO (target build is 0.17.0-omniroute.1, distinct from v0.20.4)
COLD_START=WAITING_FOR_HUMAN
BACKEND_READY=WAITING_FOR_HUMAN
RESTART=WAITING_FOR_HUMAN
FORK_GUARD_RUNTIME=WAITING_FOR_HUMAN (source logic PASS)
UPDATE_BACKOFF_RUNTIME=WAITING_FOR_HUMAN (source logic PASS)
VENV_BLOCKER_RUNTIME=WAITING_FOR_HUMAN
CORRUPT_BACKOFF_RUNTIME=WAITING_FOR_HUMAN (source logic PASS)
UPDATER_ATOMIC_LOCK_RUNTIME=WAITING_FOR_HUMAN (source real-multiprocess race PASS)
STATE_DB=WAITING_FOR_HUMAN (runbook: PRAGMA quick_check/integrity_check)
LOCAL_ONLY_RUNTIME=NOT_PROVEN (source PASS; live-network proof required on Windows — BLOCKER)
AGENTS_RUNTIME=WAITING_FOR_HUMAN
SUBAGENTS_RUNTIME=WAITING_FOR_HUMAN
GOALS_RUNTIME=WAITING_FOR_HUMAN
MEMORY_STARMAP_RUNTIME=WAITING_FOR_HUMAN
COMPUTER_USE_RUNTIME=WAITING_FOR_HUMAN
PRODUCT_STUDIO_RUNTIME=WAITING_FOR_HUMAN
SECURITY_RESEARCH_RUNTIME=WAITING_FOR_HUMAN
RAPTOR_RUNTIME=WAITING_FOR_HUMAN (may resolve to BLOCKED_BY_EXTERNAL_DEPENDENCY)
OPENWA=WAITING_FOR_HUMAN (may resolve to WAITING_FOR_HUMAN_QR_SCAN)
TERMINAL_RUNTIME=WAITING_FOR_HUMAN
FILES_ARTIFACTS_DIFF_RUNTIME=WAITING_FOR_HUMAN
PREVIEW_RUNTIME=WAITING_FOR_HUMAN
TOKEN_URL_SECURITY=WAITING_FOR_HUMAN (P1 — runtime repro needed)
FS_BOUNDARIES_RUNTIME=WAITING_FOR_HUMAN (P1 — runtime repro needed)
ELECTRON_SECURITY=WAITING_FOR_HUMAN
PT_BR=WAITING_FOR_HUMAN
ACCESSIBILITY=WAITING_FOR_HUMAN
VISUAL_QA=WAITING_FOR_HUMAN
SECRET_SCAN=PASS (repo tree)
DEPENDENCY_AUDIT=PASS (npm audit --omit=dev = 0)
ELECTRON_TESTS=PASS (1593 passed / 8 skipped / 0 failed)
PYTHON_TESTS=PASS (143 LOCAL_ONLY/memory; full suite runnable on host)
UI_TESTS=WAITING_FOR_HUMAN (renderer E2E needs the running app)
P0_OPEN=0 at source (runtime P0 gates unproven — see WAITING_FOR_HUMAN)
P1_OPEN=2 deferred (token-in-URL, fs-scope) — require Windows runtime to repro+fix+verify
P2_OPEN=0 at source
RELEASE_CANDIDATE=NOT_PROVEN (cannot declare READY without Windows runtime + LOCAL_ONLY live proof)
STABLE_RELEASE=NOT_AUTHORIZED
```

## Path to RELEASE_CANDIDATE=READY

1. On Windows: run `windows-validation.ps1` → native build + installer hash + source suites.
2. Install the new build; complete the interactive checklist (cold start, restart, fork guard,
   backoff, venv, corrupt-backoff, atomic-lock runtime, state.db).
3. Prove **LOCAL_ONLY_RUNTIME=PASS** with captured network evidence (the release blocker).
4. Reproduce + fix the two P1s (token-in-URL, fs-scope) with the running app; add regression
   tests; rebuild; reinstall; re-verify.
5. Run the 3 adversarial auditors against the installed build; fix P0/P1; retest.
6. Only then flip RELEASE_CANDIDATE — and STABLE stays NOT_AUTHORIZED regardless.
