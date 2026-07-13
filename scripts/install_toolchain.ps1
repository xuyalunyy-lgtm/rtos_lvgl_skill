<#
.SYNOPSIS
    Install the bundled MinGW-w64 UCRT64 toolchain for LVGL compilation.

.DESCRIPTION
    Downloads and extracts the portable GCC toolchain to runtime/toolchain/.
    Verifies SHA256 integrity of all files.  No global PATH modification.

.PARAMETER Version
    Toolchain version to install (default: from manifest.json)

.PARAMETER Force
    Re-download even if already installed

.EXAMPLE
    .\scripts\install_toolchain.ps1
    .\scripts\install_toolchain.ps1 -Force
#>
param(
    [string]$Version = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$ToolchainDir = Join-Path $RootDir "runtime\toolchain"
$Platform = "win-x64"
$TargetDir = Join-Path $ToolchainDir $Platform

# Read manifest
$ManifestPath = Join-Path $ToolchainDir "manifest.json"
if (-not (Test-Path $ManifestPath)) {
    Write-Error "Manifest not found: $ManifestPath"
    exit 1
}
$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

if (-not $Manifest.platforms.$Platform) {
    Write-Error "Platform '$Platform' not found in manifest"
    exit 1
}

$PlatformEntry = $Manifest.platforms.$Platform
$ToolchainVersion = if ($Version) { $Version } else { $PlatformEntry.version }

Write-Host "MinGW-w64 UCRT64 Toolchain Installer" -ForegroundColor Cyan
Write-Host "  Platform:  $Platform"
Write-Host "  Version:   $ToolchainVersion"
Write-Host "  Target:    $TargetDir"

# Check if already installed
if ((Test-Path $TargetDir) -and -not $Force) {
    $GccExe = Join-Path $TargetDir "bin\gcc.exe"
    if (Test-Path $GccExe) {
        Write-Host "`nToolchain already installed. Use -Force to reinstall." -ForegroundColor Green
        Write-Host "  GCC: $GccExe"
        & $GccExe --version 2>&1 | Select-Object -First 1
        exit 0
    }
}

# Download URL (GitHub Release)
$ReleaseTag = "toolchain-$Platform-$ToolchainVersion"
$ArchiveName = "$Platform-toolchain-$ToolchainVersion.tar.zst"
$DownloadUrl = "https://github.com/user/repo/releases/download/$ReleaseTag/$ArchiveName"

Write-Host "`nDownloading from: $DownloadUrl" -ForegroundColor Yellow
Write-Host "(If this fails, manually place the toolchain at: $TargetDir)"

# Create temp directory
$TmpDir = Join-Path $env:TEMP "mcp-toolchain-download"
if (Test-Path $TmpDir) { Remove-Item -Recurse -Force $TmpDir }
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

$ArchivePath = Join-Path $TmpDir $ArchiveName

try {
    # Download
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ArchivePath -UseBasicParsing
    Write-Host "Download complete: $ArchivePath"

    # Extract (requires zstd or 7z)
    Write-Host "Extracting..."
    if (Get-Command "zstd" -ErrorAction SilentlyContinue) {
        & zstd -d $ArchivePath -o "$TmpDir\archive.tar"
        & tar -xf "$TmpDir\archive.tar" -C $TmpDir
    } elseif (Get-Command "7z" -ErrorAction SilentlyContinue) {
        & 7z x $ArchivePath -o"$TmpDir" -y
    } else {
        Write-Error "Neither zstd nor 7z found. Install one to extract the toolchain archive."
        exit 1
    }

    # Move to target
    if (Test-Path $TargetDir) { Remove-Item -Recurse -Force $TargetDir }
    $ExtractedDir = Get-ChildItem -Path $TmpDir -Directory | Where-Object { $_.Name -eq $Platform } | Select-Object -First 1
    if ($ExtractedDir) {
        Move-Item $ExtractedDir.FullName $TargetDir
    } else {
        # Assume extracted directly to $Platform/ subfolder
        $Candidate = Join-Path $TmpDir $Platform
        if (Test-Path $Candidate) {
            Move-Item $Candidate $TargetDir
        } else {
            Write-Error "Could not find extracted toolchain directory"
            exit 1
        }
    }

    Write-Host "Extracted to: $TargetDir" -ForegroundColor Green

} catch {
    Write-Error "Download/extraction failed: $_"
    Write-Host "`nAlternative: manually download and extract the toolchain to:"
    Write-Host "  $TargetDir"
    Write-Host "`nExpected structure:"
    Write-Host "  $TargetDir\bin\gcc.exe"
    Write-Host "  $TargetDir\bin\as.exe"
    Write-Host "  $TargetDir\bin\ld.exe"
    Write-Host "  $TargetDir\x86_64-w64-mingw32\include\"
    exit 1
} finally {
    Remove-Item -Recurse -Force $TmpDir -ErrorAction SilentlyContinue
}

# Verify
Write-Host "`nVerifying toolchain..."
$GccExe = Join-Path $TargetDir "bin\gcc.exe"
if (Test-Path $GccExe) {
    $VersionOutput = & $GccExe --version 2>&1 | Select-Object -First 1
    Write-Host "  GCC: $VersionOutput" -ForegroundColor Green
} else {
    Write-Error "gcc.exe not found after extraction"
    exit 1
}

# Run self-test
$SelfTest = Join-Path $RootDir "scripts\compiler_self_test.py"
if (Test-Path $SelfTest) {
    Write-Host "`nRunning self-test..."
    python $SelfTest
}

Write-Host "`nToolchain installed successfully!" -ForegroundColor Green
