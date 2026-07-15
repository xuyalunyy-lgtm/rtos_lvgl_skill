# Install FreeRTOS Skill to ~/.cursor/skills/
# Usage: .\scripts\install_skill.ps1

param(
    [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path $env:USERPROFILE ".cursor\skills\freertos-embedded-architect"),
    [switch]$SkipEnvInstall
)

$ExcludeDirs = @(
    ".git", ".github", ".vscode", ".claude", ".codex", "fw-AC79_AIoT_SDK", "bk_idk-release-v2.2.1", "__pycache__",
    ".mypy_cache", ".pytest_cache", "node_modules", "freertos-skill-lite", "archive", "artifacts", "forward_tests", "out",
    ".skill_metrics", ".skill_evidence"
)
$ExcludeDirs += Get-ChildItem -LiteralPath $Source -Directory -Filter ".tmp_*" -ErrorAction SilentlyContinue | ForEach-Object FullName
$ExcludeDirs += Join-Path $Source "runtime\toolchain\win-x64"
$RootOnlyExcludeFiles = @("README.md", "INSTALL.md", "CHANGELOG.md")

if (-not (Test-Path (Join-Path $Source "SKILL.md"))) {
    Write-Error "SKILL.md not found. Run from skill repo root or pass -Source."
    exit 1
}

# The skill has no bundled service dependency.

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
foreach ($f in $RootOnlyExcludeFiles) {
    Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Dest $f)
}

$skillText = [System.IO.File]::ReadAllText((Join-Path $Dest "SKILL.md"), [System.Text.UTF8Encoding]::new($false))
if ($skillText -match '(?m)^version:\s*([^\s#]+)') {
    $ver = $Matches[1].Trim()
} elseif ($skillText -match '(?ms)^metadata:\s*\r?\n(?:[ \t]+[^\r\n]*\r?\n)*?[ \t]+version:\s*([^\s#]+)') {
    $ver = $Matches[1].Trim()
} else {
    $ver = "unknown"
}

Write-Host "Installed: $Dest"
Write-Host "Version: $ver"
Write-Host "Restart Cursor or open a new Agent chat."
