<# Install the private win-x64 toolchain without changing the machine PATH. #>
[CmdletBinding()]
param(
    [string]$ArchivePath = "",
    [string]$DownloadUrl = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$ToolchainRoot = Join-Path $RootDir "runtime\toolchain"
$Platform = "win-x64"
$TargetDir = Join-Path $ToolchainRoot $Platform
$Distribution = Get-Content (Join-Path $ToolchainRoot "manifest.json") -Raw | ConvertFrom-Json
$Entry = $Distribution.platforms.$Platform
if (-not $Entry) { throw "No distribution entry for $Platform" }

function Test-Payload([string]$Directory) {
    $PayloadPath = Join-Path $Directory $Entry.payload_manifest
    if (-not (Test-Path -LiteralPath $PayloadPath -PathType Leaf)) { throw "Missing payload manifest: $PayloadPath" }
    $Payload = Get-Content -LiteralPath $PayloadPath -Raw | ConvertFrom-Json
    if ($Payload.schema_version -ne 1 -or $Payload.platform -ne $Platform) { throw "Invalid payload manifest identity" }
    if ([string]$Payload.version -ne [string]$Entry.version) { throw "Payload version mismatch" }
    $Properties = @($Payload.files.PSObject.Properties)
    if ($Properties.Count -eq 0) { throw "Payload manifest has no file hashes" }
    $Root = [IO.Path]::GetFullPath($Directory).TrimEnd('\') + '\'
    foreach ($Property in $Properties) {
        $FullPath = [IO.Path]::GetFullPath((Join-Path $Directory $Property.Name))
        if (-not $FullPath.StartsWith($Root, [StringComparison]::OrdinalIgnoreCase)) { throw "Unsafe payload path: $($Property.Name)" }
        if (-not (Test-Path -LiteralPath $FullPath -PathType Leaf)) { throw "Missing payload file: $($Property.Name)" }
        $Actual = (Get-FileHash -LiteralPath $FullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Actual -ne ([string]$Property.Value).ToLowerInvariant()) { throw "Payload hash mismatch: $($Property.Name)" }
    }
    foreach ($Required in $Entry.required_files) {
        if (-not (Test-Path -LiteralPath (Join-Path $Directory $Required) -PathType Leaf)) { throw "Required tool missing: $Required" }
    }
}

if ((Test-Path -LiteralPath $TargetDir) -and -not $Force) {
    try {
        Test-Payload $TargetDir
        & python (Join-Path $ScriptDir "compiler_self_test.py") --toolchain-dir $TargetDir
        if ($LASTEXITCODE -ne 0) { throw "Compiler self-test failed" }
        Write-Host "Portable toolchain is already installed and verified." -ForegroundColor Green
        exit 0
    } catch {
        Write-Warning "Existing payload is incomplete: $_"
    }
}

$BundledExpectedHash = ""
if (-not $ArchivePath -and $Entry.bundled_archive) {
    $BundledCandidate = Join-Path $RootDir ([string]$Entry.bundled_archive)
    if (Test-Path -LiteralPath $BundledCandidate -PathType Leaf) {
        $ArchivePath = $BundledCandidate
        $BundledExpectedHash = ([string]$Entry.archive_sha256).ToLowerInvariant()
    }
}

$Temporary = Join-Path ([IO.Path]::GetTempPath()) ("lvgl-ui-toolchain-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $Temporary | Out-Null
try {
    if (-not $ArchivePath) {
        $Repository = $Distribution.repository
        if (-not $DownloadUrl) {
            $DownloadUrl = "https://github.com/$Repository/releases/download/$($Entry.release_tag)/$($Entry.archive)"
        }
        $ArchivePath = Join-Path $Temporary $Entry.archive
        $ChecksumPath = "$ArchivePath.sha256"
        $ChecksumUrl = $DownloadUrl.Substring(0, $DownloadUrl.LastIndexOf('/') + 1) + $Entry.checksum
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $ArchivePath -UseBasicParsing
        Invoke-WebRequest -Uri $ChecksumUrl -OutFile $ChecksumPath -UseBasicParsing
        $ExpectedArchiveHash = ((Get-Content -LiteralPath $ChecksumPath -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
        $ActualArchiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ExpectedArchiveHash -ne $ActualArchiveHash) { throw "Downloaded archive SHA256 mismatch" }
    } else {
        $ArchivePath = [IO.Path]::GetFullPath($ArchivePath)
        if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) { throw "Archive not found: $ArchivePath" }
        if ($BundledExpectedHash) {
            $ExpectedArchiveHash = $BundledExpectedHash
        } else {
            $Sidecar = "$ArchivePath.sha256"
            if (-not (Test-Path -LiteralPath $Sidecar -PathType Leaf)) { throw "Local archive requires checksum sidecar: $Sidecar" }
            $ExpectedArchiveHash = ((Get-Content -LiteralPath $Sidecar -Raw).Trim() -split '\s+')[0].ToLowerInvariant()
        }
        $ActualArchiveHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($ExpectedArchiveHash -ne $ActualArchiveHash) { throw "Local archive SHA256 mismatch" }
    }

    $Expanded = Join-Path $Temporary "expanded"
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $Expanded
    $Candidate = Join-Path $Expanded $Platform
    Test-Payload $Candidate

    $Backup = "$TargetDir.previous-$PID"
    if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force }
    if (Test-Path -LiteralPath $TargetDir) { Move-Item -LiteralPath $TargetDir -Destination $Backup }
    try {
        Move-Item -LiteralPath $Candidate -Destination $TargetDir
        & python (Join-Path $ScriptDir "compiler_self_test.py") --toolchain-dir $TargetDir
        if ($LASTEXITCODE -ne 0) { throw "Installed compiler self-test failed" }
        if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Recurse -Force }
    } catch {
        if (Test-Path -LiteralPath $TargetDir) { Remove-Item -LiteralPath $TargetDir -Recurse -Force }
        if (Test-Path -LiteralPath $Backup) { Move-Item -LiteralPath $Backup -Destination $TargetDir }
        throw
    }
    Write-Host "Portable toolchain installed and verified: $TargetDir" -ForegroundColor Green
} finally {
    if (Test-Path -LiteralPath $Temporary) { Remove-Item -LiteralPath $Temporary -Recurse -Force }
}
