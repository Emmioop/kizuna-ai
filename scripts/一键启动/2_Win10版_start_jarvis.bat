@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title Jarvis AI - Win10/11 一键启动
color 0B

echo.
echo  ================================================================
echo            JARVIS AI  -  Windows 10/11 一键启动
echo            （完整版，含向量记忆库）
echo  ================================================================
echo.

:: ===== 第 0 步：定位项目根目录 =====
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
:: 上溯 2 级：scripts/一键启动/ → scripts/ → kizuna-ai/
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
set "PORT=8000"

echo  [INFO] 项目目录: %PROJECT_DIR%
echo  [INFO] 后端目录: %BACKEND_DIR%
echo.

:: ===== 第 1 步：检测系统版本 =====
echo  [1/9] 检测 Windows 版本 ...
for /f "tokens=4-7 delims=. " %%a in ('ver 2^>nul') do (
    set "WIN_MAJOR=%%a"
    set "WIN_MINOR=%%b"
)
:: 备用方案：用 wmic
if not defined WIN_MAJOR (
    for /f "tokens=2 delims==" %%v in ('wmic os get version /value 2^>nul ^| find "="') do (
        for /f "tokens=1,2 delims=." %%a in ("%%v") do (
            set "WIN_MAJOR=%%a"
            set "WIN_MINOR=%%b"
        )
    )
)

:: 显示系统信息
echo        Windows 内核版本: %WIN_MAJOR%.%WIN_MINOR%
if %WIN_MAJOR% LSS 10 (
    echo        [!] 此脚本为 Win10/11 优化版，检测到旧系统
    echo        建议改用 1_Win7版_start_jarvis.bat
    echo.
    choice /C YN /M "仍然继续 (Y/N)"
    if errorlevel 2 exit /b 1
) else (
    echo        系统版本 OK
)
echo.

:: ===== 第 2 步：检查 Python =====
echo  [2/9] 检查 Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] 未检测到 Python！
    echo.
    echo      请安装 Python 3.10 或更高版本:
    echo        https://www.python.org/downloads/
    echo      安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        Python %PYVER%  OK

:: 检查 Python 版本 >= 3.10
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set "PYMAJ=%%a"
    set "PYMIN=%%b"
)
if %PYMAJ% LSS 3 (
    echo        [!] Python 版本过低，建议 3.10+
) else if %PYMAJ% EQU 3 (
    if %PYMIN% LSS 10 (
        echo        [!] Python %PYVER% 可能缺少部分新特性，建议升级到 3.10+
    )
)
echo.

:: ===== 第 3 步：检查项目结构 =====
echo  [3/9] 检查项目结构 ...
if not exist "%BACKEND_DIR%\app.py" (
    if not exist "%BACKEND_DIR%\kizuna\app.py" (
        echo  [X] 找不到 backend 文件夹！
        echo      请确认此脚本位于 kizuna-ai\scripts\ 目录下
        pause
        exit /b 1
    )
)
echo        项目结构正常  OK
echo.

:: ===== 第 4 步：自动配置 .env =====
echo  [4/9] 检查 .env 配置文件 ...
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        已自动创建 .env 文件
        echo.
        echo  ================================================================
        echo   首次启动提示：需要配置大模型 API Key
        echo  ================================================================
        echo   1. 浏览器打开后，进入「设置」页面填写 API Key
        echo   2. 推荐 智谱GLM（有免费额度）: https://open.bigmodel.cn/
        echo   3. 不填 Key 也能启动，但无法正常聊天
        echo  ================================================================
        echo.
    )
) else (
    echo        .env 已存在  OK
)
echo.

:: ===== 第 5 步：创建虚拟环境 =====
echo  [5/9] 准备 Python 虚拟环境 ...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo        虚拟环境已存在  OK
) else (
    echo        正在创建虚拟环境 ...
    if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%" 2>nul
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo  [X] 创建虚拟环境失败！
        pause
        exit /b 1
    )
    echo        虚拟环境已创建  OK
)
echo.

:: ===== 第 6 步：激活虚拟环境 + 配置清华镜像 =====
echo  [6/9] 激活虚拟环境并升级 pip ...
call "%VENV_DIR%\Scripts\activate.bat"

pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo        pip 已就绪  OK
echo.

:: ===== 第 7 步：安装完整依赖（含向量库） =====
echo  [7/9] 检查依赖 ...
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" >nul 2>&1
if errorlevel 1 (
    echo        首次安装完整依赖（含向量库 chromadb）...
    echo        使用清华镜像加速，预计 5~15 分钟
    echo        请勿关闭此窗口 ...
    echo.
    if exist "%REQ_FILE%" (
        pip install -r "%REQ_FILE%"
        if errorlevel 1 (
            echo.
            echo  [!] 第一次安装失败，正在重试 ...
            pip install -r "%REQ_FILE%" --retries 5 --timeout 180
        )
    ) else (
        :: 直接安装
        pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite pydantic pydantic-settings httpx python-multipart jinja2 apscheduler python-dotenv chromadb sentence-transformers jieba
    )
    if errorlevel 1 (
        echo.
        echo  [X] 依赖安装失败！请检查网络后重试
        pause
        exit /b 1
    )
    echo.
    echo        依赖安装完成  OK
) else (
    :: 检查向量库是否单独安装
    python -c "import chromadb" >nul 2>&1
    if errorlevel 1 (
        echo        基础依赖已安装，正在补装向量库 chromadb ...
        pip install chromadb sentence-transformers jieba >nul 2>&1
        if errorlevel 1 (
            echo        [!] 向量库安装失败，将使用关键词检索（功能受限）
        ) else (
            echo        向量库安装完成  OK
        )
    ) else (
        echo        依赖已全部安装  OK
    )
)
echo.

:: ===== 第 8 步：创建目录 + 释放端口 =====
echo  [8/9] 准备运行环境 ...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: 释放 8000 端口
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo        端口 %PORT% 被占用，正在释放 ...
    for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
        taskkill /f /pid %%p >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)
echo        端口 %PORT% 已就绪  OK
echo.

:: ===== 第 9 步：启动 Jarvis =====
echo  [9/9] 启动 Jarvis AI 后端服务 ...
echo.
echo  ================================================================
echo.
echo    Jarvis 正在启动...
echo.
echo    ★ 几秒后将自动打开浏览器:  http://127.0.0.1:%PORT%
echo.
echo    ★ 手机访问（同一 WiFi）:
echo       1. 在新窗口运行:  ipconfig
echo       2. 找到 IPv4 地址（例如 192.168.1.100）
echo       3. 手机浏览器访问:  http://192.168.1.100:%PORT%
echo.
echo    ★ 首次使用请进入「设置」页填写 API Key
echo.
echo    ★ 停止 Jarvis:  在本窗口按  Ctrl + C
echo.
echo  ================================================================
echo.

:: 4 秒后自动打开浏览器
start "" /b cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:%PORT%/"

:: 日志文件路径
set "LOG_FILE=%LOGS_DIR%\jarvis_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

cd /d "%BACKEND_DIR%"
echo  [INFO] 日志文件: %LOG_FILE%
echo  [INFO] 向量记忆库: 已启用（chromadb）
echo  [INFO] 正在启动 uvicorn ...
echo  [INFO] 按 Ctrl+C 停止服务
echo.

:: 使用 PowerShell Tee 同步写日志
powershell -NoProfile -Command "& { python -m uvicorn app:app --host 0.0.0.0 --port %PORT% 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append }"

echo.
echo  ================================================================
echo    Jarvis 已停止运行
echo    日志已保存到: %LOG_FILE%
echo  ================================================================
pause >nul
endlocal
