@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_CMD="
py -3.12 -V >nul 2>nul && set "PYTHON_CMD=py -3.12"
if not defined PYTHON_CMD (
    py -3 -V >nul 2>nul && set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
    python -V >nul 2>nul && set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    echo Python 3.12 or newer was not found.
    echo Install Python 3.12, then run this script again.
    exit /b 1
)

echo Using Python launcher: %PYTHON_CMD%
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)"
if errorlevel 1 (
    echo Python 3.12 or newer is required by this app.
    echo Install Python 3.12, then run this script again.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        exit /b 1
    )
)

echo Upgrading pip tooling...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo Failed to upgrade pip tooling.
    exit /b 1
)

echo Installing app dependencies from pyproject.toml...
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo Failed to install project dependencies.
    exit /b 1
)

echo.
echo Dependencies installed successfully.
echo Activate the environment with:
echo   .venv\Scripts\activate
echo Start the app with:
echo   run_app.bat
echo Build the standalone executable with:
echo   build_standalone.bat

exit /b 0
