# -*- coding: utf-8 -*-
"""
BioAccess Android Phone Simulator (PC Frame)
===========================================
Aplicación de escritorio PyQt6 que emula un smartphone moderno para pruebas
y demostraciones del sistema BioAccess sin necesidad de un celular real.

Incluye:
  - Marco de celular (aspecto 19.5:9, bordes redondeados, notch, nav bar)
  - Botones físicos simulados (Vol+, Vol-, Power)
  - Pantalla interna con QStackedWidget (Home, ADB, Biometría, Logs, Settings)
  - Módulo ADB (QThread) con modo Mock cuando no hay dispositivo real
  - Módulo BioAccess (conexión WS al servidor, simulación de huella)
  - Consola de logs en tiempo real
  - Temas oscuro/claro

Ejecutar:  python android_simulator.py
"""

import sys
import os
import json
import time
import socket
import subprocess
import threading

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox, QProgressBar,
    QFrame, QScrollArea, QGridLayout, QSizePolicy, QSpacerItem, QCheckBox,
    QTabWidget, QPlainTextEdit, QToolButton, QButtonGroup,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QRect, QPoint, QPropertyAnimation,
    QEasingCurve, QObject,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QIcon, QPainter, QPen, QBrush, QFontMetrics,
    QLinearGradient, QRadialGradient, QCursor,
)

# ----------------------------- Constants -----------------------------
APP_TITLE = "BioAccess Phone Simulator"
PHONE_W, PHONE_H = 400, 860          # marco total
SCREEN_W, SCREEN_H = 360, 720       # pantalla interna
ASPECT = 19.5 / 9.0

DARK_QSS = """
QWidget { background: #0a0e1a; color: #e8f0ff; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QFrame#phoneFrame { background: #1a1f2e; border: 2px solid #2a3142; border-radius: 48px; }
QFrame#screen { background: #0d1220; border-radius: 36px; }
QLabel#title { font-size: 16px; font-weight: 700; color: #00e5ff; }
QLabel#subtitle { font-size: 11px; color: #8892a6; }
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1f2937, stop:1 #111827);
    color: #e8f0ff; border: 1px solid #374151; border-radius: 12px;
    padding: 8px 14px; font-weight: 600;
}
QPushButton:hover { background: #2563eb; border-color: #3b82f6; }
QPushButton:pressed { background: #1e40af; }
QPushButton#accent { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00e5ff, stop:1 #7c3aed); color: #000; border: none; }
QPushButton#danger { background: #dc2626; border-color: #ef4444; }
QPushButton#success { background: #16a34a; border-color: #22c55e; }
QTextEdit, QPlainTextEdit, QLineEdit {
    background: #0f172a; color: #cbd5e1; border: 1px solid #1e293b; border-radius: 8px;
    padding: 6px; font-family: 'Consolas', 'Cascadia Code', monospace; font-size: 11px;
}
QComboBox { background: #1f2937; border: 1px solid #374151; border-radius: 8px; padding: 6px; }
QProgressBar { background: #1f2937; border: 1px solid #374151; border-radius: 8px; text-align: center; color: #fff; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00e5ff, stop:1 #7c3aed); border-radius: 8px; }
QCheckBox { spacing: 8px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0f172a; width: 8px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 4px; min-height: 20px; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #1f2937; color: #94a3b8; padding: 6px 12px; border-radius: 8px; margin: 2px; }
QTabBar::tab:selected { background: #2563eb; color: #fff; }
"""

LIGHT_QSS = """
QWidget { background: #f1f5f9; color: #0f172a; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QFrame#phoneFrame { background: #ffffff; border: 2px solid #cbd5e1; border-radius: 48px; }
QFrame#screen { background: #f8fafc; border-radius: 36px; }
QLabel#title { font-size: 16px; font-weight: 700; color: #2563eb; }
QPushButton { background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 12px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #3b82f6; color: #fff; }
QPushButton#accent { background: #2563eb; color: #fff; border: none; }
QTextEdit, QPlainTextEdit, QLineEdit { background: #fff; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px; font-family: monospace; font-size: 11px; }
QProgressBar { background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 8px; text-align: center; }
QProgressBar::chunk { background: #2563eb; border-radius: 8px; }
"""


