$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "Не знайдено .venv\\Scripts\\python.exe. Спочатку створіть та налаштуйте .venv."
}

& $PythonExe -m pip install pyinstaller
& $PythonExe -m PyInstaller --noconfirm --clean review_ui.spec

Write-Host ""
Write-Host "Збірку завершено. EXE знаходиться в папці dist\\UkrposhtaReviewUI.exe"
