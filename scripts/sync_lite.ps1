# Sync full skill -> freertos-skill-lite (native PowerShell, no Python required)
# Usage: .\scripts\sync_lite.ps1 [-DryRun] [-SkillOnly]

param(
    [switch]$DryRun,
    [switch]$SkillOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Lite = Join-Path $Root "freertos-skill-lite"
$SyncDirs = @("prompts", "platforms", "workflows", "references")
$PatchDir = Join-Path $Root "scripts\lite_patches"
$PatternDir = Join-Path $PatchDir "patterns"
$SkillSrc = Join-Path $Root "SKILL.md"
$SkillLiteBody = Join-Path $Root "scripts\skill_lite_body.md"
$SkillLiteDst = Join-Path $Lite "SKILL.md"

# UTF-8 literals (avoid PS 5.1 script-encoding mojibake)
$Utf8 = [System.Text.UTF8Encoding]::new($false)
$LiteExamplePrefix = $Utf8.GetString([byte[]](0xE5, 0xAE, 0x8C, 0xE6, 0x95, 0xB4, 0xE7, 0x89, 0x88))  # 完整版

function Patch-LiteExamples([string]$Content) {
    return [regex]::Replace($Content, '\[([^\]]+)\]\(\.\./examples/([^)]+)\)', {
        param($m)
        "$LiteExamplePrefix ``examples/$($m.Groups[2].Value)``"
    })
}

function Read-Utf8([string]$Path) {
    return [System.IO.File]::ReadAllText($Path, $Utf8)
}

function Write-Utf8([string]$Path, [string]$Content) {
    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    [System.IO.File]::WriteAllText($Path, $Content, $Utf8)
}

function Get-Frontmatter([string]$Path) {
    $text = Read-Utf8 $Path
    if (-not $text.StartsWith("---")) { throw "$Path missing YAML frontmatter" }
    $parts = $text -split "---", 3
    if ($parts.Count -lt 3) { throw "$Path frontmatter format error" }
    return "---$($parts[1])---`n"
}

function Read-Patch([string]$Name) {
    $path = Join-Path $PatchDir $Name
    if (-not (Test-Path $path)) { throw "Missing patch file: $path" }
    return (Read-Utf8 $path).TrimEnd()
}

function Read-Pattern([string]$Name) {
    $path = Join-Path $PatternDir $Name
    if (-not (Test-Path $path)) { throw "Missing pattern file: $path" }
    return (Read-Utf8 $path).TrimEnd()
}

function Patch-LiteWorkflow([string]$Content, [string]$FileName) {
    $rules = @{
        "l3_new_module.md"  = @{ Pattern = "l3_new_module.txt";  Patch = "l3_new_module_step3.md" }
        "debug_crash.md"    = @{ Pattern = "debug_crash.txt";    Patch = "debug_crash_step3.md" }
        "self_iterate.md"   = @{ Pattern = "self_iterate.txt";   Patch = "self_iterate_step4.md" }
        "l2_code_review.md" = @{ Pattern = "l2_code_review.txt"; Patch = "l2_code_review_step3.md" }
    }

    if ($rules.ContainsKey($FileName)) {
        $rule = $rules[$FileName]
        $pattern = Read-Pattern $rule.Pattern
        $repl = Read-Patch $rule.Patch
        if (-not [regex]::IsMatch($Content, $pattern)) {
            Write-Warning "Workflow patch skipped (no match): $FileName"
        }
        else {
            $Content = [regex]::Replace($Content, $pattern, $repl + "`n", 1)
        }
    }
    return $Content
}

function Sync-Tree([string]$SrcDir, [string]$DstDir, [string]$DirName) {
    $actions = New-Object System.Collections.Generic.List[string]
    if (-not (Test-Path $SrcDir)) { throw "Source directory not found: $SrcDir" }

    if (-not $DryRun -and -not (Test-Path $DstDir)) {
        New-Item -ItemType Directory -Force -Path $DstDir | Out-Null
    }

    $fresh = New-Object System.Collections.Generic.HashSet[string]
    foreach ($src in (Get-ChildItem -Path $SrcDir -Recurse -File)) {
        $rel = $src.FullName.Substring($SrcDir.Length).TrimStart('\', '/').Replace('\', '/')
        [void]$fresh.Add($rel)
        $dst = Join-Path $DstDir $rel
        $ext = [System.IO.Path]::GetExtension($src.Name).ToLowerInvariant()

        if ($ext -in @(".md", ".txt")) {
            $text = Read-Utf8 $src.FullName
            $patched = Patch-LiteExamples $text
            if ($DirName -eq "workflows") {
                $patched = Patch-LiteWorkflow $patched $src.Name
            }
            $actions.Add("PATCH+COPY ${DirName}/${rel}")
            if (-not $DryRun) { Write-Utf8 $dst $patched }
        }
        else {
            $actions.Add("COPY ${DirName}/${rel}")
            if (-not $DryRun) {
                $parent = Split-Path $dst -Parent
                if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
                Copy-Item -Force $src.FullName $dst
            }
        }
    }

    if (Test-Path $DstDir) {
        foreach ($dst in (Get-ChildItem -Path $DstDir -Recurse -File)) {
            $rel = $dst.FullName.Substring($DstDir.Length).TrimStart('\', '/').Replace('\', '/')
            if (-not $fresh.Contains($rel)) {
                $actions.Add("DELETE stale ${DirName}/${rel}")
                if (-not $DryRun) { Remove-Item -Force $dst.FullName }
            }
        }
    }
    return $actions
}

if (-not (Test-Path $Lite)) { throw "Lite directory not found: $Lite" }

$total = 0
Write-Host "`n=== SKILL.md -> freertos-skill-lite/SKILL.md ==="
if (-not (Test-Path $SkillLiteBody)) { throw "Missing template: $SkillLiteBody" }
if (-not (Test-Path $SkillSrc)) { throw "Missing: $SkillSrc" }

$content = (Get-Frontmatter $SkillSrc) + (Read-Utf8 $SkillLiteBody)
Write-Host "  GENERATE freertos-skill-lite/SKILL.md"
if (-not $DryRun) { Write-Utf8 $SkillLiteDst $content }
$total++

if (-not $SkillOnly) {
    foreach ($name in $SyncDirs) {
        $src = Join-Path $Root $name
        $dst = Join-Path $Lite $name
        Write-Host "`n=== ${name}/ -> freertos-skill-lite/${name}/ ==="
        try {
            $actions = Sync-Tree $src $dst $name
            foreach ($line in $actions) { Write-Host "  $line" }
            $total += $actions.Count
        }
        catch { Write-Host "  skip: $_" }
    }
}

$mode = if ($DryRun) { " (dry-run)" } else { "" }
Write-Host "`nDone${mode}, total $total items."
