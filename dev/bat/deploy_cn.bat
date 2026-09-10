@echo off
setlocal EnableExtensions
where bash >nul 2>nul || (
  echo Git Bash or WSL bash is required. Install Git for Windows, then rerun this file.
  exit /b 1
)

rem Pass the real Windows SSH directory through either Git Bash or WSL.
rem WSLENV /p performs Windows-to-WSL path translation automatically.
set "THEUMST_SSH_KEY_DIR=%USERPROFILE%\.ssh"
if defined WSLENV (
  set "WSLENV=THEUMST_SSH_KEY_DIR/p:%WSLENV%"
) else (
  set "WSLENV=THEUMST_SSH_KEY_DIR/p"
)

pushd "%~dp0..\.."
bash dev/sh/agent_deploy.sh CN %*
set "STATUS=%ERRORLEVEL%"
popd
exit /b %STATUS%
