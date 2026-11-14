"""畫面上的眼動鼠游標（不攔截滑鼠）與停留工具列。"""
import math
import sys

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import art

FLAGS_OVERLAY = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                 | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)


def _font(px, bold=True):
    f = QFont("Microsoft JhengHei UI")
    f.setFamilies(["Microsoft JhengHei UI", "PingFang TC", "Heiti TC", "Noto Sans CJK TC"])
    f.setPixelSize(int(px))
    f.setBold(bold)
    return f


def _make_click_through(w: QWidget):
    if sys.platform == "win32":
        import ctypes
        hwnd = int(w.winId())
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x80000, 0x20, 0x08000000, 0x80
        u = ctypes.windll.user32
        st = u.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


class CursorOverlay(QWidget):
    """跟著視線移動的光環＋小老鼠。中心透明，不擋住要點的目標。"""

    def __init__(self, size=96):
        super().__init__(None, FLAGS_OVERLAY)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.ring = size / 2
        self.box = int(size * 2.1)
        self.resize(self.box, self.box)
        self.spin = 0.0
        self.progress = 0.0
        self.mode = "left"
        self.look = (0.0, 0.0)
        self.blink = 0.0
        self.happy = 0.0
        self.label = ""
        self.scroll_dir = 0       # -1 上、1 下、0 無
        self.held = False         # 拖曳中
        self.dim = False          # 暫停/手動時半透明

    def set_size(self, size):
        self.ring = size / 2
        self.box = int(size * 2.1)
        self.resize(self.box, self.box)

    def showEvent(self, e):
        super().showEvent(e)
        _make_click_through(self)

    def place(self, x, y):
        self.move(int(x - self.box / 2), int(y - self.box / 2))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.dim:
            p.setOpacity(0.45)
        c = QPointF(self.box / 2, self.box / 2)
        R = self.ring * 0.62
        color = art.MODE_COLORS.get(self.mode, "#4FA3FF")
        art.draw_ring(p, c, R, self.spin, self.progress, color, width=max(4, R * 0.16))
        # 中心準星
        p.setPen(QPen(QColor(255, 255, 255, 230), 3))
        p.setBrush(QColor(color))
        p.drawEllipse(c, 3.5, 3.5)
        if self.held:
            p.setPen(QPen(QColor(art.MODE_COLORS["drag"]), 3, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(c, R * 0.55, R * 0.55)
        if self.scroll_dir:
            self._arrow(p, c, R, self.scroll_dir)
        # 小老鼠陪在右下
        mr = self.ring * 0.36
        mc = QPointF(c.x() + R * 0.98 + mr * 0.55, c.y() + R * 0.98 + mr * 0.35)
        art.draw_mouse(p, mc, mr, look=self.look, blink=self.blink, happy=self.happy > 0)
        art.draw_badge(p, QPointF(mc.x() + mr * 0.95, mc.y() + mr * 0.85), mr * 0.42, self.mode)
        if self.label:
            p.setFont(_font(max(11, self.ring * 0.24)))
            r = QRectF(0, c.y() - R - self.ring * 0.62, self.box, self.ring * 0.4)
            p.setPen(QColor(0, 0, 0, 120))
            p.drawText(r.translated(1, 1), Qt.AlignCenter, self.label)
            p.setPen(QColor("#FFFFFF"))
            p.drawText(r, Qt.AlignCenter, self.label)

    def _arrow(self, p, c, R, d):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(art.MODE_COLORS["scroll"]))
        tip = c.y() + d * R * 1.45
        base = c.y() + d * R * 1.05
        path = QPainterPath(QPointF(c.x(), tip))
        path.lineTo(c.x() - R * 0.35, base)
        path.lineTo(c.x() + R * 0.35, base)
        path.closeSubpath()
        p.drawPath(path)


class ScrollGuide(QWidget):
    """捲動模式時，在錨點上下顯示捲動區。"""

    def __init__(self):
        super().__init__(None, FLAGS_OVERLAY)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.dead = 80
        self.resize(150, 520)

    def showEvent(self, e):
        super().showEvent(e)
        _make_click_through(self)

    def place(self, x, y, dead):
        self.dead = dead
        self.move(int(x - self.width() / 2), int(y - self.height() / 2))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cy = h / 2
        col = QColor(art.MODE_COLORS["scroll"])
        for d in (-1, 1):
            r = QRectF(w * 0.2, cy + (self.dead if d > 0 else -h / 2 + 4), w * 0.6, h / 2 - self.dead - 4)
            c2 = QColor(col)
            c2.setAlpha(55)
            p.setPen(QPen(col, 2))
            p.setBrush(c2)
            p.drawRoundedRect(r, 18, 18)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(_font(22))
            p.drawText(r, Qt.AlignCenter, "▲\n往上捲" if d < 0 else "往下捲\n▼")
        p.setPen(QPen(col, 2, Qt.DashLine))
        p.setBrush(QColor(255, 255, 255, 60))
        p.drawEllipse(QPointF(w / 2, cy), self.dead * 0.75, self.dead * 0.75)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(_font(14))
        p.drawText(QRectF(0, cy - 30, w, 60), Qt.AlignCenter, "看這裡\n結束捲動")


# ---------------------------------------------------------------- 工具列
BUTTONS = [
    ("left", "左鍵"),
    ("double", "雙擊"),
    ("right", "右鍵"),
    ("drag", "拖曳"),
    ("scroll", "捲動"),
    ("keyboard", "鍵盤"),
    ("pause", "暫停"),
    ("menu", "選單"),
]


def draw_glyph(p: QPainter, key, r: QRectF, color: QColor, paused=False):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, max(2.0, r.width() * 0.07), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    cx, cy, s = r.center().x(), r.center().y(), r.width()
    if key in ("left", "double", "right"):
        body = QRectF(cx - s * 0.26, cy - s * 0.4, s * 0.52, s * 0.8)
        p.drawRoundedRect(body, s * 0.24, s * 0.24)
        p.drawLine(QPointF(cx, body.top()), QPointF(cx, cy - s * 0.08))
        p.drawLine(QPointF(body.left(), cy - s * 0.08), QPointF(body.right(), cy - s * 0.08))
        fill = QPainterPath()
        if key == "right":
            fill.moveTo(cx, body.top() + 1)
            fill.arcTo(body.adjusted(1, 1, -1, -1).left(), body.top() + 1, body.width() - 2, s * 0.48, 90, -90)
            fill.lineTo(body.right() - 1, cy - s * 0.08)
            fill.lineTo(cx, cy - s * 0.08)
        else:
            fill.moveTo(cx, body.top() + 1)
            fill.arcTo(body.left() + 1, body.top() + 1, body.width() - 2, s * 0.48, 90, 90)
            fill.lineTo(body.left() + 1, cy - s * 0.08)
            fill.lineTo(cx, cy - s * 0.08)
        fill.closeSubpath()
        p.setBrush(color)
        p.drawPath(fill)
        if key == "double":
            p.setFont(_font(s * 0.3))
            p.drawText(QRectF(cx - s * 0.25, cy, s * 0.5, s * 0.36), Qt.AlignCenter, "2")
    elif key == "drag":
        for a in range(4):
            ang = a * math.pi / 2
            dx, dy = math.cos(ang), math.sin(ang)
            tip = QPointF(cx + dx * s * 0.42, cy + dy * s * 0.42)
            p.drawLine(QPointF(cx, cy), tip)
            nx, ny = -dy, dx
            p.drawLine(tip, QPointF(tip.x() - dx * s * 0.14 + nx * s * 0.12, tip.y() - dy * s * 0.14 + ny * s * 0.12))
            p.drawLine(tip, QPointF(tip.x() - dx * s * 0.14 - nx * s * 0.12, tip.y() - dy * s * 0.14 - ny * s * 0.12))
    elif key == "scroll":
        body = QRectF(cx - s * 0.2, cy - s * 0.42, s * 0.4, s * 0.84)
        p.drawRoundedRect(body, s * 0.2, s * 0.2)
        p.setBrush(color)
        for d in (-1, 1):
            path = QPainterPath(QPointF(cx, cy + d * s * 0.3))
            path.lineTo(cx - s * 0.1, cy + d * s * 0.14)
            path.lineTo(cx + s * 0.1, cy + d * s * 0.14)
            path.closeSubpath()
            p.drawPath(path)
    elif key == "keyboard":
        body = QRectF(cx - s * 0.44, cy - s * 0.26, s * 0.88, s * 0.52)
        p.drawRoundedRect(body, s * 0.08, s * 0.08)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        k = s * 0.1
        for row in range(2):
            for col in range(5):
                p.drawRect(QRectF(body.left() + s * 0.08 + col * s * 0.155, body.top() + s * 0.08 + row * s * 0.14, k, k * 0.8))
        p.drawRect(QRectF(cx - s * 0.22, body.bottom() - s * 0.13, s * 0.44, k * 0.7))
    elif key == "pause":
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        if paused:  # 顯示「繼續」三角形
            path = QPainterPath(QPointF(cx - s * 0.2, cy - s * 0.3))
            path.lineTo(cx + s * 0.3, cy)
            path.lineTo(cx - s * 0.2, cy + s * 0.3)
            path.closeSubpath()
            p.drawPath(path)
        else:
            p.drawRoundedRect(QRectF(cx - s * 0.25, cy - s * 0.3, s * 0.17, s * 0.6), 4, 4)
            p.drawRoundedRect(QRectF(cx + s * 0.08, cy - s * 0.3, s * 0.17, s * 0.6), 4, 4)
    elif key == "menu":
        for i in (-1, 0, 1):
            p.drawLine(QPointF(cx - s * 0.3, cy + i * s * 0.22), QPointF(cx + s * 0.3, cy + i * s * 0.22))
    p.restore()


class Toolbar(QWidget):
    """貼在螢幕邊的眼動工具列：看著按鈕停留即選取，也可直接用滑鼠按。"""
    picked = Signal(str)

    def __init__(self, button=92):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.btn = button
        self.mode = "left"
        self.paused = False
        self.hover = None
        self.progress = 0.0
        self.flash = None
        self.pad = 10
        self._layout()

    def _layout(self):
        n = len(BUTTONS)
        self.gap = max(6, self.btn // 10)
        h = self.pad * 2 + n * self.btn + (n - 1) * self.gap
        self.resize(self.btn + self.pad * 2, h)

    def set_button(self, size):
        self.btn = size
        self._layout()

    def dock(self, screen_geo: QRect, side="right"):
        x = screen_geo.right() - self.width() + 1 if side == "right" else screen_geo.left()
        y = screen_geo.top() + max(0, (screen_geo.height() - self.height()) // 2)
        self.move(x, y)

    def button_rect(self, i) -> QRectF:
        return QRectF(self.pad, self.pad + i * (self.btn + self.gap), self.btn, self.btn)

    def button_at_global(self, gx, gy):
        if not self.isVisible():
            return None
        lx, ly = gx - self.x(), gy - self.y()
        if not (0 <= lx < self.width() and 0 <= ly < self.height()):
            return None
        for i, (k, _) in enumerate(BUTTONS):
            if self.button_rect(i).adjusted(-self.gap / 2, -self.gap / 2, self.gap / 2, self.gap / 2).contains(lx, ly):
                return k
        return "_bar"

    def contains_global(self, gx, gy):
        return self.isVisible() and self.geometry().adjusted(-6, -6, 6, 6).contains(int(gx), int(gy))

    def mousePressEvent(self, e):
        k = self.button_at_global(e.globalPosition().x(), e.globalPosition().y())
        if k and k != "_bar":
            self.picked.emit(k)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(QPen(QColor(125, 114, 184, 160), 2))
        p.setBrush(QColor(250, 248, 255, 235))
        p.drawRoundedRect(bg, 22, 22)
        for i, (k, label) in enumerate(BUTTONS):
            r = self.button_rect(i)
            active = (k == self.mode) or (k == "pause" and self.paused)
            col = QColor(art.MODE_COLORS.get(k, "#7D72B8"))
            if k in ("keyboard", "menu"):
                col = QColor("#7D72B8")
            if k == "pause":
                col = QColor("#E8676B") if self.paused else QColor("#8A86A8")
            if active:
                fill = QColor(col)
                fill.setAlpha(255)
                p.setPen(Qt.NoPen)
                p.setBrush(fill)
            else:
                p.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 120), 2))
                p.setBrush(QColor("#FFFFFF"))
            if self.flash == k:
                p.setBrush(QColor("#FFE066"))
            p.drawRoundedRect(r, 18, 18)
            glyph_col = QColor("#FFFFFF") if active else col
            draw_glyph(p, k, QRectF(r.left() + r.width() * 0.2, r.top() + r.height() * 0.08,
                                    r.width() * 0.6, r.height() * 0.6), glyph_col, paused=self.paused)
            p.setFont(_font(max(12, self.btn * 0.19)))
            p.setPen(glyph_col)
            txt = "繼續" if (k == "pause" and self.paused) else label
            p.drawText(QRectF(r.left(), r.bottom() - r.height() * 0.32, r.width(), r.height() * 0.28), Qt.AlignCenter, txt)
            if self.hover == k and self.progress > 0:
                # 按鈕外框的進度
                pen = QPen(QColor(art.MODE_COLORS["toolbar"]), 6, Qt.SolidLine, Qt.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                rr = r.adjusted(3, 3, -3, -3)
                path = QPainterPath()
                path.addRoundedRect(rr, 16, 16)
                n = 80
                pts = [path.pointAtPercent(min(1.0, j / n * self.progress)) for j in range(n + 1)]
                for a, b in zip(pts, pts[1:]):
                    p.drawLine(a, b)
