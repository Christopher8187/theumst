@echo off
setlocal EnableExtensions

echo Deployment actions:
echo   1^) Start deployment-style stack locally
echo   2^) Check local deployment-style stack
echo   3^) Show local deployment logs
echo   4^) Stop local deployment-style stack
echo   5^) Reset local deployment volumes/database
echo   6^) Fully deploy theumst.com ^(COM^)
echo   7^) Fully deploy theumst.cn ^(CN; interactive DNS certificate if needed^)
set /p CHOICE=Action [1]: 
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" call "%~dp0_common.bat" deploy_start
if "%CHOICE%"=="2" call "%~dp0_common.bat" deploy_check
if "%CHOICE%"=="3" call "%~dp0_common.bat" deploy_logs
if "%CHOICE%"=="4" call "%~dp0_common.bat" deploy_stop
if "%CHOICE%"=="5" call "%~dp0_common.bat" deploy_reset
if "%CHOICE%"=="6" call "%~dp0deploy_com.bat"
if "%CHOICE%"=="7" call "%~dp0deploy_cn.bat"
exit /b %ERRORLEVEL%
