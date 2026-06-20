@echo off
setlocal
cd /d "%~dp0\..\.."
docker compose -f docker\compose.deploy.yml up --build -d
echo.
echo Open: http://localhost:8080
