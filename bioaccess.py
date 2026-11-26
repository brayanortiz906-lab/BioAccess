# -*- coding: utf-8 -*-
import sys
import math
import random
import json
import os
import copy
import time
import queue
import threading
import ctypes

try:
    import winsound
except Exception:  # pragma: no cover - solo Windows
    class _WS:
        @staticmethod
        def Beep(freq=800, dur=100):
            pass
    winsound = _WS()

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QLabel, QFrame, QListWidget, 
                             QGraphicsDropShadowEffect, QProgressBar, QStackedWidget,
                             QLineEdit, QCheckBox, QSlider, QComboBox, QSpinBox,
                             QGroupBox, QFormLayout, QScrollArea, QDialog)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal, QThread
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QRadialGradient, 
                         QLinearGradient, QFont, QCursor, QPainterPath)

# --- CONFIGURACIÓN PERSISTENTE ---
# Se guarda en %APPDATA%\BioAccess (igual que el servidor) para que sobreviva
# al cierre del .exe (PyInstaller usa un _MEIPASS temporal).
_DATA_DIR = os.environ.get("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(_DATA_DIR, "BioAccess")
try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
except OSError:
    CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(CONFIG_DIR, "bioaccess_config.json")

DEFAULT_CONFIG = {
    "connection": {"ip": "", "port": "8080", "username": "Usuario PC",
                   "auto_detect": True, "timeout": 5, "retry_attempts": 3},
    "network": {"server_enabled": True, "server_port": 8080, "auto_connect": True},
    "display": {"glow_intensity": 50, "animation_speed": 1.0, "particle_density": 120,
                "show_grid": True, "show_scanlines": True},
    "audio": {"enabled": True, "volume": 70, "scan_start_sound": True,
              "scan_complete_sound": True, "button_click_sound": True},
    "scanner": {"sensitivity": 50, "auto_timeout": 10, "show_progress_arc": True,
                "haptic_feedback": False},
    "security": {"pin_enabled": False, "pin_code": "", "auto_lock": 0,
                 "failed_attempts_limit": 5}
}

def load_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for section in DEFAULT_CONFIG:
                    if section not in config or not isinstance(config.get(section), dict):
                        config[section] = copy.deepcopy(DEFAULT_CONFIG[section])
                    else:
                        for key in DEFAULT_CONFIG[section]:
                            if key not in config[section]:
                                config[section][key] = copy.deepcopy(DEFAULT_CONFIG[section][key])
                return config
    except Exception:
        pass
    return copy.deepcopy(DEFAULT_CONFIG)

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


# --- CONTROL DE VOLUMEN REAL ---
class VolumeController:
    @staticmethod
    def set_volume(volume_percent):
        try:
            winmm = ctypes.windll.winmm
            volume = int((volume_percent / 100.0) * 65535)
            packed_volume = (volume << 16) | volume
            return winmm.waveOutSetVolume(0, packed_volume) == 0
        except Exception:
            return False


# --- BOTÓN CIBERPUNK PERSONALIZADO ---
class CyberButton(QPushButton):
    """
    Botón Ciberpunk con:
    - Esquinas recortadas en bisel (QPainterPath)
    - Glow de neón dinámico (reacciona al mouse)
    - Marcadores tácticos en las esquinas
    - Respuestas de color dinámicas (hover, press, danger)
    """
    def __init__(self, text="", parent=None, accent_color="#22d3ff", hover_color="#ff9a1f", is_danger=False):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(48)
        self.setMinimumWidth(180)
        
        self.accent_color = QColor("#ff3b5c" if is_danger else accent_color)
        self.hover_color = QColor("#ff9a1f" if not is_danger else "#ff3b5c")
        self.is_danger = is_danger
        
        self.is_hovered = False
        self.is_pressed = False
        
        self.glow = QGraphicsDropShadowEffect(self)
        self.glow.setBlurRadius(15)
        self.glow.setColor(self.accent_color)
        self.glow.setOffset(0, 0)
        self.setGraphicsEffect(self.glow)

    def enterEvent(self, event):
        self.is_hovered = True
        self.glow.setBlurRadius(25)
        self.glow.setColor(self.hover_color)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.glow.setBlurRadius(15)
        self.glow.setColor(self.accent_color)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressed = False
            self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cut = 12

        # 1. Definir trazado con esquinas recortadas
        path = QPainterPath()
        path.moveTo(cut, 0)
        path.lineTo(w, 0)
        path.lineTo(w, h - cut)
        path.lineTo(w - cut, h)
        path.lineTo(0, h)
        path.lineTo(0, cut)
        path.closeSubpath()

        # 2. Colores según estado
        if self.is_pressed:
            bg_color = QColor(45, 255, 176, 60)
            border_color = QColor(45, 255, 176)
            text_color = QColor(255, 255, 255)
        elif self.is_hovered:
            bg_color = QColor(self.hover_color.red(), self.hover_color.green(), self.hover_color.blue(), 40)
            border_color = self.hover_color
            text_color = QColor(255, 255, 255)
        else:
            bg_color = QColor(2, 10, 24, 200)
            border_color = self.accent_color
            text_color = QColor(224, 247, 255)

        # 3. Fondo translúcido
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(bg_color))
        painter.drawPath(path)

        # 4. Borde fino principal
        pen_border = QPen(border_color, 1.2)
        painter.setPen(pen_border)
        painter.drawPath(path)

        # 5. Marcadores tácticos en esquinas
        pen_accent = QPen(border_color, 3)
        painter.setPen(pen_accent)
        painter.drawLine(0, cut, 0, cut + 8)
        painter.drawLine(cut, 0, cut + 8, 0)
        painter.drawLine(w, h - cut, w, h - cut - 8)
        painter.drawLine(w - cut, h, w - cut - 8, h)

        # 6. Texto
        painter.setPen(text_color)
        font = QFont("Consolas", 9)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.text())


# --- ESTILOS ULTRA CIBERPUNK ---
ESTILO_EXTREMO = """
QMainWindow { background-color: #01040a; }
QLabel { color: #b8e4ff; font-family: "Consolas", "Courier New", monospace; }
.sidebar { background-color: rgba(2, 6, 15, 0.92); border-right: 1px solid rgba(34, 211, 255, 0.3); }
.right-panel { background-color: rgba(2, 6, 15, 0.88); border-left: 1px solid rgba(34, 211, 255, 0.25); }
.nav-btn {
    background-color: transparent; border: 1px solid rgba(34, 211, 255, 0.2); border-radius: 0px;
    color: rgba(180, 230, 255, 0.7); padding: 14px 18px; font-size: 12px; letter-spacing: 2px;
    text-align: left; font-family: "Consolas", monospace; margin: 3px 10px; font-weight: bold;
}
.nav-btn:hover, .nav-btn:checked {
    background-color: rgba(34, 211, 255, 0.12); border: 1px solid #22d3ff; color: #eaffff;
    border-left: 4px solid #ff9a1f;
}
.data-box { background-color: rgba(5, 14, 30, 0.7); border: 1px solid rgba(34, 211, 255, 0.3); border-radius: 2px; padding: 12px; }
QListWidget { background: transparent; border: none; color: #eaffff; font-size: 12px; font-family: "Consolas", monospace; }
QListWidget::item { padding: 6px 8px; border-bottom: 1px solid rgba(34, 211, 255, 0.1); }
QListWidget::item:hover { background-color: rgba(34, 211, 255, 0.08); color: #22d3ff; }
QProgressBar {
    background-color: rgba(2, 6, 15, 0.8); border: 1px solid rgba(34, 211, 255, 0.3); border-radius: 0px;
    text-align: center; color: #eaffff; font-family: "Consolas", monospace; font-size: 11px; font-weight: bold; height: 22px;
}
QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22d3ff, stop:0.5 #2f6bff, stop:1 #22d3ff); }
QGroupBox {
    border: 1px solid rgba(34, 211, 255, 0.25); border-radius: 2px; margin-top: 12px; padding-top: 8px;
    color: #ff9a1f; font-family: "Consolas", monospace; font-size: 11px; font-weight: bold; letter-spacing: 1px;
}
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 8px; color: #ff9a1f; }
QLineEdit {
    background-color: rgba(2, 10, 24, 0.85); border: 1px solid rgba(34, 211, 255, 0.28); color: #eaffff;
    padding: 8px; font-family: Consolas, monospace; font-size: 12px; border-radius: 0px;
}
QLineEdit:focus { border: 1px solid #22d3ff; }
QComboBox {
    background-color: rgba(2, 10, 24, 0.85); border: 1px solid rgba(34, 211, 255, 0.28); color: #eaffff;
    padding: 6px; font-family: Consolas, monospace; font-size: 12px; border-radius: 0px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: rgba(2, 6, 15, 0.95); color: #eaffff; selection-background-color: rgba(34, 211, 255, 0.2);
    border: 1px solid rgba(34, 211, 255, 0.3);
}
QSlider::groove:horizontal { background: rgba(2, 6, 15, 0.8); border: 1px solid rgba(34, 211, 255, 0.25); height: 6px; border-radius: 0px; }
QSlider::handle:horizontal { background: #22d3ff; border: 1px solid #22d3ff; width: 14px; height: 14px; margin: -4px 0; border-radius: 0px; }
QSlider::handle:horizontal:hover { background: #2dffb0; border: 1px solid #2dffb0; }
QCheckBox { color: #b8e4ff; font-family: Consolas, monospace; font-size: 12px; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; background-color: rgba(2, 10, 24, 0.85); border: 1px solid rgba(34, 211, 255, 0.28); border-radius: 0px; }
QCheckBox::indicator:checked { background-color: #22d3ff; border: 1px solid #22d3ff; }
QSpinBox { background-color: rgba(2, 10, 24, 0.85); border: 1px solid rgba(34, 211, 255, 0.28); color: #eaffff; padding: 6px; font-family: Consolas, monospace; font-size: 12px; border-radius: 0px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: rgba(2, 6, 15, 0.8); width: 8px; border: none; }
QScrollBar::handle:vertical { background: rgba(34, 211, 255, 0.3); border-radius: 0px; min-height: 20px; }
QScrollBar::handle:vertical:hover { background: rgba(34, 211, 255, 0.5); }
QDialog { background-color: #01040a; }
"""


