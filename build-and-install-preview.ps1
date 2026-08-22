#Requires -Version 5.1
<#
  Hermes OmniRoute Studio — build de PREVIEW e instalacao
  Gerado pela auditoria independente. Seguro por construcao:
    - aborta se o repo nao for o esperado
    - aborta se o app estiver aberto
    - faz BACKUP dos dados do usuario antes de qualquer coisa
    - NAO toca no worktree (nao usa reset/clean/checkout/restore)
    - roda typecheck como portao minimo antes de empacotar
    - registra tudo em um log que a auditoria consegue ler depois

  Este e um build de PREVIEW, nao de release: o worktree tem 5 arquivos com
  poluicao de CRLF, entao install-stamp.json vai sair com "dirty": true.
  Isso e esperado aqui. Para release, limpe as quebras de linha antes.
#>

$ErrorActionPreference = 'Stop'
$repo = 'C:\Users\zodyp\Documents\Codex\Hermes-OmniRoute'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logDir = Join-Path $repo 'audit\_raw'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "build-install-$stamp.log"

function Say([string]$m, [string]$color = 'Gray') {
  $line = "[{0}] {1}" -f (Get-Date -Format 'HH:mm:ss'), $m
  Write-Host $line -ForegroundColor $color
  Add-Content -LiteralPath $log -Value $line
}
function Die([string]$m) { Say "ABORTADO: $m" 'Red'; Write-Host ''; Read-Host 'Enter para fechar'; exit 1 }

Say "log: $log" 'DarkGray'
Say '================ HERMES OMNIROUTE — BUILD DE PREVIEW ================' 'Cyan'

# ---------- 1. identidade ----------
if (-not (Test-Path -LiteralPath $repo)) { Die "checkout nao encontrado: $repo" }
Set-Location -LiteralPath $repo

$branch = (git branch --show-current) 2>&1
$head   = (git rev-parse HEAD) 2>&1
Say "branch : $branch"
Say "HEAD   : $head"
if ($branch -ne 'feature/hermes-omniroute-studio') { Die "branch inesperada: $branch" }

$dirtyCount = (git status --porcelain | Measure-Object -Line).Lines
Say "arquivos sujos no worktree: $dirtyCount  (build sairá com dirty:true — normal para preview)"
git status --short | Out-File -Append -LiteralPath $log -Encoding utf8

# ---------- 2. app precisa estar fechado ----------
$proc = Get-Process -Name 'HermesOmniRoute' -ErrorAction SilentlyContinue
if ($proc) { Die 'O Hermes OmniRoute Studio esta aberto. Feche o aplicativo e rode de novo.' }
Say 'app fechado — ok' 'Green'

# ---------- 3. backup dos dados do usuario ----------
$backup = Join-Path $env:USERPROFILE "hermes-backup-$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
Say "backup em: $backup" 'Yellow'
foreach ($pair in @(
    @{ src = Join-Path $env:USERPROFILE '.hermes';                 dst = 'hermes-home' },
    @{ src = Join-Path $env:APPDATA   'Hermes OmniRoute Studio';   dst = 'userData'    },
    @{ src = Join-Path $env:USERPROFILE '.omniroute';              dst = 'omniroute'   })) {
  if (Test-Path -LiteralPath $pair.src) {
    Copy-Item -LiteralPath $pair.src -Destination (Join-Path $backup $pair.dst) -Recurse -Force -ErrorAction SilentlyContinue
    Say ("  copiado: {0}" -f $pair.src)
  } else { Say ("  ausente (ok): {0}" -f $pair.src) 'DarkGray' }
}
$backupItems = (Get-ChildItem -LiteralPath $backup | Measure-Object).Count
if ($backupItems -eq 0) { Die 'backup ficou vazio — nao vou prosseguir sem rede de seguranca' }
Say "backup com $backupItems item(ns) — ok" 'Green'

