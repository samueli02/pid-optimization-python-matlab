@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" src\app.py
) else if exist "%USERPROFILE%\miniconda3\envs\sm_env\python.exe" (
  "%USERPROFILE%\miniconda3\envs\sm_env\python.exe" src\app.py
) else (
  python src\app.py
)
if errorlevel 1 (
  echo Please follow README.md to install Python and requirements.
  pause
)
