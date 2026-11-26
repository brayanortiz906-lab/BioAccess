"""Empaqueta el APK final: base.apk (aapt2) + classes.dex, con un zip estándar.

Uso:
    python tools/pack_apk.py build/base.apk build/dex/classes.dex build/unsigned.apk
"""
import sys
import zipfile

# Estos se guardan sin comprimir por convención (más rápido de leer en Android)
STORED = {"resources.arsc"}


def pack(src, dex, dst):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename == "classes.dex":
                continue
            data = zin.read(info.filename)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.external_attr = 0o644 << 16
            if info.filename in STORED or info.filename.endswith(".png"):
                zi.compress_type = zipfile.ZIP_STORED
            else:
                zi.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(zi, data)

        with open(dex, "rb") as f:
            code = f.read()
        zi = zipfile.ZipInfo("classes.dex", date_time=(2026, 1, 1, 0, 0, 0))
        zi.external_attr = 0o644 << 16
        zi.compress_type = zipfile.ZIP_DEFLATED
        zout.writestr(zi, code)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    pack(sys.argv[1], sys.argv[2], sys.argv[3])
    print("pack_apk OK ->", sys.argv[3])
