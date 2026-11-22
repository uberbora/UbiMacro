@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b 1
)
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
start "" pythonw run.py
