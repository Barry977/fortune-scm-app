@echo off
chcp 65001 >nul
echo ============================================================
echo   命运 (DESTINY) - 智能客户开发系统
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

:: Check if running from correct directory
if not exist "start.py" (
    echo [ERROR] start.py not found
    echo Please run this script from the application directory
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

:: Run the application
echo.
echo [INFO] Starting application...
echo.
python start.py

:: If we get here, the app has exited
echo.
echo [INFO] Application has exited
pause
