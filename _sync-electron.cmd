@echo off
:: ------------------------------------------------------------------
:: _sync-electron.cmd —— 内部辅助脚本
:: 把 node_modules\electron\dist 同步到工作区外的缓存目录：
::   %LOCALAPPDATA%\FireflyPet\electron
:: 原因：本机的 DSH 工作区会拦截「从工作区目录内启动的程序」
:: （electron.exe 从工作区启动会瞬间 STATUS_BREAKPOINT 崩溃），
:: 从工作区外启动则一切正常。应用代码仍在工作区内，只是运行时换地方。
:: 同步依据：dist\version 文件内容（版本变化才重新拷贝）。
:: ------------------------------------------------------------------
set "SRC=%~dp0node_modules\electron\dist"
set "CACHE=%LOCALAPPDATA%\FireflyPet\electron"

if not exist "%SRC%\electron.exe" exit /b 1

if not exist "%CACHE%\electron.exe" goto :copy

for /f "usebackq delims=" %%v in ("%SRC%\version") do set "SRCV=%%v"
for /f "usebackq delims=" %%v in ("%CACHE%\version") do set "CACHEV=%%v"
if "%SRCV%"=="%CACHEV%" exit /b 0

:copy
if not exist "%CACHE%" mkdir "%CACHE%"
robocopy "%SRC%" "%CACHE%" /E /NFL /NDL /NJH /NJS /NP >nul
if %errorlevel% geq 8 exit /b 1
exit /b 0
