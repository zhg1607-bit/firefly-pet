@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: ------------------------------------------------------------------
:: 安装 Electron 依赖：优先 npm，其次 DSH 自带的 pnpm；
:: 若 electron 的运行时二进制未就位（安装脚本被拦/无 PATH node），
:: 直接用找到的 node 补跑 install.js。
:: ------------------------------------------------------------------

:: --- 1) 定位 Node ---
set "NODE="
where node >nul 2>nul
if %errorlevel%==0 set "NODE=node"
if not defined NODE (
  if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe" (
    set "NODE=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
  )
)
if not defined NODE (
  echo [x] 未找到 Node.js。请先安装 Node.js 18+ ：https://nodejs.org/zh-cn
  pause
  exit /b 1
)

:: --- 2) 装包（npm / pnpm 二选一） ---
where npm >nul 2>nul
if %errorlevel%==0 (
  echo 使用 npm 安装 Electron...
  call npm install --no-audit --no-fund
) else (
  set "PNPM=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\pnpm\bin\pnpm.mjs"
  if exist "!PNPM!" (
    echo 使用 DSH 自带的 pnpm 安装 Electron...
    "%NODE%" "!PNPM!" install
  ) else (
    echo [x] 未找到 npm / pnpm。请先安装 Node.js 18+ ：https://nodejs.org/zh-cn
    pause
    exit /b 1
  )
)

:: --- 3) 补跑 electron 二进制下载（防止安装脚本因无 PATH node 而失败） ---
if not exist "node_modules\electron\dist\electron.exe" (
  if exist "node_modules\electron\install.js" (
    echo 正在下载 Electron 运行时（约 100MB，请耐心等待）...
    "%NODE%" "node_modules\electron\install.js"
  )
)

if not exist "node_modules\electron\dist\electron.exe" (
  echo [x] Electron 运行时仍缺失，请检查网络后重试。
  exit /b 1
)

echo [ok] 依赖就绪，可以双击 启动桌宠.cmd 了。
endlocal
exit /b 0
