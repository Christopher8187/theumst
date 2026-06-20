@echo off
setlocal
cd /d "%~dp0\..\.."
docker compose -f docker\compose.local.yml ps
curl -fsS http://localhost:8000/health
