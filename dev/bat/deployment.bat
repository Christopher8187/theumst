@echo off
setlocal EnableExtensions

echo Deployment actions:
echo   1^) Start deployment-style local nginx stack
echo   2^) Check deployment-style local nginx stack
echo   3^) Show deployment-style local logs
echo   4^) Stop deployment-style local nginx stack
echo   5^) Reset deployment-style local volumes/database
echo   6^) Remote full deploy: permissions + upload + start + check
echo   7^) Remote setup Docker/certbot
echo   8^) Remote upload only
echo   9^) Remote start only
echo  10^) Remote stop only
echo  11^) Remote shell
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" deploy_start
if "%CHOICE%"=="2" call "%~dp0_common.bat" deploy_check
if "%CHOICE%"=="3" call "%~dp0_common.bat" deploy_logs
if "%CHOICE%"=="4" call "%~dp0_common.bat" deploy_stop
if "%CHOICE%"=="5" call "%~dp0_common.bat" deploy_reset
if "%CHOICE%"=="6" call :remote remote_full_deploy
if "%CHOICE%"=="7" call :remote remote_setup
if "%CHOICE%"=="8" call :remote remote_upload
if "%CHOICE%"=="9" call :remote remote_start
if "%CHOICE%"=="10" call :remote remote_stop
if "%CHOICE%"=="11" call :remote remote_shell
pause
exit /b

:remote
set /p TARGET=Target server COM or CN [COM]: 
if "%TARGET%"=="" set "TARGET=COM"
call "%~dp0_common.bat" %~1 %TARGET%
exit /b
