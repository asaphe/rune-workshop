@echo off
cd /d "%~dp0"
if exist "%~dp0runtime\pythonw.exe" (
  start "" "%~dp0runtime\pythonw.exe" "%~dp0server.py"
  exit /b
)
where pyw >nul 2>nul || (
  echo Rune needs Python 3.9 or newer from https://www.python.org/downloads/
  pause
  exit /b 1
)
start "" pyw -3 "%~dp0server.py"
