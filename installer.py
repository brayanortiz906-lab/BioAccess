# -*- coding: utf-8 -*-
"""BioAccess - instalador todo-en-uno (PyQt6)."""
import os, sys, shutil, subprocess, ctypes

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QProgressBar, QPlainTextEdit, QFileDialog,
    QMessageBox, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

APP = "BioAccess"
DEFAULT_TARGET = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP)


def resource(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, **kw)
    except Exception:
        return None


QSS = """
QWidget { background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QFrame#card { background: #161b22; border: 1px solid #30363d; border-radius: 10px; }
QLabel#title { color: #58a6ff; font-size: 20px; font-weight: 700; }
QLabel#subtitle { color: #8b949e; font-size: 12px; }
QLineEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; padding: 6px 10px; color: #c9d1d9; }
QLineEdit:focus { border: 1px solid #58a6ff; }
QPushButton { background: #21262d; border: 1px solid #30363d; border-radius: 6px; padding: 7px 14px; color: #c9d1d9; }
QPushButton:hover { background: #30363d; }
QPushButton#primary { background: #238636; border: 1px solid #2ea043; color: #ffffff; font-weight: 600; }
QPushButton#primary:hover { background: #2ea043; }
QPushButton#primary:disabled { background: #1b3a24; color: #6e7681; }
QPushButton#secondary { background: transparent; border: 1px solid #30363d; color: #8b949e; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #30363d; background: #0d1117; }
QCheckBox::indicator:checked { background: #238636; border: 1px solid #2ea043; }
QProgressBar { background: #21262d; border: 1px solid #30363d; border-radius: 6px; text-align: center; color: #c9d1d9; height: 18px; }
QProgressBar::chunk { background: #238636; border-radius: 5px; }
QPlainTextEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #8b949e; font-family: 'Consolas', monospace; font-size: 11px; }
"""