# --- AUDIO ENGINE ---
class AudioEngine:
    _enabled = True
    _volume = 70
    _scan_start_sound = True
    _scan_complete_sound = True
    _button_click_sound = True
    
    @classmethod
    def configure(cls, enabled, volume, scan_start, scan_complete, button_click):
        cls._enabled = enabled
        cls._volume = volume
        cls._scan_start_sound = scan_start
        cls._scan_complete_sound = scan_complete
        cls._button_click_sound = button_click
        VolumeController.set_volume(volume if enabled else 0)
    
    @classmethod
    def set_enabled(cls, enabled):
        cls._enabled = enabled
        VolumeController.set_volume(cls._volume if enabled else 0)
    
    @classmethod
    def set_volume(cls, volume):
        cls._volume = volume
        VolumeController.set_volume(volume if cls._enabled else 0)
    
    @staticmethod
    def play_beep(freq=800, duration=100):
        if not AudioEngine._enabled:
            return
        try:
            adj_duration = int(duration * (AudioEngine._volume / 100.0))
            if adj_duration > 0:
                winsound.Beep(freq, adj_duration)
        except Exception:
            pass
    
    @staticmethod
    def play_scan_start():
        if not AudioEngine._enabled or not AudioEngine._scan_start_sound:
            return
        try:
            winsound.Beep(400, 30); winsound.Beep(600, 30); winsound.Beep(800, 30)
        except Exception:
            pass
    
    @staticmethod
    def play_scan_complete():
        if not AudioEngine._enabled or not AudioEngine._scan_complete_sound:
            return
        try:
            winsound.Beep(523, 50); winsound.Beep(659, 50); winsound.Beep(784, 50)
        except Exception:
            pass
    
    @staticmethod
    def play_scan_cancel():
        if not AudioEngine._enabled:
            return
        try:
            winsound.Beep(600, 30); winsound.Beep(400, 30)
        except Exception:
            pass
    
    @staticmethod
    def play_button_click():
        if not AudioEngine._enabled or not AudioEngine._button_click_sound:
            return
        try:
            winsound.Beep(1000, 20)
        except Exception:
            pass


# --- WIDGET DE FONDO ANIMADO ---
class BackgroundWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.scan_line_y = 0.0
        self.show_grid = True
        self.show_scanlines = True
        self.particle_count = 120
        self._init_particles()
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._update)
        self.anim_timer.start()
    
    def _init_particles(self):
        self.particles = []
        for _ in range(self.particle_count):
            self.particles.append({
                'x': random.uniform(0, 1280), 'y': random.uniform(0, 800),
                'vx': random.uniform(-0.3, 0.3), 'vy': random.uniform(-0.3, 0.3),
                'size': random.uniform(1, 2.5), 'brightness': random.uniform(0.4, 1.0),
                'pulse': random.uniform(0, math.pi * 2), 'pulse_speed': random.uniform(0.03, 0.08),
            })
    
    def set_particle_count(self, count):
        self.particle_count = count
        self._init_particles()
    
    def _update(self):
        for p in self.particles:
            p['x'] += p['vx']; p['y'] += p['vy']; p['pulse'] += p['pulse_speed']
            if p['x'] < 0: p['x'] = self.width()
            if p['x'] > self.width(): p['x'] = 0
            if p['y'] < 0: p['y'] = self.height()
            if p['y'] > self.height(): p['y'] = 0
        self.scan_line_y = (self.scan_line_y + 2.0) % self.height()
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(1, 4, 10))
        if self.show_grid: self._draw_perspective_grid(painter, w, h)
        self._draw_particles(painter)
        if self.show_scanlines: self._draw_scan_lines(painter, w, h)
        self._draw_vignette(painter, w, h)
    
    def _draw_perspective_grid(self, painter, w, h):
        vanishing_x = w / 2; vanishing_y = h * 0.25
        pen = QPen(QColor(34, 211, 255, 8), 1)
        painter.setPen(pen)
        num_lines = 30
        for i in range(-num_lines, num_lines + 1):
            x_bottom = vanishing_x + i * (w / num_lines)
            painter.drawLine(QPointF(x_bottom, h), QPointF(vanishing_x, vanishing_y))
        num_rows = 20
        for i in range(1, num_rows + 1):
            t = i / num_rows
            y = vanishing_y + (h - vanishing_y) * (t ** 1.4)
            x_left = vanishing_x - (vanishing_x * t ** 0.65)
            x_right = vanishing_x + ((w - vanishing_x) * t ** 0.65)
            painter.drawLine(QPointF(x_left, y), QPointF(x_right, y))
    
    def _draw_particles(self, painter):
        for p in self.particles:
            brightness = p['brightness'] * (0.5 + 0.5 * math.sin(p['pulse']))
            alpha = int(255 * brightness * 0.55)
            size = p['size']
            glow_color = QColor(34, 211, 255, alpha // 3)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(glow_color))
            painter.drawEllipse(QRectF(p['x'] - size * 3, p['y'] - size * 3, size * 6, size * 6))
            core_color = QColor(34, 211, 255, alpha)
            painter.setBrush(QBrush(core_color))
            painter.drawEllipse(QRectF(p['x'] - size / 2, p['y'] - size / 2, size, size))
    
    def _draw_scan_lines(self, painter, w, h):
        scan_color = QColor(34, 211, 255, 30)
        painter.setPen(QPen(scan_color, 2))
        painter.drawLine(0, int(self.scan_line_y), w, int(self.scan_line_y))
        glow_color = QColor(34, 211, 255, 10)
        painter.setPen(QPen(glow_color, 14))
        painter.drawLine(0, int(self.scan_line_y), w, int(self.scan_line_y))
        pen_crt = QPen(QColor(0, 0, 0, 15), 1)
        painter.setPen(pen_crt)
        for y in range(0, h, 4):
            painter.drawLine(0, y, w, y)
    
    def _draw_vignette(self, painter, w, h):
        grad = QRadialGradient(w / 2, h / 2, max(w, h) / 1.3)
        grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        grad.setColorAt(0.5, QColor(0, 0, 0, 0))
        grad.setColorAt(1.0, QColor(0, 0, 0, 160))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, w, h)


# --- HUD BIOMÉTRICO REALISTA ---
class HugeHUD(QWidget):
    scan_complete = pyqtSignal()
    scan_cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(340, 340)
        self.progress = 0.0
        self.display_progress = 0.0
        self.is_holding = False
        self.rotation_angle = 0.0
        self.scan_complete_triggered = False
        self.glow_intensity = 50
        self.animation_speed = 1.0
        self.remote_active = False
        self.remote_request = False
        self.last_remote = 0.0
        
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)
        self.anim_timer.timeout.connect(self._update_animation)
        self.anim_timer.start()
    
    # ---- control remoto (el progreso lo manda el celular) ----
    def start_remote(self, has_request=True):
        self.remote_active = True
        self.remote_request = has_request
        self.progress = 0.0
        self.display_progress = 0.0
        self.scan_complete_triggered = False
        self.last_remote = time.time()
        self.update()

    def set_remote_progress(self, value):
        try:
            value = float(value)
        except Exception:
            return
        self.remote_active = True
        self.last_remote = time.time()
        self.progress = max(0.0, min(1.0, value))
        if self.progress >= 1.0 and not self.scan_complete_triggered:
            self.scan_complete_triggered = True
            self.scan_complete.emit()

    def clear_remote(self, settle=True):
        self.remote_active = False
        self.remote_request = False
        if settle:
            self.progress = 0.0
            self.display_progress = 0.0
            self.scan_complete_triggered = False
        self.update()
    
    def _update_animation(self):
        self.rotation_angle = (self.rotation_angle + 0.8 * self.animation_speed) % 360
        
        if self.remote_active:
            if not self.is_holding and self.progress < 1.0 and (time.time() - self.last_remote) > 3.0:
                self.progress = max(0.0, self.progress - 0.01)
        elif self.is_holding:
            if self.progress < 1.0:
                self.progress += 0.008 * self.animation_speed
                if self.progress >= 1.0:
                    self.progress = 1.0
                    if not self.scan_complete_triggered:
                        self.scan_complete_triggered = True
                        self.scan_complete.emit()
                        if AudioEngine._enabled and AudioEngine._scan_complete_sound:
                            AudioEngine.play_scan_complete()
        else:
            if self.progress > 0.0:
                self.progress -= 0.02 * self.animation_speed
                if self.progress < 0.0:
                    self.progress = 0.0
            self.scan_complete_triggered = False
        
        self.display_progress += (self.progress - self.display_progress) * 0.15
        self.update()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.remote_active:
                return
            self.is_holding = True
            if AudioEngine._enabled and AudioEngine._scan_start_sound:
                AudioEngine.play_scan_start()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.progress > 0 and self.progress < 1.0:
                if AudioEngine._enabled:
                    AudioEngine.play_scan_cancel()
                self.scan_cancelled.emit()
            self.is_holding = False
    
    def _draw_realistic_fingerprint(self, painter, scale=0.75):
        painter.save()
        painter.scale(scale, scale)
        r_max = 70
        n_top_ridges = 13
        
        for k in range(n_top_ridges):
            w = 62.0 - k * 4.4
            ry = w * 1.04 + 1.0
            ye = math.sqrt(r_max**2 - w**2) - 4.0 if k < 4 else 46.0 - (k - 3) * 0.9
            path = QPainterPath()
            path.moveTo(-w, ye)
            path.lineTo(-w, 0)
            path.arcTo(QRectF(-w, -ry, w * 2, ry * 2), 180, -180)
            path.lineTo(w, ye)
            if k % 2 == 1:
                pen = QPen(QColor(34, 211, 255, 220), 2.2, Qt.PenStyle.DashLine)
            else:
                pen = QPen(QColor(34, 211, 255, 240), 2.2, Qt.PenStyle.SolidLine)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)
        
        for k in range(4):
            y0 = 52.0 + k * 5.4
            val = r_max**2 - y0**2
            hw = math.sqrt(max(0, val)) - 3.0
            path = QPainterPath()
            path.moveTo(-hw, y0)
            path.quadTo(0, y0 + 9.0, hw, y0)
            pen = QPen(QColor(34, 211, 255, 200), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.restore()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 20
        core_r = r * 0.78
        
        painter.setPen(QPen(QColor(34, 211, 255, 12), 1))
        for x in range(int(cx - r), int(cx + r), 20):
            painter.drawLine(x, int(cy - r), x, int(cy + r))
        for y in range(int(cy - r), int(cy + r), 20):
            painter.drawLine(int(cx - r), y, int(cx + r), y)
        
        painter.setBrush(QBrush(QColor(2, 8, 22, 240)))
        painter.setPen(QPen(QColor(34, 211, 255, 70), 1.2))
        painter.drawEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))
        
        painter.save()
        painter.translate(cx, cy)
        painter.setPen(QPen(QColor(34, 211, 255, 120), 1))
        for i in range(72):
            length = 7 if i % 6 == 0 else 3
            painter.drawLine(0, int(-r), 0, int(-r + length))
            painter.rotate(5)
        painter.restore()
        
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.rotation_angle)
        painter.setPen(QPen(QColor(255, 154, 31, 190), 1.5, Qt.PenStyle.DashLine))
        r_orange = r - 8
        painter.drawEllipse(QRectF(-r_orange, -r_orange, r_orange * 2, r_orange * 2))
        painter.restore()
        
        painter.save()
        painter.translate(cx, cy)
        self._draw_realistic_fingerprint(painter, scale=0.78)
        painter.restore()
        
        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(QRectF(cx - core_r, cy - core_r, core_r * 2, core_r * 2))
        painter.setClipPath(clip_path)
        laser_t = (math.sin(self.rotation_angle * 0.04) + 1) / 2
        laser_t = laser_t * laser_t * (3 - 2 * laser_t)
        y_laser = (cy - core_r) + (core_r * 2 * laser_t)
        laser_grad = QLinearGradient(0, y_laser - 8, 0, y_laser + 8)
        laser_grad.setColorAt(0.0, QColor(34, 211, 255, 0))
        laser_grad.setColorAt(0.5, QColor(34, 211, 255, 230))
        laser_grad.setColorAt(1.0, QColor(34, 211, 255, 0))
        painter.setBrush(QBrush(laser_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(int(cx - core_r), int(y_laser - 4), int(core_r * 2), 8)
        painter.restore()
        
        if self.display_progress > 0.01:
            if self.display_progress >= 0.99:
                pen_prog = QPen(QColor(45, 255, 176), 5)
            else:
                pen_prog = QPen(QColor(255, 154, 31), 5)
            pen_prog.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen_prog)
            r_prog = r - 4
            rect_prog = QRectF(cx - r_prog, cy - r_prog, r_prog * 2, r_prog * 2)
            angle_span = int(-self.display_progress * 360 * 16)
            painter.drawArc(rect_prog, 90 * 16, angle_span)
        
        tag_w, tag_h = 105, 22
        tag_rect = QRectF(cx - tag_w / 2, cy + core_r - 30, tag_w, tag_h)
        painter.setBrush(QBrush(QColor(3, 12, 28, 245)))
        painter.setPen(QPen(QColor(34, 211, 255, 180), 1))
        painter.drawRoundedRect(tag_rect, 4, 4)
        painter.setPen(QPen(QColor(234, 255, 255), 1))
        font = QFont("Consolas", 8)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        painter.setFont(font)
        if self.progress >= 1.0:
            status_text = "✓ VALIDADO"
        elif self.is_holding or (self.remote_active and self.progress > 0):
            status_text = f"{int(self.progress * 100)}%"
        elif self.remote_active:
            status_text = "CELULAR"
        else:
            status_text = "ESCANEAR"
        painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, status_text)


