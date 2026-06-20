@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo Permission actions:
echo   1^) Check local script permissions
echo   2^) Fix remote COM permissions
echo   3^) Fix remote CN permissions
echo   4^) Choose remote server to fix permissions
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" local_permissions
if "%CHOICE%"=="2" call "%~dp0_common.bat" remote_permissions COM
if "%CHOICE%"=="3" call "%~dp0_common.bat" remote_permissions CN
if "%CHOICE%"=="4" call :choose_server
pause
exit /b

:choose_server
set /p TARGET=Target server COM or CN [COM]: 
if "!TARGET!"=="" set "TARGET=COM"
call "%~dp0_common.bat" remote_permissions !TARGET!
exit /b
