# BIOACCESS

Sistema de control de acceso por huella para PC y celular.

## Descargas
- APK movil: ver Releases
- Pagina del proyecto: https://brayanortiz906-lab.github.io/BioAccess/

## Documentacion
- COMO_FUNCIONA.md
- COMO_FUNCIONA_CONEXION.md
- README_BIOACCESS.md

## Ejecutar en desarrollo
python bioaccess.py

Servidor standalone:
python bioaccess_server.py --port 8080

## 🛠️ Solución de Problemas (Troubleshooting)

Si al ejecutar `python sistema_simple.py` ocurre un error de módulo no encontrado (`ModuleNotFoundError: No module named 'PyQt6'`) o falla la instalación automática de dependencias, sigue estos pasos según tu caso:

### 1. Error de rutas largas en Windows (`OSError: [Errno 2] No such file or directory`)
Si tienes Python instalado desde la **Microsoft Store**, Windows puede bloquear la instalación de `PyQt6` debido al límite de 260 caracteres en las rutas de archivos.

1. Abre **PowerShell como Administrador** y ejecuta el siguiente comando para habilitar las rutas largas:
   ```powershell
   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

   # 1. Crear y activar el entorno virtual
python -m venv C:\venv_bio
C:\venv_bio\Scripts\activate

# 2. Instalar dependencias
pip install --upgrade pip
pip install PyQt6 PyQt6-WebEngine fastapi uvicorn websockets qrcode pillow

# 3. Ejecutar el sistema
python sistema_simple.py
