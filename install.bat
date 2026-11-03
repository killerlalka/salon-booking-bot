@echo off
cd /d "%~dp0"
echo ==============================================
echo   Salon booking bot - installation
echo ==============================================
echo.

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)

if not defined PY (
    echo Python not found. Installing Python 3.12 via winget...
    echo.
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo ----------------------------------------------
    echo  Python installed.
    echo  CLOSE this window and run install.bat again.
    echo ----------------------------------------------
    pause
    exit /b
)

echo Python found:
%PY% --version
echo.

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    %PY% -m venv venv
)

echo Installing libraries...
venv\Scripts\python -m pip install --upgrade pip --quiet
venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR while installing libraries. Check internet and run install.bat again.
    pause
    exit /b
)

if not exist .env copy .env.example .env >nul

echo.
echo ==============================================
echo  DONE!
echo  1. Open file .env and paste your bot token
echo  2. Run start.bat
echo ==============================================
pause