# --- DIÁLOGO DE PIN ---
class PinDialog(QDialog):
    def __init__(self, parent=None, failed_attempts=0, max_attempts=5):
        super().__init__(parent)
        self.setWindowTitle("🔒 Verificación de Seguridad")
        self.setFixedSize(320, 200)
        self.setModal(True)
        self.failed_attempts = failed_attempts
        self.max_attempts = max_attempts
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        title = QLabel("INGRESE CÓDIGO PIN")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff9a1f; font-family: Consolas, monospace; letter-spacing: 2px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.inp_pin = QLineEdit()
        self.inp_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pin.setPlaceholderText("****")
        self.inp_pin.setStyleSheet("""
            QLineEdit { background-color: rgba(2, 10, 24, 0.85); border: 1px solid rgba(34, 211, 255, 0.28);
            color: #eaffff; padding: 10px; font-family: Consolas, monospace; font-size: 18px;
            text-align: center; border-radius: 0px; }
            QLineEdit:focus { border: 1px solid #22d3ff; }
        """)
        self.inp_pin.returnPressed.connect(self.accept)
        layout.addWidget(self.inp_pin)
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #ff3b5c; font-size: 10px; font-family: Consolas, monospace;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_status)
        if failed_attempts > 0:
            self.lbl_status.setText(f"⚠ Intentos fallidos: {failed_attempts}/{max_attempts}")
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("CONFIRMAR")
        btn_ok.setStyleSheet("""
            QPushButton { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22d3ff, stop:0.5 #2f6bff, stop:1 #22d3ff);
            border: none; color: #021018; padding: 10px; font-size: 11px; font-weight: bold; letter-spacing: 2px;
            border-radius: 0px; font-family: Consolas, monospace; }
            QPushButton:hover { background-color: #2dffb0; }
        """)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.setStyleSheet("""
            QPushButton { background-color: transparent; border: 1px solid #ff3b5c; color: #ff3b5c;
            padding: 10px; font-size: 11px; font-weight: bold; letter-spacing: 2px; border-radius: 0px;
            font-family: Consolas, monospace; }
            QPushButton:hover { background-color: rgba(255, 59, 92, 0.15); }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
    
    def get_pin(self):
        return self.inp_pin.text()


# --- ENLACE DE RED PC <-> CELULAR ---
def lan_ip():
    """IP de la PC en la red local (la que se escribe en el celular)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    finally:
        try:
            s.close()
        except Exception:
            pass


class BridgeClient(QThread):
    """
    Cliente WebSocket del terminal de escritorio.
    Habla con bioaccess_server.py y por su intermedio con la APK del celular.
    """
    state_changed = pyqtSignal(bool, str)
    message = pyqtSignal(dict)

    def __init__(self, url, device_name, parent=None):
        super().__init__(parent)
        self.url = url
        self.device = device_name
        self._outbox = queue.Queue()
        self._running = True
        self.connected = False

    # ---- API publica (segura desde el hilo GUI) ----
    def send(self, obj):
        if self.isRunning():
            self._outbox.put(obj)

    def stop(self):
        self._running = False
        self._outbox.put(None)

    # ---- bucle de red ----
    def run(self):
        try:
            from websockets.sync.client import connect
        except Exception:
            self.state_changed.emit(False, "falta_websockets")
            return

        while self._running:
            try:
                with connect(self.url, open_timeout=3, close_timeout=1,
                             max_size=2 ** 22) as ws:
                    self.connected = True
                    self.state_changed.emit(True, self.url)
                    ws.send(json.dumps({"type": "hello", "role": "pc",
                                        "device": self.device}, ensure_ascii=False))
                    while self._running:
                        # 1) enviar pendientes
                        while True:
                            try:
                                item = self._outbox.get_nowait()
                            except queue.Empty:
                                break
                            if item is None:
                                self._running = False
                                break
                            try:
                                ws.send(json.dumps(item, ensure_ascii=False))
                            except Exception:
                                pass
                        if not self._running:
                            break
                        # 2) recibir
                        try:
                            raw = ws.recv(timeout=0.15)
                        except TimeoutError:
                            continue
                        except Exception:
                            break
                        if not raw:
                            continue
                        try:
                            self.message.emit(json.loads(raw))
                        except Exception:
                            continue
            except Exception:
                pass

            self.connected = False
            self.state_changed.emit(False, self.url)
            for _ in range(20):
                if not self._running:
                    break
                time.sleep(0.1)


# --- VENTANA PRINCIPAL ---
class SuperCustomBio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BioAccess Desktop Terminal v2.0")
        self.resize(1100, 720)
        self.setStyleSheet(ESTILO_EXTREMO)
        
        self.config = load_config()
        AudioEngine.configure(self.config["audio"]["enabled"], self.config["audio"]["volume"],
                             self.config["audio"]["scan_start_sound"], self.config["audio"]["scan_complete_sound"],
                             self.config["audio"]["button_click_sound"])
        
        self.failed_attempts = 0
        self.is_locked = False
        self.last_activity = None
        
        self.bg_widget = BackgroundWidget(self)
        self.setCentralWidget(self.bg_widget)
        self.bg_widget.set_particle_count(self.config["display"]["particle_density"])
        self.bg_widget.show_grid = self.config["display"]["show_grid"]
        self.bg_widget.show_scanlines = self.config["display"]["show_scanlines"]
        
        layout = QHBoxLayout(self.bg_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Sidebar
        sidebar = QFrame()
        sidebar.setProperty("class", "sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 20, 12, 20)
        
        title = QLabel("BIO<span style='color:#ff9a1f;'>ACCESS</span>")
        title.setStyleSheet("font-size: 20px; font-weight: 900; letter-spacing: 4px; color: #eaffff; font-family: 'Segoe UI', sans-serif;")
        subtitle = QLabel("// ESCRITORIO_v2.0")
        subtitle.setStyleSheet("font-size: 10px; color: rgba(160,225,255,0.5); margin-bottom: 25px; font-family: Consolas, monospace;")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        
        self.btn1 = CyberButton("> 01. ESCÁNER", accent_color="#22d3ff", hover_color="#ff9a1f")
        self.btn2 = CyberButton("> 02. HISTORIAL", accent_color="#22d3ff", hover_color="#ff9a1f")
        self.btn3 = CyberButton("> 03. AJUSTES", accent_color="#22d3ff", hover_color="#ff9a1f")
        for btn in [self.btn1, self.btn2, self.btn3]:
            btn.setFixedHeight(42)
            btn.clicked.connect(lambda checked, b=btn: self._switch_tab(b))
            sidebar_layout.addWidget(btn)
        self.btn1.setChecked(True)
        
        sidebar_layout.addStretch()
        
        self.clock_label = QLabel("00:00:00")
        self.clock_label.setStyleSheet("font-size: 20px; color: #ff9a1f; font-weight: bold; font-family: Consolas, monospace;")
        self.net_status = QLabel("[ ENLACE: ARRANCANDO ]")
        self.net_status.setStyleSheet("font-size: 10px; color: #ff9a1f; font-family: Consolas, monospace; font-weight: bold;")
        self.net_status.setWordWrap(True)
        self.net_ip = QLabel("IP: ---")
        self.net_ip.setStyleSheet("font-size: 10px; color: #2dffb0; font-family: Consolas, monospace;")
        self.net_ip.setWordWrap(True)
        self.net_peer = QLabel("CELULAR: ---")
        self.net_peer.setStyleSheet("font-size: 10px; color: rgba(184,228,255,0.75); font-family: Consolas, monospace;")
        self.net_peer.setWordWrap(True)
        self.net_ip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.net_ip.mousePressEvent = lambda ev: self._show_pair_dialog()
        self.btn_qr = CyberButton("VINCULAR (QR)", accent_color="#ff9a1f", hover_color="#ff3b5c")
        self.btn_qr.setFixedHeight(30)
        self.btn_qr.clicked.connect(self._show_pair_dialog)
        self.btn_tunnel = CyberButton("INTERNET (TUNEL)", accent_color="#22d3ff", hover_color="#2dffb0")
        self.btn_tunnel.setFixedHeight(30)
        self.btn_tunnel.clicked.connect(self._toggle_tunnel)
        sidebar_layout.addWidget(self.clock_label)
        sidebar_layout.addWidget(self.net_status)
        sidebar_layout.addWidget(self.net_ip)
        sidebar_layout.addWidget(self.net_peer)
        sidebar_layout.addWidget(self.btn_qr)
        sidebar_layout.addWidget(self.btn_tunnel)
        
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

        # Polling de solicitudes de vinculacion pendientes (respaldo al push WS)
        self._shown_pending = set()
        self.pair_poll_timer = QTimer(self)
        self.pair_poll_timer.setInterval(2000)
        self.pair_poll_timer.timeout.connect(self._poll_pending_pairs)
        self.pair_poll_timer.start()
        
        # Center panel
        center = QFrame()
        center.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(25, 20, 25, 20)
        
        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet("background: transparent;")
        self.stacked.addWidget(self._create_scanner_view())
        self.stacked.addWidget(self._create_history_view())
        self.stacked.addWidget(self._create_settings_view())
        center_layout.addWidget(self.stacked)
        
        # Right panel
        right = QFrame()
        right.setProperty("class", "right-panel")
        right.setFixedWidth(260)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 20, 12, 20)
        
        log_title = QLabel("[ // DIAGNÓSTICO_RED ]")
        log_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff9a1f; font-family: Consolas, monospace;")
        self.log_list = QListWidget()
        self.log_list.addItem("▶ SYSTEM INITIALIZED")
        self.log_list.addItem("▶ SERVER ONLINE: PORT 8080")
        self.log_list.addItem("▶ WAITING FOR PEER...")
        self.log_list.addItem("▶ ENCRYPTION KEY LOADED")
        self.log_list.addItem("▶ BIOMETRIC MODULE READY")
        
        panel_info = QFrame()
        panel_info.setProperty("class", "data-box")
        info_lay = QVBoxLayout(panel_info)
        info_lay.setContentsMargins(8, 8, 8, 8)
        info_lay.setSpacing(4)
        for t in ["VERSIÓN: v2.0.1", "BUILD: 2026.10.29", "MODO: TERMINAL", "ACCESO: NIVEL 3"]:
            info_lay.addWidget(QLabel(t))
        
        right_layout.addWidget(log_title)
        right_layout.addWidget(self.log_list, 1)
        right_layout.addWidget(QLabel("[ INFORMACIÓN ]"))
        right_layout.addWidget(panel_info)
        
        layout.addWidget(sidebar)
        layout.addWidget(center, 1)
        layout.addWidget(right)
        
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(16)
        self.progress_timer.timeout.connect(self._update_progress)
        self.progress_timer.start()
        
        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setInterval(1000)
        self.inactivity_timer.timeout.connect(self._check_inactivity)
        self.inactivity_timer.start()
        self.installEventFilter(self)
        
        self._init_network()

        if self.config["security"]["pin_enabled"]:
            self._verify_pin()
    
    def eventFilter(self, obj, event):
        if event.type() in (event.Type.MouseMove, event.Type.MouseButtonPress, event.Type.KeyPress, event.Type.Wheel):
            self.last_activity = None
        return super().eventFilter(obj, event)
    
    def _check_inactivity(self):
        if self.config["security"]["auto_lock"] <= 0 or self.is_locked:
            return
        if self.last_activity is None:
            self.last_activity = 0
        self.last_activity += 1
        timeout_seconds = self.config["security"]["auto_lock"] * 60
        if self.last_activity >= timeout_seconds:
            self._lock_app()
    
    def _lock_app(self):
        self.is_locked = True
        self.stacked.setEnabled(False)
        self.lock_overlay = QWidget(self)
        self.lock_overlay.setStyleSheet("background-color: rgba(1, 4, 10, 240);")
        self.lock_overlay.setGeometry(self.rect())
        layout = QVBoxLayout(self.lock_overlay)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lock_icon = QLabel("🔒")
        lock_icon.setStyleSheet("font-size: 64px;")
        lock_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lock_icon)
        lock_text = QLabel("SISTEMA BLOQUEADO")
        lock_text.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9a1f; font-family: Consolas, monospace; letter-spacing: 3px;")
        lock_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lock_text)
        unlock_btn = CyberButton("DESBLOQUEAR", accent_color="#22d3ff", hover_color="#2dffb0")
        unlock_btn.setFixedHeight(44)
        unlock_btn.clicked.connect(self._unlock_app)
        layout.addWidget(unlock_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        self.lock_overlay.show()
        self.lock_overlay.raise_()

    def _unlock_app(self):
        if self._verify_pin():
            self.is_locked = False
            self.stacked.setEnabled(True)
            if hasattr(self, 'lock_overlay'):
                self.lock_overlay.deleteLater()
                del self.lock_overlay
            self.last_activity = None
            AudioEngine.play_button_click()

    def _verify_pin(self):
        if not self.config["security"]["pin_enabled"]:
            return True
        max_attempts = self.config["security"]["failed_attempts_limit"]
        pin_code = self.config["security"]["pin_code"]
        if self.failed_attempts >= max_attempts:
            self.log_lbl.setText("> ⛔ ACCESO BLOQUEADO. DEMASIADOS INTENTOS FALLIDOS.")
            self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
            return False
        dialog = PinDialog(self, self.failed_attempts, max_attempts)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            entered_pin = dialog.get_pin()
            if entered_pin == pin_code:
                self.failed_attempts = 0
                return True
            else:
                self.failed_attempts += 1
                remaining = max_attempts - self.failed_attempts
                if remaining > 0:
                    self.log_lbl.setText(f"> ⚠ PIN INCORRECTO. {remaining} INTENTOS RESTANTES.")
                else:
                    self.log_lbl.setText("> ⛔ ACCESO BLOQUEADO. DEMASIADOS INTENTOS FALLIDOS.")
                self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                AudioEngine.play_scan_cancel()
                return False
        return False
    
    def _create_scanner_view(self):
        view = QWidget()
        view.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        hud_title = QLabel("[ // AUTENTICACIÓN BIOMÉTRICA DE ACCESO ]")
        hud_title.setStyleSheet("font-size: 13px; letter-spacing: 3px; font-weight: bold; color: #b8e4ff; font-family: Consolas, monospace;")
        layout.addWidget(hud_title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15)
        
        self.hud = HugeHUD()
        self.hud.scan_complete.connect(self._on_scan_complete)
        self.hud.scan_cancelled.connect(self._on_scan_cancelled)
        self.hud.glow_intensity = self.config["display"]["glow_intensity"]
        self.hud.animation_speed = self.config["display"]["animation_speed"]
        
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(self.config["display"]["glow_intensity"])
        glow.setColor(QColor(34, 211, 255, 140))
        glow.setOffset(0, 0)
        self.hud.setGraphicsEffect(glow)
        self.hud_glow = glow
        
        layout.addWidget(self.hud, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15)
        
        sub_desc = QLabel("> MANTÉN PRESIONADO EL SENSOR PARA TRANSMITIR HUELLA_")
        sub_desc.setStyleSheet("font-size: 12px; color: #b8e4ff; font-family: Consolas, monospace;")
        layout.addWidget(sub_desc, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("PROGRESO: %p%")
        layout.addWidget(self.progress_bar)
        layout.addSpacing(10)
        
        btn_req = CyberButton("🔐  PEDIR HUELLA AL CELULAR", accent_color="#22d3ff", hover_color="#2dffb0")
        btn_req.setFixedHeight(44)
        btn_req.clicked.connect(self._request_fingerprint)
        self.btn_req = btn_req
        layout.addWidget(btn_req)
        layout.addSpacing(10)
        
        self.log_lbl = QLabel("> SISTEMA LISTO. ESPERANDO ACCIÓN...")
        self.log_lbl.setStyleSheet("color: #b8e4ff; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace;")
        layout.addWidget(self.log_lbl)
        
        return view
    
    def _create_history_view(self):
        view = QWidget()
        view.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("[ // REGISTRO DE EVENTOS ]")
        title.setStyleSheet("font-size: 13px; letter-spacing: 3px; font-weight: bold; color: #b8e4ff; font-family: Consolas, monospace;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15)
        self.hist_list_full = QListWidget()
        self.hist_list_full.addItem("🟢 [00:00:00] Conexión establecida con el servidor")
        self.hist_list_full.addItem("🟠 [00:00:01] Solicitud de huella enviada al celular")
        self.hist_list_full.addItem("🔵 [00:00:02] Huella autenticada con éxito")
        self.hist_list_full.addItem("🟡 [00:00:03] Token de acceso generado")
        self.hist_list_full.addItem("🟢 [00:00:04] Sesión activa")
        layout.addWidget(self.hist_list_full, 1)
        btn_clear = CyberButton("🗑️  LIMPIAR HISTORIAL", accent_color="#ff3b5c", hover_color="#ff9a1f", is_danger=True)
        btn_clear.setFixedHeight(44)
        btn_clear.clicked.connect(lambda: self.hist_list_full.clear())
        btn_clear.clicked.connect(lambda: AudioEngine.play_button_click())
        layout.addWidget(btn_clear)
        return view
    
    def _create_settings_view(self):
        view = QWidget()
        view.setStyleSheet("background: transparent;")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        title = QLabel("[ // CONFIGURACIÓN DEL SISTEMA ]")
        title.setStyleSheet("font-size: 13px; letter-spacing: 3px; font-weight: bold; color: #b8e4ff; font-family: Consolas, monospace;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(10)
        
        # Connection settings
        conn_group = QGroupBox("CONEXIÓN DE RED")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(8)
        self.inp_ip = QLineEdit(); self.inp_ip.setText(self.config["connection"]["ip"])
        self.inp_port = QLineEdit(); self.inp_port.setText(self.config["connection"]["port"])
        self.inp_user = QLineEdit(); self.inp_user.setText(self.config["connection"]["username"])
        self.chk_auto = QCheckBox("Detección automática"); self.chk_auto.setChecked(self.config["connection"]["auto_detect"])
        self.spin_timeout = QSpinBox(); self.spin_timeout.setRange(1, 30); self.spin_timeout.setValue(self.config["connection"]["timeout"]); self.spin_timeout.setSuffix(" s")
        self.spin_retry = QSpinBox(); self.spin_retry.setRange(1, 10); self.spin_retry.setValue(self.config["connection"]["retry_attempts"])
        conn_form.addRow("IP de la PC:", self.inp_ip); conn_form.addRow("Puerto:", self.inp_port)
        conn_form.addRow("Usuario:", self.inp_user); conn_form.addRow("", self.chk_auto)
        conn_form.addRow("Timeout:", self.spin_timeout); conn_form.addRow("Reintentos:", self.spin_retry)
        layout.addWidget(conn_group)
        
        # Mobile link settings
        link_group = QGroupBox("ENLACE CON EL CELULAR (APK)")
        link_form = QFormLayout(link_group)
        link_form.setSpacing(8)
        self.chk_server = QCheckBox("Activar servidor puente en la PC")
        self.chk_server.setChecked(self.config.get("network", {}).get("server_enabled", True))
        self.spin_server_port = QSpinBox(); self.spin_server_port.setRange(1024, 65535)
        self.spin_server_port.setValue(int(self.config.get("network", {}).get("server_port", 8080)))
        lbl_ip = QLabel(f"{lan_ip()}")
        lbl_ip.setStyleSheet("color: #2dffb0; font-size: 12px; font-family: Consolas, monospace;")
        btn_pair = CyberButton("📱  VINCULAR CELULAR (IP / QR)", accent_color="#22d3ff", hover_color="#2dffb0")
        btn_pair.setFixedHeight(38)
        btn_pair.clicked.connect(self._show_pair_dialog)
        link_form.addRow("", self.chk_server)
        link_form.addRow("Puerto servidor:", self.spin_server_port)
        link_form.addRow("IP actual:", lbl_ip)
        link_form.addRow("", btn_pair)
        btn_devs = CyberButton("DISPOSITIVOS VINCULADOS", accent_color="#ff9a1f", hover_color="#ff3b5c")
        btn_devs.setFixedHeight(34)
        btn_devs.clicked.connect(self._show_trusted_devices_dialog)
        link_form.addRow("", btn_devs)
        layout.addWidget(link_group)
        
        # Display settings
        disp_group = QGroupBox("VISUALIZACIÓN")
        disp_form = QFormLayout(disp_group)
        disp_form.setSpacing(8)
        glow_layout = QHBoxLayout()
        self.slider_glow = QSlider(Qt.Orientation.Horizontal); self.slider_glow.setRange(0, 100); self.slider_glow.setValue(self.config["display"]["glow_intensity"])
        self.lbl_glow = QLabel(f"{self.config['display']['glow_intensity']}"); self.lbl_glow.setStyleSheet("color: #b8e4ff; font-size: 11px; min-width: 35px;")
        self.slider_glow.valueChanged.connect(lambda v: self.lbl_glow.setText(f"{v}"))
        glow_layout.addWidget(self.slider_glow); glow_layout.addWidget(self.lbl_glow)
        disp_form.addRow("Intensidad Glow:", glow_layout)
        speed_layout = QHBoxLayout()
        self.slider_speed = QSlider(Qt.Orientation.Horizontal); self.slider_speed.setRange(50, 200); self.slider_speed.setValue(int(self.config["display"]["animation_speed"] * 100))
        self.lbl_speed = QLabel(f"{self.config['display']['animation_speed']:.1f}x"); self.lbl_speed.setStyleSheet("color: #b8e4ff; font-size: 11px; min-width: 35px;")
        self.slider_speed.valueChanged.connect(lambda v: self.lbl_speed.setText(f"{v/100:.1f}x"))
        speed_layout.addWidget(self.slider_speed); speed_layout.addWidget(self.lbl_speed)
        disp_form.addRow("Velocidad Animación:", speed_layout)
        self.spin_particles = QSpinBox(); self.spin_particles.setRange(20, 300); self.spin_particles.setValue(self.config["display"]["particle_density"]); self.spin_particles.setSuffix(" pts")
        disp_form.addRow("Densidad Partículas:", self.spin_particles)
        self.chk_grid = QCheckBox("Mostrar cuadrícula de fondo"); self.chk_grid.setChecked(self.config["display"]["show_grid"])
        disp_form.addRow("", self.chk_grid)
        self.chk_scanlines = QCheckBox("Mostrar líneas CRT"); self.chk_scanlines.setChecked(self.config["display"]["show_scanlines"])
        disp_form.addRow("", self.chk_scanlines)
        layout.addWidget(disp_group)
        
        # Audio settings
        audio_group = QGroupBox("AUDIO")
        audio_form = QFormLayout(audio_group)
        audio_form.setSpacing(8)
        self.chk_audio = QCheckBox("Habilitar sonido"); self.chk_audio.setChecked(self.config["audio"]["enabled"])
        audio_form.addRow("", self.chk_audio)
        vol_layout = QHBoxLayout()
        self.slider_vol = QSlider(Qt.Orientation.Horizontal); self.slider_vol.setRange(0, 100); self.slider_vol.setValue(self.config["audio"]["volume"])
        self.lbl_vol = QLabel(f"{self.config['audio']['volume']}%"); self.lbl_vol.setStyleSheet("color: #b8e4ff; font-size: 11px; min-width: 35px;")
        self.slider_vol.valueChanged.connect(lambda v: self.lbl_vol.setText(f"{v}%"))
        vol_layout.addWidget(self.slider_vol); vol_layout.addWidget(self.lbl_vol)
        audio_form.addRow("Volumen:", vol_layout)
        self.chk_scan_start = QCheckBox("Sonido al iniciar escaneo"); self.chk_scan_start.setChecked(self.config["audio"]["scan_start_sound"])
        audio_form.addRow("", self.chk_scan_start)
        self.chk_scan_complete = QCheckBox("Sonido al completar escaneo"); self.chk_scan_complete.setChecked(self.config["audio"]["scan_complete_sound"])
        audio_form.addRow("", self.chk_scan_complete)
        self.chk_btn_click = QCheckBox("Sonido al hacer clic"); self.chk_btn_click.setChecked(self.config["audio"]["button_click_sound"])
        audio_form.addRow("", self.chk_btn_click)
        layout.addWidget(audio_group)
        
        # Scanner settings
        scan_group = QGroupBox("ESCÁNER BIOMÉTRICO")
        scan_form = QFormLayout(scan_group)
        scan_form.setSpacing(8)
        sens_layout = QHBoxLayout()
        self.slider_sens = QSlider(Qt.Orientation.Horizontal); self.slider_sens.setRange(10, 100); self.slider_sens.setValue(self.config["scanner"]["sensitivity"])
        self.lbl_sens = QLabel(f"{self.config['scanner']['sensitivity']}%"); self.lbl_sens.setStyleSheet("color: #b8e4ff; font-size: 11px; min-width: 35px;")
        self.slider_sens.valueChanged.connect(lambda v: self.lbl_sens.setText(f"{v}%"))
        sens_layout.addWidget(self.slider_sens); sens_layout.addWidget(self.lbl_sens)
        scan_form.addRow("Sensibilidad:", sens_layout)
        self.spin_timeout_scan = QSpinBox(); self.spin_timeout_scan.setRange(5, 60); self.spin_timeout_scan.setValue(self.config["scanner"]["auto_timeout"]); self.spin_timeout_scan.setSuffix(" s")
        scan_form.addRow("Timeout Auto:", self.spin_timeout_scan)
        self.chk_progress_arc = QCheckBox("Mostrar arco de progreso"); self.chk_progress_arc.setChecked(self.config["scanner"]["show_progress_arc"])
        scan_form.addRow("", self.chk_progress_arc)
        self.chk_haptic = QCheckBox("Feedback háptico (vibración)"); self.chk_haptic.setChecked(self.config["scanner"]["haptic_feedback"])
        scan_form.addRow("", self.chk_haptic)
        layout.addWidget(scan_group)
        
        # Security settings
        sec_group = QGroupBox("SEGURIDAD")
        sec_form = QFormLayout(sec_group)
        sec_form.setSpacing(8)
        self.chk_pin = QCheckBox("Habilitar PIN de acceso"); self.chk_pin.setChecked(self.config["security"]["pin_enabled"])
        sec_form.addRow("", self.chk_pin)
        self.inp_pin = QLineEdit(); self.inp_pin.setPlaceholderText("****"); self.inp_pin.setEchoMode(QLineEdit.EchoMode.Password); self.inp_pin.setText(self.config["security"]["pin_code"])
        sec_form.addRow("Código PIN:", self.inp_pin)
        self.spin_autolock = QSpinBox(); self.spin_autolock.setRange(0, 60); self.spin_autolock.setValue(self.config["security"]["auto_lock"]); self.spin_autolock.setSuffix(" min"); self.spin_autolock.setSpecialValueText("Deshabilitado")
        sec_form.addRow("Auto-bloqueo:", self.spin_autolock)
        self.spin_failed = QSpinBox(); self.spin_failed.setRange(3, 10); self.spin_failed.setValue(self.config["security"]["failed_attempts_limit"])
        sec_form.addRow("Intentos fallidos:", self.spin_failed)
        layout.addWidget(sec_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_save = CyberButton("💾  GUARDAR CONFIGURACIÓN", accent_color="#22d3ff", hover_color="#2dffb0")
        btn_save.setFixedHeight(44)
        btn_save.clicked.connect(self._save_settings)
        btn_reset = CyberButton("🔄  RESTAURAR DEFAULTS", accent_color="#ff9a1f", hover_color="#22d3ff")
        btn_reset.setFixedHeight(44)
        btn_reset.clicked.connect(self._reset_settings)
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_reset)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        scroll.setWidget(container)
        view_layout = QVBoxLayout(view)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.addWidget(scroll)
        return view
    
    def _save_settings(self):
        self.config["connection"]["ip"] = self.inp_ip.text()
        self.config["connection"]["port"] = self.inp_port.text()
        self.config["connection"]["username"] = self.inp_user.text()
        self.config["connection"]["auto_detect"] = self.chk_auto.isChecked()
        self.config["connection"]["timeout"] = self.spin_timeout.value()
        self.config["connection"]["retry_attempts"] = self.spin_retry.value()
        if "network" not in self.config:
            self.config["network"] = {"server_enabled": True, "server_port": 8080, "auto_connect": True}
        self.config["network"]["server_enabled"] = self.chk_server.isChecked()
        self.config["network"]["server_port"] = self.spin_server_port.value()

        self.config["display"]["glow_intensity"] = self.slider_glow.value()
        self.config["display"]["animation_speed"] = self.slider_speed.value() / 100.0
        self.config["display"]["particle_density"] = self.spin_particles.value()
        self.config["display"]["show_grid"] = self.chk_grid.isChecked()
        self.config["display"]["show_scanlines"] = self.chk_scanlines.isChecked()
        self.config["audio"]["enabled"] = self.chk_audio.isChecked()
        self.config["audio"]["volume"] = self.slider_vol.value()
        self.config["audio"]["scan_start_sound"] = self.chk_scan_start.isChecked()
        self.config["audio"]["scan_complete_sound"] = self.chk_scan_complete.isChecked()
        self.config["audio"]["button_click_sound"] = self.chk_btn_click.isChecked()
        self.config["scanner"]["sensitivity"] = self.slider_sens.value()
        self.config["scanner"]["auto_timeout"] = self.spin_timeout_scan.value()
        self.config["scanner"]["show_progress_arc"] = self.chk_progress_arc.isChecked()
        self.config["scanner"]["haptic_feedback"] = self.chk_haptic.isChecked()
        self.config["security"]["pin_enabled"] = self.chk_pin.isChecked()
        self.config["security"]["pin_code"] = self.inp_pin.text()
        self.config["security"]["auto_lock"] = self.spin_autolock.value()
        self.config["security"]["failed_attempts_limit"] = self.spin_failed.value()
        save_config(self.config)
        AudioEngine.configure(self.config["audio"]["enabled"], self.config["audio"]["volume"],
                             self.config["audio"]["scan_start_sound"], self.config["audio"]["scan_complete_sound"],
                             self.config["audio"]["button_click_sound"])
        self.bg_widget.set_particle_count(self.config["display"]["particle_density"])
        self.bg_widget.show_grid = self.config["display"]["show_grid"]
        self.bg_widget.show_scanlines = self.config["display"]["show_scanlines"]
        if hasattr(self, 'hud_glow'):
            self.hud_glow.setBlurRadius(self.config["display"]["glow_intensity"])
        if hasattr(self, 'hud'):
            self.hud.animation_speed = self.config["display"]["animation_speed"]
            self.hud.glow_intensity = self.config["display"]["glow_intensity"]
        AudioEngine.play_button_click()
        self.log_lbl.setText("> ✓ CONFIGURACIÓN GUARDADA Y APLICADA.")
        self.log_lbl.setStyleSheet("color: #2dffb0; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
        from datetime import datetime
        now = datetime.now()
        self.log_list.addItem(f"🔵 [{now.strftime('%H:%M:%S')}] CONFIGURACIÓN ACTUALIZADA")
        self.log_list.scrollToBottom()
    
    def _reset_settings(self):
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        save_config(self.config)
        self.stacked.removeWidget(self.stacked.widget(2))
        settings_view = self._create_settings_view()
        self.stacked.addWidget(settings_view)
        self.stacked.setCurrentIndex(2)
        AudioEngine.play_button_click()
        self.log_lbl.setText("> 🔄 CONFIGURACIÓN RESTAURADA A VALORES POR DEFECTO.")
        self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
    
    def _switch_tab(self, btn):
        buttons = [self.btn1, self.btn2, self.btn3]
        for i, b in enumerate(buttons):
            b.setChecked(b == btn)
            if b == btn:
                if i == 0 and self.config["security"]["pin_enabled"]:
                    if not self._verify_pin():
                        return
                self.stacked.setCurrentIndex(i)
        AudioEngine.play_button_click()
    
    def _update_clock(self):
        from datetime import datetime
        now = datetime.now()
        self.clock_label.setText(now.strftime("%H:%M:%S"))
    
    def _update_progress(self):
        value = int(self.hud.display_progress * 100)
        self.progress_bar.setValue(value)
    
    def _on_scan_complete(self):
        if getattr(self.hud, "remote_active", False):
            return  # el resultado real llega por red (_on_net_message)
        self.log_lbl.setText("> ✓ HUELLA VALIDADA. ACCESO CONCEDIDO.")
        self.log_lbl.setStyleSheet("color: #2dffb0; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
        from datetime import datetime
        now = datetime.now()
        timestamp = now.strftime('%H:%M:%S')
        self.log_list.addItem(f"🟢 [{timestamp}] HUELLA AUTENTICADA")
        self.log_list.scrollToBottom()
        if hasattr(self, 'hist_list_full'):
            self.hist_list_full.addItem(f"🟢 [{timestamp}] HUELLA AUTENTICADA")
            self.hist_list_full.scrollToBottom()
    
    def _on_scan_cancelled(self):
        self.log_lbl.setText("> ✗ ESCANEO CANCELADO. INTENTE DE NUEVO.")
        self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")

    # =================================================================
    #   ENLACE PC <-> CELULAR  (servidor embebido + cliente WebSocket)
    # =================================================================
    def _log_event(self, text, level="info"):
        icons = {"ok": "🟢", "warn": "🟠", "err": "🔴", "info": "🔵"}
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_list.addItem(f"{icons.get(level, '🔵')} [{ts}] {text}")
        self.log_list.scrollToBottom()
        if hasattr(self, "hist_list_full") and level in ("ok", "err", "warn"):
            self.hist_list_full.addItem(f"{icons.get(level, '🔵')} [{ts}] {text}")
            self.hist_list_full.scrollToBottom()

    def _init_network(self):
        from urllib.parse import quote
        net_cfg = self.config.get("network", {})
        self.server_port = int(net_cfg.get("server_port", 8080) or 8080)
        self.server = None
        self.bridge = None
        self.pending_request = None
        self.access_token = None
        self.phone_device = None
        self.phone_trusted = False
        self._net_state = False
        self.tunnel_proc = None
        self.tunnel_url = None

        # 1) servidor puente embebido (LAN) -- si el puerto esta ocupado (Docker, etc.)
        #    se prueba el siguiente disponible, y se avisa en la UI.
        if net_cfg.get("server_enabled", True):
            try:
                from bioaccess_server import EmbeddedServer
                ports_to_try = [self.server_port] + [p for p in range(self.server_port + 1, self.server_port + 20)]
                started = False
                for _p in ports_to_try:
                    self.server = EmbeddedServer(host="0.0.0.0", port=_p)
                    if self.server.start():
                        if _p != self.server_port:
                            self._log_event(f"Puerto {self.server_port} ocupado -> usando { _p}", "warn")
                        self.server_port = _p
                        # persistir puerto real en config
                        try:
                            self.config.setdefault("network", {})["server_port"] = self.server_port
                            save_config(self.config)
                        except Exception:
                            pass
                        started = True
                        self._log_event(f"Servidor LAN activo en {lan_ip()}:{self.server_port}")
                        break
                    self.server = None
                if not started:
                    self._log_event("Servidor LAN no pudo iniciar (puertos ocupados)", "warn")
            except Exception as exc:
                self.server = None
                self._log_event(f"Servidor LAN no disponible: {exc}", "warn")

        self.net_ip.setText(f"IP: {lan_ip()}:{self.server_port}")
        self.net_status.setText("[ ENLACE: CONECTANDO ]")

        # 2) cliente WebSocket del escritorio
        device = (self.config["connection"].get("username") or "Usuario PC").strip() or "Usuario PC"
        url = f"ws://127.0.0.1:{self.server_port}/ws?role=pc&device={quote(device)}"
        self.bridge = BridgeClient(url, device, self)
        self.bridge.state_changed.connect(self._on_net_state)
        self.bridge.message.connect(self._on_net_message)
        self.bridge.start()

    def _on_net_state(self, connected, url):
        if connected == self._net_state:
            return
        self._net_state = connected
        if connected:
            self.net_status.setText("[ ENLACE: ONLINE ]")
            self.net_status.setStyleSheet("font-size: 10px; color: #2dffb0; font-family: Consolas, monospace; font-weight: bold;")
            self._log_event("Enlace con el servidor establecido", "ok")
            self.log_lbl.setText("> SISTEMA LISTO. ESPERANDO ACCIÓN...")
            self.log_lbl.setStyleSheet("color: #b8e4ff; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace;")
        else:
            self.net_status.setText("[ ENLACE: OFFLINE ]")
            self.net_status.setStyleSheet("font-size: 10px; color: #ff3b5c; font-family: Consolas, monospace; font-weight: bold;")
            self._log_event("Enlace con el servidor perdido (reintentando)", "warn")

    def _poll_pending_pairs(self):
        try:
            import urllib.request, json as _j
            port = self.server_port
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/pair/pending", timeout=3) as r:
                data = _j.loads(r.read().decode())
            for pnd in (data.get("pending") or []):
                rid = pnd.get("request_id")
                if not rid or rid in self._shown_pending:
                    continue
                self._shown_pending.add(rid)
                dev = pnd.get("device") or "Celular"
                did = pnd.get("device_id") or ""
                self._log_event(f">>> SOLICITUD DE VINCULACION: {dev} <<<", "warn")
                self.log_lbl.setText(f">>> {dev} QUIERE VINCULARSE. REVISA LA VENTANA <<<")
                self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 13px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                # traer ventana al frente
                self.showNormal()
                self.raise_()
                self.activateWindow()
                self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                dlg = QDialog(self)
                dlg.setWindowTitle("VINCULAR NUEVO CELULAR")
                dlg.setFixedSize(440, 260)
                dlg.setStyleSheet(ESTILO_EXTREMO)
                dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
                lay = QVBoxLayout(dlg)
                lay.setContentsMargins(20, 18, 20, 18)
                lay.setSpacing(10)
                t = QLabel("// SOLICITUD DE VINCULACION")
                t.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff9a1f; letter-spacing: 2px;")
                lay.addWidget(t)
                info = QLabel(
                    f"El dispositivo <b>{dev}</b> quiere vincularse a esta PC.\n"
                    f"ID: <b>{did or '---'}</b>\n\n"
                    "¿Aceptas la vinculación?"
                )
                info.setTextFormat(Qt.TextFormat.RichText)
                info.setWordWrap(True)
                info.setStyleSheet("color: #b8e4ff; font-size: 11px; line-height: 150%;")
                lay.addWidget(info)
                row = QHBoxLayout()
                btn_ok = CyberButton("ACEPTAR", accent_color="#2dffb0", hover_color="#22d3ff")
                btn_ok.setFixedHeight(36)
                btn_no = CyberButton("RECHAZAR", accent_color="#ff3b5c", hover_color="#ff9a1f")
                btn_no.setFixedHeight(36)
                row.addWidget(btn_ok)
                row.addWidget(btn_no)
                lay.addLayout(row)
                result = {"accept": None}
                btn_ok.clicked.connect(lambda: (result.update({"accept": True}), dlg.accept()))
                btn_no.clicked.connect(lambda: (result.update({"accept": False}), dlg.accept()))
                dlg.raise_()
                dlg.activateWindow()
                dlg.exec()
                try:
                    import urllib.request as _ur
                    data = _j.dumps({"request_id": rid, "accept": bool(result["accept"])}).encode()
                    req = _ur.Request(
                        f"http://127.0.0.1:{port}/api/pair/decision?request_id={rid}&accept={str(bool(result['accept'])).lower()}",
                        data=data, method="POST")
                    with _ur.urlopen(req, timeout=8) as r:
                        resp = _j.loads(r.read().decode())
                    if result["accept"] and resp.get("ok"):
                        self._log_event(f"Dispositivo vinculado: {dev}", "ok")
                        self.log_lbl.setText("> CELULAR VINCULADO. LISTO PARA PEDIR HUELLA_")
                    else:
                        self._log_event(f"Vinculación rechazada: {dev}", "warn")
                except Exception as exc:
                    self._log_event(f"Error en vinculación: {exc}", "err")
        except Exception:
            pass

    def _on_net_message(self, m):
        mtype = m.get("type", "")

        if mtype == "hello_ack":
            phones = [p for p in m.get("peers", []) if p.get("role") == "phone"]
            if phones:
                ph = phones[0]
                self.phone_device = ph.get("device")
                self.phone_trusted = bool(ph.get("trusted"))
                tag = "" if self.phone_trusted else " (SIN VINCULAR)"
                self.net_peer.setText(f"CELULAR: {self.phone_device}{tag}")
            else:
                self.phone_trusted = False
                self.net_peer.setText("CELULAR: ---")
            return

        if mtype == "peer_joined":
            if m.get("role") == "phone":
                self.phone_device = m.get("device", "Celular")
                self.phone_trusted = bool(m.get("trusted", False))
                self.hud.clear_remote()
                self._log_event(f"Celular conectado: {self.phone_device}", "ok" if self.phone_trusted else "warn")
                if self.phone_trusted:
                    self.net_peer.setText(f"CELULAR: {self.phone_device}")
                    self.log_lbl.setText("> CELULAR VINCULADO. LISTO PARA PEDIR HUELLA_")
                    self.log_lbl.setStyleSheet("color: #2dffb0; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                else:
                    self.net_peer.setText(f"CELULAR: {self.phone_device} (SIN VINCULAR)")
                    self.log_lbl.setText("> CELULAR CONECTADO PERO SIN VINCULAR. PULSA VINCULAR Y ACEPTA_")
                    self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                    self._log_event(f"El celular {self.phone_device} NO esta vinculado. Abre VINCULAR en la app y pulsa ACEPTAR aqui.", "warn")
            return

        if mtype == "peer_left":
            if m.get("role") == "phone":
                self.phone_device = None
                self.phone_trusted = False
                self.net_peer.setText("CELULAR: ---")
                self._log_event("Celular desconectado", "warn")
                self.hud.clear_remote()
            return

        if mtype == "pair_request":
            rid = m.get("request_id")
            dev = m.get("device", "Celular")
            did = m.get("device_id", "")
            self._log_event(f"Solicitud de vinculacion recibida: {dev} ({did})", "warn")
            self.log_lbl.setText("> SOLICITUD DE VINCULACION RECIBIDA. REVISA LA VENTANA_")
            self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
            dlg = QDialog(self)
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.raise_()
            dlg.activateWindow()
            dlg.setWindowTitle("VINCULAR NUEVO CELULAR")
            dlg.setFixedSize(440, 260)
            dlg.setStyleSheet(ESTILO_EXTREMO)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(20, 18, 20, 18)
            lay.setSpacing(10)
            t = QLabel("// SOLICITUD DE VINCULACION")
            t.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff9a1f; letter-spacing: 2px;")
            lay.addWidget(t)
            info = QLabel(
                f"El dispositivo <b>{dev}</b> quiere vincularse a esta PC.\n"
                f"ID: <b>{did or '---'}</b>\n\n"
                "¿Aceptas la vinculación? Solo los dispositivos aceptados\n"
                "podrán usar el lector de huellas de esta PC."
            )
            info.setTextFormat(Qt.TextFormat.RichText)
            info.setWordWrap(True)
            info.setStyleSheet("color: #b8e4ff; font-size: 11px; line-height: 150%;")
            lay.addWidget(info)
            row = QHBoxLayout()
            btn_ok = CyberButton("ACEPTAR", accent_color="#2dffb0", hover_color="#22d3ff")
            btn_ok.setFixedHeight(36)
            btn_no = CyberButton("RECHAZAR", accent_color="#ff3b5c", hover_color="#ff9a1f")
            btn_no.setFixedHeight(36)
            row.addWidget(btn_ok)
            row.addWidget(btn_no)
            lay.addLayout(row)
            result = {"accept": None}
            btn_ok.clicked.connect(lambda: (result.update({"accept": True}), dlg.accept()))
            btn_no.clicked.connect(lambda: (result.update({"accept": False}), dlg.accept()))
            dlg.exec()
            try:
                import urllib.request, json as _j
                port = self.server_port
                data = _j.dumps({"request_id": rid, "accept": bool(result["accept"])}).encode()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/pair/decision?request_id={rid}&accept={str(bool(result['accept'])).lower()}",
                    data=data, method="POST")
                with urllib.request.urlopen(req, timeout=8) as r:
                    resp = _j.loads(r.read().decode())
                if result["accept"] and resp.get("ok"):
                    self._log_event(f"Dispositivo vinculado: {dev}", "ok")
                    self.log_lbl.setText("> CELULAR VINCULADO. LISTO PARA PEDIR HUELLA_")
                else:
                    self._log_event(f"Vinculación rechazada: {dev}", "warn")
            except Exception as exc:
                self._log_event(f"Error en vinculación: {exc}", "err")
            return

        if mtype == "scan_pending":
            self.pending_request = m.get("id")
            self.hud.start_remote(True)
            self._log_event("Solicitud de huella enviada al celular", "warn")
            self.log_lbl.setText("> ESPERANDO HUELLA DEL CELULAR...")
            self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
            return

        if mtype == "scan_progress":
            if m.get("id") == self.pending_request or self.hud.remote_active:
                self.hud.set_remote_progress(m.get("progress", 0))
                self.log_lbl.setText(f"> CAPTURANDO HUELLA EN EL CELULAR... {int(float(m.get('progress', 0)) * 100)}%")
                self.log_lbl.setStyleSheet("color: #22d3ff; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace;")
            return

        if mtype == "scan_result":
            ok = bool(m.get("ok"))
            self.pending_request = None
            if ok:
                self.access_token = m.get("token")
                self.hud.set_remote_progress(1.0)
                AudioEngine.play_scan_complete()
                self.log_lbl.setText(f"> ✓ HUELLA VALIDADA. ACCESO CONCEDIDO. TOKEN {self.access_token}")
                self.log_lbl.setStyleSheet("color: #2dffb0; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                self._log_event(f"Huella autenticada en {m.get('device', 'celular')} · token {self.access_token}", "ok")
                self.net_peer.setText(f"CELULAR: {self.phone_device or '---'}\nTOKEN: {self.access_token}")
                QTimer.singleShot(2500, lambda: self.hud.clear_remote(True))
            else:
                self.hud.clear_remote(True)
                err = m.get("error", "rechazada")
                if err == "sin_celular_vinculado":
                    AudioEngine.play_button_click()
                    self.log_lbl.setText("> ! EL CELULAR CONECTADO NO ESTA VINCULADO. PULSA VINCULAR Y ACEPTA_")
                    self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                    self._log_event("Acceso denegado: celular conectado pero NO vinculado. Abre VINCULAR en la app y pulsa ACEPTAR en la PC.", "warn")
                    return
                if err == "sin_celular":
                    AudioEngine.play_button_click()
                    self.log_lbl.setText("> ⚠ NO HAY CELULAR VINCULADO. ABRE LA APK Y CONECTA A ESTA PC.")
                    self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                    self._log_event("Sin celular vinculado · abre la APK BioAccess en el móvil", "warn")
                    return
                AudioEngine.play_scan_cancel()
                self.log_lbl.setText(f"> ✗ ACCESO DENEGADO ({err}).")
                self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
                self._log_event(f"Acceso denegado ({err})", "err")
            return

        if mtype == "scan_cancel":
            self.pending_request = None
            self.hud.clear_remote(True)
            self.log_lbl.setText("> ✗ ESCANEO CANCELADO EN EL CELULAR.")
            self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
            self._log_event("Escaneo cancelado en el celular", "warn")
            return

        if mtype == "log":
            self._log_event(m.get("text", ""), m.get("level", "info"))
            return

    def _request_fingerprint(self):
        AudioEngine.play_button_click()
        if not self.bridge or not self.bridge.connected:
            self._log_event("Sin enlace: no se puede pedir la huella", "err")
            self.log_lbl.setText("> ⚠ SIN ENLACE AL SERVIDOR. REINTENTANDO CONEXIÓN...")
            self.log_lbl.setStyleSheet("color: #ff3b5c; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
            return
        self.bridge.send({"type": "scan_request", "ttl": 30})
        self.hud.start_remote(True)
        self.log_lbl.setText("> SOLICITUD ENVIADA AL CELULAR. ESPERANDO RESPUESTA...")
        self.log_lbl.setStyleSheet("color: #ff9a1f; font-size: 12px; margin-top: 5px; font-family: Consolas, monospace; font-weight: bold;")
        self._log_event("Solicitud de huella enviada al celular", "warn")

    def _show_pair_dialog(self):
        AudioEngine.play_button_click()
        ip = lan_ip()
        port = self.server_port
        try:
            import bioaccess_server as _bs
            code = _bs.pair_code(refresh=True)
            payload = _bs.pair_payload(ip, port)
        except Exception:
            code = "------"
            payload = f"bioaccess://pair?ip={ip}&port={port}&code={code}&name=BioAccess"
        url = f"http://{ip}:{port}/mobile"

        dlg = QDialog(self)
        dlg.setWindowTitle("VINCULAR CELULAR")
        dlg.setFixedSize(520, 620)
        dlg.setStyleSheet(ESTILO_EXTREMO)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        t = QLabel("// VINCULAR CELULAR A LA PC")
        t.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff9a1f; letter-spacing: 2px;")
        lay.addWidget(t)

        info = QLabel(
            "1. Instala <b>BioAccessMobile.apk</b> en el celular.\n"
            "2. PC y celular en el <b>mismo WiFi</b>.\n"
            "3. En la app: <b>AJUSTES \u2192 ESCANEAR QR</b>\n"
            "   (o BUSCAR PC / IP a mano).\n\n"
            f"IP de la PC : <b>{ip}</b>\n"
            f"Puerto      : <b>{port}</b>\n"
            f"Navegador   : <b>{url}</b>\n"
            f"Codigo      : <b>{code}</b>  (10 min)"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("color: #b8e4ff; font-size: 11px; line-height: 150%;")
        lay.addWidget(info)

        try:
            import qrcode
            from PyQt6.QtGui import QPixmap, QPainter, QColor
            qr = qrcode.QRCode(version=None, box_size=1, border=2,
                               error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(payload)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            n = len(matrix)
            mod = 8
            size = n * mod
            pm = QPixmap(size, size)
            pm.fill(QColor("#ffffff"))
            p = QPainter(pm)
            p.setPen(Qt.PenStyle.NoPen)
            for r in range(n):
                for c in range(n):
                    if matrix[r][c]:
                        p.setBrush(QColor("#000000"))
                        p.drawRect(c * mod, r * mod, mod, mod)
            p.end()
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
        except Exception as e:
            err = QLabel(f"(QR no disponible: {e})")
            err.setStyleSheet("color: #ff3b5c; font-size: 10px;")
            lay.addWidget(err)

        row = QHBoxLayout()
        btn_reg = CyberButton("REGENERAR", accent_color="#22d3ff", hover_color="#2dffb0")
        btn_reg.setFixedHeight(34)
        btn_reg.clicked.connect(lambda: (self._show_pair_dialog(), dlg.accept()))
        row.addWidget(btn_reg)
        btn = CyberButton("CERRAR", accent_color="#ff9a1f", hover_color="#ff3b5c")
        btn.setFixedHeight(34)
        btn.clicked.connect(dlg.accept)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

    def _show_trusted_devices_dialog(self):
        import urllib.request, json as _j
        AudioEngine.play_button_click()
        dlg = QDialog(self)
        dlg.setWindowTitle("DISPOSITIVOS VINCULADOS")
        dlg.setFixedSize(520, 420)
        dlg.setStyleSheet(ESTILO_EXTREMO)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        t = QLabel("// DISPOSITIVOS VINCULADOS A ESTA PC")
        t.setStyleSheet("font-size: 12px; font-weight: bold; color: #ff9a1f; letter-spacing: 2px;")
        lay.addWidget(t)
        info = QLabel("Solo estos dispositivos pueden usar el lector de huellas de esta PC.\nRevoca el que ya no uses (por ejemplo, si perdiste el celular).")
        info.setWordWrap(True)
        info.setStyleSheet("color: #b8e4ff; font-size: 10px;")
        lay.addWidget(info)

        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        lst = QListWidget()
        lst.setStyleSheet("background: #020814; color: #b8e4ff; font-family: Consolas, monospace; font-size: 11px;")
        lay.addWidget(lst, 1)

        def refresh():
            lst.clear()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.server_port}/api/pair/trusted", timeout=5) as r:
                    data = _j.loads(r.read().decode())
                for dev in data.get("devices", []):
                    item = QListWidgetItem(f"{dev.get('device_name','?')}  |  {dev.get('device_id','?')}  |  {dev.get('paired_at','')}")
                    item.setData(Qt.ItemDataRole.UserRole, dev.get("device_id"))
                    lst.addItem(item)
                if lst.count() == 0:
                    lst.addItem(QListWidgetItem("(sin dispositivos vinculados)"))
            except Exception as exc:
                lst.addItem(QListWidgetItem(f"(error: {exc})"))

        def revoke_selected():
            it = lst.currentItem()
            if not it:
                return
            did = it.data(Qt.ItemDataRole.UserRole)
            if not did:
                return
            try:
                data = _j.dumps({"device_id": did}).encode()
                req = urllib.request.Request(f"http://127.0.0.1:{self.server_port}/api/pair/revoke?device_id={did}",
                                            data=data, method="POST")
                with urllib.request.urlopen(req, timeout=5) as r:
                    _j.loads(r.read().decode())
                self._log_event(f"Dispositivo revocado: {did}", "warn")
            except Exception as exc:
                self._log_event(f"Error al revocar: {exc}", "err")
            refresh()

        refresh()
        row = QHBoxLayout()
        btn_ref = CyberButton("ACTUALIZAR", accent_color="#22d3ff", hover_color="#2dffb0")
        btn_ref.setFixedHeight(34)
        btn_ref.clicked.connect(refresh)
        btn_rev = CyberButton("REVOCAR SELECCIONADO", accent_color="#ff3b5c", hover_color="#ff9a1f")
        btn_rev.setFixedHeight(34)
        btn_rev.clicked.connect(revoke_selected)
        btn_close = CyberButton("CERRAR", accent_color="#ff9a1f", hover_color="#ff3b5c")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(dlg.accept)
        row.addWidget(btn_ref); row.addWidget(btn_rev); row.addWidget(btn_close)
        lay.addLayout(row)
        dlg.exec()

    def _toggle_tunnel(self):
        AudioEngine.play_button_click()
        if self.tunnel_proc is not None:
            self._stop_tunnel()
            return
        self._start_tunnel()

    def _start_tunnel(self):
        import subprocess, re, threading
        port = self.server_port
        candidates = []
        # serveo primero: no muestra pagina intersticial (localtunnel bloquea fetch/ws)
        candidates.append((["ssh", "-o", "StrictHostKeyChecking=no", "-R",
                           "80:localhost:" + str(port), "serveo.net"], "serveo"))
        candidates.append((["lt", "--port", str(port)], "localtunnel"))
        candidates.append((["npx", "--yes", "localtunnel", "--port", str(port)], "localtunnel"))

        def worker(cmd, label):
            try:
                self.tunnel_proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, text=True, bufsize=1,
                    creationflags=0x08000000)
            except FileNotFoundError:
                self._log_event("Tunel: " + label + " no disponible", "warn")
                self.tunnel_proc = None
                return
            url_found = None
            for line in self.tunnel_proc.stdout:
                m = re.search(r"https://[A-Za-z0-9\-\.]+\.[A-Za-z]{2,}[^ \t\r\n]*", line)
                if m and url_found is None:
                    url_found = m.group(0).rstrip(".,)")
                    self.tunnel_url = url_found
                    self._log_event("TUNEL ACTIVO: " + url_found, "ok")
                    self._show_tunnel_dialog(url_found)
                if self.tunnel_proc.poll() is not None:
                    break
            if url_found is None:
                self._log_event("Tunel: no se obtuvo URL publica", "err")
            self.tunnel_proc = None
            self.tunnel_url = None

        chosen = None
        for cmd, label in candidates:
            try:
                if cmd[0] == "ssh":
                    subprocess.run([cmd[0], "-V"], capture_output=True, timeout=5)
                else:
                    subprocess.run([cmd[0], "--version"], capture_output=True, timeout=5)
                chosen = (cmd, label)
                break
            except Exception:
                continue
        if chosen is None:
            chosen = (candidates[-1][0], candidates[-1][1])
        cmd, label = chosen
        self._log_event("Iniciando tunel (" + label + ")...", "warn")
        threading.Thread(target=worker, args=(cmd, label), daemon=True).start()

    def _stop_tunnel(self):
        if self.tunnel_proc is not None:
            try:
                self.tunnel_proc.terminate()
            except Exception:
                pass
            self.tunnel_proc = None
            self.tunnel_url = None
            self._log_event("Tunel detenido", "warn")

    def _show_tunnel_dialog(self, url):
        from urllib.parse import urlparse
        AudioEngine.play_button_click()
        parsed = urlparse(url)
        host = parsed.hostname or url
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        dlg = QDialog(self)
        dlg.setWindowTitle("MODO INTERNET (TUNEL)")
        dlg.setFixedSize(520, 640)
        dlg.setStyleSheet(ESTILO_EXTREMO)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)
        t = QLabel("// CONEXION POR INTERNET (TUNEL)")
        t.setStyleSheet("font-size: 12px; font-weight: bold; color: #22d3ff; letter-spacing: 2px;")
        lay.addWidget(t)
        info = QLabel(
            "La PC esta expuesta a internet mediante un tunel publico.\\n"
            "El celular puede conectarse desde CUALQUIER red (datos moviles, otra WiFi).\\n\\n"
            "URL publica : " + url + "\\n"
            "Host        : " + host + "\\n"
            "Puerto      : " + str(port) + "\\n\\n"
            "En el celular: AJUSTES -> escribe el Host y Puerto de arriba -> GUARDAR.\\n"
            "O escanea el QR de abajo.\\n\\n"
            "ADVERTENCIA: la URL es publica. Solo compartela con quien autorices.\\n"
            "La PC debe aprobar cada celular nuevo (dialogo de vinculacion)."
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("color: #b8e4ff; font-size: 11px; line-height: 150%;")
        lay.addWidget(info)
        try:
            import qrcode, bioaccess_server
            from PyQt6.QtGui import QPixmap, QPainter, QColor
            code = bioaccess_server.pair_code()
            payload = "bioaccess://pair?ip=" + host + "&port=" + str(port) + "&code=" + code + "&name=BioAccess%20PC"
            qr = qrcode.QRCode(version=None, box_size=1, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
            qr.add_data(payload)
            qr.make(fit=True)
            matrix = qr.get_matrix()
            n = len(matrix); mod = 8; size = n * mod
            pm = QPixmap(size, size); pm.fill(QColor("#ffffff"))
            p = QPainter(pm); p.setPen(Qt.PenStyle.NoPen)
            for r in range(n):
                for c in range(n):
                    if matrix[r][c]:
                        p.setBrush(QColor("#000000"))
                        p.drawRect(c * mod, r * mod, mod, mod)
            p.end()
            lbl = QLabel()
            lbl.setPixmap(pm.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
        except Exception as e:
            err = QLabel("(QR no disponible: " + str(e) + ")")
            err.setStyleSheet("color: #ff3b5c; font-size: 10px;")
            lay.addWidget(err)
        btn = CyberButton("CERRAR TUNEL", accent_color="#ff9a1f", hover_color="#ff3b5c")
        btn.setFixedHeight(38)
        btn.clicked.connect(lambda: (self._stop_tunnel(), dlg.accept()))
        lay.addWidget(btn)
        dlg.exec()

    def closeEvent(self, event):
        self._stop_tunnel()
        try:
            if self.bridge:
                self.bridge.stop()
                self.bridge.wait(1200)
        except Exception:
            pass
        try:
            if self.server:
                self.server.stop()
        except Exception:
            pass
        super().closeEvent(event)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SuperCustomBio()
    w.show()
    sys.exit(app.exec())