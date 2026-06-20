@echo off
setlocal EnableExtensions

echo Permission actions:
echo   1^) Show Windows Docker permission help
echo   2^) Fix remote COM permissions
echo   3^) Fix remote CN permissions
echo   4^) Choose remote server to fix permissions
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" goto local_help
if "%CHOICE%"=="2" call "%~dp0_common.bat" remote_permissions COM
if "%CHOICE%"=="3" call "%~dp0_common.bat" remote_permissions CN
if "%CHOICE%"=="4" call :remote
pause
exit /b

:remote
set /p TARGET=Target server COM or CN [COM]: 
if "%TARGET%"=="" set "TARGET=COM"
call "%~dp0_common.bat" remote_permissions %TARGET%
exit /b

:local_help
echo.
echo On Windows, Docker permissions are usually controlled by Docker Desktop.
echo Open Docker Desktop, make sure it is running, then try:
echo   docker run --rm hello-world
echo.
echo If WSL or Git Bash created odd Linux permissions, run this from Linux/WSL:
echo   chmod +x dev/sh/*.sh
echo   ./dev/sh/linux_first_fix.sh
pause
