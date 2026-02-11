@echo off
echo Starting JustInsurance Student Dashboard...

:: Start Flask server
cd /d "C:\Users\Chidd\Downloads\justinsurance-student-dashboard\backend"
start /B cmd /c "call venv\Scripts\activate && python app.py"

:: Wait a moment for server to start
timeout /t 3 /nobreak >nul

:: Start Cloudflare tunnel
start /B "C:\Users\Chidd\Downloads\cloudflared.exe" tunnel run justinsurance-dashboard

echo Dashboard is running!
echo Flask server: http://localhost:5000
echo Public URL: https://dashboard.justinsuranceco.com
echo.
echo Press any key to stop...
pause >nul

:: Kill processes when done
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM cloudflared.exe >nul 2>&1
