@echo off
echo ================================================
echo    DENOVE APS - Windows Setup Script
echo ================================================
echo.

echo [1/5] Setting up Python virtual environment...
cd backend
python -m venv venv
call venv\Scripts\activate

echo.
echo [2/5] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [3/5] Seeding database with demo data...
python seed_data.py

echo.
echo [4/5] Installing Node.js dependencies...
cd ..\frontend
call npm install

echo.
echo ================================================
echo    Setup Complete!
echo ================================================
echo.
echo To start the application:
echo.
echo 1. Backend (in one terminal):
echo    cd backend
echo    venv\Scripts\activate
echo    python run.py
echo.
echo 2. Frontend (in another terminal):
echo    cd frontend
echo    npm run dev
echo.
echo Then open: http://localhost:3000
echo.
echo Demo Login:
echo   Username: manager
echo   Password: admin123
echo.
echo ================================================
pause
