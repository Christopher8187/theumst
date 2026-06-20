@echo off
setlocal EnableExtensions

echo Local testing uses hot reload:
echo   Webpage   http://localhost:5173
echo   Dashboard http://localhost:5174/dashboard/profile/
echo   FastAPI   http://localhost:8000
echo.
echo Choose an action:
echo   1^) Start local testing
echo   2^) Check local testing
echo   3^) Show local logs
echo   4^) Stop local testing
echo   5^) Build local images
echo   6^) Reset local volumes/database
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" local_start
if "%CHOICE%"=="2" call "%~dp0_common.bat" local_check
if "%CHOICE%"=="3" call "%~dp0_common.bat" local_logs
if "%CHOICE%"=="4" call "%~dp0_common.bat" local_stop
if "%CHOICE%"=="5" call "%~dp0_common.bat" local_build
if "%CHOICE%"=="6" call "%~dp0_common.bat" local_reset
pause
