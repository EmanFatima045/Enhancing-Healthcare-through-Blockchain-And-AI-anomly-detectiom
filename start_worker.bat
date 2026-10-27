@echo off
title HealerPlus 2.0 - Durable Outbox Worker
cd /d "%~dp0"
echo Starting HealerPlus blockchain and notification worker...

where py >nul 2>&1
if not errorlevel 1 (
  py -3 -u -m backend.worker
  goto stopped
)

where python >nul 2>&1
if not errorlevel 1 (
  python -u -m backend.worker
  goto stopped
)

echo [ERROR] Python was not found. Install Python 3 and run this file again.
pause

:stopped
if errorlevel 1 (
  echo.
  echo [ERROR] The HealerPlus worker stopped with an error.
  pause
)
