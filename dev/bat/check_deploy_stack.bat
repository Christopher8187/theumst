@echo off
setlocal
cd /d "%~dp0\..\.."
docker compose -f docker\compose.deploy.yml ps
curl -fsS http://localhost:8080/health
