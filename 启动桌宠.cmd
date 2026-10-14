@echo off
setlocal
cd /d "%~dp0"

:: ------------------------------------------------------------------
:: 流萤桌宠 一键启动器
:: 1) 首次运行自动安装 Electron 依赖
:: 2) 把 Electron 运行时同步到工作区外的缓存（见 _sync-electron.cmd 说明）
:: 3) 启动宠物（本窗口保持打开；按 Ctrl+C 结束宠物，关窗口不影响宠物）
:: ------------------------------------------------------------------

if not exist "node_modules\electron\dist\electron.exe" (
  echo 首次运行：正在安装 Electron（约 100MB，需要联网，请耐心等待）...
  call "%~dp0安装依赖.cmd"
  if errorlevel 1 (
    echo [x] 依赖安装失败。请打开 安装依赖.cmd 查看错误，或按 README.md 手动安装。
    pause
    exit /b 1
  )
)

call "%~dp0_sync-electron.cmd"
if errorlevel 1 (
  echo [x] Electron 运行时同步失败。
  echo     请先双击 安装依赖.cmd，再重试本文件。
  pause
  exit /b 1
)

set "ELECTRON_EXE=%LOCALAPPDATA%\FireflyPet\electron\electron.exe"
set ELECTRON_RUN_AS_NODE=

echo 流萤桌宠启动中...（宠物出现后，右键她或托盘小图标可以打开菜单）
echo 提示：本窗口保持打开即可；按 Ctrl+C 结束宠物；直接关掉本窗口不影响宠物。
echo.
"%ELECTRON_EXE%" . %*
set "PET_EXIT=%ERRORLEVEL%"
echo.
if "%PET_EXIT%"=="0" (
  echo [i] 宠物已退出（正常退出）。
) else (
  echo [x] 宠物异常退出，退出码 %PET_EXIT%。
  echo     诊断日志： %APPDATA%\firefly-pet\firefly-pet.log
  echo     也可以双击 诊断.cmd 抓更详细的日志。
)
pause
endlocal
