@echo off
title HealerPlus 2.0 - FastAPI Backend Server
echo ======================================================================
echo    HEALERPLUS 2.0 - BACKEND SERVER (FASTAPI ^& AI IDS)
echo    Starting on http://127.0.0.1:8000 ...
echo ======================================================================
cd /d "%~dp0"

if exist "%LocalAppData%\Programs\Python\Python311\python.exe" goto use_local_python

"%SystemRoot%\System32\where.exe" py >nul 2>&1
if not errorlevel 1 goto use_py

if exist "%LocalAppData%\Programs\Python\Launcher\py.exe" goto use_local_py

"%SystemRoot%\System32\where.exe" python >nul 2>&1
if not errorlevel 1 goto use_python

echo [ERROR] Python was not found.
echo Install Python 3 and make sure it is available on PATH.
pause
exit /b 1

:use_local_python
"%LocalAppData%\Programs\Python\Python311\python.exe" -u backend/run_backend.py
goto server_stopped

:use_py
py -3 -u backend/run_backend.py
goto server_stopped

:use_local_py
"%LocalAppData%\Programs\Python\Launcher\py.exe" -3 -u backend/run_backend.py
goto server_stopped

:use_python
python -u backend/run_backend.py

:server_stopped
if errorlevel 1 (
  echo.
  echo [ERROR] The backend server stopped with an error.
  pause
)
