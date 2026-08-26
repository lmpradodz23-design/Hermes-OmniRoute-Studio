<#
  native-runner.ps1 - robust native-command runner for Windows PowerShell 5.1.

  WHY: In Windows PowerShell 5.1, with $ErrorActionPreference = 'Stop', a native
  process that writes ANYTHING to stderr (even a benign warning, e.g. npm's
  "Unknown project config") is turned into a NativeCommandError terminating
  error, aborting the script - regardless of the real exit code. That is a
  harness defect, not a product failure.

  CONTRACT of Invoke-NativeCommand:
    * Runs an .exe/.cmd/.bat correctly on Windows (and cross-platform).
    * Captures stdout AND stderr; writes both to the console and (optionally) a log.
    * NEVER aborts just because stderr received text.
    * Uses the REAL process exit code as the sole authority.
    * Only exitCode != 0 fails; returns the exit code as an [int].
    * A process that cannot even be launched returns 127.
    * Pure ASCII; PowerShell 5.1 and 7 compatible.
#>

function Invoke-NativeCommand {
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$File,
    [string[]]$Arguments = @(),
    [string]$WorkingDirectory,
    [string]$LogPath,
    [switch]$Quiet
  )

  $prevEAP = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'   # 5.1: native stderr must NOT throw
  $prevLoc = $null
  if ($WorkingDirectory) { $prevLoc = (Get-Location).Path; Set-Location -LiteralPath $WorkingDirectory }

  $global:LASTEXITCODE = 0
  $output = @()
  $code = $null
  try {
    # 2>&1 folds stderr into the output stream as records; capture everything.
    $output = & $File @Arguments 2>&1
    $code = $LASTEXITCODE
  }
  catch {
    # A genuine launch failure (command not found / cannot start), NOT a stderr line.
    $output = @('LAUNCH-ERROR: ' + $_.Exception.Message)
    $code = 127
  }
  finally {
    if ($prevLoc) { Set-Location -LiteralPath $prevLoc }
    $ErrorActionPreference = $prevEAP
  }

  foreach ($rec in $output) {
    if ($rec -is [System.Management.Automation.ErrorRecord]) {
      $line = [string]$rec.Exception.Message
    }
    else {
      $line = [string]$rec
    }
    if (-not $Quiet) { Write-Host $line }
    if ($LogPath) { Add-Content -Path $LogPath -Value $line }
  }

  if ($null -eq $code) { $code = 0 }  # some wrappers do not set LASTEXITCODE
  return [int]$code
}

function Invoke-NativeCapture {
  <#
    Like Invoke-NativeCommand, but RETURNS the trimmed STDOUT text - for reading
    a value (e.g. `git rev-parse HEAD`). stderr is captured to the log (never
    thrown); an empty string means no stdout (or launch failure).
  #>
  [CmdletBinding()]
  param(
    [Parameter(Mandatory = $true)][string]$File,
    [string[]]$Arguments = @(),
    [string]$WorkingDirectory,
    [string]$LogPath
  )

  $prevEAP = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $prevLoc = $null
  if ($WorkingDirectory) { $prevLoc = (Get-Location).Path; Set-Location -LiteralPath $WorkingDirectory }

  $global:LASTEXITCODE = 0
  $out = @()
  try { $out = & $File @Arguments 2>&1 }
  catch { $out = @() }
  finally {
    if ($prevLoc) { Set-Location -LiteralPath $prevLoc }
    $ErrorActionPreference = $prevEAP
  }

  $stdout = @()
  foreach ($rec in $out) {
    if ($rec -is [System.Management.Automation.ErrorRecord]) {
      if ($LogPath) { Add-Content -Path $LogPath -Value ([string]$rec.Exception.Message) }
    }
    else {
      $stdout += [string]$rec
    }
  }
  return (($stdout -join "`n").Trim())
}
