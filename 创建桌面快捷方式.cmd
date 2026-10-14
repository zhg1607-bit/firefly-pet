@echo off
setlocal
cd /d "%~dp0"

:: ------------------------------------------------------------------
:: 在桌面创建「流萤桌宠」快捷方式（双击即可召唤）
:: ------------------------------------------------------------------

set "LINK=%USERPROFILE%\Desktop\流萤桌宠.lnk"
set "TARGET=%~dp0启动桌宠.cmd"
set "VBS=%TEMP%\firefly-pet-shortcut.vbs"

> "%VBS%" echo Set ws = CreateObject("WScript.Shell")
>> "%VBS%" echo Set sc = ws.CreateShortcut("%LINK%")
>> "%VBS%" echo sc.TargetPath = "%TARGET%"
>> "%VBS%" echo sc.WorkingDirectory = "%~dp0"
>> "%VBS%" echo sc.Description = "流萤桌宠"
>> "%VBS%" echo sc.Save

cscript //nologo "%VBS%"
del "%VBS%" >nul

echo.
echo 已在桌面创建快捷方式「流萤桌宠」，双击它就能把流萤召唤出来。
echo 提示：托盘菜单里勾选「开机自启」，之后每次开机都会自动出现。
pause
endlocal
