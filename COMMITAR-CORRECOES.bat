@echo off
setlocal enabledelayedexpansion
REM ===========================================================================
REM  Hermes OmniRoute Studio - commit das correcoes de seguranca e de CRLF
REM
REM  Por que este arquivo existe: a identidade do git (user.name / user.email)
REM  vive no gitconfig global do Windows. Eu trabalho a partir de uma VM Linux
REM  que nao enxerga esse arquivo, entao `git config user.name` volta vazio
REM  para mim. Nao vou inventar nem emprestar uma identidade para assinar um
REM  commit no seu nome, entao o commit fica com voce - com o conteudo ja
REM  montado, conferido e com a mensagem escrita.
REM
REM  Este script NAO faz push, NAO faz reset, NAO faz clean, NAO descarta nada.
REM ===========================================================================

cd /d "%~dp0"

set MSGFILE=audit\_raw\_commit_msg_r3.txt
if not exist "%MSGFILE%" (
  echo ERRO: nao achei "%MSGFILE%".
  goto :fim
)

echo.
echo == Identidade do git ==
set GITNAME=
for /f "delims=" %%i in ('git config user.name 2^>nul') do set GITNAME=%%i
for /f "delims=" %%i in ('git config user.email 2^>nul') do set GITMAIL=%%i
if "!GITNAME!"=="" (
  echo   ERRO: git config user.name esta vazio.
  echo   Rode:  git config --global user.name  "Seu Nome"
  echo          git config --global user.email "seu@email"
  goto :fim
)
echo   !GITNAME! ^<!GITMAIL!^>

echo.
echo == Branch e HEAD atual ==
git rev-parse --abbrev-ref HEAD
git log -1 --oneline

echo.
echo == Preparando o indice ==
git add .gitattributes tools/approval.py tests/tools/test_package_fetch_guard.py
if errorlevel 1 goto :fim
git add plugins/dz23-guardrail/__init__.py tests/plugins/test_dz23_guardrail_fallback.py
if errorlevel 1 goto :fim
git add apps/desktop/electron/omniroute-security.test.ts apps/desktop/electron/windows-hermes-path.test.ts
if errorlevel 1 goto :fim
git add hermes docker scripts contributors datagen-config-examples
if errorlevel 1 goto :fim
git add apps/bootstrap-installer apps/desktop/src/plugins/hermes-bots/LICENSE
if errorlevel 1 goto :fim
git add apps/desktop/src/components/chat/intro-copy.jsonl audit
if errorlevel 1 goto :fim
git add CODE_OF_CONDUCT.md CHANGELOG.md SECURITY.md
if errorlevel 1 goto :fim
git add apps/desktop/src/i18n/pt-br.ts apps/desktop/src/i18n/pt-br.test.ts
if errorlevel 1 goto :fim
git add web/index.html web/public web/src/pwa web/src/main.tsx
if errorlevel 1 goto :fim
git add web/src/lib/gateway-origin.ts web/src/lib/gateway-origin.test.ts web/src/lib/api.ts
if errorlevel 1 goto :fim
git add apps/mobile
if errorlevel 1 goto :fim
git add hermes_cli/goals.py hermes_cli/cli_commands_mixin.py gateway/slash_commands.py
if errorlevel 1 goto :fim
git add tests/hermes_cli/test_goal_start.py
if errorlevel 1 goto :fim

echo.
echo == O que vai entrar no commit ==
git status --short --untracked-files=no

echo.
echo Confira a lista acima.
echo   Enter    = commitar
echo   Ctrl+C   = abortar sem commitar (o indice fica preparado, nada e perdido)
pause >nul

git commit -F "%MSGFILE%"
if errorlevel 1 goto :fim

echo.
echo == Commit criado ==
git log -1 --stat --oneline

echo.
echo Nada foi enviado para o remoto.
echo Para publicar, quando voce quiser:
echo    git push origin feature/hermes-omniroute-studio

:fim
echo.
pause
