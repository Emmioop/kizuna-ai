@echo off
chcp 65001 >nul
title Jarvis - 数据备份

cd /d "%~dp0"
cd ..\..

set "BACKEND=%cd%\backend"
set "DATA_DIR=%BACKEND%\data"
set "OUT_DIR=%cd%\backups"

if not exist "%DATA_DIR%" (
    echo [错误] 找不到数据目录 %DATA_DIR%
    echo 请先启动过一次贾维斯，再运行本脚本
    pause
    exit /b 1
)

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

:: 时间戳生成 YYYYMMDD_HHMMSS
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "dt=%%I"
set "TS=%dt:~0,8%_%dt:~8,6%"

set "OUT_FILE=%OUT_DIR%\jarvis_backup_%TS%.zip"

echo.
echo ============================================
echo  Jarvis 数据备份
echo ============================================
echo.
echo  源目录: %DATA_DIR%
echo  输出文件: %OUT_FILE%
echo.

:: 尝试用 PowerShell 压缩（Win7 自带 PowerShell 2.0，支持压缩）
where powershell >nul 2>&1
if %errorLevel% equ 0 (
    echo 使用 PowerShell 压缩中 ...
    powershell -Command "Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory('%DATA_DIR%', '%OUT_FILE%')"
    if not errorlevel 1 (
        echo.
        echo ============================================
        echo  ✅ 备份完成！
        echo ============================================
        echo.
        echo 文件: %OUT_FILE%
        echo.
        echo 建议：每月备份一次，并将备份文件复制到 U 盘/网盘
        pause
        :: 打开输出目录
        explorer "%OUT_DIR%"
        exit /b 0
    )
)

:: 如果 PowerShell 失败，尝试 7z
where 7z >nul 2>&1
if %errorLevel% equ 0 (
    echo 使用 7z 压缩中 ...
    7z a -tzip "%OUT_FILE%" "%DATA_DIR%\*"
    if not errorlevel 1 (
        echo.
        echo ============================================
        echo  ✅ 备份完成！
        echo ============================================
        echo.
        echo 文件: %OUT_FILE%
        pause
        explorer "%OUT_DIR%"
        exit /b 0
    )
)

echo.
echo [错误] 无法压缩：没有可用的 PowerShell 或 7z
echo 请手动将以下目录复制保存到安全位置：
echo    %DATA_DIR%
echo.
pause
explorer "%DATA_DIR%"
