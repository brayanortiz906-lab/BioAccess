@echo off
REM ============================================================
REM  BioAccess - solo el servidor puente (sin interfaz de escritorio)
REM  Útil para probar desde el navegador del celular: http://IP:8080
REM ============================================================
setlocal
cd /d "%~dp0"
title BioAccess - servidor puente

set PYTHONIOENCODING=utf-8

echo.
echo  Iniciando servidor puente BioAccess ...
echo  (deja esta ventana abierta; Ctrl+C para detener)
echo.

if exist "C:\Python314\python.exe" (
    "C:\Python314\python.exe" -u "%~dp0bioaccess_server.py" --port 8080
) else (
    python -u "%~dp0bioaccess_server.py" --port 8080
)

pause
