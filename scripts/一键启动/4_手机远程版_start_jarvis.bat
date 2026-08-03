@echo off
:: ================================================================
::  Jarvis AI - Mobile Remote Edition
::  Starts backend + Cloudflare Tunnel for phone access anywhere
::  Pure ASCII display for cross-system compatibility
:: ================================================================
setlocal enabledelayedexpansion
title Jarvis AI - Mobile Remote
color 0B

echo.
echo  ================================================================
echo          JARVIS AI  -  MOBILE REMOTE EDITION
echo          (Backend + Cloudflare Tunnel for 4G/5G access)
echo  ================================================================
echo.

:: ===== Step 0: Locate project root =====
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "PROJECT_DIR=%PROJECT_DIR%\..\.."
pushd "%PROJECT_DIR%" 2>nul
set "PROJECT_DIR=%CD%"
popd

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "DATA_DIR=%BACKEND_DIR%\data"
set "LOGS_DIR=%PROJECT_DIR%\logs"
set "ENV_FILE=%BACKEND_DIR%\.env"
set "ENV_EXAMPLE=%BACKEND_DIR%\.env.example"
set "REQ_FILE=%BACKEND_DIR%\requirements.txt"
set "REQ_WIN7=%PROJECT_DIR%\requirements-win7.txt"
set "PORT=8000"
set "TUNNEL_LOG=%LOGS_DIR%\cloudflared.log"
set "BACKEND_LOG=%LOGS_DIR%\backend.log"
set "IS_WIN7=0"

echo  [INFO] Project: %PROJECT_DIR%
echo  [INFO] Backend:  %BACKEND_DIR%
echo.

:: ===== Step 1: Detect Windows version =====
echo  [1/10] Detecting Windows version ...
set "WIN_MAJOR=0"
for /f "tokens=2 delims==" %%v in ('wmic os get version /value 2^>nul ^| find "=" 2^>nul') do (
    for /f "tokens=1,2 delims=." %%a in ("%%v") do (
        set "WIN_MAJOR=%%a"
        set "WIN_MINOR=%%b"
    )
)
if "%WIN_MAJOR%"=="0" (
    ver | find "6.1" >nul && set "WIN_MAJOR=6"
    ver | find "10." >nul && set "WIN_MAJOR=10"
)
if %WIN_MAJOR% LSS 10 (
    set "IS_WIN7=1"
    echo        Detected: Win7/8 mode (no vector DB)
) else (
    echo        Detected: Win10/11 mode (full features)
)
echo.

:: ===== Step 2: Check Python =====
echo  [2/10] Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Python not found!
    if "%IS_WIN7%"=="1" (
        echo      Win7 needs Python 3.8.10:
        echo        https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
    ) else (
        echo      Install Python 3.10+ from: https://www.python.org/downloads/
    )
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        Python %PYVER% OK
echo.

:: ===== Step 3: Check cloudflared =====
echo  [3/10] Checking cloudflared ...
set "CF_BIN="
:: Check common locations
where cloudflared >nul 2>&1 && set "CF_BIN=cloudflared"
if not defined CF_BIN if exist "%PROJECT_DIR%\cloudflared.exe" set "CF_BIN=%PROJECT_DIR%\cloudflared.exe"
if not defined CF_BIN if exist "%PROJECT_DIR%\scripts\一键启动\cloudflared.exe" set "CF_BIN=%PROJECT_DIR%\scripts\一键启动\cloudflared.exe"
if not defined CF_BIN if exist "C:\Windows\System32\cloudflared.exe" set "CF_BIN=C:\Windows\System32\cloudflared.exe"

