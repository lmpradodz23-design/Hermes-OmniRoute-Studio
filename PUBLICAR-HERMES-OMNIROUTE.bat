@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Publicar Hermes OmniRoute Studio (open source)
color 0F

rem ===========================================================================
rem  PUBLICAR-HERMES-OMNIROUTE.bat
rem  Duplo clique: publica o projeto no repositorio open source (remote "oss"),
rem  na branch "develop", com portoes de seguranca. NUNCA faz push no origin
rem  (upstream NousResearch). NUNCA usa --force. Para em erro. Gera RESULT.
rem  A credencial do GitHub fica no seu PC (gh auth) - nunca neste arquivo.
rem ===========================================================================

cd /d "%~dp0"
set "PROJ=%CD%"
set "REPO=Hermes-OmniRoute-Studio"
set "LOG=%PROJ%\HERMES-PUBLISH-LOG.txt"
set "RESULT=%PROJ%\HERMES-PUBLISH-RESULT.txt"
set "TREE=%PROJ%\HERMES-REMOTE-TREE.txt"
set "TMPN=%TEMP%\hero_names_%RANDOM%.txt"
set "TMPD=%TEMP%\hero_diff_%RANDOM%.txt"
set "TMPH=%TEMP%\hero_hits_%RANDOM%.txt"
set "TMPJSON=%TEMP%\hero_gl_%RANDOM%.json"
set "PATH=%PATH%;%LOCALAPPDATA%\HermesTools\gh\bin"
set "PATH=%PATH%;%LOCALAPPDATA%\HermesTools\gitleaks\bin"

rem --- result fields (defaults) ---
set "FAILSTEP="
set "GHUSER="
set "REPOURL="
set "ORIGINURL="
set "OSSURL="
set "R_SECRET=PENDING"
set "R_FORBID=PENDING"
set "R_WORKTREE=PENDING"
set "R_COMMIT=PENDING"
set "R_PUSH=PENDING"
set "R_REMOTEVERIFY=PENDING"
set "R_REMOTEHEAD="
set "R_REMOTEFILES="
set "R_REPOCREATED=UNKNOWN"
set "R_BRANCH="
set "R_LOCALHEAD="

> "%LOG%" echo ==== Hermes OmniRoute publish %DATE% %TIME% ====
call :log "Projeto: %PROJ%"

rem =========================== 1. Ferramentas ================================
call :step "Verificando git"
where git >nul 2>&1 || (call :log "git nao encontrado. Instale: https://git-scm.com/download/win e rode o .bat de novo." & set "FAILSTEP=GIT_NOT_FOUND" & goto :FAIL)
git --version >>"%LOG%" 2>&1 || (set "FAILSTEP=GIT_NOT_FOUND" & goto :FAIL)
call :log "git OK."

call :step "Verificando GitHub CLI (gh)"
where gh >nul 2>&1
if errorlevel 1 (
  call :log "gh (GitHub CLI) nao encontrado - instalando versao portatil no seu usuario (sem admin, sem winget)..."
  call :install_gh
  set "PATH=%PATH%;%LOCALAPPDATA%\HermesTools\gh\bin"
  where gh >nul 2>&1
  if errorlevel 1 (call :log "Nao consegui instalar o gh automaticamente (veja HERMES-PUBLISH-LOG.txt). Instale manual: https://cli.github.com e rode o .bat de novo." & set "FAILSTEP=GH_NOT_FOUND" & goto :FAIL)
  call :log "gh instalado (portatil)."
)
gh --version >>"%LOG%" 2>&1 || (set "FAILSTEP=GH_NOT_FOUND" & goto :FAIL)
call :log "gh OK."

call :step "Confirmando que estamos num checkout git"
git rev-parse --is-inside-work-tree >>"%LOG%" 2>&1 || (set "FAILSTEP=NOT_A_GIT_REPO" & goto :FAIL)

