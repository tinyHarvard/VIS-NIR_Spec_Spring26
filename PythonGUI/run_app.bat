@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment was not found.
    echo Run install_dependencies.bat first.
    exit /b 1
)

echo Starting VIS-NIR Spectrometer desktop app...
".venv\Scripts\python.exe" desktop_app.py
exit /b %ERRORLEVEL%
