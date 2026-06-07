@echo off
chcp 65001 >nul
python --version 2>nul
if errorlevel 1 (
    echo Python not found. Install Python 3.10+ from https://www.python.org
    pause
    exit /b 1
)
if not exist .venv python -m venv .venv
echo Installing...
.venv\Scripts\pip install -q -r requirements.txt
echo Done! Now run: run.bat
pause
