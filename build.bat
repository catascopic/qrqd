@echo off
rem Rebuilds every program in build\ from src\: QR.8xp (BASIC front end), the Axe
rem sources (QRSRC, LOREMSRC, SPEEDSRC; compile those on the calculator with Axe),
rem and the pure-BASIC set (QRBASIC, 83_safe_QRBASIC for the TI-83+, _theta_QRBIT, lists).
cd /d "%~dp0"
python tools\build.py
if errorlevel 1 (
    echo.
    echo BUILD FAILED - see the message above.
)
echo.
pause