rem =========================== 2. Autenticacao ==============================
call :step "Verificando autenticacao GitHub (gh auth status)"
gh auth status >>"%LOG%" 2>&1
if errorlevel 1 (
  call :log "Nao autenticado. Abrindo 'gh auth login' - siga as instrucoes na janela."
  echo.
  echo  ================================================================
  echo   Voce precisa entrar no GitHub UMA vez. Uma janela/prompt vai abrir.
  echo   Escolha: GitHub.com  ^>  HTTPS  ^>  Login with a web browser.
  echo  ================================================================
  echo.
  gh auth login
  gh auth status >>"%LOG%" 2>&1 || (set "FAILSTEP=GH_AUTH" & goto :FAIL)
)
call :log "GitHub autenticado."

call :step "Descobrindo usuario GitHub"
for /f "usebackq delims=" %%u in (`gh api user --jq .login 2^>nul`) do set "GHUSER=%%u"
if "%GHUSER%"=="" (set "FAILSTEP=GH_USER" & goto :FAIL)
set "REPOURL=https://github.com/%GHUSER%/%REPO%.git"
call :log "Usuario: %GHUSER%   Repo alvo: %REPOURL%"

rem =========================== 3. Estado local ==============================
call :step "Registrando estado do working tree"
for /f "usebackq delims=" %%b in (`git rev-parse --abbrev-ref HEAD 2^>nul`) do set "R_BRANCH=%%b"
for /f "usebackq delims=" %%h in (`git rev-parse HEAD 2^>nul`) do set "R_LOCALHEAD=%%h"
call :log "Branch local: !R_BRANCH!   HEAD: !R_LOCALHEAD!"
git remote -v >>"%LOG%" 2>&1
for /f "usebackq delims=" %%o in (`git remote get-url origin 2^>nul`) do set "ORIGINURL=%%o"
call :log "origin: !ORIGINURL!"
git status --short >>"%LOG%" 2>&1
set "R_WORKTREE=RECORDED"

rem =========================== 4. Origin = upstream (nunca push) =============
call :step "Confirmando que origin e o upstream (nunca daremos push nele)"
echo !ORIGINURL! | findstr /I "NousResearch/hermes-agent" >nul 2>&1
if errorlevel 1 (
  call :log "AVISO: origin nao e o upstream NousResearch esperado. Prosseguindo, mas NAO usaremos origin para push."
) else (
  call :log "OK: origin e o upstream NousResearch (esperado). Nunca daremos push aqui."
)

rem =========================== 5. Docs obrigatorias ==========================
call :step "Verificando documentacao obrigatoria"
set "MISSING="
for %%f in (README.md LICENSE SECURITY.md CONTRIBUTING.md THIRD_PARTY_NOTICES.md) do if not exist "%%f" set "MISSING=!MISSING! %%f"
if not exist "docs\ARCHITECTURE.md" set "MISSING=!MISSING! docs/ARCHITECTURE.md"
if not "!MISSING!"=="" (call :log "Faltando doc(s):!MISSING!" & set "FAILSTEP=MISSING_DOCS" & goto :FAIL)
call :log "Docs obrigatorias presentes."

rem =========================== 6. Nao bundlar upstream =======================
call :step "Confirmando que RAPTOR/OpenWA nao estao bundlados como clones"
if exist "raptor\" (call :log "Diretorio 'raptor\' (clone upstream) presente - nao deve ir ao repo." & set "FAILSTEP=RAPTOR_BUNDLED" & goto :FAIL)
if exist "wa-automate-nodejs\" (call :log "Clone 'wa-automate-nodejs\' presente." & set "FAILSTEP=OPENWA_BUNDLED" & goto :FAIL)
call :log "OK: apenas adapters proprios (security_research/, whatsapp_provider/)."

rem =========================== 7. Repositorio remoto =========================
call :step "Verificando/criando repositorio %GHUSER%/%REPO%"
gh repo view %GHUSER%/%REPO% >>"%LOG%" 2>&1
if errorlevel 1 (
  call :log "Repo nao existe - criando PUBLIC..."
  gh repo create %GHUSER%/%REPO% --public --disable-wiki --description "Hermes OmniRoute Studio - open-source autonomous engineering desktop with OmniRoute, agents, memory, MCP, security research and automation." >>"%LOG%" 2>&1
  if errorlevel 1 (set "FAILSTEP=REPO_CREATE" & goto :FAIL)
  set "R_REPOCREATED=YES"
) else (
  call :log "Repo ja existe - usando o existente."
  set "R_REPOCREATED=NO_ALREADY_EXISTS"
)

