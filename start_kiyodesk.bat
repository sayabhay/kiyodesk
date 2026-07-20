@echo off
SETLOCAL EnableDelayedExpansion

:: KiyoDesk One-Click Windows Startup Script
:: This script checks for dependencies, installs them if missing, and launches the project.

echo ====================================================
echo           KiyoDesk - Trading Intelligence
echo ====================================================
echo.

:: 1. Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.12+ from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Check for Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

:: 3. Setup Backend
echo [1/4] Setting up Backend...
cd backend
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv || (echo [ERROR] Failed to create venv. Check permissions. && pause && exit /b 1)
)
echo Activating environment and installing dependencies...
call venv\Scripts\activate || (echo [ERROR] Failed to activate venv. && pause && exit /b 1)
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt || (echo [ERROR] Failed to install requirements. && pause && exit /b 1)
cd ..

:: 4. Setup Frontend
echo [2/4] Setting up Frontend...
cd frontend
echo Installing frontend dependencies...
call npm install >nul
cd ..

:: 5. Launch VS Code
echo [3/4] Opening VS Code...
code .
if %errorlevel% neq 0 (
    echo [WARN] 'code' command not found. Make sure VS Code is installed and in PATH.
)

:: 6. Start Services
echo [4/4] Starting Services...
echo.
echo ----------------------------------------------------
echo Backend will run at: http://localhost:8000
echo Frontend will run at: http://localhost:5000
echo ----------------------------------------------------
echo.

:: Start Backend in a new window
start "KiyoDesk Backend" cmd /k "cd backend && call venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

:: Start Frontend in a new window
start "KiyoDesk Frontend" cmd /k "cd frontend && npm run dev -- --port 5000"

echo.
echo All systems go! Happy trading.
echo.
pause