class InstallWorker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, target, opt_apk, opt_shortcut, opt_launch):
        super().__init__()
        self.target = target
        self.opt_apk = opt_apk
        self.opt_shortcut = opt_shortcut
        self.opt_launch = opt_launch

    def run(self):
        target = self.target.strip()
        if not target:
            self.log.emit("[!] Carpeta de destino vacia")
            self.finished.emit(False, "Instalacion cancelada")
            return
        try:
            os.makedirs(target, exist_ok=True)
        except Exception as e:
            self.log.emit(f"[!] No se pudo crear {target}: {e}")
            self.finished.emit(False, "Instalacion fallida")
            return

        self.log.emit(f"Destino: {target}")
        files = ["bioaccess.exe", "BioAccessMobile.apk"]
        total = len(files) + 5
        done = 0

        # 1 copiar principales
        for name in files:
            src = resource(name)
            dst = os.path.join(target, name)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dst)
                    self.log.emit(f"  [ok] {name}")
                except Exception as e:
                    self.log.emit(f"  [err] {name}: {e}")
            else:
                self.log.emit(f"  [skip] {name} (no empaquetado)")
            done += 1
            self.progress.emit(int(done / total * 100))

        # requirements.txt (si existe)
        req_src = resource("requirements.txt")
        req_dst = os.path.join(target, "requirements.txt")
        if os.path.exists(req_src):
            try:
                shutil.copy2(req_src, req_dst)
                self.log.emit("  [ok] requirements.txt")
            except Exception as e:
                self.log.emit(f"  [err] requirements.txt: {e}")

        # 2 dependencias python
        try:
            import PyQt6, fastapi, uvicorn, websockets, qrcode  # noqa
            self.log.emit("  [ok] dependencias Python presentes")
        except Exception:
            if os.path.exists(req_dst):
                self.log.emit("  [..] instalando dependencias Python ...")
                r = run([sys.executable, "-m", "pip", "install", "-r", req_dst],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if r is not None and r.returncode == 0:
                    self.log.emit("  [ok] dependencias instaladas")
                else:
                    self.log.emit("  [warn] pip install termino con errores")
            else:
                self.log.emit("  [skip] requirements.txt no encontrado")
        done += 1
        self.progress.emit(int(done / total * 100))

        # 2b regla de firewall (para que el celular alcance el servidor)
        try:
            run(["netsh", "advfirewall", "firewall", "add", "rule",
                 "name=BioAccess 8080", "dir=in", "action=allow",
                 "protocol=TCP", "localport=8080"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log.emit("  [ok] regla de firewall (TCP 8080) agregada")
        except Exception:
            self.log.emit("  [warn] no se pudo agregar la regla de firewall (ejecuta como admin)")
        done += 1
        self.progress.emit(int(done / total * 100))

        # 3 APK por USB
        if self.opt_apk:
            adb = shutil.which("adb")
            apk_path = os.path.join(target, "BioAccessMobile.apk")
            if adb and os.path.exists(apk_path):
                r = run([adb, "devices"], capture_output=True, text=True)
                if r and "device" in (r.stdout or ""):
                    self.log.emit("  [..] instalando APK en el celular por USB ...")
                    run([adb, "install", "-r", apk_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    run([adb, "shell", "am", "start", "-n", "com.bioaccess.mobile/.MainActivity"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    run([adb, "reverse", "tcp:8080", "tcp:8080"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.log.emit("  [ok] APK instalada + adb reverse tcp:8080")
                else:
                    self.log.emit("  [skip] no hay celular conectado por USB")
            else:
                self.log.emit("  [skip] adb o APK no disponible")
        done += 1
        self.progress.emit(int(done / total * 100))

        # 4 acceso directo
        if self.opt_shortcut:
            try:
                import win32com.client
                sh = win32com.client.Dispatch("WScript.Shell")
                lnk = os.path.join(os.path.expanduser("~"), "Desktop", "BioAccess.lnk")
                sc = sh.CreateShortCut(lnk)
                sc.TargetPath = os.path.join(target, "bioaccess.exe")
                sc.WorkingDirectory = target
                sc.IconLocation = os.path.join(target, "bioaccess.exe")
                sc.save()
                self.log.emit("  [ok] acceso directo en el escritorio")
            except Exception:
                bat = os.path.join(os.path.expanduser("~"), "Desktop", "BioAccess.bat")
                with open(bat, "w", encoding="utf-8") as f:
                    f.write('@echo off\ncd /d "' + target + '"\nstart "" bioaccess.exe\n')
                self.log.emit("  [ok] lanzador en el escritorio (BioAccess.bat)")
        done += 1
        self.progress.emit(int(done / total * 100))

        # 5 lanzar
        if self.opt_launch:
            exe = os.path.join(target, "bioaccess.exe")
            if os.path.exists(exe):
                run(["cmd", "/c", "start", "", exe], shell=False)
                self.log.emit("  [ok] BioAccess lanzado")
            else:
                self.log.emit("  [!] bioaccess.exe no encontrado")
        done += 1
        self.progress.emit(100)

        self.log.emit("=" * 50)
        self.log.emit(f"  Instalacion completa. Carpeta: {target}")
        self.log.emit("=" * 50)
        self.finished.emit(True, "Instalacion completa.")


class InstallerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instalador de BioAccess")
        self.setFixedSize(640, 620)
        self.setStyleSheet(QSS)
        self.worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        # Encabezado
        hdr = QHBoxLayout()
        logo = QLabel("⬡")
        logo.setStyleSheet("font-size: 34px; color: #58a6ff;")
        hdr.addWidget(logo)
        title_col = QVBoxLayout()
        t = QLabel("Instalador de BioAccess")
        t.setObjectName("title")
        sub = QLabel("Terminal biométrico PC + móvil · Instalación guiada")
        sub.setObjectName("subtitle")
        title_col.addWidget(t)
        title_col.addWidget(sub)
        hdr.addLayout(title_col)
        hdr.addStretch()
        root.addLayout(hdr)

        # Ruta
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 12, 14, 12)
        cl.setSpacing(8)
        cl.addWidget(QLabel("Carpeta de instalación"))
        path_row = QHBoxLayout()
        self.dest = QLineEdit(DEFAULT_TARGET)
        path_row.addWidget(self.dest, 1)
        btn_browse = QPushButton("Examinar...")
        btn_browse.clicked.connect(self.browse)
        path_row.addWidget(btn_browse)
        cl.addLayout(path_row)
        root.addWidget(card)

        # Opciones
        card2 = QFrame()
        card2.setObjectName("card")
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(14, 12, 14, 12)
        c2.setSpacing(6)
        c2.addWidget(QLabel("Opciones de instalación"))
        self.opt_apk = QCheckBox("Instalar aplicación móvil en Android vía USB (requiere ADB)")
        self.opt_apk.setChecked(True)
        self.opt_shortcut = QCheckBox("Crear acceso directo en el escritorio")
        self.opt_shortcut.setChecked(True)
        self.opt_launch = QCheckBox("Iniciar BioAccess al finalizar la instalación")
        self.opt_launch.setChecked(True)
        for cb in (self.opt_apk, self.opt_shortcut, self.opt_launch):
            c2.addWidget(cb)
        root.addWidget(card2)

        # Progreso
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        # Log
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Los logs de instalación aparecerán aquí...")
        self.log.setMinimumHeight(180)
        root.addWidget(self.log, 1)

        # Botones
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setObjectName("secondary")
        self.btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(self.btn_cancel)
        self.btn_install = QPushButton("Instalar")
        self.btn_install.setObjectName("primary")
        self.btn_install.clicked.connect(self.start)
        btn_row.addWidget(self.btn_install)
        root.addLayout(btn_row)

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Carpeta de instalación", self.dest.text())
        if d:
            self.dest.setText(d)

    def append_log(self, text):
        self.log.appendPlainText(text)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def start(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.btn_install.setEnabled(False)
        self.btn_install.setText("Instalando...")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log.clear()
        self.worker = InstallWorker(
            self.dest.text(),
            self.opt_apk.isChecked(),
            self.opt_shortcut.isChecked(),
            self.opt_launch.isChecked(),
        )
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, ok, msg):
        self.btn_install.setEnabled(True)
        self.btn_install.setText("Finalizar")
        try:
            self.btn_install.clicked.disconnect()
        except Exception:
            pass
        self.btn_install.clicked.connect(self.close)
        if ok:
            QMessageBox.information(self, "BioAccess", msg)
        else:
            QMessageBox.warning(self, "BioAccess", msg)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = InstallerWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
