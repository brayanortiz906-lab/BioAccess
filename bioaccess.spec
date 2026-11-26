# -*- mode: python ; coding: utf-8 -*-
# BioAccess Desktop + servidor puente (LAN) empacado en un solo .exe
from PyInstaller.utils.hooks import collect_all

datas = [('mobile', 'mobile')]
binaries = []
hiddenimports = []

for pkg in ("fastapi", "starlette", "uvicorn", "websockets", "anyio", "pydantic", "qrcode"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

hiddenimports += [
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
    'websockets.sync.client',
    'websockets.legacy.client',
    'email.mime.multipart',
    'email.mime.text',
]

a = Analysis(
    ['bioaccess.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='bioaccess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icono_bioaccess.ico'] if __import__('os').path.exists('icono_bioaccess.ico') else None,
)
