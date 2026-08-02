@echo off
REM ============================================================
REM   羁绊 AI · 一键启动脚本（Windows）
REM   双击运行即可
REM ============================================================
chcp 65001 >nul
setlocal enabledelayedexpansion

set ROOT=%~dp0
cd /d "%ROOT%"

echo ========================================
echo   🌙 羁绊 AI 启动中
echo ========================================

REM ---- 后端依赖 ----
if not exist "backend\venv" (
    echo [1/4] 创建 Python 虚拟环境…
    cd /d "%ROOT%\backend"
    python -m venv venv
)

echo [2/4] 安装后端依赖…
cd /d "%ROOT%\backend"
call venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM ---- 前端依赖 ----
if not exist "frontend\node_modules" (
    echo [3/4] 安装前端依赖（首次会慢一点）…
    cd /d "%ROOT%\frontend"
    call npm install
)

if not exist "frontend\dist" (
    echo [3.5/4] 首次构建前端…
    cd /d "%ROOT%\frontend"
    call npm run build
)

REM ---- 启动 ----
echo [4/4] 启动后端（端口 8000）…
cd /d "%ROOT%\backend"
call venv\Scripts\activate.bat

echo.
echo  ✅ 启动完成！浏览器打开：
echo     http://127.0.0.1:8000
echo.
echo  （首次使用请在「LLM 设置」里填入你的 API Key）
echo.

uvicorn app:app --host 0.0.0.0 --port 8000
pause
