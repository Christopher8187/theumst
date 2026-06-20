@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo Certificate actions:
echo   1^) Renew/issue COM certificate
echo   2^) Renew/issue CN certificate
echo   3^) Choose target server
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" remote_certs COM
if "%CHOICE%"=="2" call "%~dp0_common.bat" remote_certs CN
if "%CHOICE%"=="3" call :choose_server
pause
exit /b

:choose_server
set /p TARGET=Target server COM or CN [COM]: 
if "!TARGET!"=="" set "TARGET=COM"
call "%~dp0_common.bat" remote_certs !TARGET!
exit /b
