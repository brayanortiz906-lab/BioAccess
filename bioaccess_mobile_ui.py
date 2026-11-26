# -*- coding: utf-8 -*-
"""
BioAccess Mobile UI (PC) — Pantalla móvil sin marco decorativo
================================================================
Interfaz vertical optimizada para PC (412x869) que emula la app móvil
BioAccess + módulos de prueba ADB/Hardware/Logs. Sin marcos de teléfono.

Ejecutar:  python bioaccess_mobile_ui.py
"""

import sys, os, json, time, socket, subprocess

from PyQt6.QtWidgets import (
    QApplication, QWidget, QMainWindow, QStackedWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox,
    QProgressBar, QFrame, QScrollArea, QGridLayout, QCheckBox, QSizePolicy,
    QSpacerItem, QButtonGroup, QToolButton,
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QSize, QRect, QPoint, QPropertyAnimation,
    QEasingCurve, QParallelAnimationGroup,
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QLinearGradient, QFontMetrics

APP_TITLE = "BioAccess Mobile UI"
WIN_W, WIN_H = 412, 869

DARK_QSS = """
QWidget { background: #0b1020; color: #e8f0ff; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }
QLabel#title { font-size: 18px; font-weight: 700; color: #00e5ff; }
QLabel#subtitle { font-size: 11px; color: #8892a6; }
QLabel#statusbar { background: #06091a; color: #cbd5e1; font-size: 11px; padding: 4px 10px; }
QFrame#card { background: #131a2e; border: 1px solid #1f2a44; border-radius: 16px; }
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1f2937, stop:1 #111827);
    color: #e8f0ff; border: 1px solid #374151; border-radius: 14px;
    padding: 10px 16px; font-weight: 600;
}
QPushButton:hover { background: #2563eb; border-color: #3b82f6; }
QPushButton:pressed { background: #1e40af; }
QPushButton#accent { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00e5ff, stop:1 #7c3aed); color: #000; border: none; }
QPushButton#danger { background: #dc2626; border-color: #ef4444; }
QPushButton#success { background: #16a34a; border-color: #22c55e; }
QPushButton#nav { background: transparent; border: none; color: #94a3b8; font-size: 11px; padding: 6px; border-radius: 0; }
QPushButton#nav:checked { color: #00e5ff; }
QTextEdit, QPlainTextEdit, QLineEdit {
    background: #0f172a; color: #cbd5e1; border: 1px solid #1e293b; border-radius: 10px;
    padding: 6px; font-family: 'Consolas', monospace; font-size: 11px;
}
QProgressBar { background: #1f2937; border: 1px solid #374151; border-radius: 8px; text-align: center; color: #fff; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #00e5ff, stop:1 #7c3aed); border-radius: 8px; }
QCheckBox { spacing: 8px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0f172a; width: 6px; border-radius: 3px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 3px; min-height: 20px; }
"""


# ----------------------------- Workers -----------------------------
class AdbWorker(QThread):
    result = pyqtSignal(str, object)
    log = pyqtSignal(str)

    def __init__(self, key, args):
        super().__init__()
        self.key = key; self.args = args

    def run(self):
        try:
            self.log.emit(f"[ADB] {' '.join(self.args)}")
            proc = subprocess.run(self.args, capture_output=True, text=True, timeout=20,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            payload = {"rc": proc.returncode, "stdout": (proc.stdout or "").strip(),
                       "stderr": (proc.stderr or "").strip()}
            self.log.emit(f"[ADB] rc={proc.returncode}")
            self.result.emit(self.key, payload)
        except FileNotFoundError:
            self.result.emit(self.key, {"rc": -1, "stdout": "", "stderr": "adb not found"})
        except Exception as e:
            self.result.emit(self.key, {"rc": -2, "stdout": "", "stderr": str(e)})


class BioAccessWorker(QThread):
    connected = pyqtSignal(bool, str)
    message = pyqtSignal(dict)
    log = pyqtSignal(str)

    def __init__(self, ip, port, device_id):
        super().__init__()
        self.ip = ip; self.port = port; self.device_id = device_id
        self._running = True; self._ws = None

    def stop(self):
        self._running = False
        try:
            if self._ws: self._ws.close()
        except Exception: pass

    def send(self, obj):
        try:
            if self._ws: self._ws.send(json.dumps(obj))
        except Exception as e:
            self.log.emit(f"[WS] send err: {e}")

    def run(self):
        try:
            import websocket as wslib
        except ImportError:
            self.connected.emit(False, "websocket-client missing"); return
        url = f"ws://{self.ip}:{self.port}/ws?role=phone&device=MobileUI&device_id={self.device_id}"
        self.log.emit(f"[WS] conectando {url}")
        try:
            self._ws = wslib.create_connection(url, timeout=8)
        except Exception as e:
            self.log.emit(f"[WS] fallo: {e}")
            self.connected.emit(False, str(e)); return
        self.connected.emit(True, "connected")
        try:
            self._ws.send(json.dumps({"type": "hello", "device": "MobileUI", "device_id": self.device_id}))
        except Exception: pass
        while self._running:
            try:
                self._ws.settimeout(1.0)
                raw = self._ws.recv()
                if not raw: continue
                try: obj = json.loads(raw)
                except Exception: obj = {"raw": raw}
                self.message.emit(obj)
            except Exception as e:
                if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                    continue
                self.log.emit(f"[WS] recv err: {e}"); break
        try: self._ws.close()
        except Exception: pass
        self.connected.emit(False, "disconnected")


# ----------------------------- Status Bar -----------------------------
class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.setStyleSheet("background:#06091a;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        self.time_lbl = QLabel(time.strftime("%H:%M"))
        self.time_lbl.setStyleSheet("color:#fff;font-weight:700;font-size:12px;")
        lay.addWidget(self.time_lbl)
        lay.addStretch()
        self.wifi = QLabel("📶")
        self.batt = QLabel("🔋 87%")
        self.usb = QLabel("🔌")
        for w in (self.wifi, self.batt, self.usb):
            w.setStyleSheet("font-size:12px;"); lay.addWidget(w)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30000)

    def _tick(self):
        self.time_lbl.setText(time.strftime("%H:%M"))

    def set_usb(self, state):
        self.usb.setText("🔌" if state else "⬜")
        self.usb.setStyleSheet(f"font-size:12px;color:{'#4ade80' if state else '#94a3b8'};")


# ----------------------------- Pages -----------------------------
class BioAccessPage(QWidget):
    def __init__(self, log_cb, parent=None):
        super().__init__(parent)
        self.log_cb = log_cb
        self._ba = None
        self._progress = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        t = QLabel("BioAccess"); t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Control de acceso biométrico"); sub.setObjectName("subtitle"); layout.addWidget(sub)

        # connection card
        card = QFrame(); card.setObjectName("card")
        cl = QVBoxLayout(card); cl.setContentsMargins(14, 12, 14, 12)
        self.conn_lbl = QLabel("Estado: Desconectado")
        self.conn_lbl.setStyleSheet("font-weight:700;color:#f87171;")
        cl.addWidget(self.conn_lbl)
        form = QGridLayout()
        form.addWidget(QLabel("IP servidor:"), 0, 0)
        self.ip_edit = QLineEdit("127.0.0.1"); form.addWidget(self.ip_edit, 0, 1)
        form.addWidget(QLabel("Puerto:"), 1, 0)
        self.port_edit = QLineEdit("8080"); form.addWidget(self.port_edit, 1, 1)
        form.addWidget(QLabel("Código:"), 2, 0)
        self.code_edit = QLineEdit(""); form.addWidget(self.code_edit, 2, 1)
        cl.addLayout(form)
        btns = QHBoxLayout()
        self.btn_conn = QPushButton("Conectar"); self.btn_conn.setObjectName("accent")
        self.btn_conn.clicked.connect(self.connect)
        self.btn_pair = QPushButton("Vincular")
        self.btn_pair.clicked.connect(self.pair)
        btns.addWidget(self.btn_conn); btns.addWidget(self.btn_pair)
        cl.addLayout(btns)
        layout.addWidget(card)

        # fingerprint card
        card2 = QFrame(); card2.setObjectName("card")
        c2 = QVBoxLayout(card2); c2.setContentsMargins(14, 12, 14, 12)
        self.finger = QLabel("👆"); self.finger.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.finger.setStyleSheet("font-size: 72px;")
        c2.addWidget(self.finger)
        self.status = QLabel("Esperando escaneo…"); self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("font-weight:700;color:#94a3b8;")
        c2.addWidget(self.status)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setValue(0)
        c2.addWidget(self.bar)
        b = QHBoxLayout()
        ok = QPushButton("Huella Correcta"); ok.setObjectName("success"); ok.clicked.connect(lambda: self.simulate(True))
        bad = QPushButton("Huella Incorrecta"); bad.setObjectName("danger"); bad.clicked.connect(lambda: self.simulate(False))
        b.addWidget(ok); b.addWidget(bad)
        c2.addLayout(b)
        self.result = QLabel(""); self.result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c2.addWidget(self.result)
        layout.addWidget(card2)

        # recent events
        card3 = QFrame(); card3.setObjectName("card")
        c3 = QVBoxLayout(card3); c3.setContentsMargins(14, 12, 14, 12)
        c3.addWidget(QLabel("Eventos recientes"))
        self.events = QPlainTextEdit(); self.events.setReadOnly(True); self.events.setFixedHeight(120)
        c3.addWidget(self.events)
        layout.addWidget(card3)
        layout.addStretch()

        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._target = 0

    def simulate(self, ok):
        self._progress = 0; self.bar.setValue(0)
        self.status.setText("Escaneando…"); self.status.setStyleSheet("font-weight:700;color:#fbbf24;")
        self.finger.setText("🔍"); self._target = 100; self._timer.start(30)
        QTimer.singleShot(1100, lambda: self._finish(ok))

    def _tick(self):
        if self._progress < self._target:
            self._progress += 5; self.bar.setValue(min(self._progress, 100))
        else: self._timer.stop()

    def _finish(self, ok):
        self._timer.stop(); self.bar.setValue(100)
        if ok:
            self.finger.setText("✅"); self.status.setText("Huella válida")
            self.status.setStyleSheet("font-weight:700;color:#4ade80;")
            self.result.setText("Acceso concedido"); self.result.setStyleSheet("color:#4ade80;")
            self.events.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Acceso concedido")
            self.log_cb("[BIO] huella correcta → concedido")
            if self._ba: self._ba.send({"type": "scan_result", "ok": True, "method": "fingerprint", "device": "MobileUI"})
        else:
            self.finger.setText("❌"); self.status.setText("No reconocida")
            self.status.setStyleSheet("font-weight:700;color:#f87171;")
            self.result.setText("Acceso denegado"); self.result.setStyleSheet("color:#f87171;")
            self.events.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Acceso denegado")
            self.log_cb("[BIO] huella incorrecta → denegado")
            if self._ba: self._ba.send({"type": "scan_result", "ok": False, "method": "fingerprint", "device": "MobileUI"})

    def connect(self):
        ip = self.ip_edit.text().strip(); port = self.port_edit.text().strip()
        dev_id = "mui-" + socket.gethostname()
        if self._ba: self._ba.stop()
        w = BioAccessWorker(ip, port, dev_id)
        w.connected.connect(self._on_conn); w.message.connect(self._on_msg); w.log.connect(self.log_cb)
        self._ba = w; w.start()
        self.conn_lbl.setText("Conectando…"); self.conn_lbl.setStyleSheet("font-weight:700;color:#fbbf24;")
        self.log_cb(f"[BA] conectando {ip}:{port}")

    def _on_conn(self, ok, msg):
        if ok:
            self.conn_lbl.setText("Conectado ✓"); self.conn_lbl.setStyleSheet("font-weight:700;color:#4ade80;")
            self.log_cb("[BA] conectado")
        else:
            self.conn_lbl.setText(f"Error: {msg}"); self.conn_lbl.setStyleSheet("font-weight:700;color:#f87171;")
            self.log_cb(f"[BA] error {msg}")

    def _on_msg(self, obj):
        self.log_cb(f"[BA-WS] {json.dumps(obj)[:150]}")
        t = obj.get("type")
        if t == "scan_request":
            self.log_cb(f"[BA] scan_request id={obj.get('id')}")
            self.status.setText("Escaneo solicitado por PC…")
            self.status.setStyleSheet("font-weight:700;color:#fbbf24;")
            QTimer.singleShot(700, lambda: self.simulate(True))
        elif t == "pair_result":
            self.events.appendPlainText(f"[{time.strftime('%H:%M:%S')}] Vinculación: {'OK' if obj.get('ok') else 'FAIL'}")
        elif t == "hello_ack":
            self.log_cb("[BA] hello_ack")

    def pair(self):
        code = self.code_edit.text().strip()
        if not code:
            self.log_cb("[BA] código vacío"); return
        if self._ba:
            self._ba.send({"type": "pair_request", "code": code, "device": "MobileUI", "device_id": "mui-" + socket.gethostname()})
            self.log_cb(f"[BA] pair_request {code}")


class AdbPage(QWidget):
    def __init__(self, log_cb, parent=None):
        super().__init__(parent)
        self.log_cb = log_cb
        self._workers = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(10)
        t = QLabel("ADB & Hardware USB"); t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Estado de dispositivos y comandos"); sub.setObjectName("subtitle"); layout.addWidget(sub)

        card = QFrame(); card.setObjectName("card"); cl = QVBoxLayout(card); cl.setContentsMargins(14, 12, 14, 12)
        self.state = QLabel("Estado: Desconectado"); self.state.setStyleSheet("font-weight:700;color:#f87171;")
        cl.addWidget(self.state)
        form = QGridLayout()
        form.addWidget(QLabel("IP:"), 0, 0); self.ip = QLineEdit("127.0.0.1"); form.addWidget(self.ip, 0, 1)
        form.addWidget(QLabel("Puerto:"), 1, 0); self.port = QLineEdit("5555"); form.addWidget(self.port, 1, 1)
        form.addWidget(QLabel("Device ID:"), 2, 0); self.dev = QLineEdit("emulator-5554"); form.addWidget(self.dev, 2, 1)
        cl.addLayout(form)
        btns = QHBoxLayout()
        d = QPushButton("Detectar"); d.clicked.connect(self.detect)
        c = QPushButton("Conectar"); c.clicked.connect(self.connect_tcp)
        btns.addWidget(d); btns.addWidget(c)
        cl.addLayout(btns)
        btns2 = QHBoxLayout()
        i = QPushButton("Instalar APK"); i.clicked.connect(self.install)
        s = QPushButton("Shell getprop"); s.clicked.connect(self.shell)
        btns2.addWidget(i); btns2.addWidget(s)
        cl.addLayout(btns2)
        self.mock = QCheckBox("Modo Mock / Simulación"); self.mock.setChecked(True)
        self.mock.stateChanged.connect(lambda v: self.log_cb(f"[ADB] Mock {'ON' if v else 'OFF'}"))
        cl.addWidget(self.mock)
        layout.addWidget(card)

        card2 = QFrame(); card2.setObjectName("card"); c2 = QVBoxLayout(card2); c2.setContentsMargins(14, 12, 14, 12)
        c2.addWidget(QLabel("Salida de comandos"))
        self.out = QPlainTextEdit(); self.out.setReadOnly(True); self.out.setFixedHeight(260)
        c2.addWidget(self.out)
        layout.addWidget(card2)
        layout.addStretch()

    def _run(self, key, args):
        w = AdbWorker(key, args); w.result.connect(self._on); w.log.connect(self.log_cb); self._workers.append(w); w.start()

    def _on(self, key, payload):
        rc = payload.get("rc"); out = payload.get("stdout", ""); err = payload.get("stderr", "")
        if rc == 0:
            self.state.setText(f"Conectado ({key})"); self.state.setStyleSheet("font-weight:700;color:#4ade80;")
        else:
            if self.mock.isChecked():
                self._mock(key); return
            self.state.setText("Error/Desconectado"); self.state.setStyleSheet("font-weight:700;color:#f87171;")
        self.out.appendPlainText(f"=== {key} (rc={rc}) ===\n{out}\n{err}\n")
        self.log_cb(f"[ADB] {key} rc={rc}")

    def _mock(self, key):
        self.state.setText("Dispositivo detectado (MOCK)"); self.state.setStyleSheet("font-weight:700;color:#fbbf24;")
        mocks = {"devices": "emulator-5554\tdevice", "connect": "connected to 127.0.0.1:5555",
                 "install": "Success", "prop": "ro.product.model=Pixel 7\nro.build.version.release=14"}
        self.out.appendPlainText(f"=== {key} (mock) ===\n{mocks.get(key, 'OK')}\n")
        self.log_cb(f"[ADB-MOCK] {key} OK")

    def detect(self):
        if self.mock.isChecked(): self._mock("devices"); return
        self._run("devices", ["adb", "devices"])
    def connect_tcp(self):
        if self.mock.isChecked(): self._mock("connect"); return
        self._run("connect", ["adb", "connect", f"{self.ip.text()}:{self.port.text()}"])
    def install(self):
        if self.mock.isChecked(): self._mock("install"); return
        self._run("install", ["adb", "install", "-r", "app.apk"])
    def shell(self):
        if self.mock.isChecked(): self._mock("prop"); return
        self._run("prop", ["adb", "shell", "getprop"])


class LogsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(10)
        t = QLabel("Consola de Logs"); t.setObjectName("title"); layout.addWidget(t)
        sub = QLabel("Eventos del sistema en tiempo real"); sub.setObjectName("subtitle"); layout.addWidget(sub)
        self.box = QPlainTextEdit(); self.box.setReadOnly(True)
        layout.addWidget(self.box, 1)
        btns = QHBoxLayout()
        clr = QPushButton("Limpiar"); clr.clicked.connect(self.box.clear)
        exp = QPushButton("Exportar"); exp.clicked.connect(self.export)
        btns.addWidget(clr); btns.addWidget(exp)
        layout.addLayout(btns)

    def append(self, line):
        self.box.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {line}")

    def export(self):
        path = os.path.join(os.path.expanduser("~"), "mobile_ui_logs.txt")
        try:
            with open(path, "w", encoding="utf-8") as f: f.write(self.box.toPlainText())
            self.append(f"Logs exportados a {path}")
        except Exception as e:
            self.append(f"Error: {e}")


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 10, 14, 10); layout.setSpacing(10)
        t = QLabel("Ajustes"); t.setObjectName("title"); layout.addWidget(t)
        card = QFrame(); card.setObjectName("card"); cl = QVBoxLayout(card); cl.setContentsMargins(14, 12, 14, 12)
        self.theme = QCheckBox("Tema claro"); cl.addWidget(self.theme)
        self.mock = QCheckBox("Modo simulación global"); self.mock.setChecked(True); cl.addWidget(self.mock)
        cl.addWidget(QLabel("Servidor BioAccess:"))
        self.srv = QLineEdit("127.0.0.1:8080"); cl.addWidget(self.srv)
        layout.addWidget(card)
        layout.addStretch()


# ----------------------------- Main Window -----------------------------
class MobileUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setFixedSize(WIN_W, WIN_H)
        self.setStyleSheet(DARK_QSS)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # status bar
        self.statusbar = StatusBar()
        root.addWidget(self.statusbar)

        # stacked pages
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # logs page shared reference for append from others
        self.logs_page = LogsPage()
        self.bio_page = BioAccessPage(self.logs_page.append)
        self.adb_page = AdbPage(self.logs_page.append)
        self.settings_page = SettingsPage()

        self.stack.addWidget(self.bio_page)      # 0 BioAccess
        self.stack.addWidget(self.adb_page)      # 1 ADB
        self.stack.addWidget(self.logs_page)     # 2 Logs
        self.stack.addWidget(self.settings_page) # 3 Settings

        # bottom nav
        nav = QFrame(); nav.setFixedHeight(64); nav.setStyleSheet("background:#06091a;border-top:1px solid #1f2a44;")
        nlay = QHBoxLayout(nav); nlay.setContentsMargins(8, 6, 8, 6)
        self.nav_group = QButtonGroup(self); self.nav_group.setExclusive(True)
        items = [("🏠", "Inicio", 0), ("🔐", "BioAccess", 0), ("📋", "Logs", 2), ("⚙️", "Ajustes", 3)]
        # We want 4 distinct: Home->bio, BioAccess->bio, Logs->logs, Settings->settings
        # Make Home also go to bio (index 0)
        defs = [("🏠", "Inicio", 0), ("🔐", "BioAccess", 0), ("📋", "Logs", 2), ("⚙️", "Ajustes", 3)]
        for emoji, name, idx in defs:
            b = QPushButton(f"{emoji}\n{name}")
            b.setObjectName("nav"); b.setCheckable(True)
            b.clicked.connect(lambda checked, i=idx: self.stack.setCurrentIndex(i))
            self.nav_group.addButton(b)
            nlay.addWidget(b)
        # check first
        self.nav_group.buttons()[0].setChecked(True)
        root.addWidget(nav)

        self.stack.currentChanged.connect(self._on_page_changed)
        self.go(0)

    def _on_page_changed(self, idx):
        btns = self.nav_group.buttons()
        # map page idx to nav button index: bio(0)->1, adb not in nav, logs(2)->2, settings(3)->3
        mapping = {0: 1, 2: 2, 3: 3}
        bi = mapping.get(idx, 0)
        if bi < len(btns):
            btns[bi].setChecked(True)

    def go(self, idx):
        self.stack.setCurrentIndex(idx)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    w = MobileUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
