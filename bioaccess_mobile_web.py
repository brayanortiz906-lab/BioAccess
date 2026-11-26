# -*- coding: utf-8 -*-
"""
BioAccess Mobile (PC) — WebView fiel al APK
==========================================
Ventana vertical (412x869) que renderiza la MISMA interfaz móvil que ya
existe en mobile/ (y que usa el APK), mediante QWebEngineView. No inventa
una UI nueva: reutiliza mobile/index.html + app.css + app.js tal cual.

Modos:
  - Local/offline: carga mobile/index.html desde disco (apariencia idéntica).
  - Servidor: carga http://<ip>:<port>/mobile del servidor BioAccess real.

Ejecutar:  python bioaccess_mobile_web.py
"""

import sys, os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QToolBar, QStatusBar,
)
from PyQt6.QtCore import Qt, QUrl, QSize
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

APP_TITLE = "BioAccess Mobile (PC)"
WIN_W, WIN_H = 412, 869


def resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class MobileWebWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(WIN_W, WIN_H)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- toolbar (compacta) ---
        tb = QWidget()
        tb.setStyleSheet("background:#06091a; padding:4px;")
        tlay = QHBoxLayout(tb)
        tlay.setContentsMargins(6, 4, 6, 4)
        tlay.setSpacing(4)
        self.url_edit = QLineEdit("http://127.0.0.1:8080/mobile")
        self.url_edit.setStyleSheet("background:#0f172a;color:#cbd5e1;border:1px solid #1e293b;border-radius:6px;padding:4px;")
        tlay.addWidget(self.url_edit, 1)
        btn_srv = QPushButton("Servidor")
        btn_srv.setStyleSheet("background:#2563eb;color:#fff;border:none;border-radius:6px;padding:4px 8px;font-size:11px;")
        btn_srv.clicked.connect(self.load_server)
        tlay.addWidget(btn_srv)
        btn_loc = QPushButton("Local")
        btn_loc.setStyleSheet("background:#374151;color:#fff;border:none;border-radius:6px;padding:4px 8px;font-size:11px;")
        btn_loc.clicked.connect(self.load_local)
        tlay.addWidget(btn_loc)
        root.addWidget(tb)

        # --- webview ---
        self.view = QWebEngineView()
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        root.addWidget(self.view, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo")

        # carga inicial: local (apariencia idéntica sin servidor)
        self.load_local()

    def load_local(self):
        idx = resource_path(os.path.join("mobile", "index.html"))
        if not os.path.exists(idx):
            self.status.showMessage(f"No se encontró {idx}")
            return
        self.view.setUrl(QUrl.fromLocalFile(idx))
        self.status.showMessage(f"Local: {idx}")

    def load_server(self):
        url = self.url_edit.text().strip()
        if not url:
            return
        self.view.setUrl(QUrl(url))
        self.status.showMessage(f"Servidor: {url}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = MobileWebWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
