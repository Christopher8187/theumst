@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ACTION=%~1"
set "TARGET=%~2"
set "ROOT=%~dp0..\.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
set "LOCAL_COMPOSE=%ROOT%\compose.local.yml"
set "DEPLOY_COMPOSE=%ROOT%\compose.deploy.yml"
set "ENV_FILE=%ROOT%\.env"
call :load_env

if "%ACTION%"=="" goto usage
if /I "%ACTION%"=="show_env" goto show_env
if /I "%ACTION%"=="local_build" goto local_build
if /I "%ACTION%"=="local_start" goto local_start
if /I "%ACTION%"=="local_check" goto local_check
if /I "%ACTION%"=="local_logs" goto local_logs
if /I "%ACTION%"=="local_stop" goto local_stop
if /I "%ACTION%"=="local_reset" goto local_reset
if /I "%ACTION%"=="deploy_build" goto deploy_build
if /I "%ACTION%"=="deploy_start" goto deploy_start
if /I "%ACTION%"=="deploy_check" goto deploy_check
if /I "%ACTION%"=="deploy_logs" goto deploy_logs
if /I "%ACTION%"=="deploy_stop" goto deploy_stop
if /I "%ACTION%"=="deploy_reset" goto deploy_reset
if /I "%ACTION%"=="remote_setup" goto remote_setup
if /I "%ACTION%"=="remote_permissions" goto remote_permissions
if /I "%ACTION%"=="remote_upload" goto remote_upload
if /I "%ACTION%"=="remote_start" goto remote_start
if /I "%ACTION%"=="remote_stop" goto remote_stop
if /I "%ACTION%"=="remote_check" goto remote_check
if /I "%ACTION%"=="remote_logs" goto remote_logs
if /I "%ACTION%"=="remote_shell" goto remote_shell
if /I "%ACTION%"=="remote_certs" goto remote_certs
if /I "%ACTION%"=="remote_full_deploy" goto remote_full_deploy
if /I "%ACTION%"=="local_permissions" goto local_permissions

echo Unknown helper action: %ACTION%
goto usage

:load_env
if exist "%ENV_FILE%" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
        set "ENV_KEY=%%A"
        if not "!ENV_KEY!"=="" if not "!ENV_KEY:~0,1!"=="#" set "%%A=%%B"
    )
)
if "%SERVER%"=="" set "SERVER=LOCAL"
if "%REMOTE_SERVER%"=="" set "REMOTE_SERVER=COM"
if "%HTTP_PORT%"=="" set "HTTP_PORT=8080"
if "%SSH_KEY_DIR%"=="" set "SSH_KEY_DIR=%USERPROFILE%\.ssh"
if /I "%SSH_KEY_DIR%"=="__AUTO__" set "SSH_KEY_DIR=%USERPROFILE%\.ssh"
if "%TARGET%"=="" set "TARGET=%REMOTE_SERVER%"
if /I "%TARGET%"=="com" set "TARGET=COM"
if /I "%TARGET%"=="cn" set "TARGET=CN"
exit /b 0

:show_env
echo Project root:     %ROOT%
echo Environment file: %ENV_FILE%
echo SERVER:           %SERVER%
echo REMOTE_SERVER:    %REMOTE_SERVER%
echo HTTP_PORT:        %HTTP_PORT%
echo.
echo Local URLs:
echo   Webpage:   http://localhost:5173
echo   Dashboard: http://localhost:5174/dashboard/profile/
echo   FastAPI:   http://localhost:8000
echo   Nginx:     http://localhost:%HTTP_PORT%
exit /b 0

:need_docker
docker info >nul 2>nul
if errorlevel 1 (
    echo Docker is missing or not running. Start Docker Desktop, then try again.
    exit /b 1
)
exit /b 0

:local_build
call :need_docker || exit /b 1
echo Building local hot-reload Docker images...
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" build
exit /b %ERRORLEVEL%

:local_start
call :need_docker || exit /b 1
echo Starting local hot-reload stack...
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" up --build -d
echo.
echo Open:
echo   Main webpage: http://localhost:5173
echo   Dashboard:    http://localhost:5174/dashboard/profile/
echo   FastAPI:      http://localhost:8000
exit /b %ERRORLEVEL%