# ----------------------------- ADB Worker -----------------------------
class AdbWorker(QThread):
    result = pyqtSignal(str, object)   # (command_key, payload)
    log = pyqtSignal(str)

    def __init__(self, cmd_key, args, parent=None):
        super().__init__(parent)
        self.cmd_key = cmd_key
        self.args = args

    def run(self):
        try:
            self.log.emit(f"[ADB] ejecutando: {' '.join(self.args)}")
            proc = subprocess.run(
                self.args, capture_output=True, text=True, timeout=30,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            out = (proc.stdout or "").strip()
            err = (proc.stderr or "").strip()
            payload = {"rc": proc.returncode, "stdout": out, "stderr": err}
            self.log.emit(f"[ADB] rc={proc.returncode} out={out[:200]}")
            self.result.emit(self.cmd_key, payload)
        except FileNotFoundError:
            self.log.emit("[ADB] adb no encontrado en PATH")
            self.result.emit(self.cmd_key, {"rc": -1, "stdout": "", "stderr": "adb not found"})
        except subprocess.TimeoutExpired:
            self.log.emit("[ADB] timeout")
            self.result.emit(self.cmd_key, {"rc": -2, "stdout": "", "stderr": "timeout"})
        except Exception as e:
            self.log.emit(f"[ADB] error: {e}")
            self.result.emit(self.cmd_key, {"rc": -3, "stdout": "", "stderr": str(e)})


# ----------------------------- BioAccess WS Worker -----------------------------
class BioAccessWorker(QThread):
    connected = pyqtSignal(bool, str)
    message = pyqtSignal(dict)
    log = pyqtSignal(str)

    def __init__(self, ip, port, device_id, parent=None):
        super().__init__(parent)
        self.ip = ip
        self.port = port
        self.device_id = device_id
        self._running = True
        self._ws = None

    def stop(self):
        self._running = False
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass

    def send(self, obj):
        try:
            if self._ws:
                self._ws.send(json.dumps(obj))
        except Exception as e:
            self.log.emit(f"[WS] send error: {e}")

    def run(self):
        try:
            import websocket as wslib
        except ImportError:
            self.log.emit("[WS] websocket-client no instalado")
            self.connected.emit(False, "websocket-client missing")
            return
        url = f"ws://{self.ip}:{self.port}/ws?role=phone&device=SimulatorPhone&device_id={self.device_id}"
        self.log.emit(f"[WS] conectando a {url}")
        try:
            self._ws = wslib.create_connection(url, timeout=8)
        except Exception as e:
            self.log.emit(f"[WS] fallo conexion: {e}")
            self.connected.emit(False, str(e))
            return
        self.connected.emit(True, "connected")
        # hello
        try:
            self._ws.send(json.dumps({"type": "hello", "device": "SimulatorPhone", "device_id": self.device_id}))
        except Exception:
            pass
        while self._running:
            try:
                self._ws.settimeout(1.0)
                raw = self._ws.recv()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except Exception:
                    obj = {"raw": raw}
                self.message.emit(obj)
            except Exception as e:
                if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                    continue
                self.log.emit(f"[WS] recv error: {e}")
                break
        try:
            self._ws.close()
        except Exception:
            pass
        self.connected.emit(False, "disconnected")


# ----------------------------- Phone Frame Widgets -----------------------------
class AppIcon(QPushButton):
    def __init__(self, emoji, name, callback=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(76, 84)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 6, 4, 6)
        v.setSpacing(4)
        ico = QLabel(emoji)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size: 34px; background: transparent;")
        lbl = QLabel(name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 10px; color: #cbd5e1; background: transparent;")
        lbl.setWordWrap(True)
        v.addWidget(ico)
        v.addWidget(lbl)
        self.setStyleSheet("""
            QPushButton { background: transparent; border: none; }
            QPushButton:hover { background: rgba(255,255,255,0.08); border-radius: 14px; }
        """)
        if callback:
            self.clicked.connect(callback)


class HomeScreen(QWidget):
    open_app = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 16)
        # status bar
        sb = QHBoxLayout()
        t = QLabel("9:41")
        t.setStyleSheet("color:#fff;font-weight:700;font-size:12px;background:transparent;")
        sb.addWidget(t)
        sb.addStretch()
        for ic in ("📶", "🔋"):
            l = QLabel(ic); l.setStyleSheet("font-size:12px;background:transparent;"); sb.addWidget(l)
        layout.addLayout(sb)
        layout.addSpacing(8)
        # search
        search = QLabel("🔍  Buscar apps…")
        search.setStyleSheet("background: rgba(255,255,255,0.1); color:#94a3b8; padding:8px 12px; border-radius:14px; font-size:12px;")
        layout.addWidget(search)
        layout.addSpacing(12)
        # grid
        grid = QGridLayout()
        grid.setSpacing(8)
        apps = [
            ("🔐", "BioAccess", "bioaccess"),
            ("⚙️", "Ajustes", "settings"),
            ("📋", "Logs", "logs"),
            ("📱", "ADB", "adb"),
            ("🌐", "Navegador", "browser"),
            ("📷", "Cámara", "camera"),
            ("💬", "Mensajes", "msgs"),
            ("🎵", "Música", "music"),
            ("🧮", "Calc", "calc"),
            ("📁", "Archivos", "files"),
            ("🗺️", "Mapas", "maps"),
            ("🎮", "Juegos", "games"),
        ]
        r, c = 0, 0
        for emoji, name, key in apps:
            icon = AppIcon(emoji, name, lambda k=key: self.open_app.emit(k))
            grid.addWidget(icon, r, c)
            c += 1
            if c >= 4:
                c = 0; r += 1
        layout.addLayout(grid)
        layout.addStretch()
        # dock
        dock = QHBoxLayout()
        for emoji in ("🏠", "🔍", "➕", "◀"):
            b = QLabel(emoji); b.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b.setStyleSheet("font-size:20px;background:rgba(255,255,255,0.08);border-radius:18px;padding:6px;")
            dock.addWidget(b)
        layout.addLayout(dock)


class AdbPanel(QWidget):
    def __init__(self, log_cb, parent=None):
        super().__init__(parent)
        self.log_cb = log_cb
        self._workers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        t = QLabel("Módulo ADB / USB")
        t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Conexión por cable y comandos de sistema")
        sub.setObjectName("subtitle"); layout.addWidget(sub)
        layout.addSpacing(10)

        self.state_lbl = QLabel("Estado: Desconectado")
        self.state_lbl.setStyleSheet("font-weight:700;color:#f87171;")
        layout.addWidget(self.state_lbl)

        form = QGridLayout()
        form.addWidget(QLabel("IP:"), 0, 0)
        self.ip_edit = QLineEdit("127.0.0.1"); form.addWidget(self.ip_edit, 0, 1)
        form.addWidget(QLabel("Puerto ADB:"), 1, 0)
        self.port_edit = QLineEdit("5555"); form.addWidget(self.port_edit, 1, 1)
        form.addWidget(QLabel("Device ID:"), 2, 0)
        self.dev_edit = QLineEdit("emulator-5554"); form.addWidget(self.dev_edit, 2, 1)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.btn_detect = QPushButton("Detectar dispositivos")
        self.btn_detect.clicked.connect(self.detect)
        self.btn_connect = QPushButton("Conectar TCP/IP")
        self.btn_connect.clicked.connect(self.connect_tcp)
        btns.addWidget(self.btn_detect); btns.addWidget(self.btn_connect)
        layout.addLayout(btns)

        btns2 = QHBoxLayout()
        self.btn_install = QPushButton("Instalar APK")
        self.btn_install.clicked.connect(self.install_apk)
        self.btn_shell = QPushButton("Shell: getprop")
        self.btn_shell.clicked.connect(self.shell_prop)
        btns2.addWidget(self.btn_install); btns2.addWidget(self.btn_shell)
        layout.addLayout(btns2)

        self.mock_chk = QCheckBox("Modo Demostración / Mock (sin ADB real)")
        self.mock_chk.setChecked(True)
        self.mock_chk.stateChanged.connect(self.toggle_mock)
        layout.addWidget(self.mock_chk)

        self.result_box = QPlainTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setPlaceholderText("Resultados de comandos ADB aparecerán aquí…")
        layout.addWidget(self.result_box, 1)

    def _run(self, key, args):
        w = AdbWorker(key, args)
        w.result.connect(self._on_result)
        w.log.connect(self.log_cb)
        self._workers.append(w)
        w.start()

    def _on_result(self, key, payload):
        rc = payload.get("rc")
        out = payload.get("stdout", "")
        err = payload.get("stderr", "")
        if rc == 0:
            self.state_lbl.setText(f"Estado: Conectado ({key})")
            self.state_lbl.setStyleSheet("font-weight:700;color:#4ade80;")
        else:
            if self.mock_chk.isChecked():
                self._mock_result(key)
                return
            self.state_lbl.setText("Estado: Error / Desconectado")
            self.state_lbl.setStyleSheet("font-weight:700;color:#f87171;")
        text = f"=== {key} (rc={rc}) ===\n{out}\n{err}\n"
        self.result_box.appendPlainText(text)
        self.log_cb(f"[ADB] {key}: rc={rc}")

    def _mock_result(self, key):
        self.state_lbl.setText("Estado: Dispositivo detectado (MOCK)")
        self.state_lbl.setStyleSheet("font-weight:700;color:#fbbf24;")
        mocks = {
            "devices": "List of devices attached\nemulator-5554\tdevice",
            "connect": "connected to 127.0.0.1:5555",
            "install": "Success",
            "prop": "ro.product.model=Pixel 7\nro.build.version.release=14",
        }
        out = mocks.get(key, "OK (mock)")
        self.result_box.appendPlainText(f"=== {key} (mock) ===\n{out}\n")
        self.log_cb(f"[ADB-MOCK] {key}: OK")

    def detect(self):
        if self.mock_chk.isChecked():
            self._mock_result("devices"); return
        self._run("devices", ["adb", "devices"])

    def connect_tcp(self):
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        if self.mock_chk.isChecked():
            self._mock_result("connect"); return
        self._run("connect", ["adb", "connect", f"{ip}:{port}"])

    def install_apk(self):
        if self.mock_chk.isChecked():
            self._mock_result("install"); return
        self._run("install", ["adb", "install", "-r", "app.apk"])

    def shell_prop(self):
        if self.mock_chk.isChecked():
            self._mock_result("prop"); return
        self._run("prop", ["adb", "shell", "getprop"])

    def toggle_mock(self, state):
        self.log_cb(f"[ADB] Mock mode: {'ON' if state else 'OFF'}")


class BiometricPanel(QWidget):
    def __init__(self, log_cb, parent=None):
        super().__init__(parent)
        self.log_cb = log_cb
        self._progress = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        t = QLabel("Biometría / BioAccess")
        t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Simulación de escaneo dactilar")
        sub.setObjectName("subtitle"); layout.addWidget(sub)
        layout.addSpacing(10)

        self.finger = QLabel("👆")
        self.finger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.finger.setStyleSheet("font-size: 96px; background: transparent;")
        layout.addWidget(self.finger)

        self.status = QLabel("Esperando escaneo…")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-weight:700;color:#94a3b8;")
        layout.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100); self.bar.setValue(0)
        layout.addWidget(self.bar)

        btns = QHBoxLayout()
        self.btn_ok = QPushButton("Simular Huella Correcta")
        self.btn_ok.setObjectName("success")
        self.btn_ok.clicked.connect(lambda: self.simulate(True))
        self.btn_bad = QPushButton("Simular Huella Incorrecta")
        self.btn_bad.setObjectName("danger")
        self.btn_bad.clicked.connect(lambda: self.simulate(False))
        btns.addWidget(self.btn_ok); btns.addWidget(self.btn_bad)
        layout.addLayout(btns)

        layout.addSpacing(6)
        self.result = QLabel("")
        self.result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result.setStyleSheet("font-size:12px;")
        layout.addWidget(self.result)

        # BioAccess connection section
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#334155;"); layout.addWidget(sep)
        layout.addWidget(QLabel("Conexión BioAccess (servidor PC):"))
        form = QGridLayout()
        form.addWidget(QLabel("IP servidor:"), 0, 0)
        self.ba_ip = QLineEdit("127.0.0.1"); form.addWidget(self.ba_ip, 0, 1)
        form.addWidget(QLabel("Puerto:"), 1, 0)
        self.ba_port = QLineEdit("8080"); form.addWidget(self.ba_port, 1, 1)
        form.addWidget(QLabel("Código pairing:"), 2, 0)
        self.ba_code = QLineEdit(""); form.addWidget(self.ba_code, 2, 1)
        layout.addLayout(form)
        b2 = QHBoxLayout()
        self.btn_ba_connect = QPushButton("Conectar al servidor")
        self.btn_ba_connect.setObjectName("accent")
        self.btn_ba_connect.clicked.connect(self.ba_connect)
        self.btn_ba_pair = QPushButton("Vincular (código)")
        self.btn_ba_pair.clicked.connect(self.ba_pair)
        b2.addWidget(self.btn_ba_connect); b2.addWidget(self.btn_ba_pair)
        layout.addLayout(b2)
        self.ba_status = QLabel("BioAccess: desconectado")
        self.ba_status.setStyleSheet("color:#94a3b8;font-size:11px;")
        layout.addWidget(self.ba_status)
        self._ba_worker = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._tick_target = 0

    def simulate(self, ok):
        self._progress = 0
        self.bar.setValue(0)
        self.status.setText("Escaneando…")
        self.status.setStyleSheet("font-weight:700;color:#fbbf24;")
        self.finger.setText("🔍")
        self._tick_target = 100
        self._timer.start(30)
        QTimer.singleShot(1200, lambda: self._finish(ok))

    def _tick(self):
        if self._progress < self._tick_target:
            self._progress += 4
            self.bar.setValue(min(self._progress, 100))
        else:
            self._timer.stop()

    def _finish(self, ok):
        self._timer.stop()
        self.bar.setValue(100)
        if ok:
            self.finger.setText("✅")
            self.status.setText("Huella válida")
            self.status.setStyleSheet("font-weight:700;color:#4ade80;")
            self.result.setText("Acceso concedido — token generado")
            self.result.setStyleSheet("color:#4ade80;")
            self.log_cb("[BIO] huella correcta → acceso concedido")
            if self._ba_worker:
                self._ba_worker.send({"type": "scan_result", "ok": True, "method": "fingerprint", "device": "SimulatorPhone"})
        else:
            self.finger.setText("❌")
            self.status.setText("Huella no reconocida")
            self.status.setStyleSheet("font-weight:700;color:#f87171;")
            self.result.setText("Acceso denegado")
            self.result.setStyleSheet("color:#f87171;")
            self.log_cb("[BIO] huella incorrecta → acceso denegado")
            if self._ba_worker:
                self._ba_worker.send({"type": "scan_result", "ok": False, "method": "fingerprint", "device": "SimulatorPhone"})

    def ba_connect(self):
        ip = self.ba_ip.text().strip()
        port = self.ba_port.text().strip()
        dev_id = "sim-" + (socket.gethostname() or "pc")
        if self._ba_worker:
            self._ba_worker.stop()
            self._ba_worker = None
        w = BioAccessWorker(ip, port, dev_id)
        w.connected.connect(self._ba_on_conn)
        w.message.connect(self._ba_on_msg)
        w.log.connect(self.log_cb)
        self._ba_worker = w
        w.start()
        self.ba_status.setText("BioAccess: conectando…")
        self.log_cb(f"[BA] conectando a {ip}:{port}")

    def _ba_on_conn(self, ok, msg):
        if ok:
            self.ba_status.setText("BioAccess: conectado ✓")
            self.ba_status.setStyleSheet("color:#4ade80;font-size:11px;")
            self.log_cb("[BA] conectado")
        else:
            self.ba_status.setText(f"BioAccess: {msg}")
            self.ba_status.setStyleSheet("color:#f87171;font-size:11px;")
            self.log_cb(f"[BA] error: {msg}")

    def _ba_on_msg(self, obj):
        self.log_cb(f"[BA-WS] {json.dumps(obj)[:200]}")
        t = obj.get("type")
        if t == "scan_request":
            rid = obj.get("id")
            self.log_cb(f"[BA] scan_request recibido id={rid}")
            self.status.setText("Escaneo solicitado por PC…")
            self.status.setStyleSheet("font-weight:700;color:#fbbf24;")
            # auto-simulate after short delay
            QTimer.singleShot(800, lambda: self.simulate(True))
        elif t == "pair_result":
            ok = obj.get("ok", False)
            self.log_cb(f"[BA] pair_result ok={ok}")
            self.ba_status.setText(f"Vinculación: {'OK' if ok else 'FAIL'}")
        elif t == "hello_ack":
            self.log_cb("[BA] hello_ack recibido")

    def ba_pair(self):
        code = self.ba_code.text().strip()
        if not code:
            self.log_cb("[BA] código vacío"); return
        if self._ba_worker:
            self._ba_worker.send({"type": "pair_request", "code": code, "device": "SimulatorPhone", "device_id": "sim-" + socket.gethostname()})
            self.log_cb(f"[BA] pair_request enviado código={code}")
        else:
            self.log_cb("[BA] no conectado")


class LogsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        t = QLabel("Consola de Logs")
        t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Intents, comandos ADB y eventos del sistema")
        sub.setObjectName("subtitle"); layout.addWidget(sub)
        self.box = QPlainTextEdit()
        self.box.setReadOnly(True)
        layout.addWidget(self.box, 1)
        btns = QHBoxLayout()
        clr = QPushButton("Limpiar"); clr.clicked.connect(self.box.clear)
        exp = QPushButton("Exportar"); exp.clicked.connect(self.export)
        btns.addWidget(clr); btns.addWidget(exp)
        layout.addLayout(btns)

    def append(self, line):
        ts = time.strftime("%H:%M:%S")
        self.box.appendPlainText(f"[{ts}] {line}")

    def export(self):
        path = os.path.join(os.path.expanduser("~"), "simulator_logs.txt")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.box.toPlainText())
            self.append(f"Logs exportados a {path}")
        except Exception as e:
            self.append(f"Error exportando: {e}")


class SettingsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 16)
        t = QLabel("Ajustes")
        t.setObjectName("title"); layout.addWidget(t)
        self.theme_chk = QCheckBox("Tema claro")
        layout.addWidget(self.theme_chk)
        self.mock_chk2 = QCheckBox("Forzar modo mock global")
        self.mock_chk2.setChecked(True)
        layout.addWidget(self.mock_chk2)
        layout.addStretch()


