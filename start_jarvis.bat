@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title Jarvis AI - 一键启动
color 0B

echo.
echo  ================================================================
echo                 JARVIS AI  -  一键启动
echo            （第一次运行会自动配置环境，请耐心等待）
echo  ================================================================
echo.

:: ============================================================
:: 第 0 步：定位项目目录
:: ============================================================
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "DATA_DIR=%BACKEND_DIR%\data"
set "LOGS_DIR=%PROJECT_DIR%\logs"
set "ENV_FILE=%BACKEND_DIR%\.env"
set "ENV_EXAMPLE=%BACKEND_DIR%\.env.example"
set "PORT=8000"

echo  [INFO] 项目目录: %PROJECT_DIR%
echo  [INFO] 后端目录: %BACKEND_DIR%
echo.

:: ============================================================
:: 第 1 步：检查 Python
:: ============================================================
echo  [1/8] 检查 Python ...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [X] 未检测到 Python！
    echo.
    echo      请到官网下载并安装:  https://www.python.org/downloads/
    echo      安装时务必勾选  "Add Python to PATH"
    echo      Win7 系统请选 Python 3.8.10
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo        已检测到 Python %PYVER%  OK
echo.

:: ============================================================
:: 第 2 步：检查 backend 目录
:: ============================================================
echo  [2/8] 检查项目结构 ...
if not exist "%BACKEND_DIR%\app.py" (
    if not exist "%BACKEND_DIR%\kizuna\app.py" (
        echo  [X] 找不到 backend 文件夹！
        echo      请确认此脚本位于 kizuna-ai 项目根目录。
        pause
        exit /b 1
    )
)
echo        项目结构正常  OK
echo.

:: ============================================================
:: 第 3 步：自动配置 .env（首次启动关键步骤）
:: ============================================================
echo  [3/8] 检查环境配置文件 .env ...
if not exist "%ENV_FILE%" (
    if exist "%ENV_EXAMPLE%" (
        copy "%ENV_EXAMPLE%" "%ENV_FILE%" >nul
        echo        已自动创建 .env 文件（基于 .env.example）
        echo.
        echo  ================================================================
        echo   重要提示：首次启动需要配置大模型 API Key
        echo  ================================================================
        echo   1. 浏览器打开后，进入「设置」页面填写 API Key
        echo   2. 推荐 智谱GLM（有免费额度）:  https://open.bigmodel.cn/
        echo      注册后在「API Keys」页面创建密钥
        echo   3. 不填 API Key 也能启动，但无法正常聊天
        echo  ================================================================
        echo.
    ) else (
        echo        [!] 未找到 .env.example，将使用默认配置
    )
) else (
    echo        .env 已存在  OK
)
echo.

:: ============================================================
:: 第 4 步：创建虚拟环境
:: ============================================================
echo  [4/8] 准备 Python 虚拟环境 ...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo        虚拟环境已存在  OK
) else (
    echo        正在创建虚拟环境（位于 backend\.venv）...
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

:: ============================================================
:: 第 5 步：激活虚拟环境 + 升级 pip
:: ============================================================
echo  [5/8] 激活虚拟环境并升级 pip ...
call "%VENV_DIR%\Scripts\activate.bat"

:: 配置国内 pip 镜像（清华源），大幅加速下载
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

python -m pip install --upgrade pip setuptools wheel >nul 2>&1
echo        pip 已就绪  OK
echo.

:: ============================================================
:: 第 6 步：安装依赖（首次较慢，使用国内镜像加速）
:: ============================================================
echo  [6/8] 检查依赖 ...
python -c "import fastapi, uvicorn, sqlalchemy, aiosqlite" >nul 2>&1
if errorlevel 1 (
    echo        首次安装依赖，使用清华镜像加速，预计 3~10 分钟
    echo        请勿关闭此窗口 ...
    echo.
    pip install -r "%BACKEND_DIR%\requirements.txt"
    if errorlevel 1 (
        echo.
        echo  [!] 第一次安装失败，正在重试 ...
        pip install -r "%BACKEND_DIR%\requirements.txt" --retries 5 --timeout 120
    )
    if errorlevel 1 (
        echo.
        echo  [X] 依赖安装失败！请检查网络或手动执行:
        echo      pip install -r backend\requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo        依赖安装完成  OK
) else (
    echo        依赖已安装  OK
)
echo.

:: ============================================================
:: 第 7 步：创建必要的目录 + 释放端口
:: ============================================================
echo  [7/8] 准备运行环境 ...
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: 检查端口 8000 是否被占用，若占用则尝试释放
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

:: ============================================================
:: 第 8 步：启动 Jarvis + 自动打开浏览器
:: ============================================================
echo  [8/8] 启动 Jarvis AI 后端服务 ...
echo.
echo  ================================================================
echo.
echo    Jarvis 正在启动中...
echo.
echo    ★ 几秒后将自动打开浏览器，地址:  http://127.0.0.1:%PORT%
echo.
echo    ★ 手机访问（同一 WiFi 下）:
echo       1. 在新窗口运行:  ipconfig
echo       2. 找到「IPv4 地址」（例如 192.168.1.100）
echo       3. 手机浏览器访问:  http://192.168.1.100:%PORT%
echo.
echo    ★ 首次使用请进入「设置」页填写大模型 API Key
echo.
echo    ★ 停止 Jarvis:  在本窗口按  Ctrl + C
echo.
echo  ================================================================
echo.

:: 后台启动浏览器（等待 4 秒后打开）
start "" /b cmd /c "timeout /t 4 /nobreak >nul && start http://127.0.0.1:%PORT%/"

:: 日志文件路径（按启动时间命名）
set "LOG_FILE=%LOGS_DIR%\jarvis_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log"
set "LOG_FILE=%LOG_FILE: =0%"

cd /d "%BACKEND_DIR%"
echo  [INFO] 日志文件: %LOG_FILE%
echo  [INFO] 正在启动 uvicorn ...
echo  [INFO] 按 Ctrl+C 停止服务
echo.

:: 直接前台运行 uvicorn，输出同时显示在控制台
:: 用 PowerShell 的 Tee-Object 同步写日志（Win7/Win10 自带 PowerShell）
where powershell >nul 2>&1
if not errorlevel 1 (
    powershell -NoProfile -Command "& { python -m uvicorn app:app --host 0.0.0.0 --port %PORT% 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append }"
) else (
    :: 没有 PowerShell 就直接运行，不记录日志
    python -m uvicorn app:app --host 0.0.0.0 --port %PORT%
)

echo.
echo  ================================================================
echo    Jarvis 已停止运行
echo    日志已保存到: %LOG_FILE%
echo  ================================================================
pause >nul
endlocal