# ---------- 4. portao minimo: typecheck ----------
Say 'rodando typecheck (portao minimo — pode levar alguns minutos)...' 'Cyan'
& npm run --prefix apps/desktop typecheck 2>&1 | Tee-Object -Append -LiteralPath $log
if ($LASTEXITCODE -ne 0) { Die "typecheck falhou (exit $LASTEXITCODE). Veja o log: $log" }
Say 'typecheck PASSOU' 'Green'

# ---------- 5. build + NSIS ----------
Say 'empacotando (npm run dist:win:nsis) — isto demora, pode ir tomar um cafe...' 'Cyan'
& npm run --prefix apps/desktop dist:win:nsis 2>&1 | Tee-Object -Append -LiteralPath $log
if ($LASTEXITCODE -ne 0) { Die "build falhou (exit $LASTEXITCODE). Veja o log: $log" }
Say 'build CONCLUIDO' 'Green'

# ---------- 6. evidencia do artefato ----------
$installer = Get-ChildItem -LiteralPath (Join-Path $repo 'apps\desktop\release') -Filter '*.exe' |
             Where-Object { $_.Name -notlike '*Uninstall*' } |
             Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $installer) { Die 'instalador nao encontrado em apps\desktop\release' }

$hash = (Get-FileHash -LiteralPath $installer.FullName -Algorithm SHA256).Hash
Say '---------------- ARTEFATO ----------------' 'Cyan'
Say "arquivo : $($installer.Name)"
Say "tamanho : $([math]::Round($installer.Length/1MB,1)) MB"
Say "sha256  : $hash"
$stampFile = Join-Path $repo 'apps\desktop\release\win-unpacked\resources\install-stamp.json'
if (Test-Path -LiteralPath $stampFile) {
  Say 'install-stamp.json do build:'
  Get-Content -LiteralPath $stampFile | ForEach-Object { Say "  $_" }
}

# ---------- 7. instalacao ----------
Say 'instalando (silencioso)...' 'Cyan'
$p = Start-Process -FilePath $installer.FullName -ArgumentList '/S' -Wait -PassThru
Say "instalador saiu com codigo $($p.ExitCode)"
if ($p.ExitCode -ne 0) { Die "instalacao falhou (exit $($p.ExitCode)). Backup intacto em $backup" }

# ---------- 8. verificacao pos-instalacao ----------
$installed = Join-Path $env:LOCALAPPDATA 'Programs\HermesOmniRoute'
$exe = Join-Path $installed 'HermesOmniRoute.exe'
Say '---------------- INSTALADO ----------------' 'Cyan'
if (Test-Path -LiteralPath $exe) {
  Say "exe     : $exe"
  Say "sha256  : $((Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash)"
  $st = Join-Path $installed 'resources\install-stamp.json'
  if (Test-Path -LiteralPath $st) { Get-Content -LiteralPath $st | ForEach-Object { Say "  $_" } }
  Say 'paridade dos componentes gerenciados (build x instalado):'
  foreach ($n in @('omniroute-mcp-bridge.mjs','omniroute-mcp-policy.mjs','omniroute-daily-health.py')) {
    $a = Join-Path $repo "apps\desktop\release\win-unpacked\resources\$n"
    $b = Join-Path $installed "resources\$n"
    if ((Test-Path $a) -and (Test-Path $b)) {
      $ha = (Get-FileHash $a -Algorithm SHA256).Hash; $hb = (Get-FileHash $b -Algorithm SHA256).Hash
      Say ("  {0,-32} {1}" -f $n, $(if ($ha -eq $hb) { 'IGUAL' } else { '** DIVERGENTE **' }))
    }
  }
} else { Die "app nao encontrado apos instalar: $exe" }

Say '' 
Say 'PRONTO. Abra o Hermes OmniRoute Studio e veja como ficou.' 'Green'
Say "backup do seu estado anterior: $backup" 'Yellow'
Say "log completo: $log" 'DarkGray'
Write-Host ''
Read-Host 'Enter para fechar'
