@echo off
:: ================================================================
::  Jarvis AI - Universal Edition (Auto-detect Win7/Win10/Win11)
::  Pure ASCII display for cross-system compatibility
::  Auto-selects dependencies based on Windows version
:: ================================================================
setlocal enabledelayedexpansion
title Jarvis AI - Universal One-Click Start
color 0B

echo.
echo  ================================================================
echo          JARVIS AI  -  UNIVERSAL ONE-CLICK START
echo          (Auto-detects Windows 7 / 10 / 11)
echo  ================================================================
echo.

:: ===== Step 0: Locate project root =====
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
:: Go up 2 levels: scripts/一键启动/ -> scripts/ -> kizuna-ai/
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
set "IS_WIN7=0"
set "USE_VECTOR_DB=1"

echo  [INFO] Project: %PROJECT_DIR%
echo  [INFO] Backend:  %BACKEND_DIR%
echo.

:: ===== Step 1: Detect Windows version =====
echo  [1/9] Detecting Windows version ...
set "WIN_MAJOR=0"
:: Method 1: wmic (works on Win7+)
for /f "tokens=2 delims==" %%v in ('wmic os get version /value 2^>nul ^| find "=" 2^>nul') do (
    for /f "tokens=1,2 delims=." %%a in ("%%v") do (
        set "WIN_MAJOR=%%a"
        set "WIN_MINOR=%%b"
    )
)
:: Method 2: ver command fallback
if "%WIN_MAJOR%"=="0" (
    ver | find "6.1" >nul && (set "WIN_MAJOR=6" & set "WIN_MINOR=1")
    ver | find "6.2" >nul && (set "WIN_MAJOR=6" & set "WIN_MINOR=2")
    ver | find "6.3" >nul && (set "WIN_MAJOR=6" & set "WIN_MINOR=3")
    ver | find "10." >nul && (set "WIN_MAJOR=10")
)

:: Determine mode based on Windows version
:: Win7 = 6.1, Win8 = 6.2, Win8.1 = 6.3, Win10/11 = 10+
if %WIN_MAJOR% LSS 10 (
    set "IS_WIN7=1"
    set "USE_VECTOR_DB=0"
    echo        Detected: Windows 6.%WIN_MINOR%  (Win7/8 mode)
    echo        Mode:    Simplified (no vector DB)
) else (
    echo        Detected: Windows %WIN_MAJOR%.%WIN_MINOR%  (Win10/11 mode)
    echo        Mode:    Full (with vector DB)
)
echo.

:: ===== Step 2: Check Python =====
echo  [2/9] Checking Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] Python not found!
    echo.
    if "%IS_WIN7%"=="1" (
        echo      Win7 ONLY supports Python 3.8.10:
        echo        https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
        echo      Install tips: check "Add Python to PATH"
    ) else (
        echo      Please install Python 3.10+ from:
        echo        https://www.python.org/downloads/
        echo      Install tips: check "Add Python to PATH"
    )
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        Found Python %PYVER%

:: Verify Python version matches system
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set "PYMAJ=%%a"
    set "PYMIN=%%b"
)
if "%IS_WIN7%"=="1" (
    :: Win7: recommend 3.8.x
    if not "%PYMAJ%"=="3" goto :pywarn
    if not "%PYMIN%"=="8" goto :pywarn
    echo        Python version matches Win7 (3.8.x)  OK
) else (
    :: Win10+: recommend 3.10+
    if %PYMAJ% LSS 3 goto :pywarn
    if %PYMAJ% EQU 3 if %PYMIN% LSS 10 goto :pywarn
    echo        Python version OK for Win10+
)
goto :pyok
:pywarn
echo        [!] Warning: Python %PYVER% may have compatibility issues
echo        Continue anyway...
:pyok
echo.

:: ===== Step 3: Check backend folder =====
echo  [3/9] Checking project structure ...
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

:: ===== Step 4: Auto-create .env =====
echo  [4/9] Checking .env config ...
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

:: ===== Step 5: Create virtual environment =====
echo  [5/9] Setting up virtual environment ...
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

:: ===== Step 6: Activate + upgrade pip + China mirror =====
echo  [6/9] Activating env and upgrading pip ...
call "%VENV_DIR%\Scripts\activate.bat"

pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo        pip ready
echo.

