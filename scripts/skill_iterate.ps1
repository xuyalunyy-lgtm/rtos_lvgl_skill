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
$LiteSkill = Join-Path $Root "freertos-skill-lite\SKILL.md"
$Changelog = Join-Path $Root "CHANGELOG.md"
$IterationLog = Join-Path $Root "references\iteration_log.md"
$SyncLitePs1 = Join-Path $Root "scripts\sync_lite.ps1"
$Utf8 = [System.Text.UTF8Encoding]::new($false)

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, $Utf8)
}

function Get-SkillVersion([string]$Path) {
    if (-not (Test-Path $Path)) { return $null }
    $text = Read-Utf8 $Path
    if ($text -match '(?m)^version:\s*([^\s#]+)') { return $Matches[1].Trim() }
    if ($text -match '(?ms)^metadata:\s*\r?\n(?:[ \t]+[^\r\n]*\r?\n)*?[ \t]+version:\s*([^\s#]+)') { return $Matches[1].Trim() }
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
    $env:PYTHONIOENCODING = "utf-8"
    $proc = Start-Process -FilePath $PythonExe -ArgumentList $PyArgs -WorkingDirectory $Root -Wait -PassThru -NoNewWindow
    if ($proc.ExitCode -ne 0) {
        [void]$Errors.Value.Add("$Label failed (exit $($proc.ExitCode))")
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
    Invoke-PythonCheck -PythonExe $python -Label "[1/6] tools/run_review.py --self-test" `
        -PyArgs @((Join-Path $Root "tools\run_review.py"), "--self-test") `
        -Errors ([ref]$errors)
}

Invoke-PythonCheck -PythonExe $python -Label "[2/6] tools/run_review.py --validate-examples" `
    -PyArgs @((Join-Path $Root "tools\run_review.py"), "--validate-examples") `
    -Errors ([ref]$errors)

Write-Host "`n[3/6] SKILL.md version"
$fullVer = Get-SkillVersion $Skill
$liteVer = Get-SkillVersion $LiteSkill
if (-not $fullVer) {
    $errors.Add("SKILL.md missing metadata.version field")
}
else {
    Write-Host "  full: $fullVer"
}
if ($liteVer) {
    Write-Host "  lite: $liteVer"
    if ($fullVer -and $liteVer -ne $fullVer) {
        $errors.Add("version mismatch: full $fullVer vs lite $liteVer (run sync_lite.ps1)")
    }
}
else {
    $errors.Add("freertos-skill-lite/SKILL.md missing or no metadata.version")
}

Write-Host "`n[4/6] CHANGELOG / iteration_log"
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

Write-Host "`n[5/6] sync_lite.ps1 -DryRun"
if (-not (Test-Path $SyncLitePs1)) {
    $errors.Add("missing scripts/sync_lite.ps1")
}
else {
    & $SyncLitePs1 -DryRun
    if ($LASTEXITCODE -ne 0) { $errors.Add("sync_lite.ps1 -DryRun failed") }
}

Write-Host "`n[6/6] optional sync_lite.ps1"
if ($Sync -and $errors.Count -eq 0) {
    & $SyncLitePs1
    if ($LASTEXITCODE -ne 0) {
        $errors.Add("sync_lite.ps1 failed")
    }
    else {
        $liteVer2 = Get-SkillVersion $LiteSkill
        if ($fullVer -and $liteVer2 -ne $fullVer) {
            $errors.Add("after sync, lite version still differs from full")
        }
    }
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
