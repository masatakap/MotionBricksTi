@echo off
setlocal
set "STUDIO_SETUP_HELP=Move or clone Studio into a local folder you can write to, then run Setup Studio.cmd again."
cd /d "%~dp0" || goto failed
echo [1/5] Checking tools, Python and folder access...
set "STUDIO_SETUP_HELP=Install Git for Windows, then open a new terminal or launch Setup Studio.cmd again."
git --version || goto failed
set "STUDIO_SETUP_HELP=Install Git LFS and run git lfs install, then retry."
git lfs version || goto failed
set "STUDIO_SETUP_HELP=Use git clone to download Studio. Run Setup Studio.cmd inside that checkout."
if not exist "..\..\.git" goto failed
set "STUDIO_SETUP_HELP=Install uv and ensure it is on PATH. See https://docs.astral.sh/uv/getting-started/installation/"
uv --version || goto failed
set "STUDIO_SETUP_HELP=Use Windows x64 and Python 3.12. Check the message above for Python, network or folder access problems."
uv run --no-project --python 3.12 python -m app.studio_setup paths || goto failed

echo [2/5] Installing the locked Python dependencies...
set "STUDIO_SETUP_HELP=Check internet access, available disk space and the Python package error above, then rerun setup."
uv sync --locked
if errorlevel 1 goto failed

echo [3/5] Checking the NVIDIA GPU and TensorRT...
set "STUDIO_SETUP_HELP=Studio requires a compatible NVIDIA GPU. Update its NVIDIA driver and rerun setup. See the diagnostic above."
".venv\Scripts\python.exe" -m app.studio_setup gpu || goto failed

echo [4/5] Downloading Git LFS assets and checking the official model files...
set "STUDIO_SETUP_HELP=Check Git LFS and access to GitHub, then retry. See README if a model already exists but fails verification."
git lfs pull --exclude="assets/motions/**"
if errorlevel 1 goto failed
if exist "..\..\tools\fetch_studio_models.py" (
  ".venv\Scripts\python.exe" "..\..\tools\fetch_studio_models.py"
  if errorlevel 1 goto failed
)
echo [5/5] Checking the distributed motion files...
set "STUDIO_SETUP_HELP=Review the reported file paths. Use a fresh clone if this is your first installation."
".venv\Scripts\python.exe" tools\audit_distribution_motions.py
if errorlevel 1 goto failed
echo Setup complete. Open Launch MotionBricks Studio Ti.cmd.
echo The first launch builds a TensorRT engine. Keep the loading window open.
pause
exit /b 0
:failed
echo.
echo Setup stopped. %STUDIO_SETUP_HELP%
pause
exit /b 1
