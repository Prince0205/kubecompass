@echo off
REM Quick Start Script for KubeCompass Unified App (Windows)
REM This script sets up and runs the complete integrated application on port 8000

setlocal enabledelayedexpansion

echo.
echo ==========================================
echo KubeCompass - Unified App Quick Start
echo ==========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if Node is available
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node is not installed or not in PATH
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i

echo Python: %PYTHON_VERSION%
echo Node: %NODE_VERSION%
echo NPM: %NPM_VERSION%
echo.

REM Check and warn about MongoDB
echo Checking MongoDB...
tasklist /FI "IMAGENAME eq mongod.exe" >nul 2>&1
if errorlevel 1 (
    echo WARNING: MongoDB does not appear to be running
    echo Make sure MongoDB is running on localhost:27017
    echo You can start MongoDB manually
    echo.
) else (
    echo MongoDB is running
    echo.
)

REM Build React if needed
if not exist "ui\dist" (
    echo Building React frontend...
    cd ui
    call npm install --silent
    call npm run build
    cd ..
    echo React build complete
    echo.
) else (
    if not exist "ui\dist\index.html" (
        echo Building React frontend...
        cd ui
        call npm install --silent
        call npm run build
        cd ..
        echo React build complete
        echo.
    )
)

REM Install Python dependencies if needed
echo Checking Python dependencies...
python -m pip install -q -r requirements.txt

echo.
echo ==========================================
echo Starting KubeCompass on Port 8000
echo ==========================================
echo.
echo Access the app at: http://localhost:8000
echo.
echo To stop the server: Press Ctrl+C
echo.
echo Default Login Credentials:
echo   Email: admin@example.com
echo   Password: admin123
echo.
echo ==========================================
echo.

REM Start the backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause
