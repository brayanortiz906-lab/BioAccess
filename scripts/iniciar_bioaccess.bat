@echo off
REM ============================================================
REM  BioAccess - iniciar TODO (PC + servidor puente)
REM  Instala dependencias si faltan y lanza la app.
REM ============================================================
setlocal
cd /d "%~dp0.."
title BioAccess - lanzador

python -c "import PyQt6, fastapi, uvicorn, websockets, qrcode" >nul 2>&1
if errorlevel 1 (
    echo  Instalando dependencias necesarias ...
    python -m pip install -r "%~dp0..\requirements.txt" >nul 2>&1
)

echo.
echo  ============================================
echo   BIOACCESS  ::  PC + ENLACE AL CELULAR
echo  ============================================
echo.

if exist "%~dp0..\bioaccess.exe" (
    echo  [1/2] Abriendo BioAccess Desktop ...
    start "" "%~dp0..\bioaccess.exe"
) else if exist "%~dp0..\dist\bioaccess.exe" (
    echo  [1/2] Abriendo BioAccess Desktop (dist) ...
    start "" "%~dp0..\dist\bioaccess.exe"
) else (
    echo  [1/2] Abriendo BioAccess Desktop con Python ...
    start "" pythonw "%~dp0..\bioaccess.py"
)

echo  [2/2] El servidor de enlace arranca dentro de la app.
echo.
echo  En el celular: abre BioAccess y pulsa BUSCAR PC o ESCANEAR QR.
echo.
pause