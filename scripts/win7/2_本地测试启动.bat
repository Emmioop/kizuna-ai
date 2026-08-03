@echo off
chcp 65001 >nul
title Jarvis - 本地测试启动 (调试模式)

echo.
echo ============================================
echo  Jarvis 贾维斯管家 AI · 本地调试启动
echo ============================================
echo.
echo [提示] 这是调试模式：关闭窗口即停止贾维斯
echo [提示] 要开机自启 + 后台运行，请用管理员身份运行 3_安装服务_贾维斯.bat
echo.

cd /d "%~dp0"
cd ..\..\backend

if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 请先双击运行 "1_安装依赖.bat" 创建虚拟环境
    pause
    exit /b 1
)

echo 激活虚拟环境 ...
call .venv\Scripts\activate.bat

echo.
echo 启动 Jarvis 大脑 (监听 0.0.0.0:8000) ...
echo.
echo 看到下面这行就是启动成功：
echo   "Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)"
echo.
echo 按 Ctrl + C 停止（或直接关闭窗口）
echo ============================================
echo.

:: 设置环境变量：Win7 不用向量数据库，用 SQLite FTS5 全文检索替代
set KIZUNA_SKIP_VECTOR_DB=1
:: 启动 uvicorn
python -m uvicorn app:app --host 0.0.0.0 --port 8000

pause
