@echo off
setlocal
REM QTrack backend launcher. Usage: scripts\start-backend.bat [dev|prod|install]

cd /d "%~dp0..\backend"

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in backend\.venv ...
    python -m venv .venv || goto :error
    set "MODE=install"
)

set "PY=.venv\Scripts\python.exe"
if not defined MODE set "MODE=%~1"
if "%MODE%"=="" set "MODE=dev"

if /i "%MODE%"=="install" (
    echo Installing backend dependencies...
    "%PY%" -m pip install -r requirements-dev.txt || goto :error
    set "MODE=dev"
)

if not exist ".env" (
    echo WARNING: backend\.env not found. Copy backend\.env.example to backend\.env and fill it in.
)

if /i "%MODE%"=="prod" (
    "%PY%" run_server.py --prod
) else (
    "%PY%" run_server.py
)
goto :eof

:error
echo Failed to start the QTrack backend.
pause
exit /b 1
