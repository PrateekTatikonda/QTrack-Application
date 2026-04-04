@echo off
echo ====================================
echo    QTrack Backend Server Launcher
echo ====================================
echo.
echo Activating Python Virtual Environment...
echo.

REM Navigate to project root and activate virtual environment
cd /d "%~dp0"
call Scripts\activate.bat

if errorlevel 1 (
    echo ❌ Failed to activate virtual environment!
    echo Please ensure the virtual environment is set up correctly.
    pause
    exit /b 1
)

echo ✅ Virtual Environment Activated
echo.
echo Choose running mode:
echo [1] Development (with auto-reload)
echo [2] Production (no auto-reload)
echo [3] Direct uvicorn command
echo [4] Install dependencies first
echo.
set /p choice="Enter your choice (1-4): "

if "%choice%"=="4" (
    echo.
    echo Installing Python dependencies...
    cd backend\app
    pip install -r requirements.txt
    echo.
    echo Dependencies installed! Choose server mode:
    echo [1] Development (with auto-reload)
    echo [2] Production (no auto-reload)
    set /p choice="Enter your choice (1-2): "
)

cd /d "%~dp0backend"

if "%choice%"=="1" (
    echo.
    echo 🚀 Starting Development Server...
    python run_server.py
) else if "%choice%"=="2" (
    echo.
    echo 🚀 Starting Production Server...
    python run_server_prod.py
) else if "%choice%"=="3" (
    echo.
    echo 🚀 Starting with Direct Command...
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) else (
    echo Invalid choice! Starting Development Server by default...
    python run_server.py
)

echo.
pause