rem =========================== 8. Remote oss ================================
call :step "Configurando remote 'oss'"
git remote get-url oss >nul 2>&1
if errorlevel 1 (
  git remote add oss "%REPOURL%" >>"%LOG%" 2>&1 || (set "FAILSTEP=REMOTE_ADD" & goto :FAIL)
  call :log "Remote 'oss' adicionado: %REPOURL%"
) else (
  for /f "usebackq delims=" %%x in (`git remote get-url oss 2^>nul`) do set "OSSURL=%%x"
  echo !OSSURL! | findstr /I "%GHUSER%/%REPO%" >nul 2>&1
  if errorlevel 1 (call :log "Remote 'oss' aponta para lugar inesperado: !OSSURL!" & set "FAILSTEP=OSS_REMOTE_MISMATCH" & goto :FAIL)
  call :log "Remote 'oss' ja correto: !OSSURL!"
)
for /f "usebackq delims=" %%x in (`git remote get-url oss 2^>nul`) do set "OSSURL=%%x"

rem =========================== 9. Stage ======================================
call :step "Adicionando arquivos (git add -A) - .gitignore ja protege estado local"
git add -A >>"%LOG%" 2>&1 || (set "FAILSTEP=GIT_ADD" & goto :FAIL)

rem =========================== 10. Portao de arquivos proibidos ==============
call :step "Portao: arquivos proibidos entre os staged"
git diff --cached --name-only > "%TMPN%" 2>>"%LOG%"
findstr /I /R /C:"\.env$" /C:"/\.env$" /C:"^\.env$" /C:"\.db$" /C:"\.db-" /C:"\.sqlite" /C:"state\.db" /C:"auth\.json$" /C:"\.pem$" /C:"\.key$" /C:"\.p12$" /C:"\.pfx$" /C:"id_rsa" /C:"id_ed25519" /C:"\.wa-session" /C:"wwebjs" /C:"whatsapp-sessions/" /C:"/venv/" /C:"node_modules/" /C:"\.update_check$" /C:"update-backoff\.json$" /C:"cookies\.json$" "%TMPN%" > "%TMPH%" 2>nul
for %%A in ("%TMPH%") do set "HITSIZE=%%~zA"
if not "!HITSIZE!"=="0" (
  call :log "ARQUIVO PROIBIDO staged:"
  type "%TMPH%" >>"%LOG%"
  git reset >>"%LOG%" 2>&1
  set "R_FORBID=FAILED"
  set "FAILSTEP=FORBIDDEN_FILE" & goto :FAIL
)
set "R_FORBID=PASS"
call :log "OK: nenhum arquivo proibido staged."

rem =========================== 11. Secret scan (gitleaks, staged) ============
call :step "Portao: secret scan (gitleaks nos arquivos staged)"
where gitleaks >nul 2>&1
if errorlevel 1 (
  call :log "gitleaks nao encontrado - instalando versao portatil (sem admin, sem winget)..."
  call :install_gitleaks
  set "PATH=%PATH%;%LOCALAPPDATA%\HermesTools\gitleaks\bin"
  where gitleaks >nul 2>&1
  if errorlevel 1 (call :log "Nao consegui instalar o gitleaks (veja o LOG). O secret scan e OBRIGATORIO - abortando SEM publicar. Instale manual: https://github.com/gitleaks/gitleaks/releases e rode o .bat de novo." & git reset >>"%LOG%" 2>&1 & set "R_SECRET=NO_SCANNER" & set "FAILSTEP=SECRET_SCAN_NO_SCANNER" & goto :FAIL)
)
call :log "gitleaks: escaneando o delta staged (git diff --cached)..."
if exist ".gitleaks.toml" (
  gitleaks protect --staged --config .gitleaks.toml --redact --no-banner --report-format json --report-path "%TMPJSON%" >>"%LOG%" 2>&1
) else (
  gitleaks protect --staged --redact --no-banner --report-format json --report-path "%TMPJSON%" >>"%LOG%" 2>&1
)
if errorlevel 1 (
  call :log "gitleaks acusou possiveis segredos nos arquivos staged. Detalhes (redigidos) em HERMES-SECRET-FINDINGS.txt"
  call :write_secret_findings
  git reset >>"%LOG%" 2>&1
  set "R_SECRET=FAILED"
  set "FAILSTEP=SECRET_SCAN_GITLEAKS" & goto :FAIL
)
set "R_SECRET=PASS_GITLEAKS_STAGED"
call :log "Secret scan (staged): !R_SECRET!"

