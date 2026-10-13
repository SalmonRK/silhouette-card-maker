@echo off
rem SCM Studio - local web UI for Silhouette Card Maker
title SCM Studio
cd /d "%~dp0.."
if not exist venv\Scripts\python.exe (
  echo Creating venv...
  python -m venv venv || goto :err
  venv\Scripts\python.exe -m pip install -r requirements.txt -r webui\requirements.txt || goto :err
)
venv\Scripts\python.exe -c "import flask, requests_cache, openpyxl" 2>nul || venv\Scripts\python.exe -m pip install -r webui\requirements.txt
if not exist webui\static\assets\games\mtg.jpg (
  echo Downloading sample card art for the game picker...
  venv\Scripts\python.exe webui\tools\fetch_game_art.py
)
venv\Scripts\python.exe webui\app.py
echo.
echo SCM Studio stopped (exit code %errorlevel%).
pause
goto :eof
:err
echo Setup failed. Install Python 3.12+ and try again.
pause
