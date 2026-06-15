# Install FreeRTOS Skill to ~/.cursor/skills/
# Usage: .\scripts\install_skill.ps1

param(
    [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path $env:USERPROFILE ".cursor\skills\freertos-embedded-architect")
)

$ExcludeDirs = @(".git", "fw-AC79_AIoT_SDK", "__pycache__", ".pytest_cache", "node_modules")

if (-not (Test-Path (Join-Path $Source "SKILL.md"))) {
    Write-Error "SKILL.md not found. Run from skill repo root or pass -Source."
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $Dest -Parent) | Out-Null
if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
}

$robocopyArgs = @($Source, $Dest, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np")
foreach ($d in $ExcludeDirs) {
    $robocopyArgs += "/XD"
    $robocopyArgs += $d
}

& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Error "robocopy failed (exit $LASTEXITCODE)"
    exit 1
}

$verLine = Select-String -Path (Join-Path $Dest "SKILL.md") -Pattern "^version:" | Select-Object -First 1
$ver = if ($verLine) { $verLine.Line -replace "version:\s*", "" } else { "unknown" }

Write-Host "Installed: $Dest"
Write-Host "Version: $ver"
Write-Host "Restart Cursor or open a new Agent chat."
