"""可愛眼動鼠的繪圖（QPainter，向量繪製可任意縮放）。"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QIcon, QImage,
                           QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)

MODE_COLORS = {
    "left": "#4FA3FF",
    "double": "#9B6BFF",
    "right": "#FF9F43",
    "drag": "#2ECC71",
    "scroll": "#16C2B0",
    "pause": "#A3A3B5",
    "toolbar": "#FF6FA8",
}
MODE_BADGE = {"left": "左", "double": "雙", "right": "右", "drag": "拖", "scroll": "捲", "pause": "停"}

FUR = QColor("#D9D4F2")
FUR_DARK = QColor("#7D72B8")
EAR_IN = QColor("#FFB8CF")
NOSE = QColor("#FF7FA6")


def draw_mouse(p: QPainter, c: QPointF, r: float, look=(0.0, 0.0), blink=0.0, happy=False):
    """畫眼動鼠的臉。c 中心、r 臉半徑、look 視線方向 (-1~1)、blink 0~1。"""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    outline = QPen(FUR_DARK, max(1.0, r * 0.07))
    outline.setJoinStyle(Qt.RoundJoin)
    # 耳朵
    for sx in (-1, 1):
        ec = QPointF(c.x() + sx * r * 0.78, c.y() - r * 0.72)
        p.setPen(outline)
        p.setBrush(FUR)
        p.drawEllipse(ec, r * 0.52, r * 0.52)
        p.setPen(Qt.NoPen)
        p.setBrush(EAR_IN)
        p.drawEllipse(ec, r * 0.32, r * 0.32)
    # 臉
    g = QRadialGradient(QPointF(c.x() - r * 0.3, c.y() - r * 0.4), r * 1.4)
    g.setColorAt(0, QColor("#F4F1FF"))
    g.setColorAt(1, FUR)
    p.setPen(outline)
    p.setBrush(QBrush(g))
    p.drawEllipse(QRectF(c.x() - r, c.y() - r * 0.92, r * 2, r * 1.9))
    # 腮紅
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 140, 170, 110))
    for sx in (-1, 1):
        p.drawEllipse(QPointF(c.x() + sx * r * 0.62, c.y() + r * 0.33), r * 0.2, r * 0.12)
    # 眼睛（大、亮晶晶，會跟著視線方向轉）
    lx, ly = max(-1, min(1, look[0])), max(-1, min(1, look[1]))
    for sx in (-1, 1):
        ex, ey = c.x() + sx * r * 0.36, c.y() - r * 0.05
        ew, eh = r * 0.27, r * 0.33 * (1 - 0.92 * blink)
        if happy:
            pen = QPen(QColor("#2E2A47"), r * 0.09, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            path = QPainterPath(QPointF(ex - ew * 0.8, ey + eh * 0.1))
            path.quadTo(QPointF(ex, ey - eh * 0.9), QPointF(ex + ew * 0.8, ey + eh * 0.1))
            p.drawPath(path)
            continue
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(ex, ey), ew, max(eh, r * 0.03))
        if blink < 0.7:
            px, py = ex + lx * ew * 0.35, ey + ly * eh * 0.3
            p.setBrush(QColor("#2E2A47"))
            p.drawEllipse(QPointF(px, py), ew * 0.72, max(eh * 0.78, r * 0.02))
            p.setBrush(QColor("#6C5CE7"))
            p.drawEllipse(QPointF(px, py + eh * 0.15), ew * 0.4, max(eh * 0.38, r * 0.01))
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(QPointF(px - ew * 0.25, py - eh * 0.3), ew * 0.24, ew * 0.24)
            p.drawEllipse(QPointF(px + ew * 0.22, py + eh * 0.25), ew * 0.1, ew * 0.1)
        p.setPen(QPen(QColor("#2E2A47"), r * 0.05))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(ex, ey), ew, max(eh, r * 0.03))
    # 鼻子
    p.setPen(Qt.NoPen)
    p.setBrush(NOSE)
    p.drawEllipse(QPointF(c.x(), c.y() + r * 0.3), r * 0.11, r * 0.08)
    # 嘴巴 ω
    p.setPen(QPen(QColor("#5B4E8C"), r * 0.05, Qt.SolidLine, Qt.RoundCap))
    m = QPainterPath(QPointF(c.x() - r * 0.18, c.y() + r * 0.42))
    m.quadTo(QPointF(c.x() - r * 0.09, c.y() + r * 0.56), QPointF(c.x(), c.y() + r * 0.42))
    m.quadTo(QPointF(c.x() + r * 0.09, c.y() + r * 0.56), QPointF(c.x() + r * 0.18, c.y() + r * 0.42))
    p.drawPath(m)
    # 鬍鬚
    p.setPen(QPen(QColor(90, 80, 140, 170), r * 0.035, Qt.SolidLine, Qt.RoundCap))
    for sx in (-1, 1):
        for k, dy in enumerate((-0.08, 0.04, 0.16)):
            x0 = c.x() + sx * r * 0.42
            y0 = c.y() + r * (0.32 + dy * 0.4)
            p.drawLine(QPointF(x0, y0), QPointF(x0 + sx * r * 0.5, y0 + r * dy))
    p.restore()


def draw_ring(p: QPainter, c: QPointF, R: float, spin: float, progress: float, color: str, width=None):
    """光環：閒置時三段彩色弧線旋轉；停留時變成進度條。"""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    w = width or max(2.0, R * 0.13)
    rect = QRectF(c.x() - R, c.y() - R, 2 * R, 2 * R)
    # 底圈
    p.setPen(QPen(QColor(255, 255, 255, 120), w + 2))
    p.drawEllipse(rect)
    p.setPen(QPen(QColor(125, 114, 184, 60), w))
    p.drawEllipse(rect)
    if progress > 0:
        col = QColor(color)
        grad = QConicalGradient(c, 90)
        grad.setColorAt(0.0, col.lighter(140))
        grad.setColorAt(1.0, col)
        pen = QPen(QBrush(grad), w, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        span = -int(360 * 16 * min(1.0, progress))
        p.drawArc(rect, 90 * 16, span)
        # 弧線前端的小亮點
        a = math.radians(90 - 360 * min(1.0, progress))
        hx, hy = c.x() + R * math.cos(a), c.y() - R * math.sin(a)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(hx, hy), w * 0.42, w * 0.42)
    else:
        cols = ["#FF8FB8", "#8FC8FF", "#B9A7FF"]
        for i, cs in enumerate(cols):
            pen = QPen(QColor(cs), w * 0.75, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            start = int((spin + i * 120) * 16)
            p.drawArc(rect, -start, 60 * 16)
        # 繞圈的小星點
        a = math.radians(-spin * 1.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 230))
        p.drawEllipse(QPointF(c.x() + R * math.cos(a), c.y() + R * math.sin(a)), w * 0.35, w * 0.35)
    p.restore()


def draw_badge(p: QPainter, c: QPointF, r: float, mode: str):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#FFFFFF"), r * 0.18))
    p.setBrush(QColor(MODE_COLORS.get(mode, "#4FA3FF")))
    p.drawEllipse(c, r, r)
    f = QFont("Microsoft JhengHei UI")
    f.setFamilies(["Microsoft JhengHei UI", "PingFang TC", "Heiti TC", "Noto Sans CJK TC"])
    f.setPixelSize(max(6, int(r * 1.15)))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r), Qt.AlignCenter, MODE_BADGE.get(mode, ""))
    p.restore()


def render_icon(size=256, spin=30.0) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    c = QPointF(size / 2, size / 2)
    p.setRenderHint(QPainter.Antialiasing)
    # 底板
    p.setPen(Qt.NoPen)
    g = QRadialGradient(c, size / 2)
    g.setColorAt(0, QColor("#FFFFFF"))
    g.setColorAt(1, QColor("#EEE9FF"))
    p.setBrush(QBrush(g))
    p.drawEllipse(c, size * 0.48, size * 0.48)
    draw_ring(p, c, size * 0.43, spin, 0, "#4FA3FF", width=size * 0.055)
    draw_mouse(p, QPointF(c.x(), c.y() + size * 0.06), size * 0.25, look=(0.4, -0.2))
    p.end()
    return img


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(QPixmap.fromImage(render_icon(s)))
    return ic
