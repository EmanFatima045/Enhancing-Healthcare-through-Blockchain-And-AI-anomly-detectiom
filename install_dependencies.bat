@echo off
title HealerPlus 2.0 - Dependencies Setup
echo ======================================================================
echo    HEALERPLUS 2.0: HEALTHCARE SECURITY WITH BLOCKCHAIN AND AI
echo    Installing Python Backend Dependencies...
echo ======================================================================
cd /d "%~dp0backend"
pip install -r requirements.txt
echo.
echo Dependencies installation completed.
pause
