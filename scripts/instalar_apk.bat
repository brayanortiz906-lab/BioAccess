@echo off
REM ============================================================
REM  BioAccess - instalar la APK en el celular por USB (adb)
REM ============================================================
setlocal
cd /d "%~dp0.."
title BioAccess - instalar APK

set ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe
if not exist "%ADB%" set ADB=adb

echo.
echo  Esperando al celular (activa "Depuracion USB") ...
"%ADB%" wait-for-device
echo.
"%ADB%" install -r "%~dp0..\dist\BioAccessMobile.apk"
echo.
"%ADB%" shell am start -n com.bioaccess.mobile/.MainActivity
echo.
echo  Listo. Abre la app BioAccess en el celular.
pause