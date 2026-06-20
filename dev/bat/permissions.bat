@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%_common.bat"
call :load_env

echo Permission actions:
echo   1^) Show Windows Docker permission help
echo   2^) Fix remote COM permissions
echo   3^) Fix remote CN permissions
echo   4^) Choose remote server to fix permissions
set /p choice="Action [1]: "
if "%choice%"=="" set choice=1

if "%choice%"=="1" goto local_help
if "%choice%"=="2" call :remote_permissions COM & goto done
if "%choice%"=="3" call :remote_permissions CN & goto done
if "%choice%"=="4" call :pick_server & call :remote_permissions %PICKED_SERVER% & goto done

goto done

:local_help
echo.
echo On Windows, Docker permissions are usually controlled by Docker Desktop.
echo Open Docker Desktop, make sure it is running, then try:
echo   docker run --rm hello-world
echo.
echo If Git Bash/WSL created odd file permissions, run the Linux permissions script from WSL:
echo   chmod +x dev/sh/*.sh

goto done

:done
pause
