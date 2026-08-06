@echo off
REM skills-hub —— Windows CMD 入口（转交 PowerShell 实现）
setlocal
set "BIN_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%BIN_DIR%skills-hub.ps1" %*
exit /b %ERRORLEVEL%
