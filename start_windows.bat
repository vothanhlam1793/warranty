@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
set "ROOT=%CD%"

:: Load .env variables
if exist .env (
    for /f "usebackq tokens=1,2 delims==" %%i in (".env") do (
        set "%%i=%%j"
    )
)

:: Set defaults if not in .env
if "%BACKEND_PORT%"=="" set "BACKEND_PORT=8001"
if "%FRONTEND_PORT%"=="" set "FRONTEND_PORT=3000"
set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"

echo === Warranty Management System (Windows) ===
echo Backend Port: %BACKEND_PORT%
echo Frontend Port: %FRONTEND_PORT%
echo.

call :kill_port %BACKEND_PORT%
call :kill_port %FRONTEND_PORT%

echo Starting backend API on http://localhost:%BACKEND_PORT% ...
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
start "warranty-backend" "%PYTHON_EXE%" -m uvicorn server.main:app --host 0.0.0.0 --port %BACKEND_PORT%

echo Starting web frontend on http://localhost:%FRONTEND_PORT% ...
start "warranty-frontend" cmd /c "cd /d "%ROOT%\apps\web" && "%PYTHON_EXE%" -m http.server %FRONTEND_PORT%"

echo.
echo Waiting for services to start...
timeout /t 4 /nobreak >nul

echo.
echo ===================================
echo   Backend  -^> http://localhost:%BACKEND_PORT%
echo   Frontend -^> http://localhost:%FRONTEND_PORT%
echo   API docs -^> http://localhost:%BACKEND_PORT%/docs
echo ===================================
echo.
echo Use restart_windows.bat to restart both services.
echo Use stop_windows.bat to stop both services.
goto :eof

:kill_port
set "TARGET_PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%TARGET_PORT% .*LISTENING" ^| sort /unique') do (
  echo Stopping process on port %TARGET_PORT%: PID %%P
  taskkill /PID %%P /T /F >nul 2>nul
)
goto :eof
