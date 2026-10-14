@echo off
setlocal
cd /d "%~dp0"

:: ------------------------------------------------------------------
:: 诊断模式：带完整日志启动桌宠
::  - 应用日志：%APPDATA%\firefly-pet\firefly-pet.log
::  - Chromium 底层日志：build\chromium.log（连窗口都没创建时的兜底线索）
:: ------------------------------------------------------------------

if not exist "node_modules\electron\dist\electron.exe" (
  echo 尚未安装依赖，请先双击 安装依赖.cmd
  pause
  exit /b 1
)

call "%~dp0_sync-electron.cmd"
if errorlevel 1 (
  echo [x] Electron 运行时同步失败，请先双击 安装依赖.cmd。
  pause
  exit /b 1
)

set "ELECTRON_EXE=%LOCALAPPDATA%\FireflyPet\electron\electron.exe"
set ELECTRON_RUN_AS_NODE=

echo 诊断模式启动中（--verbose --safe，禁用硬件加速以排除显卡因素）...
echo.

if not exist build mkdir build
"%ELECTRON_EXE%" . --verbose --safe --enable-logging=file --log-file="build\chromium.log" --v=1
set "PET_EXIT=%ERRORLEVEL%"

echo.
echo 退出码：%PET_EXIT%
echo 应用日志： %APPDATA%\firefly-pet\firefly-pet.log
echo 底层日志： %CD%\build\chromium.log
echo.
if exist "%APPDATA%\firefly-pet\firefly-pet.log" notepad "%APPDATA%\firefly-pet\firefly-pet.log"
pause
endlocal
