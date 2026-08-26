@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "PYTHON_CMD=python"
) else (
  set "PYTHON_CMD=py"
)
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :error
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python main.py
exit /b 0
:error
echo.
echo Setup failed. Please check the Python installation and network used only for dependency installation.
pause
exit /b 1