# ----------------------------- Main Phone Window -----------------------------
class PhoneSimulator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(PHONE_W, PHONE_H)
        self.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # phone frame
        self.frame = QFrame()
        self.frame.setObjectName("phoneFrame")
        self.frame.setFixedSize(PHONE_W, PHONE_H)
        froot = QVBoxLayout(self.frame)
        froot.setContentsMargins(20, 24, 20, 20)
        froot.setSpacing(0)

        # notch
        notch = QFrame()
        notch.setFixedHeight(28)
        notch.setStyleSheet("background: transparent;")
        nlay = QHBoxLayout(notch)
        nlay.setContentsMargins(0, 0, 0, 0)
        island = QFrame()
        island.setFixedSize(110, 22)
        island.setStyleSheet("background:#000; border-radius:11px;")
        nlay.addStretch(); nlay.addWidget(island); nlay.addStretch()
        froot.addWidget(notch)

        # screen
        self.screen = QFrame()
        self.screen.setObjectName("screen")
        self.screen.setFixedSize(SCREEN_W, SCREEN_H)
        slay = QVBoxLayout(self.screen)
        slay.setContentsMargins(0, 0, 0, 0)
        slay.setSpacing(0)

        self.stack = QStackedWidget()
        slay.addWidget(self.stack)

        # bottom nav bar
        nav = QFrame()
        nav.setFixedHeight(44)
        nav.setStyleSheet("background: rgba(0,0,0,0.3);")
        nlay2 = QHBoxLayout(nav)
        nlay2.setContentsMargins(20, 4, 20, 4)
        for emoji in ("◀", "●", "■"):
            b = QPushButton(emoji)
            b.setFixedSize(40, 32)
            b.setStyleSheet("background:transparent;border:none;font-size:16px;color:#94a3b8;")
            b.clicked.connect(self.go_home)
            nlay2.addWidget(b)
        slay.addWidget(nav)

        froot.addWidget(self.screen, 0, Qt.AlignmentFlag.AlignHCenter)

        # side buttons (power/volume) as floating widgets on frame edges
        # We'll add them as child widgets positioned absolutely
        self.vol_up = QPushButton("VOL+", self.frame)
        self.vol_up.setFixedSize(6, 40)
        self.vol_up.move(0, 180)
        self.vol_up.setStyleSheet("background:#2a3142;border:none;border-radius:3px;")
        self.vol_down = QPushButton("VOL-", self.frame)
        self.vol_down.setFixedSize(6, 40)
        self.vol_down.move(0, 230)
        self.vol_down.setStyleSheet("background:#2a3142;border:none;border-radius:3px;")
        self.power = QPushButton("PWR", self.frame)
        self.power.setFixedSize(6, 50)
        self.power.move(PHONE_W - 6, 200)
        self.power.setStyleSheet("background:#2a3142;border:none;border-radius:3px;")
        self.power.clicked.connect(self.toggle_lock)

        root.addWidget(self.frame, 0, Qt.AlignmentFlag.AlignCenter)

        # logs panel shared
        self.logs = LogsPanel()

        # pages
        self.home = HomeScreen()
        self.home.open_app.connect(self.open_app)
        self.adb = AdbPanel(self.logs.append)
        self.bio = BiometricPanel(self.logs.append)
        self.settings = SettingsPanel()

        self.stack.addWidget(self.home)       # 0
        self.stack.addWidget(self.adb)        # 1
        self.stack.addWidget(self.bio)        # 2
        self.stack.addWidget(self.logs)       # 3
        self.stack.addWidget(self.settings)   # 4

        self._locked = False
        self.go_home()

    def open_app(self, key):
        mapping = {
            "bioaccess": 2,
            "adb": 1,
            "logs": 3,
            "settings": 4,
        }
        if key in mapping:
            self.stack.setCurrentIndex(mapping[key])
            self.logs.append(f"[HOME] abrió app: {key}")
        else:
            self.logs.append(f"[HOME] app no implementada: {key}")

    def go_home(self):
        self.stack.setCurrentIndex(0)

    def toggle_lock(self):
        self._locked = not self._locked
        if self._locked:
            self.screen.setStyleSheet("background:#000;border-radius:36px;")
            self.logs.append("[PWR] pantalla bloqueada")
        else:
            self.screen.setStyleSheet("")
            self.screen.setObjectName("screen")
            self.logs.append("[PWR] pantalla desbloqueada")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = PhoneSimulator()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
