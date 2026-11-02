@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating a local virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 goto :failed
)

".venv\Scripts\python.exe" -c "import streamlit, supabase" >nul 2>nul
if errorlevel 1 (
    echo Installing portal dependencies...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :failed
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)

echo Starting the Markit PDF portal...
".venv\Scripts\python.exe" -m streamlit run app.py
exit /b %errorlevel%

:failed
echo.
echo Could not prepare or start the local portal. Read the error above.
pause
exit /b 1
