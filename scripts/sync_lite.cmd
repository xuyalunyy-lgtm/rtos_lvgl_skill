@echo off
REM Sync full skill -> freertos-skill-lite (bypasses PowerShell ExecutionPolicy)
REM Usage: scripts\sync_lite.cmd [-DryRun] [-SkillOnly]

set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell"

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0sync_lite.ps1" %*
