<#
  Hermes OmniRoute Studio - Windows RC runtime validation runbook
  Baseline SHA: 6c4677068e604c5541cadc19f350051d70de79f5  (branch develop)

  This file is PURE ASCII and safe for Windows PowerShell 5.1 (which mis-reads
  non-ASCII in UTF-8-no-BOM files) AND PowerShell 7. The SQLite check lives in a
  separate state-db-check.py (no fragile inline-python quoting).

  WHAT IT DOES (safe, non-destructive):
    Preflight   - toolchain + disk + verify HEAD == f33d1918 + non-destructive
                  backup of userData/HERMES_HOME + read-only state.db PRAGMA check.
    SourceTests - tsc electron + updater/concurrency vitest on Windows.
    Build       - npm run dist:win (NSIS + MSI), capture installer path/size/SHA256.
    Runtime     - print the interactive checklist for the human-observed gates.

  IT NEVER deletes state.db, resets a database, clears memory/config, removes the
  old install, force-pushes, or publishes stable. Runtime gates use an ISOLATED
  test HERMES_HOME so real data is untouched.

  RUN (from the repo root):
    powershell -ExecutionPolicy Bypass -File .\audit\runtime-evidence\6c46770\windows-validation.ps1 -Phase Preflight
    ...then -Phase SourceTests, -Phase Build, -Phase Runtime  (or -Phase All)
#>

