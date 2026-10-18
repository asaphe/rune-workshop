@echo off
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
if exist "%~dp0runtime\pythonw.exe" (
  start "" "%~dp0runtime\pythonw.exe" -E -s "%~dp0launch.py"
  exit /b
)
where pyw >nul 2>nul || (
  echo Rune needs the official embeddable Python runtime, or Python with the Windows launcher.
  echo Extract the official Windows embeddable Python ZIP into runtime. See README.md.
  echo For source setup, see README.md. Python 3.9 is the minimum, not the recommended release.
  pause
  exit /b 1
)
start "" pyw -3 -E -s "%~dp0launch.py"
