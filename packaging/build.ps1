# Builds dist\Jarvis\Jarvis.exe, then dist\JarvisSetup.exe if Inno Setup is installed.
# Run from the repo root:  powershell -File packaging\build.ps1
$ErrorActionPreference = "Stop"
.venv\Scripts\python -m pip install -e ".[dev]" pyinstaller
.venv\Scripts\pyinstaller packaging\jarvis.spec --noconfirm --distpath dist --workpath build
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" }
if (Test-Path $iscc) { & $iscc packaging\installer.iss }
else { Write-Host "Inno Setup not found (winget install JRSoftware.InnoSetup); skipped the installer." }
