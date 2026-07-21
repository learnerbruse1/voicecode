@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
python --version 2>nul
if errorlevel 1 (
    echo Python not found. Install Python 3.10+ from https://www.python.org
    pause
    exit /b 1
)
if not exist .venv python -m venv .venv
echo Installing dependencies...
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)
echo Setup complete. Now run: run.bat
pause
