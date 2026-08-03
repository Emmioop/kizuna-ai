@echo off
:: ================================================================
::  Jarvis AI - Windows 7 Edition (Pure ASCII for GBK safety)
::  Compatible with Python 3.8.10 only
::  Skips vector DB (chromadb) for stability on old systems
:: ================================================================
setlocal enabledelayedexpansion
title Jarvis AI - Win7 Edition
color 0B

echo.
echo  ================================================================
echo              JARVIS AI  -  Windows 7 EDITION
echo  ================================================================
echo.

:: ===== Step 0: Locate project root =====
set "PROJECT_DIR=%~dp0"
:: Strip trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
:: Go up 2 levels: scripts/一键启动/ -> scripts/ -> kizuna-ai/
set "PROJECT_DIR=%PROJECT_DIR%\..\.."
:: Resolve to absolute path
pushd "%PROJECT_DIR%" 2>nul
set "PROJECT_DIR=%CD%"
popd

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "DATA_DIR=%BACKEND_DIR%\data"
set "LOGS_DIR=%PROJECT_DIR%\logs"
set "ENV_FILE=%BACKEND_DIR%\.env"
set "ENV_EXAMPLE=%BACKEND_DIR%\.env.example"
set "REQ_WIN7=%PROJECT_DIR%\requirements-win7.txt"
set "PORT=8000"

echo  [INFO] Project: %PROJECT_DIR%
echo  [INFO] Backend:  %BACKEND_DIR%
echo.

:: ===== Step 1: Check Python (must be 3.8.x for Win7) =====
echo  [1/8] Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Python not found!
    echo.
    echo      Win7 ONLY supports Python 3.8.10 (newer versions do not install)
    echo.
    echo      Download 64-bit:
    echo        https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
    echo      Download 32-bit:
    echo        https://www.python.org/ftp/python/3.8.10/python-3.8.10.exe
    echo.
    echo      Install tips:
    echo        - Check "Add Python 3.8 to PATH" at the bottom
    echo        - Install to C:\Python38 (no spaces in path)
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        Found Python %PYVER%

:: Verify it is 3.8.x
echo %PYVER% | findstr /R "^3\.8\." >nul
if errorlevel 1 (
    echo.
    echo  [!] Warning: Python %PYVER% may not work on Win7
    echo      Recommended: Python 3.8.10
    echo      If install fails, download from:
    echo        https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
    echo.
    choice /C YN /M "Continue anyway"
    if errorlevel 2 exit /b 1
)
echo        Python version OK
echo.

:: ===== Step 2: Check backend folder =====
echo  [2/8] Checking project structure ...
if not exist "%BACKEND_DIR%\app.py" (
    if not exist "%BACKEND_DIR%\kizuna\app.py" (
        echo  [X] Cannot find backend folder!
        echo      Please make sure this script is inside kizuna-ai\scripts\
        pause
        exit /b 1
    )
)
echo        Structure OK
echo.

:: ===== Step 3: Auto-create .env =====
echo  [3/8] Checking .env config ...
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        Created .env from .env.example
        echo.
        echo  ================================================================
        echo   IMPORTANT: First run needs LLM API Key
        echo  ================================================================
        echo   1. After browser opens, go to Settings page
        echo   2. Recommended: Zhipu GLM (free quota)
        echo      https://open.bigmodel.cn/
        echo   3. Without API Key, Jarvis can start but cannot chat
        echo  ================================================================
        echo.
    )
) else (
    echo        .env already exists
)
echo.

:: ===== Step 4: Create virtual environment =====
echo  [4/8] Setting up virtual environment ...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo        Virtual env exists
) else (
    echo        Creating virtual environment ...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  [X] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo        Virtual env created
)
echo.

:: ===== Step 5: Activate + upgrade pip + use China mirror =====
echo  [5/8] Activating env and upgrading pip ...
call "%VENV_DIR%\Scripts\activate.bat"

:: Use Tsinghua mirror (faster in China)
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo        pip ready
echo.

:: ===== Step 6: Install Win7-compatible dependencies =====
echo  [6/8] Checking dependencies ...
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" >nul 2>&1
if errorlevel 1 (
    if exist "%REQ_WIN7%" (
        echo        Installing Win7-locked dependencies ...
        echo        Using Tsinghua mirror, please wait 5-15 min ...
        echo.
        pip install -r "%REQ_WIN7%"
        if errorlevel 1 (
            echo.
            echo  [!] Retry ...
            pip install -r "%REQ_WIN7%" --retries 5 --timeout 180
        )
    ) else (
        echo        requirements-win7.txt not found, installing minimal set ...
        pip install fastapi==0.110.3 "uvicorn[standard]==0.27.1" pydantic==2.6.4 pydantic-settings==2.2.1 SQLAlchemy==2.0.29 aiosqlite==0.19.0 httpx==0.27.0 python-dotenv==1.0.1 APScheduler==3.10.4
    )
    if errorlevel 1 (
        echo.
        echo  [X] Install failed! Check network, then retry.
        pause
        exit /b 1
    )
    echo.
    echo        Dependencies installed
) else (
    echo        Dependencies present
)
echo.

:: ===== Step 7: Create folders + free port =====
echo  [7/8] Preparing runtime ...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: Free port 8000 if occupied
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        Port %PORT% busy, releasing ...
    for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
        taskkill /f /pid %%p >nul 2>&1
    )
    :: Wait 2 seconds (ping trick for Win7 compatibility)
    ping 127.0.0.1 -n 3 >nul
)
echo        Port %PORT% ready
echo.

:: ===== Step 8: Start Jarvis =====
echo  [8/8] Starting Jarvis AI ...
echo.
echo  ================================================================
echo.
echo    Jarvis starting...
echo.
echo    Browser will open in 5 seconds at:
echo      http://127.0.0.1:%PORT%
echo.
echo    Phone access (same WiFi):
echo      1. Run: ipconfig
echo      2. Find IPv4 Address (e.g. 192.168.1.100)
echo      3. Open http://YOUR_IP:%PORT% on phone
echo.
echo    First time? Go to Settings page, fill LLM API Key
echo.
echo    Stop Jarvis: press Ctrl+C in this window
echo.
echo  ================================================================
echo.

:: Open browser after 5 seconds (using start /b + ping delay)
start "" /b cmd /c "ping 127.0.0.1 -n 6 >nul && start http://127.0.0.1:%PORT%/"

:: Set env var to skip vector DB (chromadb not supported on Win7)
set "KIZUNA_SKIP_VECTOR_DB=1"

cd /d "%BACKEND_DIR%"

:: Log file with timestamp
set "D=%DATE%"
set "T=%TIME%"
set "D=%D:/=_%"
set "T=%T: =0%"
set "T=%T::=_%"
set "LOG_FILE=%LOGS_DIR%\jarvis_%D%_%T%.log"

echo  [INFO] Log file: %LOG_FILE%
echo  [INFO] Vector DB: DISABLED (Win7 mode)
echo  [INFO] Starting uvicorn ...
echo.

:: Try PowerShell Tee-Object first, fallback to direct run
where powershell >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "& { python -m uvicorn app:app --host 0.0.0.0 --port %PORT% 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append }"
) else (
    :: No PowerShell, redirect to log + show on screen
    python -m uvicorn app:app --host 0.0.0.0 --port %PORT%
)

echo.
echo  ================================================================
echo    Jarvis stopped.
echo    Log saved to: %LOG_FILE%
echo  ================================================================
pause >nul
endlocal
