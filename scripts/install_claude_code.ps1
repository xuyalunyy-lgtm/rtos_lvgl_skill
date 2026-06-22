# Install FreeRTOS Skill for Claude Code → ~/.claude/skills/
# Usage: .\scripts\install_claude_code.ps1
# Optional: .\scripts\install_claude_code.ps1 -ProjectRoot C:\firmware  (copy CLAUDE template)

param(
    [string]$Source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dest = (Join-Path $env:USERPROFILE ".claude\skills\freertos-embedded-architect"),
    [string]$ProjectRoot = ""
)

$ExcludeDirs = @(
    ".git", ".github", ".vscode", "fw-AC79_AIoT_SDK", "bk_idk-release-v2.2.1", "__pycache__",
    ".pytest_cache", "node_modules", "freertos-skill-lite"
)
$RootOnlyExcludeFiles = @("README.md", "INSTALL.md", "CHANGELOG.md")

if (-not (Test-Path (Join-Path $Source "SKILL.md"))) {
    Write-Error "SKILL.md not found. Run from skill repo root."
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

Write-Host "Claude Code skill installed: $Dest"
Write-Host "Version: $ver"
Write-Host "Invoke: /freertos-embedded-architect"
Write-Host "Token guide: references/claude_code.md"

if ($ProjectRoot -and (Test-Path $ProjectRoot)) {
    $claudeTpl = Join-Path $Source "templates\CLAUDE.embedded.md"
    $ignoreTpl = Join-Path $Source "templates\claudeignore.embedded"
    $claudeDst = Join-Path $ProjectRoot "CLAUDE.md"
    $ignoreDst = Join-Path $ProjectRoot ".claudeignore"

    if (-not (Test-Path $claudeDst)) {
        Copy-Item $claudeTpl $claudeDst
        Write-Host "Created: $claudeDst (edit compile command)"
    } else {
        Write-Host "Skip CLAUDE.md (exists): $claudeDst"
    }
    if (-not (Test-Path $ignoreDst)) {
        Copy-Item $ignoreTpl $ignoreDst
        Write-Host "Created: $ignoreDst"
    } else {
        Write-Host "Skip .claudeignore (exists): $ignoreDst"
    }
}

Write-Host "Restart Claude Code to discover skill."
