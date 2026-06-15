# 同步完整版 prompts/、platforms/ → freertos-skill-lite/
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $Py) { $Py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $Py) {
    Write-Error "未找到 python3/python，请先安装 Python 3"
}

& $Py.Source (Join-Path $Root "scripts\sync_lite.py") @args
