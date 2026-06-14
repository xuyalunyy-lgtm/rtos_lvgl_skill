@echo off
REM Install skill to ~/.cursor/skills/ (bypasses PowerShell ExecutionPolicy)
REM Usage: scripts\install_skill.cmd

set "PS_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS_EXE%" set "PS_EXE=powershell"

"%PS_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_skill.ps1" %*
