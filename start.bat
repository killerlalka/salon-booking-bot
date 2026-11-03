@echo off
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if not exist venv\Scripts\python.exe (
    echo Run install.bat first.
    pause
    exit /b
)

venv\Scripts\python bot.py
pause
