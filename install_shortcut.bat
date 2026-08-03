@echo off
chcp 65001 >nul 2>&1
title Jarvis AI - 创建桌面快捷方式
color 0B

echo.
echo  ================================================================
echo            在桌面创建 Jarvis 一键启动 / 停止快捷方式
echo  ================================================================
echo.

set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "DESKTOP=%USERPROFILE%\Desktop"
if not exist "%DESKTOP%" set "DESKTOP=%USERPROFILE%\桌面"

echo  [INFO] 项目目录: %PROJECT_DIR%
echo  [INFO] 桌面目录: %DESKTOP%
echo.

:: 用 PowerShell 创建快捷方式（Win7/Win10 自带）
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$s = $ws.CreateShortcut('%DESKTOP%\Jarvis 启动.lnk'); " ^
  "$s.TargetPath = '%PROJECT_DIR%\start_jarvis.bat'; " ^
  "$s.WorkingDirectory = '%PROJECT_DIR%'; " ^
  "$s.IconLocation = 'shell32.dll,13'; " ^
  "$s.Description = '一键启动 Jarvis AI'; " ^
  "$s.Save(); " ^
  "$s2 = $ws.CreateShortcut('%DESKTOP%\Jarvis 停止.lnk'); " ^
  "$s2.TargetPath = '%PROJECT_DIR%\stop_jarvis.bat'; " ^
  "$s2.WorkingDirectory = '%PROJECT_DIR%'; " ^
  "$s2.IconLocation = 'shell32.dll,131'; " ^
  "$s2.Description = '一键停止 Jarvis AI'; " ^
  "$s2.Save()"

if errorlevel 1 (
    echo  [X] 创建快捷方式失败！
    echo      请手动把 start_jarvis.bat 拖到桌面创建快捷方式
    pause
    exit /b 1
)

echo  [OK] 桌面快捷方式已创建：
echo        - Jarvis 启动.lnk   （双击启动）
echo        - Jarvis 停止.lnk   （双击停止）
echo.
echo  ================================================================
echo    使用方法：
echo      1. 双击桌面「Jarvis 启动」即可一键启动
echo      2. 启动后浏览器会自动打开 http://127.0.0.1:8000
echo      3. 双击桌面「Jarvis 停止」即可一键停止
echo  ================================================================
echo.
pause