if not defined CF_BIN (
    echo.
    echo  [X] cloudflared not found!
    echo.
    echo      This script needs cloudflared to expose public URL.
    echo.
    if "%IS_WIN7%"=="1" (
        echo      Win7 download (last supported version 2023.8.2):
        echo        64-bit: https://github.com/cloudflare/cloudflared/releases/download/2023.8.2/cloudflared-windows-amd64.msi
        echo        32-bit: https://github.com/cloudflare/cloudflared/releases/download/2023.8.2/cloudflared-windows-386.msi
    ) else (
        echo      Win10/11 download (latest):
        echo        https://github.com/cloudflare/cloudflared/releases/latest
    )
    echo.
    echo      Install options:
    echo        1. Run the .msi installer (installs to System32, auto PATH)
    echo        2. OR download cloudflared.exe and put it in:
    echo           %PROJECT_DIR%\
    echo           or: %PROJECT_DIR%\scripts\一键启动\
    echo.
    choice /C YN /M "Try to download cloudflared.exe automatically now"
    if errorlevel 2 (
        pause
        exit /b 1
    )
    echo.
    echo        Downloading cloudflared.exe ...
    if "%IS_WIN7%"=="1" (
        :: Win7: use 2023.8.2 version
        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/download/2023.8.2/cloudflared-windows-amd64.exe' -OutFile '%PROJECT_DIR%\cloudflared.exe' -UseBasicParsing } catch { exit 1 }"
    ) else (
        :: Win10+: use latest
        powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe' -OutFile '%PROJECT_DIR%\cloudflared.exe' -UseBasicParsing } catch { exit 1 }"
    )
    if exist "%PROJECT_DIR%\cloudflared.exe" (
        set "CF_BIN=%PROJECT_DIR%\cloudflared.exe"
        echo        Downloaded to: %PROJECT_DIR%\cloudflared.exe
    ) else (
        echo  [X] Auto-download failed. Please download manually.
        pause
        exit /b 1
    )
) else (
    echo        Found: %CF_BIN%
)
echo.

:: ===== Step 4: Auto-create .env =====
echo  [4/10] Checking .env config ...
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        Created .env from .env.example
    )
) else (
    echo        .env exists
)
echo.

:: ===== Step 5: Create virtual environment =====
echo  [5/10] Setting up virtual environment ...
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  [X] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo        Virtual env created
) else (
    echo        Virtual env exists
)
echo.

:: ===== Step 6: Activate + upgrade pip =====
echo  [6/10] Activating env and upgrading pip ...
call "%VENV_DIR%\Scripts\activate.bat"
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1
python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo        pip ready
echo.

:: ===== Step 7: Install dependencies =====
echo  [7/10] Checking dependencies ...
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" >nul 2>&1
if errorlevel 1 (
    if "%IS_WIN7%"=="1" (
        if exist "%REQ_WIN7%" (
            pip install -r "%REQ_WIN7%"
        ) else (
            pip install fastapi==0.110.3 "uvicorn[standard]==0.27.1" pydantic==2.6.4 pydantic-settings==2.2.1 SQLAlchemy==2.0.29 aiosqlite==0.19.0 httpx==0.27.0 python-dotenv==1.0.1 APScheduler==3.10.4
        )
    ) else (
        if exist "%REQ_FILE%" (
            pip install -r "%REQ_FILE%"
        ) else (
            pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite pydantic pydantic-settings httpx python-multipart jinja2 apscheduler python-dotenv chromadb sentence-transformers jieba
        )
    )
    if errorlevel 1 (
        echo  [X] Install failed!
        pause
        exit /b 1
    )
    echo        Dependencies installed
) else (
    echo        Dependencies present
)
:: Try to install qrcode for QR display
pip install qrcode >nul 2>&1
echo.

:: ===== Step 8: Create folders + free port =====
echo  [8/10] Preparing runtime ...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: Free port 8000
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        Freeing port %PORT% ...
    for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
        taskkill /f /pid %%p >nul 2>&1
    )
    ping 127.0.0.1 -n 3 >nul
)
echo        Port %PORT% ready
echo.

:: ===== Step 9: Start backend in background =====
echo  [9/10] Starting Jarvis backend (background) ...
if "%IS_WIN7%"=="1" set "KIZUNA_SKIP_VECTOR_DB=1"

cd /d "%BACKEND_DIR%"
:: Start backend in minimized window, log to file
start "Jarvis Backend" /min cmd /c "python -m uvicorn app:app --host 0.0.0.0 --port %PORT% > "%BACKEND_LOG%" 2>&1"

:: Wait for backend to be ready
echo        Waiting for backend to start ...
set "BACKEND_READY=0"
for /l %%i in (1,1,30) do (
    ping 127.0.0.1 -n 2 >nul
    powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:%PORT%/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode } catch { 0 }" 2>nul | find "200" >nul
    if not errorlevel 1 (
        set "BACKEND_READY=1"
        goto :backend_ok
    )
    echo        ... waiting [%%i/30]
)
:backend_ok
if "%BACKEND_READY%"=="1" (
    echo        Backend ready at http://127.0.0.1:%PORT%
) else (
    echo        [!] Backend not responding yet, continuing anyway...
    echo        Check backend.log: type "%BACKEND_LOG%"
)
echo.

