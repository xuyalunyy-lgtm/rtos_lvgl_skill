# bk_build.ps1 — BK (Beken Armino) 编译/清理脚本 (Windows)
#
# 放置位置：与 SDK 同级目录，例如：
#   C:\armino\
#   ├── bk_avdk_smp\           ← SDK
#   ├── bk_solution_ai\        ← 可选方案仓
#   └── bk_build.ps1           ← 本脚本
#
# 用法：
#   .\bk_build.ps1 build
#   .\bk_build.ps1 clean
#   .\bk_build.ps1 rebuild
#   .\bk_build.ps1 build -Project bk_solution_ai\projects\beken_genie
#   .\bk_build.ps1 build -Soc bk7258 -Project lvgl\widgets
#
# 可选配置文件：同级 bk_build.env.ps1
#   $env:BK_SDK_DIR = "C:\armino\bk_avdk_smp"
#   $env:BK_PROJECT_DIR = "C:\armino\bk_solution_ai\projects\beken_genie"

param(
    [Parameter(Position = 0)]
    [ValidateSet("build", "clean", "rebuild")]
    [string]$Action = "build",

    [Alias("p")]
    [string]$Project = "",

    [Alias("s")]
    [string]$Soc = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SocDefault = "bk7258"

# 加载可选配置
$EnvFile = Join-Path $ScriptDir "bk_build.env.ps1"
if (Test-Path $EnvFile) {
    . $EnvFile
}

function Log($msg) { Write-Host "[bk_build] $msg" }
function Die($msg) { Write-Error "[bk_build] $msg"; exit 1 }

function Resolve-WorkspacePath([string]$p) {
    if ([System.IO.Path]::IsPathRooted($p)) { return $p }
    return Join-Path $ScriptDir $p
}

function Find-SdkDir {
    if ($env:BK_SDK_DIR -and (Test-Path (Join-Path $env:BK_SDK_DIR "Makefile"))) {
        return (Resolve-WorkspacePath $env:BK_SDK_DIR)
    }
    foreach ($c in @("bk_avdk_smp", "bk_avdk", "armino\bk_avdk_smp", "armino\bk_avdk")) {
        $abs = Resolve-WorkspacePath $c
        if (Test-Path (Join-Path $abs "Makefile")) { return $abs }
    }
    Die "未找到 SDK。请设置 `$env:BK_SDK_DIR 或将 bk_avdk_smp 放在与脚本同级目录。"
}

function Get-SdkInternalProjectRel([string]$ProjAbs, [string]$SdkAbs) {
    $sdkNorm = $SdkAbs.TrimEnd('\', '/')
    $projNorm = $ProjAbs.TrimEnd('\', '/')
    if (-not $projNorm.StartsWith($sdkNorm, [StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }
    $rel = $projNorm.Substring($sdkNorm.Length).TrimStart('\', '/')
    if ($rel -match "^projects\\(.+)$" -or $rel -match "^projects/(.+)$") {
        return ($rel -replace "^projects[/\\]", "") -replace "\\", "/"
    }
    return $null
}

function Detect-ProjectMode([string]$SdkDir) {
    $proj = ""

    if ($Project) {
        $proj = Resolve-WorkspacePath $Project
    }
    elseif ($env:BK_PROJECT_DIR) {
        $proj = Resolve-WorkspacePath $env:BK_PROJECT_DIR
    }
    elseif ($env:BK_PROJECT) {
        return @{ Mode = "SDK_INTERNAL"; Value = ($env:BK_PROJECT -replace "\\", "/") }
    }
    elseif (Test-Path (Join-Path $PWD "Makefile")) {
        $proj = $PWD.Path
    }

    if (-not $proj) {
        Die "未指定工程。使用 -Project <path> 或设置 BK_PROJECT_DIR / BK_PROJECT，或在工程目录内执行。"
    }

    if (-not (Test-Path (Join-Path $proj "Makefile"))) {
        Die "工程目录无 Makefile: $proj"
    }

    $internal = Get-SdkInternalProjectRel $proj $SdkDir
    if ($internal) {
        return @{ Mode = "SDK_INTERNAL"; Value = $internal }
    }
    return @{ Mode = "EXTERNAL"; Value = $proj }
}

function Invoke-BkMake {
    param(
        [string]$TargetCmd,   # build | clean
        [string]$SdkDir,
        [hashtable]$ProjectMode,
        [string]$SocName
    )

    if ($ProjectMode.Mode -eq "SDK_INTERNAL") {
        $projRel = $ProjectMode.Value
        Log "模式: SDK 内工程"
        Log "SDK_DIR=$SdkDir"
        Log "PROJECT=$projRel"
        Log "SOC=$SocName"
        Push-Location $SdkDir
        try {
            if ($TargetCmd -eq "clean") {
                & make clean $SocName "PROJECT=$projRel"
            } else {
                & make $SocName "PROJECT=$projRel"
            }
            if ($LASTEXITCODE -ne 0) { Die "make 失败，exit=$LASTEXITCODE" }
        } finally {
            Pop-Location
        }
    }
    else {
        $projDir = $ProjectMode.Value
        Log "模式: 方案仓 / 外部工程"
        Log "SDK_DIR=$SdkDir"
        Log "PROJECT_DIR=$projDir"
        Log "SOC=$SocName"

        $dbuild = Join-Path $projDir "dbuild.ps1"
        Push-Location $projDir
        try {
            $env:SDK_DIR = $SdkDir
            if (Test-Path $dbuild) {
                Log "使用 dbuild.ps1 (Docker/Windows 推荐)"
                if ($TargetCmd -eq "clean") {
                    & $dbuild make clean $SocName
                } else {
                    & $dbuild make $SocName
                }
            }
            else {
                Log "使用本地 make (需 WSL/Git Bash 等)"
                if ($TargetCmd -eq "clean") {
                    & make clean $SocName
                } else {
                    & make $SocName
                }
            }
            if ($LASTEXITCODE -ne 0) { Die "编译/清理失败，exit=$LASTEXITCODE" }
        } finally {
            Pop-Location
        }
    }
}

function Show-ArtifactHint([string]$SdkDir, [hashtable]$ProjectMode, [string]$SocName) {
    Log "编译完成。固件路径请查看工程 build/ 目录，常见："
    if ($ProjectMode.Mode -eq "EXTERNAL") {
        Log "  $($ProjectMode.Value)\build\$SocName\*\package\all-app.bin"
    } else {
        Log "  $SdkDir\build\$SocName\...\package\  (依 SDK 版本可能略有差异)"
    }
}

# ── 主流程 ───────────────────────────────────────────────
$SocName = if ($Soc) { $Soc } elseif ($env:BK_SOC) { $env:BK_SOC } else { $SocDefault }
$SdkDir = Find-SdkDir
$ProjectMode = Detect-ProjectMode $SdkDir

switch ($Action) {
    "clean" {
        Invoke-BkMake -TargetCmd clean -SdkDir $SdkDir -ProjectMode $ProjectMode -SocName $SocName
    }
    "build" {
        Invoke-BkMake -TargetCmd build -SdkDir $SdkDir -ProjectMode $ProjectMode -SocName $SocName
        Show-ArtifactHint $SdkDir $ProjectMode $SocName
    }
    "rebuild" {
        Invoke-BkMake -TargetCmd clean -SdkDir $SdkDir -ProjectMode $ProjectMode -SocName $SocName
        Invoke-BkMake -TargetCmd build -SdkDir $SdkDir -ProjectMode $ProjectMode -SocName $SocName
        Show-ArtifactHint $SdkDir $ProjectMode $SocName
    }
}

Log "完成: $Action"
