@echo off
setlocal
where bash >nul 2>nul || (
  echo Git Bash or WSL bash is required. Install Git for Windows, then rerun this file.
  exit /b 1
)
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=local"
pushd "%~dp0..\.."
bash dev/sh/make_christopher_superadmin.sh "%TARGET%"
set "STATUS=%ERRORLEVEL%"
popd
exit /b %STATUS%
