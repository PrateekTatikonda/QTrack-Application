@echo off
REM QTrack frontend launcher (Vite dev server)

cd /d "%~dp0..\frontend"

if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install || exit /b 1
)

echo Starting QTrack frontend... Press Ctrl+C to stop.
npm run dev
