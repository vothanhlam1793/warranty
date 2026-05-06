@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo Stopping Warranty services on ports 8001 and 3000...
call :kill_port 8001
call :kill_port 3000
echo Done.
goto :eof

:kill_port
set "TARGET_PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:":%TARGET_PORT% .*LISTENING" ^| sort /unique') do (
  echo Stopping process on port %TARGET_PORT%: PID %%P
  taskkill /PID %%P /T /F >nul 2>nul
)
goto :eof