rem =========================== 12. Commit ===================================
call :step "Commit (se houver mudancas)"
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "chore: publish Hermes OmniRoute Studio open-source development baseline" >>"%LOG%" 2>&1 || (set "FAILSTEP=COMMIT" & goto :FAIL)
  set "R_COMMIT=CREATED"
  for /f "usebackq delims=" %%h in (`git rev-parse HEAD 2^>nul`) do set "R_LOCALHEAD=%%h"
) else (
  set "R_COMMIT=NO_NEW_COMMIT_REQUIRED"
)
call :log "Commit: !R_COMMIT!   HEAD: !R_LOCALHEAD!"

rem =========================== 13. Push (sem force) =========================
call :step "Push para oss develop (SEM force)"
git push -u oss HEAD:develop >>"%LOG%" 2>&1 || (set "R_PUSH=FAILED" & set "FAILSTEP=PUSH" & goto :FAIL)
set "R_PUSH=OK"
call :log "Push concluido."

rem =========================== 14. Verificacao remota ========================
call :step "Verificando refs remotas"
git ls-remote oss >>"%LOG%" 2>&1
for /f "usebackq tokens=1" %%s in (`git ls-remote oss refs/heads/develop 2^>nul`) do set "R_REMOTEHEAD=%%s"
if "!R_REMOTEHEAD!"=="" (set "R_REMOTEVERIFY=FAILED" & set "FAILSTEP=REMOTE_VERIFY" & goto :FAIL)
set "R_REMOTEVERIFY=OK"
gh repo view %GHUSER%/%REPO% >>"%LOG%" 2>&1

call :step "Gerando inventario remoto (oss/develop)"
git fetch oss >>"%LOG%" 2>&1
git ls-tree -r --name-only oss/develop > "%TREE%" 2>>"%LOG%"
set "R_REMOTEFILES=0"
for /f %%c in ('type "%TREE%" ^| find /c /v ""') do set "R_REMOTEFILES=%%c"
call :log "Arquivos na arvore remota: !R_REMOTEFILES!   remote HEAD develop: !R_REMOTEHEAD!"

set "OVERALL=SUCCESS"
goto :WRITE_RESULT

rem =========================== FAIL ==========================================
:FAIL
set "OVERALL=FAILED"
call :log "FALHA na etapa: %FAILSTEP%"
goto :WRITE_RESULT

rem =========================== RESULT ========================================
:WRITE_RESULT
(
  echo HERMES OMNIROUTE - PUBLISH RESULT
  echo DATE_TIME=%DATE% %TIME%
  echo PROJECT_PATH=%PROJ%
  echo CURRENT_BRANCH=!R_BRANCH!
  echo LOCAL_HEAD=!R_LOCALHEAD!
  echo UPSTREAM_ORIGIN=!ORIGINURL!
  echo OSS_REMOTE=!OSSURL!
  echo GITHUB_USER=%GHUSER%
  echo REPOSITORY_URL=https://github.com/%GHUSER%/%REPO%
  echo SECRET_SCAN=!R_SECRET!
  echo FORBIDDEN_FILE_SCAN=!R_FORBID!
  echo WORKTREE=!R_WORKTREE!
  echo COMMIT=!R_COMMIT!
  echo PUSH=!R_PUSH!
  echo REMOTE_VERIFY=!R_REMOTEVERIFY!
  echo REMOTE_HEAD=!R_REMOTEHEAD!
  echo REMOTE_FILES=!R_REMOTEFILES!
  echo REPOSITORY_CREATED=!R_REPOCREATED!
  echo VISIBILITY=PUBLIC
  echo DEVELOP_BRANCH=develop
  echo RELEASE_CREATED=NO
  if defined FAILSTEP echo FAILED_STEP=%FAILSTEP%
  echo RESULT=%OVERALL%
) > "%RESULT%"

