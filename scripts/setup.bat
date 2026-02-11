@echo off
REM JustInsurance Student Dashboard - Windows Setup Script

echo.
echo ========================================
echo JustInsurance Student Dashboard Setup
echo ========================================
echo.

REM Check for Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.11+ from https://python.org
    exit /b 1
)

REM Check for Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js 20+ from https://nodejs.org
    exit /b 1
)

echo [1/5] Creating Python virtual environment...
cd backend
python -m venv venv

echo [2/5] Activating virtual environment and installing Python dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

echo [3/5] Installing Node.js dependencies...
cd ..\frontend
call npm install

echo [4/5] Copying environment file...
cd ..
if not exist .env (
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit .env file with your Absorb API credentials!
    echo.
)

echo [5/5] Creating session directory...
if not exist backend\flask_session mkdir backend\flask_session

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo To start the application:
echo.
echo 1. Edit .env with your Absorb API credentials
echo.
echo 2. Start backend (in a new terminal):
echo    cd backend
echo    venv\Scripts\activate
echo    python app.py
echo.
echo 3. Start frontend (in another terminal):
echo    cd frontend
echo    npm run dev
echo.
echo 4. Open http://localhost:3000
echo.
pause
