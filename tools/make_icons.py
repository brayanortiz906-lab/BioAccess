# -*- coding: utf-8 -*-
"""Genera los iconos de la APK (huella cyberpunk) usando PyQt6 sin pantalla."""
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PyQt6.QtGui import (QColor, QFont, QImage, QLinearGradient, QPainter,  # noqa: E402
                         QPainterPath, QPen, QBrush)
from PyQt6.QtWidgets import QApplication  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
RES = BASE / "android" / "app" / "src" / "main" / "res"

DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def draw_fingerprint(p: QPainter, scale: float, alpha: int = 240):
    p.save()
    p.scale(scale, scale)
    r_max = 70
    n_top = 13
    for k in range(n_top):
        w = 62.0 - k * 4.4
        ry = w * 1.04 + 1.0
        ye = math.sqrt(r_max ** 2 - w ** 2) - 4.0 if k < 4 else 46.0 - (k - 3) * 0.9
        path = QPainterPath()
        path.moveTo(-w, ye)
        path.lineTo(-w, 0)
        path.arcTo(QRectF(-w, -ry, w * 2, ry * 2), 180, -180)
        path.lineTo(w, ye)
        if k % 2 == 1:
            pen = QPen(QColor(34, 211, 255, int(alpha * 0.85)), 8.0, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor(34, 211, 255, alpha), 8.0, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(path)
    for k in range(4):
        y0 = 52.0 + k * 5.4
        hw = math.sqrt(max(0, r_max ** 2 - y0 ** 2)) - 3.0
        path = QPainterPath()
        path.moveTo(-hw, y0)
        path.quadTo(0, y0 + 9.0, hw, y0)
        p.setPen(QPen(QColor(34, 211, 255, int(alpha * 0.8)), 8.0,
                      Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawPath(path)
    p.restore()


def render(size: int, with_bg: bool = True) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent if not with_bg else QColor(1, 4, 10))

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    s = size / 256.0

    c = size / 2.0
    r = size * 0.46

    if with_bg:
        # rejilla tenue
        p.setPen(QPen(QColor(34, 211, 255, 22), max(1.0, 1.2 * s)))
        step = size / 8.0
        for i in range(1, 8):
            p.drawLine(QPointF(i * step, 0), QPointF(i * step, size))
            p.drawLine(QPointF(0, i * step), QPointF(size, i * step))

        # halo
        grad = QLinearGradient(0, 0, 0, size)
        grad.setColorAt(0.0, QColor(34, 211, 255, 40))
        grad.setColorAt(1.0, QColor(1, 4, 10, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QRectF(c - r * 1.25, c - r * 1.25, r * 2.5, r * 2.5))

    # aro externo
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(34, 211, 255, 190), max(1.0, 2.0 * s)))
    p.drawEllipse(QRectF(c - r, c - r, r * 2, r * 2))

    # marcas
    p.save()
    p.translate(c, c)
    p.setPen(QPen(QColor(34, 211, 255, 150), max(1.0, 1.6 * s)))
    for i in range(48):
        ln = r * 0.10 if i % 4 == 0 else r * 0.05
        p.drawLine(QPointF(0, -r), QPointF(0, -r + ln))
        p.rotate(360.0 / 48.0)
    p.restore()

    # anillo naranja
    p.save()
    p.translate(c, c)
    p.rotate(-30)
    p.setPen(QPen(QColor(255, 154, 31, 210), max(1.5, 3.0 * s), Qt.PenStyle.DashLine))
    rr = r * 0.90
    p.drawEllipse(QRectF(-rr, -rr, rr * 2, rr * 2))
    p.restore()

    # huella
    p.save()
    p.translate(c, c)
    draw_fingerprint(p, (r * 0.62) / 70.0)
    p.restore()

    p.end()
    return img


def main():
    app = QApplication.instance() or QApplication([])
    made = []

    for dpi, px in DENSITIES.items():
        d = RES / ("mipmap-" + dpi)
        d.mkdir(parents=True, exist_ok=True)
        img = render(px, with_bg=True)
        out = d / "ic_launcher.png"
        img.save(str(out), "PNG")
        made.append(out)

    # icono adaptativo (Android 8+): fondo oscuro + huella al 66%
    fg_dir = RES / "drawable-nodpi"
    fg_dir.mkdir(parents=True, exist_ok=True)
    fg = render(432, with_bg=False)
    fg_out = fg_dir / "ic_launcher_foreground.png"
    fg.save(str(fg_out), "PNG")
    made.append(fg_out)

    # banner para el diálogo de vinculación / README
    banner = render(512, with_bg=True)
    banner_out = BASE / "icono_bioaccess.png"
    banner.save(str(banner_out), "PNG")
    made.append(banner_out)

    app.quit()
    for m in made:
        print("icono:", m.relative_to(BASE), os.path.getsize(m), "bytes")


if __name__ == "__main__":
    main()