echo.
if /I "%OVERALL%"=="SUCCESS" (
  color 0A
  echo  ============================================================
  echo   SUCESSO  ^!  Publicado em: https://github.com/%GHUSER%/%REPO%  (branch develop^)
  echo   Detalhes: HERMES-PUBLISH-RESULT.txt   ^|   Log: HERMES-PUBLISH-LOG.txt
  echo  ============================================================
) else (
  color 0C
  echo  ============================================================
  echo   FALHA na etapa: %FAILSTEP%
  echo   NADA foi forcado. Veja HERMES-PUBLISH-RESULT.txt e HERMES-PUBLISH-LOG.txt
  echo  ============================================================
)
del "%TMPN%" "%TMPD%" "%TMPH%" "%TMPJSON%" >nul 2>&1
echo.
echo Pressione uma tecla para fechar...
pause >nul
endlocal
exit /b 0

rem =========================== helpers =======================================
:log
echo [%TIME%] %~1
>> "%LOG%" echo [%TIME%] %~1
exit /b 0

:step
echo.
echo === %~1 ===
>> "%LOG%" echo.
>> "%LOG%" echo === %~1 ===
exit /b 0

rem =========================== instalador gh (portatil, sem admin) ===========
:install_gh
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;$dest=Join-Path $env:LOCALAPPDATA 'HermesTools\gh';$bin=Join-Path $dest 'bin';try{$rel=Invoke-RestMethod 'https://api.github.com/repos/cli/cli/releases/latest' -Headers @{'User-Agent'='hermes-omniroute'};$asset=$rel.assets|Where-Object{$_.name -match 'windows_amd64\.zip$'}|Select-Object -First 1;if(-not $asset){throw 'no zip asset'};$zip=Join-Path $env:TEMP $asset.name;Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing;$tmp=Join-Path $env:TEMP ('ghx_'+[guid]::NewGuid().ToString('N'));Expand-Archive -Path $zip -DestinationPath $tmp -Force;$src=Get-ChildItem -Path $tmp -Recurse -Filter gh.exe|Select-Object -First 1;if(-not $src){throw 'gh.exe missing'};New-Item -ItemType Directory -Force -Path $bin|Out-Null;Copy-Item -Path (Join-Path $src.Directory.FullName '*') -Destination $bin -Recurse -Force;Write-Host ('GH_INSTALLED='+$bin)}catch{Write-Host ('GH_INSTALL_ERROR='+$_.Exception.Message);exit 5}" >>"%LOG%" 2>&1
exit /b 0

rem =========================== instalador gitleaks (portatil) ================
:install_gitleaks
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;$v='8.21.2';$dest=Join-Path $env:LOCALAPPDATA 'HermesTools\gitleaks';$bin=Join-Path $dest 'bin';try{$url='https://github.com/gitleaks/gitleaks/releases/download/v'+$v+'/gitleaks_'+$v+'_windows_x64.zip';$zip=Join-Path $env:TEMP ('gitleaks_'+$v+'.zip');Invoke-WebRequest $url -OutFile $zip -UseBasicParsing;$tmp=Join-Path $env:TEMP ('glx_'+[guid]::NewGuid().ToString('N'));Expand-Archive -Path $zip -DestinationPath $tmp -Force;$src=Get-ChildItem -Path $tmp -Recurse -Filter gitleaks.exe|Select-Object -First 1;if(-not $src){throw 'gitleaks.exe missing'};New-Item -ItemType Directory -Force -Path $bin|Out-Null;Copy-Item -Path $src.FullName -Destination $bin -Force;Write-Host ('GITLEAKS_INSTALLED='+$bin)}catch{Write-Host ('GITLEAKS_INSTALL_ERROR='+$_.Exception.Message);exit 5}" >>"%LOG%" 2>&1
exit /b 0

rem =========================== formatador de achados (redigido) =============
:write_secret_findings
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{if(Test-Path '%TMPJSON%'){$j=Get-Content -Raw '%TMPJSON%'|ConvertFrom-Json;$o=@('HERMES OMNIROUTE - SECRET FINDINGS (redigido)');$o+=($j|ForEach-Object{'{0}  {1}:{2}' -f $_.RuleID,$_.File,$_.StartLine});$o|Set-Content -Encoding ASCII '%PROJ%\HERMES-SECRET-FINDINGS.txt'}}catch{}" >>"%LOG%" 2>&1
exit /b 0
