@echo off
echo Starting QTrack Frontend...
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0frontend\qtrack-frontend"
npm run dev

pause