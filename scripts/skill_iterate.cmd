@echo off
REM Skill iteration validation (bypasses PowerShell ExecutionPolicy)
REM Usage: scripts\skill_iterate.cmd [-Sync] [-SkipSelfTest]

set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell"

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0skill_iterate.ps1" %*
