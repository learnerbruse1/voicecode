@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
echo Starting VoiceCode...
.venv\Scripts\python -X utf8 main.py
if errorlevel 1 pause
