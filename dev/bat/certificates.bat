@echo off
setlocal
where bash >nul 2>nul || (
  echo Git Bash or WSL bash is required. Install Git for Windows, then rerun this file.
  exit /b 1
)
pushd "%~dp0..\.."
bash dev/sh/certificates.sh
set "STATUS=%ERRORLEVEL%"
popd
exit /b %STATUS%
