@echo off
setlocal
title HealerPlus 2.0 - Vite Frontend Server
echo ======================================================================
echo    HEALERPLUS 2.0 - CYBER-MEDICAL WEB APPLICATION
echo    Starting on http://127.0.0.1:3000 ...
echo ======================================================================
cd /d "%~dp0frontend"

if exist "%ProgramFiles%\nodejs\npm.cmd" goto use_program_files_node
if exist "%LocalAppData%\Programs\nodejs\npm.cmd" goto use_local_node

"%SystemRoot%\System32\where.exe" npm >nul 2>&1
if not errorlevel 1 goto use_path_node

echo [ERROR] Node.js and npm were not found.
echo Install Node.js LTS from https://nodejs.org/ and run this file again.
pause
exit /b 1

:use_program_files_node
set "NPM_CMD=%ProgramFiles%\nodejs\npm.cmd"
goto npm_ready

:use_local_node
set "NPM_CMD=%LocalAppData%\Programs\nodejs\npm.cmd"
goto npm_ready

:use_path_node
set "NPM_CMD=npm"

:npm_ready

if not exist "node_modules\vite\bin\vite.js" (
  echo Installing frontend dependencies...
  call "%NPM_CMD%" install
  if errorlevel 1 (
    echo.
    echo [ERROR] Frontend dependencies could not be installed.
    pause
    exit /b 1
  )
)

echo Opening http://127.0.0.1:3000/ in your default browser...
start "" "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:3000/'"
call "%NPM_CMD%" run dev

if errorlevel 1 (
  echo.
  echo [ERROR] The frontend server could not start.
  echo Check the error above. Port 3000 may already be in use.
  pause
  exit /b 1
)

endlocal
