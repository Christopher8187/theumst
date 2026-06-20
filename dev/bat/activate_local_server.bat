@echo off
setlocal
cd /d "%~dp0\..\.."
docker compose -f docker\compose.local.yml up --build -d
echo.
echo Main webpage: http://localhost:5173
echo Dashboard:    http://localhost:5174/dashboard/profile/
echo FastAPI:      http://localhost:8000
