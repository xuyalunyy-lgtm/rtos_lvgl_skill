@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_toolchain.ps1" %*
exit /b %errorlevel%
