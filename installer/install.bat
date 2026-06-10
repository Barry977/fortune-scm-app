@echo off
:: 命运 (DESTINY) 安装程序
:: 双击运行此文件即可安装

echo ==========================================
echo   命运 (DESTINY) - 智能客户开发系统
echo   安装程序
echo ==========================================
echo.

:: Check admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在请求管理员权限...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run installer
echo 正在安装...
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if %errorlevel% neq 0 (
    echo.
    echo 安装出错，请重试
    pause
)
