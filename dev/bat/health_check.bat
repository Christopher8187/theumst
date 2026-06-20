@echo off
setlocal EnableExtensions

echo Health checks:
echo   1^) Local testing stack
echo   2^) Deployment-style local nginx stack
echo   3^) Remote COM server
echo   4^) Remote CN server
echo   5^) All local checks
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" local_check
if "%CHOICE%"=="2" call "%~dp0_common.bat" deploy_check
if "%CHOICE%"=="3" call "%~dp0_common.bat" remote_check COM
if "%CHOICE%"=="4" call "%~dp0_common.bat" remote_check CN
if "%CHOICE%"=="5" (
    call "%~dp0_common.bat" local_check
    call "%~dp0_common.bat" deploy_check
)
pause
