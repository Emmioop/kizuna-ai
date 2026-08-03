@echo off
chcp 65001 >nul
title Jarvis - 安装开机自启服务 (需管理员身份运行!)

:: 检查是否管理员
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo ============================================
    echo   ❌ 权限不足
    echo ============================================
    echo.
    echo   请在本脚本上点「右键」→「以管理员身份运行」
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Jarvis 贾维斯管家 AI · 注册 Windows 服务
echo ============================================
echo.
echo 功能：
echo   1. 注册 JarvisAI 服务（开机自动启动 + 崩溃自动重启）
echo   2. 如果检测到 cloudflared，可选注册 JarvisTunnel 公网隧道
echo.
echo 按任意键开始 ...
pause >nul

cd /d "%~dp0"
cd ..\..

:: 基础信息
set "ROOT=%cd%"
set "BACKEND=%ROOT%\backend"
set "VENV=%BACKEND%\.venv"
set "APP=%VENV%\Scripts\uvicorn.exe"
set "LOG_DIR=%ROOT%\logs"

if not exist "%APP%" (
    echo [错误] 找不到 uvicorn.exe，请先运行 1_安装依赖.bat
    echo 期望路径: %APP%
    pause
    exit /b 1
)

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
echo [1/5] 检测 NSSM ...
where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo   - 未检测到 NSSM，正在尝试从脚本目录复制 ...
    if exist "%~dp0nssm.exe" (
        copy "%~dp0nssm.exe" "C:\Windows\System32\nssm.exe" >nul
        where nssm >nul 2>&1
        if %errorLevel% neq 0 (
            echo.
            echo [错误] NSSM 未安装
            echo   请从 https://nssm.cc/release/nssm-2.24.zip 下载
            echo   将 win64/nssm.exe 复制到 C:\Windows\System32\ 再重试
            pause
            exit /b 1
        )
    ) else (
        echo.
        echo [错误] NSSM 未安装
        echo   请从 https://nssm.cc/release/nssm-2.24.zip 下载
        echo   将 win64/nssm.exe 复制到 C:\Windows\System32\ 再重试
        echo   或者把 nssm.exe 放到本脚本同目录（scripts\win7\）
        pause
        exit /b 1
    )
)
echo   - OK: nssm 已就绪

echo.
echo [2/5] 停止并删除已有 JarvisAI 服务（如果有）...
nssm stop JarvisAI >nul 2>&1
nssm remove JarvisAI confirm >nul 2>&1

echo.
echo [3/5] 安装 JarvisAI 服务 ...
nssm install JarvisAI "%APP%"
if %errorLevel% neq 0 (
    echo [错误] 安装服务失败
    pause
    exit /b 1
)
:: 设置参数
nssm set JarvisAI AppDirectory "%BACKEND%"
nssm set JarvisAI AppParameters "app:app --host 0.0.0.0 --port 8000"
nssm set JarvisAI AppStdout "%LOG_DIR%\jarvis-out.log"
nssm set JarvisAI AppStderr "%LOG_DIR%\jarvis-err.log"
nssm set JarvisAI AppStdoutCreationDisposition 2
nssm set JarvisAI AppStderrCreationDisposition 2
nssm set JarvisAI AppRotateFiles 1
nssm set JarvisAI AppRotateBytes 10485760
nssm set JarvisAI AppRotateOnline 1
nssm set JarvisAI DisplayName "Jarvis AI Backend"
nssm set JarvisAI Description "贾维斯管家AI后端服务：大脑 + 记忆 + LLM API 网关 + 工具调用"
nssm set JarvisAI Start SERVICE_AUTO_START
:: 崩溃重启策略
nssm set JarvisAI AppExit Default Restart
nssm set JarvisAI AppRestartDelay 5000
:: 环境变量：Win7 禁用向量数据库
nssm set JarvisAI AppEnvironmentExtra "KIZUNA_SKIP_VECTOR_DB=1"
echo   - 参数配置完成

echo.
echo [4/5] 启动 JarvisAI 服务 ...
nssm start JarvisAI
if %errorLevel% neq 0 (
    echo [错误] 服务启动失败，查看日志:
    echo    %LOG_DIR%\jarvis-err.log
    echo   或运行 2_本地测试启动.bat 看具体报错
    pause
    exit /b 1
)

echo.
echo [5/5] 检查服务状态 ...
timeout /t 3 /nobreak >nul
nssm status JarvisAI

:: 检查 cloudflared
echo.
where cloudflared >nul 2>&1
if %errorLevel% equ 0 (
    echo.
    echo [可选] 检测到 cloudflared 已安装
    echo   是否同时注册 JarvisTunnel 公网隧道服务？(Y/N)
    echo   (需要您已经配置过命名隧道: cloudflared tunnel create jarvis + 配置文件)
    set /p TUN="   输入 Y/N: "
    if /i "%TUN%"=="Y" (
        echo.
        echo   - 注册 JarvisTunnel 服务 ...
        nssm stop JarvisTunnel >nul 2>&1
        nssm remove JarvisTunnel confirm >nul 2>&1
        nssm install JarvisTunnel cloudflared
        nssm set JarvisTunnel AppDirectory "%ROOT%"
        nssm set JarvisTunnel AppParameters "tunnel run"
        nssm set JarvisTunnel AppStdout "%LOG_DIR%\tunnel-out.log"
        nssm set JarvisTunnel AppStderr "%LOG_DIR%\tunnel-err.log"
        nssm set JarvisTunnel AppStdoutCreationDisposition 2
        nssm set JarvisTunnel AppStderrCreationDisposition 2
        nssm set JarvisTunnel DependsOnService JarvisAI
        nssm set JarvisTunnel DisplayName "Jarvis Cloudflare Tunnel"
        nssm set JarvisTunnel Description "贾维斯公网隧道：手机4G/5G访问贾维斯"
        nssm set JarvisTunnel Start SERVICE_AUTO_START
        nssm set JarvisTunnel AppExit Default Restart
        nssm set JarvisTunnel AppRestartDelay 8000
        nssm start JarvisTunnel
        echo   - 隧道服务已启动
    ) else (
        echo   - 跳过（以后想注册了重新运行本脚本即可）
    )
)

echo.
echo ============================================
echo  ✅ 贾维斯服务安装完成！
echo ============================================
echo.
echo  服务状态查看:
echo    nssm status JarvisAI
echo  服务重启:
echo    nssm restart JarvisAI
echo  日志文件:
echo    %LOG_DIR%\jarvis-out.log
echo    %LOG_DIR%\jarvis-err.log
echo.
echo  访问地址（本机/同Wi-Fi）:
echo    http://127.0.0.1:8000
echo.
pause
