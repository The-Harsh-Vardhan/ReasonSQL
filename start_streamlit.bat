@echo off
REM NL2SQL Multi-Agent System - Streamlit Launcher
REM This batch file starts the Streamlit web UI

echo =====================================
echo  NL2SQL Multi-Agent System
echo  Starting Streamlit Web UI...
echo =====================================
echo.

REM Change to the UI directory
cd /d "%~dp0ui"

REM Start Streamlit
echo Starting Streamlit server...
echo.
echo The app will open in your default browser automatically.
echo Press Ctrl+C to stop the server.
echo.

REM Try using python -m streamlit (more reliable)
python -m streamlit run streamlit_app.py

REM If streamlit command fails, show error and pause
if errorlevel 1 (
    echo.
    echo =====================================
    echo  ERROR: Failed to start Streamlit
    echo =====================================
    echo.
    echo Possible reasons:
    echo  1. Streamlit is not installed
    echo  2. Python is not in PATH
    echo  3. Virtual environment not activated
    echo.
    echo To fix:
    echo  - Install Streamlit: pip install streamlit
    echo  - Or activate your virtual environment first
    echo.
    pause
)
