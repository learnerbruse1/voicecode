@echo off
chcp 65001 >nul
echo Starting VoiceCode...
.venv\Scripts\python main.py
if errorlevel 1 pause