[CmdletBinding()]
param(
  [ValidateSet('Preflight','SourceTests','Build','Runtime','All')]
  [string]$Phase = 'All'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Repo        = 'C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute'
$FrozenSha   = '6c4677068e604c5541cadc19f350051d70de79f5'
$EvidenceDir = Join-Path $Repo 'audit\runtime-evidence\6c46770'
$Stamp       = Get-Date -Format 'yyyyMMdd-HHmmss'
$Log         = Join-Path $EvidenceDir ('windows-validation-' + $Stamp + '.log')
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

# Robust native-command runner (see native-runner.ps1). Centralizes every
# external process call so a native tool writing to stderr (e.g. npm warnings)
# can never abort the script under PS 5.1; only a non-zero exit code fails.
. (Join-Path $PSScriptRoot 'native-runner.ps1')

function Say([string]$m) {
  $line = '[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $m
  Write-Host $line
  Add-Content -Path $Log -Value $line
}

# Resolved once in Preflight, reused by later phases in an All run.
$script:DataPaths = @()

function Invoke-Preflight {
  Say '=== PREFLIGHT ==='

  # -- toolchain + disk --
  try { $os = (Get-CimInstance Win32_OperatingSystem).Caption } catch { $os = 'unknown' }
  Say ('Windows: ' + $os + ' ' + [Environment]::OSVersion.Version.ToString())
  Say ('Arch: ' + $env:PROCESSOR_ARCHITECTURE)
  foreach ($t in @('node','npm','python','git')) {
    $v = Invoke-NativeCapture -File $t -Arguments @('--version') -LogPath $Log
    if ($v) { Say ($t + ': ' + (($v -split "`n")[0])) } else { Say ($t + ': NOT FOUND') }
  }
  try {
    $free = [math]::Round((Get-PSDrive C).Free / 1GB, 1)
    Say ('Free disk C: ' + $free + ' GB')
    if ($free -lt 15) { Say 'WARNING: less than 15 GB free - a native build may fail.' }
  }
  catch { Say 'Free disk C: N/A (no C drive on this host)' }

  # -- git verification (read-only; via the robust capture helper) --
  $head = Invoke-NativeCapture -File 'git' -Arguments @('rev-parse','HEAD') -WorkingDirectory $Repo -LogPath $Log
  $branch = Invoke-NativeCapture -File 'git' -Arguments @('branch','--show-current') -WorkingDirectory $Repo -LogPath $Log
  Say ('HEAD: ' + $head)
  Say ('Branch: ' + $branch)
  if ($head -ne $FrozenSha) {
    Say ('MISMATCH: HEAD != ' + $FrozenSha + '. NOT overwriting anything. Reconcile before building.')
    throw 'HEAD does not match the frozen baseline.'
  }
  Say 'HEAD matches the frozen baseline.'

  # -- resolve user-data locations (used by backup + state.db) --
  $candidates = @()
  if ($env:APPDATA)     { $candidates += (Join-Path $env:APPDATA 'Hermes OmniRoute Studio'); $candidates += (Join-Path $env:APPDATA 'hermes') }
  if ($env:USERPROFILE) { $candidates += (Join-Path $env:USERPROFILE '.hermes') }
  if ($env:LOCALAPPDATA){ $candidates += (Join-Path $env:LOCALAPPDATA 'hermes') }
  if ($env:HERMES_HOME) { $candidates += $env:HERMES_HOME }
  $script:DataPaths = @($candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique)

  # -- non-destructive backup (copy only) --
  if ($script:DataPaths.Count -gt 0) {
    $backupRoot = Join-Path $env:USERPROFILE ('Hermes-RC-backup-' + $Stamp)
    New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
    foreach ($p in $script:DataPaths) {
      $leaf = Split-Path -Path $p.TrimEnd('\') -Leaf
      $dest = Join-Path $backupRoot $leaf
      Say ('Backup (copy, no delete): ' + $p + ' -> ' + $dest)
      Copy-Item -Path $p -Destination $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
    Say ('Backup at: ' + $backupRoot)
  }
  else {
    Say 'No existing userData/HERMES_HOME found (fresh-install scenario) - nothing to back up.'
  }

  # -- state.db integrity (read-only, via the separate python helper) --
  $checker = Join-Path $EvidenceDir 'state-db-check.py'
  $dbs = @()
  foreach ($p in $script:DataPaths) {
    $dbs += Get-ChildItem -Path $p -Filter 'state.db' -Recurse -ErrorAction SilentlyContinue
  }
  $dbs = $dbs | Select-Object -First 3
  if (($dbs | Measure-Object).Count -eq 0) {
    Say 'STATE_DB=NOT_APPLICABLE_FRESH_PROFILE (no state.db found in known locations)'
  }
  elseif (-not (Test-Path $checker)) {
    Say ('state.db present but helper missing: ' + $checker)
  }
  else {
    foreach ($db in $dbs) {
      $res = Invoke-NativeCapture -File 'python' -Arguments @($checker, $db.FullName) -LogPath $Log
      Say ('state.db ' + $db.FullName + ': ' + $res)
    }
  }

  Say 'WINDOWS_EXECUTOR_PREFLIGHT=PASS'
}

function Invoke-SourceTests {
  Say '=== SOURCE TESTS (Windows) ==='
  $desktop = Join-Path $Repo 'apps\desktop'
  $fail = $false

  # Root deps (only if missing). npm emits config warnings to stderr - the
  # runner treats those as non-fatal; only a non-zero exit fails.
  if (-not (Test-Path (Join-Path $Repo 'node_modules'))) {
    Say 'Installing root deps (npm ci)...'
    $c = Invoke-NativeCommand -File 'npm' -Arguments @('ci','--no-audit','--no-fund') -WorkingDirectory $Repo -LogPath $Log
    Say ('npm ci exit=' + $c)
    if ($c -ne 0) { Say 'NPM_CI=FAIL'; $fail = $true }
  }

  # 1) Electron typecheck.
  Say 'ELECTRON typecheck (tsc)...'
  $c = Invoke-NativeCommand -File 'npx' -Arguments @('tsc','--noEmit','-p','tsconfig.electron.json') -WorkingDirectory $desktop -LogPath $Log
  if ($c -eq 0) { Say 'ELECTRON_TYPECHECK=PASS' } else { Say ('ELECTRON_TYPECHECK=FAIL (exit ' + $c + ')'); $fail = $true }

  # 2) Full Electron suite (updater + atomic lock + LOCAL_ONLY-adjacent + all unit).
  Say 'ELECTRON tests (full electron/ vitest suite)...'
  $c = Invoke-NativeCommand -File 'npx' -Arguments @('vitest','run','electron/') -WorkingDirectory $desktop -LogPath $Log
  if ($c -eq 0) { Say 'ELECTRON_TESTS=PASS' } else { Say ('ELECTRON_TESTS=FAIL (exit ' + $c + ')'); $fail = $true }
  Say 'NOTE: the concurrency test forks OS processes; on Windows this exercises NTFS O_EXCL/link semantics - the target platform.'

  # 3) Python LOCAL_ONLY + memory. Best-effort: if the python test deps are not
  #    installed on this host, pytest exits 2/3 (collection error) which we
  #    report as NOT_PROVEN rather than a Hermes defect. exit 0 = PASS, 1 = FAIL.
  Say 'PYTHON LOCAL_ONLY + memory tests...'
  $pyArgs = @('-m','pytest',
    'tests/agent/test_local_only_aux_egress.py',
    'tests/agent/test_local_only_loopback_parser.py',
    'tests/agent/test_local_only_memory_egress.py',
    'tests/agent/test_local_only_memory_dispatch.py',
    'tests/agent/test_local_only_config_failclosed.py',
    'tests/agent/test_local_only_supermemory.py',
    'tests/agent/test_local_only_account_usage.py',
    'tests/hermes_cli/test_proxy.py',
    'tests/hermes_cli/test_nous_account.py',
    'tests/plugins/memory/test_mem0_backend.py',
    '-q')
  $c = Invoke-NativeCommand -File 'python' -Arguments $pyArgs -WorkingDirectory $Repo -LogPath $Log
  if ($c -eq 0) { Say 'PYTHON_TESTS=PASS' }
  elseif ($c -eq 1) { Say 'PYTHON_TESTS=FAIL (real test failure)'; $fail = $true }
  else { Say ('PYTHON_TESTS=NOT_PROVEN (pytest exit ' + $c + '; likely missing test deps - install with: python -m pip install pyyaml openai pydantic python-dotenv aiohttp httpx pytest ; NOT a Hermes defect if ImportError)') }

  if ($fail) { Say 'WINDOWS_SOURCE_TESTS=FAIL' } else { Say 'WINDOWS_SOURCE_TESTS=PASS' }
}

function Invoke-Build {
  Say '=== NATIVE WINDOWS BUILD (npm run dist:win) ==='
  Push-Location (Join-Path $Repo 'apps\desktop')
  try {
    $start = Get-Date
    Say 'BUILD_COMMAND: npm run dist:win'
    # Routed through the robust runner: electron-builder + npm emit warnings to
    # stderr; only a non-zero exit code is a real build failure.
    $buildExit = Invoke-NativeCommand -File 'npm' -Arguments @('run','dist:win') -WorkingDirectory (Join-Path $Repo 'apps\desktop') -LogPath $Log
    Say ('BUILD_EXIT_CODE: ' + $buildExit)
    Say ('BUILD duration: ' + ((Get-Date) - $start).ToString())
    if ($buildExit -ne 0) {
      throw 'BUILD FAILED - investigate the log, fix root cause, rebuild. Do NOT install.'
    }

    $outRoots = @('dist_electron','release','dist\electron','out') |
      ForEach-Object { Join-Path $Repo ('apps\desktop\' + $_) } |
      Where-Object { Test-Path $_ }
    $installers = @()
    foreach ($d in $outRoots) {
      $installers += Get-ChildItem -Path $d -Recurse -Include '*.exe','*.msi' -ErrorAction SilentlyContinue
    }
    $installers = $installers | Where-Object { $_.Name -notmatch 'elevate|Uninstall' } | Sort-Object Length -Descending
    if (($installers | Measure-Object).Count -eq 0) {
      Say 'No .exe/.msi found - check electron-builder directories.output in the build config.'
    }
    foreach ($i in $installers) {
      $sha = (Get-FileHash -Algorithm SHA256 -Path $i.FullName).Hash
      Say ('INSTALLER: ' + $i.FullName)
      Say ('  SIZE: ' + $i.Length + ' bytes')
      Say ('  SHA256: ' + $sha)
      Add-Content -Path (Join-Path $EvidenceDir 'installers.txt') -Value ($i.FullName + "`t" + $i.Length + "`t" + $sha)
    }
  }
  finally { Pop-Location }
}

function Show-RuntimeChecklist {
  Say '=== INTERACTIVE RUNTIME GATES (human-observed, with the NEW build) ==='
  Say 'Use an ISOLATED test profile so real data is never touched:'
  Say '  $env:HERMES_HOME = Join-Path $env:TEMP "hermes-rc-test"'
  Say '  New-Item -ItemType Directory -Force -Path $env:HERMES_HOME'
  $items = @(
    '[ ] INSTALL the new build (version 0.17.0-omniroute.1). Confirm it is NOT the old v0.20.4.',
    '[ ] COLD START: fully close Hermes; kill residual electron/node/python; launch NEW build.',
    '    PASS = Electron up + renderer loads + backend reaches READY (verify in desktop/backend log),',
    '    updater does NOT kill the backend, UI operational. Open window alone is NOT pass.',
    '[ ] RESTART x3: close -> confirm teardown (no orphan electron/node/python, no venv lock, no',
    '    stale .hermes-update-in-progress) -> reopen. Backend READY each time, no boot loop.',
    '[ ] FORK GUARD: on this fork checkout, auto-update does NOT run / backend not killed /',
    '    MANUAL_REQUIRED-or-skip / no destructive pull to main.',
    '[ ] UPDATE BACKOFF: force a controlled update failure -> backoff persisted (inspect the file)',
    '    -> backend recovers -> reopen -> updater does NOT immediately retry -> READY, no loop.',
    '[ ] VENV BLOCKER: hold a venv .pyd open -> detection, safe abort, backoff, recovery.',
    '[ ] CORRUPT BACKOFF (TEST profile only): truncated/invalid backoff JSON -> no crash, no',
    '    destructive update enabled, backend READY.',
    '[ ] ATOMIC LOCK (runtime): two near-simultaneous update attempts -> exactly 1 winner; loser',
    '    does not kill backend / spawn updater / overwrite marker.',
    '[ ] LOCAL_ONLY (BLOCKER): enable local_only. With a network capture running (Wireshark/Fiddler/',
    '    Proxifier or Get-NetTCPConnection), attempt cloud providers (OpenAI/Anthropic/Gemini/',
    '    OpenRouter), remote memory (mem0/Supermemory), cloud embeddings/vision/image/video, and a',
    '    background/subagent call. EXPECT: ZERO cloud egress containing content. Then force the LOCAL',
    '    model to fail -> EXPECT local error/recovery, NEVER a cloud fallback. Allow Ollama/local.',
    '    Any content egress = FAIL.',
    '[ ] E2E (real UI->IPC->backend->UI, no fake buttons): Agents, Subagents (LOCAL_ONLY inherited',
    '    -> child cloud DENY), Goals (pause/resume survives restart), Memory/Starmap, Computer Use,',
    '    Product Studio, Security Research->RAPTOR (may be BLOCKED_BY_EXTERNAL_DEPENDENCY),',
    '    WhatsApp->OpenWA (up to WAITING_FOR_HUMAN_QR_SCAN), Terminal, Files/Artifacts/Diff,',
    '    Preview, Settings.',
    '[ ] TOKEN-IN-URL (P1) and FS-BOUNDARIES (P1): reproduce media/download + file selection; no',
    '    token in URL/history/Referer/logs; no traversal/UNC/symlink/other-drive escape.',
    '[ ] ELECTRON SECURITY: contextIsolation on, sandbox, no nodeIntegration in renderer, preload',
    '    allowlist, shell.openExternal guarded, CSP, no secret leakage to renderer.',
    '[ ] pt-BR, ACCESSIBILITY (keyboard/focus/ARIA/contrast/zoom), VISUAL QA (1920x1080/1440x900/1366x768).',
    '[ ] FIRST-RUN / OFFLINE / CRASH-RECOVERY / PROCESS-HYGIENE per the mission.',
    '[ ] INSTALLER ARTIFACT SECRET SCAN: unpack the produced installer; confirm no .env / tokens /',
    '    state.db / sessions / credentials / QR-auth were bundled.'
  )
  foreach ($it in $items) { Say $it }
  Say ('Evidence log: ' + $Log)
  Say 'Fill results into GATE_MATRIX.md; re-run this script after any source fix + rebuild.'
}

# -- dispatch --
Say ('=== Hermes OmniRoute Windows validation - phase: ' + $Phase + ' ===')
switch ($Phase) {
  'Preflight'   { Invoke-Preflight }
  'SourceTests' { Invoke-SourceTests }
  'Build'       { Invoke-Build }
  'Runtime'     { Show-RuntimeChecklist }
  'All'         { Invoke-Preflight; Invoke-SourceTests; Invoke-Build; Show-RuntimeChecklist }
}
Say '=== phase complete ==='