:: ===== Step 10: Start Cloudflare Tunnel =====
echo  [10/10] Starting Cloudflare Tunnel ...
echo.
echo  ================================================================
echo.
echo    Starting tunnel... this provides a PUBLIC URL for your phone
echo    Works on 4G/5G, no router config, no public IP needed
echo.
echo    [INFO] Tunnel log: %TUNNEL_LOG%
echo.
echo    Please wait 5-15 seconds for tunnel URL ...
echo.
echo  ================================================================
echo.

:: Clear old tunnel log
if exist "%TUNNEL_LOG%" del "%TUNNEL_LOG%"

:: Start cloudflared in background, log to file
start "Cloudflare Tunnel" /min cmd /c ""%CF_BIN%" tunnel --url http://localhost:%PORT% --no-autoupdate > "%TUNNEL_LOG%" 2>&1"

:: Wait and parse the tunnel URL from log
set "TUNNEL_URL="
for /l %%i in (1,1,40) do (
    ping 127.0.0.1 -n 2 >nul
    if exist "%TUNNEL_LOG%" (
        :: Look for trycloudflare URL in log
        for /f "tokens=*" %%l in ('findstr /R "https://.*trycloudflare.com" "%TUNNEL_LOG%" 2^>nul') do (
            for %%w in (%%l) do (
                echo %%w | findstr /R "^https://.*trycloudflare.com" >nul
                if not errorlevel 1 (
                    set "TUNNEL_URL=%%w"
                    goto :got_url
                )
            )
        )
    )
    echo        ... waiting for tunnel [%%i/40]
)
:got_url

:: Clean up trailing characters
set "TUNNEL_URL=%TUNNEL_URL:!=%"
set "TUNNEL_URL=%TUNNEL_URL:,=%"
set "TUNNEL_URL=%TUNNEL_URL:.<=%"
set "TUNNEL_URL=%TUNNEL_URL:>=%"

if not defined TUNNEL_URL (
    echo.
    echo  ================================================================
    echo    [!] Could not auto-detect tunnel URL
    echo.
    echo    Please check the tunnel log:
    echo      type "%TUNNEL_LOG%"
    echo.
    echo    Look for a line containing https://xxx.trycloudflare.com
    echo    Open that URL on your phone.
    echo.
    echo    Backend is running at:  http://127.0.0.1:%PORT%
    echo  ================================================================
    echo.
    echo  Press Ctrl+C to stop everything, or close this window.
    echo.
    pause >nul
    goto :cleanup
)

echo.
echo  ================================================================
echo.
echo    SUCCESS! Jarvis is now publicly accessible:
echo.
echo    PUBLIC URL:
echo.
echo      %TUNNEL_URL%
echo.
echo    Open this URL on your phone (4G/5G/WiFi all work)
echo.
echo    Local access:  http://127.0.0.1:%PORT%
echo.
echo  ================================================================
echo.

:: Try to generate and display QR code with Python
python -c "import qrcode" >nul 2>&1
if not errorlevel 1 (
    echo    Generating QR code ...
    echo.
    python -c "import qrcode, sys; qr = qrcode.QRCode(border=1); qr.add_data('%TUNNEL_URL%'); qr.print_ascii(invert=True)"
    echo.
    echo    Scan this QR code with your phone camera
    echo.
) else (
    echo    [Tip] Install qrcode library for QR display:
    echo       pip install qrcode
    echo.
)

echo  ================================================================
echo    Tunnel is running. Keep this window open!
echo.
echo    To stop everything:  press Ctrl+C in this window
echo  ================================================================
echo.

:: Open URL in default browser too
start "" "%TUNNEL_URL%"

:: Wait for user to stop
:waitloop
echo  Tunnel running... Press Ctrl+C to stop.
ping 127.0.0.1 -n 30 >nul
goto :waitloop

:cleanup
:: Kill backend and tunnel processes
echo.
echo  Stopping backend and tunnel ...
taskkill /fi "WINDOWTITLE eq Jarvis Backend*" /f >nul 2>&1
taskkill /fi "WINDOWTITLE eq Cloudflare Tunnel*" /f >nul 2>&1
:: Also kill by image name as backup
taskkill /im cloudflared.exe /f >nul 2>&1
:: Kill python on port 8000
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)
echo  Stopped.
pause >nul
endlocal
