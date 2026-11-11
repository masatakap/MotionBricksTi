@echo off
setlocal
cd /d "%~dp0" || goto failed
if not exist ".venv\Scripts\pythonw.exe" (
  echo Run Setup Studio.cmd first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m app.studio_launcher %*
if not errorlevel 1 exit /b 0
:failed
echo Could not start Studio. Check that the folder is accessible and rerun Setup Studio.cmd.
pause
exit /b 1
