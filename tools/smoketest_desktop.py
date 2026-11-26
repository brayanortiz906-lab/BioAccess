# -*- coding: utf-8 -*-
"""Smoke test del terminal de escritorio (sin pantalla, QT offscreen)."""
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bioaccess as B  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
win = B.SuperCustomBio()
win.show()


def check():
    print("HUD remote_active :", win.hud.remote_active)
    print("net_status        :", win.net_status.text())
    print("net_ip            :", win.net_ip.text())
    print("bridge connected  :", bool(win.bridge and win.bridge.connected))
    print("server_port       :", getattr(win, "server_port", None))
    print("--- log_list ---")
    for i in range(win.log_list.count()):
        print("   ", win.log_list.item(i).text())
    print("--- pidiendo huella (sin celular) ---")
    win._request_fingerprint()
    QTimer.singleShot(1200, finish)


def finish():
    print("log_lbl:", win.log_lbl.text())
    print("--- log_list final ---")
    for i in range(win.log_list.count()):
        print("   ", win.log_list.item(i).text())
    win.close()
    app.quit()


QTimer.singleShot(4500, check)
app.exec()
print("SMOKE TEST OK")
