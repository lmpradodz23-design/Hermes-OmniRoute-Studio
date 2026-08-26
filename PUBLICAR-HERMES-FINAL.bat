@echo off
REM ============================================================
REM  PUBLICAR-HERMES-FINAL.bat  (one-click FINAL publish)
REM  Imports the newest integrated develop bundle into a local
REM  ref and fast-forward pushes it to the fork's develop.
REM  Checkout-free (immune to the Windows dirty-tree/EOL issue).
REM  NEVER force-pushes. NEVER pushes to NousResearch upstream.
REM  Writes HERMES-FINAL-PUSH-RESULT.txt.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"
set RESULT=HERMES-FINAL-PUSH-RESULT.txt
> "%RESULT%" echo Hermes FINAL publish %DATE% %TIME%

echo [1/9] repo check
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 ( echo   NOT a git repo & >>"%RESULT%" echo STATUS=ABORT reason=not_a_git_repo & goto :fail )

echo [2/9] locate newest integrated bundle
set BUNDLE=
for /f "delims=" %%f in ('dir /b /o-d hos-develop-integrated-*.bundle 2^>nul') do if not defined BUNDLE set BUNDLE=%%f
if not defined BUNDLE ( echo   no hos-develop-integrated-*.bundle found & >>"%RESULT%" echo STATUS=ABORT reason=no_bundle & goto :fail )
echo   bundle: !BUNDLE!
>>"%RESULT%" echo BUNDLE=!BUNDLE!

echo [3/9] verify bundle
git bundle verify "!BUNDLE!"
if errorlevel 1 ( echo   bundle verify failed & >>"%RESULT%" echo STATUS=ABORT reason=bundle_verify_failed & goto :fail )

echo [4/9] detect fork remote (must be lmpradodz23-design/Hermes-OmniRoute-Studio)
set PUSH_REMOTE=
for /f "tokens=1,2" %%a in ('git remote -v ^| findstr /i "(push)"') do (
  echo %%b | findstr /i "lmpradodz23-design/Hermes-OmniRoute-Studio" >nul
  if not errorlevel 1 set PUSH_REMOTE=%%a
)
if not defined PUSH_REMOTE ( echo   no fork remote found - NEVER pushing upstream & >>"%RESULT%" echo STATUS=ABORT reason=no_fork_remote & goto :fail )
echo   push remote: !PUSH_REMOTE!
>>"%RESULT%" echo PUSH_REMOTE=!PUSH_REMOTE!

echo [5/9] guard: refuse if remote is NousResearch upstream
git remote get-url !PUSH_REMOTE! | findstr /i "NousResearch" >nul
if not errorlevel 1 ( echo   remote points to upstream - REFUSING & >>"%RESULT%" echo STATUS=ABORT reason=refuse_upstream & goto :fail )

echo [6/9] import integrated develop into a local ref (no working-tree change)
git fetch "!BUNDLE!" +develop-integrated:develop-integrated
if errorlevel 1 ( echo   bundle fetch failed & >>"%RESULT%" echo STATUS=ABORT reason=bundle_fetch_failed & goto :fail )

echo [7/9] final secret scan on the incoming tree (best-effort)
where gitleaks >nul 2>&1
if errorlevel 1 (
  echo   gitleaks not found - skipping
  >>"%RESULT%" echo SECRET_SCAN=SKIPPED_no_gitleaks
) else (
  git stash create >nul 2>&1
  gitleaks detect --no-banner --source . >nul 2>&1
  if errorlevel 1 ( echo   secret scan flagged something - ABORT & >>"%RESULT%" echo STATUS=ABORT reason=secret_scan_failed & goto :fail )
  >>"%RESULT%" echo SECRET_SCAN=PASS
)

echo [8/9] refresh remote develop, require fast-forward, then push (NO force)
git fetch !PUSH_REMOTE! develop
if errorlevel 1 ( echo   remote fetch failed & >>"%RESULT%" echo STATUS=ABORT reason=remote_fetch_failed & goto :fail )
git merge-base --is-ancestor !PUSH_REMOTE!/develop develop-integrated
if errorlevel 1 ( echo   remote develop advanced - NOT a fast-forward, re-integrate needed & >>"%RESULT%" echo STATUS=ABORT reason=not_fast_forward & goto :fail )
echo   commits ahead of remote:
git log --oneline !PUSH_REMOTE!/develop..develop-integrated
git log --oneline !PUSH_REMOTE!/develop..develop-integrated >> "%RESULT%"
git push !PUSH_REMOTE! develop-integrated:develop
if errorlevel 1 ( echo   push failed & >>"%RESULT%" echo STATUS=ABORT reason=push_failed PUSH=FAIL & goto :fail )

echo [9/9] verify remote HEAD
git fetch !PUSH_REMOTE! develop
for /f %%h in ('git rev-parse develop-integrated') do set LH=%%h
for /f %%h in ('git rev-parse !PUSH_REMOTE!/develop') do set RH=%%h
>>"%RESULT%" echo LOCAL_HEAD=!LH!
>>"%RESULT%" echo REMOTE_HEAD=!RH!
if /i "!LH!"=="!RH!" (
  echo   PUSH=PASS  develop=!LH!
  >>"%RESULT%" echo PUSH=PASS
  >>"%RESULT%" echo STATUS=SUCCESS
) else (
  echo   remote HEAD mismatch
  >>"%RESULT%" echo PUSH=FAIL reason=head_mismatch
  goto :fail
)

echo.
echo DONE. Hermes OmniRoute Studio published to fork develop.
echo (No release/tag created; no upstream push; no force.)
echo Result written to %RESULT%
endlocal
exit /b 0

:fail
echo.
echo PUBLISH ABORTED - see %RESULT% (nothing was force-pushed)
endlocal
exit /b 1
