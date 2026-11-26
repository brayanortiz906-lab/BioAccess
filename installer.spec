# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

for f in ("bioaccess.exe", "dist/BioAccessMobile.apk", "README_BIOACCESS.md",
          "requirements.txt", "scripts/iniciar_bioaccess.bat",
          "scripts/instalar_apk.bat"):
    if os.path.exists(f):
        datas.append((f, "."))

try:
    d, b, h = collect_all("win32com")
    datas += d; binaries += b; hiddenimports += h
except Exception:
    pass
try:
    d, b, h = collect_all("PyQt6")
    datas += d; binaries += b; hiddenimports += h
except Exception:
    pass

a = Analysis(
    ["installer.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name="BioAccessInstaller",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="icono_bioaccess.ico",
)
