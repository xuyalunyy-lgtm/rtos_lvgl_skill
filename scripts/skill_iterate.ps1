# Skill self-iteration validation loop (native PowerShell; Python checks optional)
# Usage:
#   .\scripts\skill_iterate.ps1              # -Check (default)
#   .\scripts\skill_iterate.ps1 -Sync
#   .\scripts\skill_iterate.ps1 -SkipSelfTest

param(
    [switch]$Check,
    [switch]$Sync,
    [switch]$SkipSelfTest
)

$ErrorActionPreference = "Continue"
if (-not $Check -and -not $Sync) { $Check = $true }

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Skill = Join-Path $Root "SKILL.md"
$Pyproject = Join-Path $Root "pyproject.toml"
$LiteRoot = Join-Path $Root "freertos-skill-lite"
$LiteSkill = Join-Path $LiteRoot "SKILL.md"
$Changelog = Join-Path $Root "CHANGELOG.md"
$IterationLog = Join-Path $Root "references\iteration_log.md"
$SyncLitePs1 = Join-Path $Root "scripts\sync_lite.ps1"
$Utf8 = [System.Text.UTF8Encoding]::new($false)

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, $Utf8)
}

function Get-ProjectVersion([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    $text = Read-Utf8 $Path
    if ($text -match '(?m)^version\s*=\s*"([^"]+)"') { return $Matches[1] }
    return $null
}

function Resolve-PythonExe {
    $names = @("python", "python3", "py")
    foreach ($name in $names) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $src = $cmd.Source
        if ($src -match 'WindowsApps') { continue }
        try {
            $out = & $src --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $out -match 'Python') { return $src }
        }
        catch { }
    }

    $roots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "$env:ProgramFiles\Python*",
        "${env:ProgramFiles(x86)}\Python*"
    )
    foreach ($pattern in $roots) {
        Get-ChildItem -Path $pattern -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty FullName |
            ForEach-Object {
                try {
                    $out = & $_ --version 2>&1
                    if ($LASTEXITCODE -eq 0) { return $_ }
                }
                catch { }
            }
    }
    return $null
}

function Invoke-PythonCheck {
    param(
        [string]$PythonExe,
        [string]$Label,
        [string[]]$PyArgs,
        [ref]$Errors
    )
    Write-Host "`n$Label"
    if (-not $PythonExe) {
        $msg = "$Label skipped (Python not found)"
        Write-Host "  $msg"
        return
    }
    Write-Host "  $PythonExe $($PyArgs -join ' ')"
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Push-Location $Root
    try {
        & $PythonExe @PyArgs
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($exitCode -ne 0) {
        [void]$Errors.Value.Add("$Label failed (exit $exitCode)")
    }
}

$errors = New-Object System.Collections.Generic.List[string]

Write-Host ("=" * 60)
Write-Host "Skill self-iteration validation (PowerShell)"
Write-Host ("=" * 60)

$python = Resolve-PythonExe
if ($python) {
    Write-Host "`nPython: $python"
}
else {
    Write-Host "`nPython: not found — metadata + sync_lite.ps1 only; checker steps skipped"
    Write-Host "  Install: https://www.python.org/downloads/ (check 'Add to PATH')"
}

if (-not $SkipSelfTest) {
    Invoke-PythonCheck -PythonExe $python -Label "[1/9] tools/run_review.py --self-test" `
        -PyArgs @((Join-Path $Root "tools\run_review.py"), "--self-test") `
        -Errors ([ref]$errors)
}

Invoke-PythonCheck -PythonExe $python -Label "[2/9] tools/run_review.py --validate-examples" `
    -PyArgs @((Join-Path $Root "tools\run_review.py"), "--validate-examples") `
    -Errors ([ref]$errors)

Invoke-PythonCheck -PythonExe $python -Label "[3/9] tools/run_review.py --list-checkers" `
    -PyArgs @((Join-Path $Root "tools\run_review.py"), "--list-checkers") `
    -Errors ([ref]$errors)

Invoke-PythonCheck -PythonExe $python -Label "[4/9] scripts/check_runtime_distribution.py" `
    -PyArgs @((Join-Path $Root "scripts\check_runtime_distribution.py")) `
    -Errors ([ref]$errors)

Invoke-PythonCheck -PythonExe $python -Label "[5/9] scripts/check_skill_metadata.py" `
    -PyArgs @((Join-Path $Root "scripts\check_skill_metadata.py")) `
    -Errors ([ref]$errors)
Invoke-PythonCheck -PythonExe $python -Label "      scripts/check_skill_metadata.py --self-test" `
    -PyArgs @((Join-Path $Root "scripts\check_skill_metadata.py"), "--self-test") `
    -Errors ([ref]$errors)

Write-Host "`n[6/9] package version"
$fullVer = Get-ProjectVersion $Pyproject
if (-not $fullVer) {
    $errors.Add("pyproject.toml missing [project].version")
}
else {
    Write-Host "  project: $fullVer"
}

Write-Host "`n[7/9] CHANGELOG / iteration_log"
if (-not (Test-Path $Changelog)) {
    $errors.Add("missing CHANGELOG.md")
}
elseif ($fullVer) {
    $head = (Read-Utf8 $Changelog).Substring(0, [Math]::Min(800, (Read-Utf8 $Changelog).Length))
    if ($head -notmatch [regex]::Escape($fullVer)) {
        $errors.Add("CHANGELOG.md does not mention version $fullVer")
    }
    else { Write-Host "  CHANGELOG.md OK" }
}
if (-not (Test-Path $IterationLog)) {
    $errors.Add("missing references/iteration_log.md")
}
else { Write-Host "  iteration_log.md OK" }

Write-Host "`n[8/9] sync_lite.ps1 -DryRun"
if (-not (Test-Path $SyncLitePs1)) {
    $errors.Add("missing scripts/sync_lite.ps1")
}
else {
    & $SyncLitePs1 -DryRun
    if ($LASTEXITCODE -ne 0) { $errors.Add("sync_lite.ps1 -DryRun failed") }
}

Write-Host "`n[9/9] optional sync_lite.ps1"
if ($Sync -and $errors.Count -eq 0 -and (Test-Path $LiteRoot)) {
    & $SyncLitePs1
    if ($LASTEXITCODE -ne 0) {
        $errors.Add("sync_lite.ps1 failed")
    }
}
elseif ($Sync -and -not (Test-Path $LiteRoot)) {
    Write-Host "  skip sync (freertos-skill-lite absent)"
}
elseif ($Sync) {
    Write-Host "  skip sync (prior errors)"
}

Write-Host "`n$("=" * 60)"
if ($errors.Count -gt 0) {
    Write-Host "Validation failed:"
    foreach ($e in $errors) { Write-Host "  - $e" }
    Write-Host ("=" * 60)
    if (-not $python) {
        Write-Host "Tip: install Python 3.8+ for checker steps, or rely on GitHub Actions CI."
    }
    exit 1
}

Write-Host "Validation passed. Confirm iteration_log.md records this change."
if (-not $python) {
    Write-Host "Note: checker steps skipped (no Python). CI will run full validation on push."
}
Write-Host ("=" * 60)
exit 0
