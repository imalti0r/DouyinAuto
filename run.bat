@echo off
rem DouyinAuto launcher. Double-click = normal run.
rem Usage: run.bat [--dry-run] [--max-videos N] [--mode vision|text|both] [--no-overlay]
cd /d "%~dp0"

set "PY=C:\Users\Admin\AppData\Local\Programs\Python\Python314\python.exe"
if not exist "%PY%" (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PY=py -3"
    ) else (
        set "PY=python"
    )
)

"%PY%" main.py %*

echo.
echo ============== program exited ==============
pause