:local_check
call :need_docker || exit /b 1
echo Local containers:
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" ps
echo.
echo FastAPI health:
curl -fsS http://localhost:8000/health 2>nul
echo.
exit /b %ERRORLEVEL%

:local_logs
call :need_docker || exit /b 1
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" logs -f
exit /b %ERRORLEVEL%

:local_stop
call :need_docker || exit /b 1
echo Stopping local hot-reload stack...
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" down
exit /b %ERRORLEVEL%

:local_reset
call :need_docker || exit /b 1
echo Stopping local stack and deleting local Docker volumes...
cd /d "%ROOT%"
docker compose -f "%LOCAL_COMPOSE%" down -v
exit /b %ERRORLEVEL%

:deploy_build
call :need_docker || exit /b 1
echo Building deployment-style Docker images...
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" build
exit /b %ERRORLEVEL%

:deploy_start
call :need_docker || exit /b 1
echo Starting deployment-style nginx stack...
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" up --build -d
echo.
echo Open: http://localhost:%HTTP_PORT%
exit /b %ERRORLEVEL%

:deploy_check
call :need_docker || exit /b 1
echo Deployment containers:
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" ps
echo.
echo Nginx health path:
curl -fsS http://localhost:%HTTP_PORT%/health 2>nul
echo.
exit /b %ERRORLEVEL%

:deploy_logs
call :need_docker || exit /b 1
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" logs -f
exit /b %ERRORLEVEL%

:deploy_stop
call :need_docker || exit /b 1
echo Stopping deployment-style nginx stack...
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" down
exit /b %ERRORLEVEL%

:deploy_reset
call :need_docker || exit /b 1
echo Stopping deployment stack and deleting deployment Docker volumes...
cd /d "%ROOT%"
docker compose -f "%DEPLOY_COMPOSE%" down -v
exit /b %ERRORLEVEL%

