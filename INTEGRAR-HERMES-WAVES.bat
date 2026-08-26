@echo off
REM ============================================================
REM  INTEGRAR-HERMES-WAVES.bat  (one-click, safe, no-force)
REM  Integrates the feature/autonomy-kernel bundle into develop
REM  and pushes to the fork remote. NEVER pushes upstream, NEVER
REM  force-pushes, NEVER cuts a release. Aborts on any non-trivial
REM  problem and writes HERMES-INTEGRATION-RESULT.txt.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set RESULT=HERMES-INTEGRATION-RESULT.txt
> "%RESULT%" echo Hermes waves integration %DATE% %TIME%

echo [1/13] repo check
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 ( echo   NOT a git repo & >>"%RESULT%" echo STATUS=ABORT reason=not_a_git_repo & goto :fail )

echo [2/13] working tree must be clean
set DIRTY=
for /f "delims=" %%s in ('git status --porcelain') do set DIRTY=1
if defined DIRTY ( echo   working tree is dirty - commit or stash first & >>"%RESULT%" echo STATUS=ABORT reason=dirty_working_tree & goto :fail )

echo [3/13] locate newest bundle
set BUNDLE=
for /f "delims=" %%f in ('dir /b /o-d hos-waves-*.bundle 2^>nul') do if not defined BUNDLE set BUNDLE=%%f
if not defined BUNDLE ( echo   no hos-waves-*.bundle found in this folder & >>"%RESULT%" echo STATUS=ABORT reason=no_bundle & goto :fail )
echo   bundle: !BUNDLE!
>>"%RESULT%" echo BUNDLE=!BUNDLE!

echo [4/13] verify bundle
git bundle verify "!BUNDLE!"
if errorlevel 1 ( echo   bundle verify failed & >>"%RESULT%" echo STATUS=ABORT reason=bundle_verify_failed & goto :fail )

echo [5/13] detect fork remote (must be lmpradodz23-design/Hermes-OmniRoute-Studio)
set PUSH_REMOTE=
for /f "tokens=1,2" %%a in ('git remote -v ^| findstr /i "(push)"') do (
  echo %%b | findstr /i "lmpradodz23-design/Hermes-OmniRoute-Studio" >nul
  if not errorlevel 1 set PUSH_REMOTE=%%a
)
if not defined PUSH_REMOTE ( echo   no fork remote found - never pushing upstream & >>"%RESULT%" echo STATUS=ABORT reason=no_fork_remote & goto :fail )
echo   push remote: !PUSH_REMOTE!
>>"%RESULT%" echo PUSH_REMOTE=!PUSH_REMOTE!

echo [6/13] import bundle into local ref hermes-waves-incoming
git fetch "!BUNDLE!" +feature/autonomy-kernel:hermes-waves-incoming
if errorlevel 1 ( echo   bundle fetch failed & >>"%RESULT%" echo STATUS=ABORT reason=bundle_fetch_failed & goto :fail )

echo [7/13] run targeted kernel tests on the incoming code
git checkout hermes-waves-incoming
if errorlevel 1 ( echo   checkout incoming failed & >>"%RESULT%" echo STATUS=ABORT reason=checkout_incoming_failed & goto :fail )
where python >nul 2>&1
if errorlevel 1 (
  echo   python not found - skipping targeted tests
  >>"%RESULT%" echo TARGETED_TESTS=SKIPPED_no_python
) else (
  python -m pytest tests/agent/test_budget_state.py tests/agent/test_mission_dag.py tests/agent/test_progress_signal.py tests/agent/test_mission.py tests/agent/test_product_spec.py tests/agent/test_kernel_pipeline.py tests/agent/test_route_history.py tests/canary/test_canary_framework.py tests/agent/test_mission_runtime.py -q
  if errorlevel 1 ( echo   targeted tests FAILED & git checkout - & >>"%RESULT%" echo STATUS=ABORT reason=targeted_tests_failed & goto :fail )
  >>"%RESULT%" echo TARGETED_TESTS=PASS
)

echo [8/13] sync develop with remote (fast-forward only)
git fetch !PUSH_REMOTE! develop
if errorlevel 1 ( echo   remote fetch failed & >>"%RESULT%" echo STATUS=ABORT reason=remote_fetch_failed & goto :fail )
git checkout develop 2>nul || git checkout -b develop !PUSH_REMOTE!/develop
git merge --ff-only !PUSH_REMOTE!/develop
if errorlevel 1 ( echo   local develop diverged from remote - resolve manually & >>"%RESULT%" echo STATUS=ABORT reason=develop_not_ff_with_remote & goto :fail )

echo [9/13] incoming commits:
git log --oneline develop..hermes-waves-incoming
git log --oneline develop..hermes-waves-incoming >> "%RESULT%"

echo [10/13] merge incoming (no-ff, NO force)
git merge --no-ff --no-edit hermes-waves-incoming
if errorlevel 1 (
  echo   merge conflict - aborting merge, no changes kept
  git merge --abort
  >>"%RESULT%" echo STATUS=ABORT reason=merge_conflict
  goto :fail
)

echo [11/13] secret scan (best-effort)
where gitleaks >nul 2>&1
if errorlevel 1 (
  echo   gitleaks not found - skipping
  >>"%RESULT%" echo SECRET_SCAN=SKIPPED_no_gitleaks
) else (
  gitleaks detect --no-banner
  if errorlevel 1 ( echo   secret scan found something - undoing merge & git reset --hard !PUSH_REMOTE!/develop & >>"%RESULT%" echo STATUS=ABORT reason=secret_scan_failed & goto :fail )
  >>"%RESULT%" echo SECRET_SCAN=PASS
)

echo [12/13] push to fork develop (NO force)
git push !PUSH_REMOTE! develop
if errorlevel 1 ( echo   push failed & >>"%RESULT%" echo STATUS=ABORT reason=push_failed PUSH=FAIL & goto :fail )

echo [13/13] verify remote HEAD
git fetch !PUSH_REMOTE! develop
for /f %%h in ('git rev-parse develop') do set DEVHEAD=%%h
for /f %%h in ('git rev-parse !PUSH_REMOTE!/develop') do set REMHEAD=%%h
>>"%RESULT%" echo DEVELOP_HEAD=!DEVHEAD!
>>"%RESULT%" echo REMOTE_HEAD=!REMHEAD!
if /i "!DEVHEAD!"=="!REMHEAD!" (
  echo   PUSH=PASS  develop=!DEVHEAD!
  >>"%RESULT%" echo PUSH=PASS
  >>"%RESULT%" echo STATUS=SUCCESS
) else (
  echo   remote HEAD mismatch
  >>"%RESULT%" echo PUSH=FAIL reason=head_mismatch
  goto :fail
)

echo.
echo DONE. Result written to %RESULT%
echo NOTE: this integrated development work into develop. It did NOT create a
echo release or a tag; the Public Preview tag stays pinned to its tested SHA.
endlocal
exit /b 0

:fail
echo.
echo INTEGRATION ABORTED - see %RESULT% (nothing was force-pushed)
endlocal
exit /b 1
