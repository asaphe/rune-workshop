@echo off
cd /d "%~dp0"
if exist "%~dp0runtime\pythonw.exe" (
  start "" "%~dp0runtime\pythonw.exe" "%~dp0server.py"
) else (
  start "" pyw -3 "%~dp0server.py"
)
