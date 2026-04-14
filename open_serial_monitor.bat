@echo off
REM Simple batch file to open PuTTY serial monitor for STM32F411 CCD ADC output

set COM_PORT=COM3
set BAUD_RATE=115200
set PUTTY_EXE=putty.exe

if exist "%ProgramFiles%\PuTTY\putty.exe" set PUTTY_EXE=%ProgramFiles%\PuTTY\putty.exe
if exist "%ProgramFiles(x86)%\PuTTY\putty.exe" set PUTTY_EXE=%ProgramFiles(x86)%\PuTTY\putty.exe

echo Launching PuTTY serial monitor...
echo Port: %COM_PORT%
echo Baud Rate: %BAUD_RATE%
echo.

where "%PUTTY_EXE%" >nul 2>nul
if errorlevel 1 if not exist "%PUTTY_EXE%" (
    echo PuTTY was not found.
    echo Install PuTTY or add it to PATH, then run this script again.
    pause
    exit /b 1
)

"%PUTTY_EXE%" -serial %COM_PORT% -sercfg %BAUD_RATE%,8,n,1,N

REM If PuTTY closes, show this message
echo.
echo Serial monitor closed.
pause


