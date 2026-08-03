@echo off
chcp 65001 >nul
title Jarvis - 安装依赖 (Win7 专用)

echo.
echo ============================================
echo  Jarvis 贾维斯管家 AI · Win7 依赖安装
echo ============================================
echo.
echo [提示] 本脚本需要 Python 3.8.10 已安装并已加入 PATH
echo [提示] 如果没有安装，请先安装 python-3.8.10-amd64.exe
echo.

:: 切换到脚本所在盘符/目录
cd /d "%~dp0"
cd ..\..

:: 检查当前目录结构
if not exist "backend\app.py" (
    echo [错误] 找不到 backend\app.py，请将此脚本放在 kizuna-ai\scripts\win7\ 目录下运行
    echo 当前目录: %cd%
    pause
    exit /b 1
)

echo [1/4] 进入后端目录 ...
cd backend

echo.
echo [2/4] 创建虚拟环境 .venv ...
if exist ".venv" (
    echo   - 检测到已有虚拟环境，跳过创建
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败，请确认 Python 3.8 已安装
        pause
        exit /b 1
    )
    echo   - 创建成功
)

echo.
echo [3/4] 升级 pip + setuptools + wheel ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade "pip<24.0" "setuptools<69.0" wheel
if errorlevel 1 (
    echo [错误] pip 升级失败，检查网络连接
    pause
    exit /b 1
)

echo.
echo [4/4] 安装 Win7 专用依赖（可能需要5-15分钟，耐心等待）...
pip install -r ..\requirements-win7.txt
if errorlevel 1 (
    echo [警告] 部分依赖安装失败，正在尝试单独重试...
    echo   若仍失败，请将最后 20 行红色报错复制给贾维斯
    pause
    exit /b 1
)

echo.
echo ============================================
echo  ✅ 依赖安装完成！
echo ============================================
echo.
echo 下一步：
echo   1. 双击 "2_本地测试启动.bat" 测试大脑能否正常启动
echo   2. 启动成功无报错后，管理员身份运行 "3_安装服务_贾维斯.bat" 注册开机自启
echo.
pause
