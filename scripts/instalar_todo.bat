@echo off
REM ============================================================
REM  BioAccess - INSTALADOR TODO AUTOMATICO
REM ============================================================
setlocal
cd /d "%~dp0.."
title BioAccess - instalador

echo.
echo  ============================================
echo   BIOACCESS  ::  INSTALADOR AUTOMATICO
echo  ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo  [X] Python no encontrado. Descargalo de https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  [1/4] Instalando dependencias de Python ...
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r "%~dp0..\requirements.txt"
if errorlevel 1 (
    echo  [X] Fallo al instalar dependencias.
    pause
    exit /b 1
)
echo  [OK] Dependencias instaladas.

if not exist "%~dp0..\bioaccess.exe" (
    if not exist "%~dp0..\dist\bioaccess.exe" (
        echo  [2/4] Compilando bioaccess.exe (puede tardar ~2 min) ...
        python -m PyInstaller --noconfirm --clean "%~dp0..\bioaccess.spec" >nul 2>&1
        if errorlevel 1 (
            echo  [!] No se pudo compilar el .exe. Se usara Python directo.
        ) else (
            if exist "%~dp0..\dist\bioaccess.exe" copy /y "%~dp0..\dist\bioaccess.exe" "%~dp0..\bioaccess.exe" >nul
        )
    ) else (
        copy /y "%~dp0..\dist\bioaccess.exe" "%~dp0..\bioaccess.exe" >nul
    )
) else (
    echo  [2/4] bioaccess.exe ya presente.
)

if exist "%~dp0..\dist\BioAccessMobile.apk" (
    where adb >nul 2>&1
    if not errorlevel 1 (
        echo  [3/4] Buscando celular por USB para instalar la APK ...
        adb wait-for-device >nul 2>&1
        adb devices | findstr /i "device" >nul 2>&1
        if not errorlevel 1 (
            adb install -r "%~dp0..\dist\BioAccessMobile.apk" >nul 2>&1
            adb shell am start -n com.bioaccess.mobile/.MainActivity >nul 2>&1
            echo  [OK] APK instalada/actualizada en el celular.
        ) else (
            echo  [3/4] Sin celular conectado por USB. Instala la APK manualmente.
        )
    ) else (
        echo  [3/4] adb no encontrado (instala Android platform-tools). APK en dist\.
    )
) else (
    echo  [3/4] APK no encontrada en dist\. Compila con android\build.ps1.
)

echo  [4/4] Lanzando BioAccess ...
if exist "%~dp0..\bioaccess.exe" (
    start "" "%~dp0..\bioaccess.exe"
) else (
    start "" pythonw "%~dp0..\bioaccess.py"
)
echo.
echo  Listo. En el celular: abre BioAccess y pulsa BUSCAR PC (o ESCANEAR QR).
echo.
pause