:: ===== Step 7: Install dependencies (auto-select by OS) =====
echo  [7/9] Checking dependencies ...
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" >nul 2>&1
if errorlevel 1 (
    if "%IS_WIN7%"=="1" (
        :: Win7 mode: use locked requirements
        echo        [Win7 mode] Installing Win7-locked dependencies ...
        if exist "%REQ_WIN7%" (
            pip install -r "%REQ_WIN7%"
            if errorlevel 1 (
                echo  [!] Retry ...
                pip install -r "%REQ_WIN7%" --retries 5 --timeout 180
            )
        ) else (
            pip install fastapi==0.110.3 "uvicorn[standard]==0.27.1" pydantic==2.6.4 pydantic-settings==2.2.1 SQLAlchemy==2.0.29 aiosqlite==0.19.0 httpx==0.27.0 python-dotenv==1.0.1 APScheduler==3.10.4
        )
    ) else (
        :: Win10+ mode: use full requirements
        echo        [Win10+ mode] Installing full dependencies ...
        echo        (includes chromadb for vector memory)
        if exist "%REQ_FILE%" (
            pip install -r "%REQ_FILE%"
            if errorlevel 1 (
                echo  [!] Retry ...
                pip install -r "%REQ_FILE%" --retries 5 --timeout 180
            )
        ) else (
            pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite pydantic pydantic-settings httpx python-multipart jinja2 apscheduler python-dotenv chromadb sentence-transformers jieba
        )
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
    :: Base deps present, check vector DB on Win10+
    if not "%IS_WIN7%"=="1" (
        python -c "import chromadb" >nul 2>&1
        if errorlevel 1 (
            echo        Base deps present, installing vector DB ...
            pip install chromadb sentence-transformers jieba >nul 2>&1
            if not errorlevel 1 (
                echo        Vector DB installed
            ) else (
                echo        [!] Vector DB install failed, using keyword search
                set "USE_VECTOR_DB=0"
            )
        ) else (
            echo        All dependencies present
        )
    ) else (
        echo        Dependencies present (Win7 mode)
    )
)
echo.

:: ===== Step 8: Create folders + free port =====
echo  [8/9] Preparing runtime ...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: Free port 8000 if occupied
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        Port %PORT% busy, releasing ...
    for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
        taskkill /f /pid %%p >nul 2>&1
    )
    :: Wait 2 seconds (use ping for cross-version compatibility)
    ping 127.0.0.1 -n 3 >nul
)
echo        Port %PORT% ready
echo.

:: ===== Step 9: Start Jarvis =====
echo  [9/9] Starting Jarvis AI ...
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
if "%USE_VECTOR_DB%"=="1" (
    echo    Vector DB: ENABLED (full memory search)
) else (
    echo    Vector DB: DISABLED (keyword search only)
)
echo.
echo    First time? Go to Settings page, fill LLM API Key
echo.
echo    Stop Jarvis: press Ctrl+C in this window
echo.
echo  ================================================================
echo.

:: Open browser after 5 seconds (ping delay for cross-version compat)
start "" /b cmd /c "ping 127.0.0.1 -n 6 >nul && start http://127.0.0.1:%PORT%/"

:: Set env var to skip vector DB on Win7
if "%USE_VECTOR_DB%"=="0" (
    set "KIZUNA_SKIP_VECTOR_DB=1"
)

cd /d "%BACKEND_DIR%"

:: Log file with timestamp
set "D=%DATE%"
set "T=%TIME%"
set "D=%D:/=_%"
set "T=%T: =0%"
set "T=%T::=_%"
set "LOG_FILE=%LOGS_DIR%\jarvis_%D%_%T%.log"

echo  [INFO] Log file: %LOG_FILE%
echo  [INFO] Starting uvicorn ...
echo  [INFO] Press Ctrl+C to stop
echo.

:: Try PowerShell Tee-Object, fallback to direct run
where powershell >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "& { python -m uvicorn app:app --host 0.0.0.0 --port %PORT% 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append }"
) else (
    python -m uvicorn app:app --host 0.0.0.0 --port %PORT%
)

echo.
echo  ================================================================
echo    Jarvis stopped.
echo    Log saved to: %LOG_FILE%
echo  ================================================================
pause >nul
endlocal