:local_permissions
powershell -NoProfile -Command "Get-ChildItem -Path '%ROOT%\dev\sh' -Filter '*.sh' | ForEach-Object { $_.Attributes = $_.Attributes -band (-bnot [IO.FileAttributes]::ReadOnly) }"
echo Checked dev\sh files. On Linux/Git Bash, run chmod +x dev/sh/*.sh if needed.
exit /b 0

:remote_context
if /I "%TARGET%"=="com" set "TARGET=COM"
if /I "%TARGET%"=="cn" set "TARGET=CN"
call set "KEY_NAME=%%SSH_KEY_%TARGET%%%"
call set "SSH_USER=%%SSH_USER_%TARGET%%%"
call set "SSH_HOST=%%SSH_HOST_%TARGET%%%"
call set "REMOTE_ROOT=%%REMOTE_ROOT_%TARGET%%%"
call set "REMOTE_URL=%%REMOTE_URL_%TARGET%%%"
call set "DOMAIN=%%DOMAIN_%TARGET%%%"
call set "CERT_NAME=%%CERT_%TARGET%%%"
call set "CERT_MODE=%%CERT_MODE_%TARGET%%%"
call set "SUDO_PASSWORD=%%SUDO_PASSWORD_%TARGET%%%"
if "%KEY_NAME%%SSH_USER%%SSH_HOST%"=="" (
    echo Missing SSH settings for %TARGET% in .env
    exit /b 1
)
set "KEY=%SSH_KEY_DIR%\%KEY_NAME%"
set "REMOTE=%SSH_USER%@%SSH_HOST%"
if not exist "%KEY%" (
    echo Missing SSH key: %KEY%
    exit /b 1
)
if "%SUDO_PASSWORD%"=="" (
    set "SUDO=sudo"
) else (
    set "SUDO=printf '%%s\n' '%SUDO_PASSWORD%' ^| sudo -S -p ''"
)
exit /b 0

:remote_setup
call :remote_context || exit /b 1
echo Installing/updating Docker and certbot on %REMOTE%...
ssh -i "%KEY%" "%REMOTE%" "%SUDO% apt update && %SUDO% apt install -y ca-certificates curl gnupg rsync certbot && curl -fsSL https://get.docker.com -o /tmp/get-docker.sh && %SUDO% sh /tmp/get-docker.sh && %SUDO% usermod -aG docker '%SSH_USER%'"
exit /b %ERRORLEVEL%

:remote_permissions
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
echo Fixing permissions on %REMOTE%:%REMOTE_ROOT%...
ssh -i "%KEY%" "%REMOTE%" "mkdir -p '%REMOTE_ROOT%' && %SUDO% chown -R '%SSH_USER%:%SSH_USER%' '%REMOTE_ROOT%' && chmod -R u+rwX '%REMOTE_ROOT%' && %SUDO% usermod -aG docker '%SSH_USER%' || true"
exit /b %ERRORLEVEL%

:remote_upload
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
set "TARFILE=%TEMP%\theumst_upload_%RANDOM%.tar"
echo Preparing upload archive...
cd /d "%ROOT%"
tar --exclude=.git --exclude=.local --exclude=backend/python/.venv --exclude=frontend/webpage/node_modules --exclude=frontend/webpage/dist --exclude=frontend/dashboard/node_modules --exclude=frontend/dashboard/dist -cf "%TARFILE%" .
echo Uploading to %REMOTE%:%REMOTE_ROOT%...
ssh -i "%KEY%" "%REMOTE%" "mkdir -p '%REMOTE_ROOT%'"
scp -i "%KEY%" "%TARFILE%" "%REMOTE%:%REMOTE_ROOT%/theumst_upload.tar"
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' && tar -xf theumst_upload.tar && rm theumst_upload.tar"
del "%TARFILE%" >nul 2>nul
exit /b %ERRORLEVEL%

:remote_start
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
echo Starting Docker deployment on %REMOTE%...
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' && SERVER='%TARGET%' docker compose -f compose.deploy.yml up --build -d"
exit /b %ERRORLEVEL%

:remote_stop
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
echo Stopping Docker deployment on %REMOTE%...
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' && docker compose -f compose.deploy.yml down"
exit /b %ERRORLEVEL%

:remote_check
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
echo Remote containers on %REMOTE%:
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' && docker compose -f compose.deploy.yml ps"
if not "%REMOTE_URL%"=="" echo URL: %REMOTE_URL%
exit /b %ERRORLEVEL%

:remote_logs
call :remote_context || exit /b 1
if "%REMOTE_ROOT%"=="" (
    echo Missing REMOTE_ROOT_%TARGET% in .env
    exit /b 1
)
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' && docker compose -f compose.deploy.yml logs --tail=120"
exit /b %ERRORLEVEL%

:remote_shell
call :remote_context || exit /b 1
ssh -i "%KEY%" "%REMOTE%"
exit /b %ERRORLEVEL%

:remote_certs
call :remote_context || exit /b 1
if "%DOMAIN%"=="" (
    echo Missing DOMAIN_%TARGET% in .env
    exit /b 1
)
if "%CERT_NAME%"=="" set "CERT_NAME=%DOMAIN%"
if "%CERT_EMAIL%"=="" set "CERT_EMAIL=admin@%DOMAIN%"
if /I "%CERT_MODE%"=="manual" (
    echo CERT_MODE_%TARGET% is manual.
    echo Suggested command:
    echo sudo certbot certonly --manual --preferred-challenges dns -d "%DOMAIN%" -d "*.%DOMAIN%" --cert-name "%CERT_NAME%"
    ssh -i "%KEY%" "%REMOTE%"
    exit /b %ERRORLEVEL%
)
echo Renewing/issuing certificate for %DOMAIN% on %REMOTE%...
ssh -i "%KEY%" "%REMOTE%" "cd '%REMOTE_ROOT%' 2>/dev/null || true; docker compose -f compose.deploy.yml stop nginx >/dev/null 2>&1 || true; %SUDO% apt update && %SUDO% apt install -y certbot; %SUDO% certbot certonly --standalone --non-interactive --agree-tos -m '%CERT_EMAIL%' --cert-name '%CERT_NAME%' -d '%DOMAIN%' -d 'www.%DOMAIN%' || %SUDO% certbot renew; cd '%REMOTE_ROOT%' 2>/dev/null && docker compose -f compose.deploy.yml up -d nginx >/dev/null 2>&1 || true"
exit /b %ERRORLEVEL%

:remote_full_deploy
call "%~f0" remote_permissions %TARGET% || exit /b 1
call "%~f0" remote_upload %TARGET% || exit /b 1
call "%~f0" remote_start %TARGET% || exit /b 1
call "%~f0" remote_check %TARGET% || exit /b 1
exit /b 0

:usage
echo This is an internal helper. Run the button scripts in dev\bat instead.
exit /b 1
