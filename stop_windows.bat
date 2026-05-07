@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

:: Load .env variables
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%i in (".env") do (
        set "%%i=%%j"
    )
)

:: Set defaults if not in .env
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8001"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=3000"

echo Stopping Warranty services on ports %BACKEND_PORT% and %FRONTEND_PORT%...
call :kill_port %BACKEND_PORT%
call :kill_port %FRONTEND_PORT%
echo Done.
goto :eof

:kill_port
set "TARGET_PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%TARGET_PORT% .*LISTENING" ^| sort /unique') do (
  echo Stopping process on port %TARGET_PORT%: PID %%P
  taskkill /PID %%P /T /F >nul 2>nul
)
goto :eof
