@echo off
chcp 65001 >nul 2>&1
title Jarvis AI - 一键停止
color 0C

echo.
echo  ================================================================
echo                 JARVIS AI  -  一键停止
echo  ================================================================
echo.

set "PORT=8000"

:: ============================================================
:: 第 1 步：停止 NSSM 服务（如果注册过）
:: ============================================================
echo  [1/3] 检查 NSSM 服务 ...
where nssm >nul 2>&1
if not errorlevel 1 (
    nssm stop JarvisAI >nul 2>&1
    if not errorlevel 1 (
        echo        NSSM 服务 JarvisAI 已停止  OK
    ) else (
        echo        NSSM 服务未运行或未安装
    )
) else (
    echo        未安装 NSSM，跳过
)
echo.

:: ============================================================
:: 第 2 步：杀掉占用 8000 端口的进程
:: ============================================================
echo  [2/3] 检查端口 %PORT% ...
set "FOUND_PID=0"
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":%PORT% " ^| findstr "LISTENING" 2^>nul') do (
    set "FOUND_PID=%%p"
    taskkill /f /pid %%p >nul 2>&1
    if not errorlevel 1 (
        echo        已终止进程 PID=%%p  OK
    )
)
if "%FOUND_PID%"=="0" (
    echo        端口 %PORT% 无占用进程
)
echo.

:: 等待 2 秒让端口完全释放
timeout /t 2 /nobreak >nul

:: ============================================================
:: 第 3 步：二次确认端口已释放
:: ============================================================
echo  [3/3] 二次确认 ...
netstat -aon | findstr ":%PORT% " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo        端口 %PORT% 已完全释放  OK
    echo        Jarvis 已完全停止
) else (
    echo        [!] 端口 %PORT% 仍被占用
    echo        请尝试重启电脑，或手动在「任务管理器」中结束 python.exe 进程
)
echo.

echo  ================================================================
echo    Jarvis 已停止运行
echo    按任意键关闭窗口
echo  ================================================================
pause >nul
