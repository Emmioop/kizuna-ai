@echo off
chcp 65001 >nul
title Jarvis - 卸载服务 (管理员身份)

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ❌ 请右键「以管理员身份运行」
    pause
    exit /b 1
)

echo.
echo ============================================
echo  卸载 Jarvis 服务（开机自启 + 隧道）
echo ============================================
echo.

where nssm >nul 2>&1
if %errorLevel% neq 0 (
    echo NSSM 未安装，没有服务需要卸载
    pause
    exit /b 0
)

echo [1/2] 停止 + 删除 JarvisAI 后台服务 ...
nssm stop JarvisAI >nul 2>&1
nssm remove JarvisAI confirm >nul 2>&1
echo   - 完成

echo [2/2] 停止 + 删除 JarvisTunnel 公网隧道（如有）...
nssm stop JarvisTunnel >nul 2>&1
nssm remove JarvisTunnel confirm >nul 2>&1
echo   - 完成

echo.
echo ============================================
echo  ✅ 卸载完成！
echo ============================================
echo.
echo 您的数据没有被删除，都在 backend\data\ 目录里
echo.
pause
