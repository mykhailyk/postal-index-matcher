@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "%~dp0start_review_ui.pyw"
  exit /b 0
)

if exist ".venv\Scripts\python.exe" (
  start "" ".venv\Scripts\python.exe" "%~dp0start_review_ui.pyw"
  exit /b 0
)

start "" pythonw "%~dp0start_review_ui.pyw"
