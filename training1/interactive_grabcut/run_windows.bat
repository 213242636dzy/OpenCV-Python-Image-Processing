@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe main.py
) else (
  where py >nul 2>nul
  if errorlevel 1 (
    python main.py
  ) else (
    py main.py
  )
)
if errorlevel 1 pause
