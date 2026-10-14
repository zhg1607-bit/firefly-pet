@echo off
setlocal
cd /d "%~dp0"

:: ------------------------------------------------------------------
:: 启动桌宠（调试模式）：开发者工具 + 完整日志
:: 日志文件：%APPDATA%\firefly-pet\firefly-pet.log
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

"%ELECTRON_EXE%" . --dev --verbose
pause
endlocal
