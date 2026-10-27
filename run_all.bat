@echo off
title HealerPlus 2.0 - Master Launcher
echo ======================================================================
echo    LAUNCHING HEALERPLUS 2.0 (BLOCKCHAIN ^& AI HEALTHCARE SECURITY)
echo ======================================================================
echo 1. Launching FastAPI backend server...
start "HealerPlus Backend" /D "%~dp0" "%ComSpec%" /k call "start_backend.bat"

echo 2. Launching durable outbox worker...
start "HealerPlus Worker" /D "%~dp0" "%ComSpec%" /k call "start_worker.bat"

echo 3. Launching frontend server and browser...
start "HealerPlus Frontend" /D "%~dp0" "%ComSpec%" /k call "start_frontend.bat"

echo.
echo HealerPlus 2.0 is now up and running!
echo - Web Dashboard: http://127.0.0.1:3000/
echo - Backend API Docs: http://127.0.0.1:8000/docs
echo ======================================================================
timeout /t 3 /nobreak >nul
