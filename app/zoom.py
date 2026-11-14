"""放大鏡精準點擊：第一次停留先把那一區放大，再盯著放大畫面裡真正要點的位置。"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from . import art
from .overlay import _font


class ZoomWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.pix = QPixmap()
        self.region = QRectF()
        self.factor = 2.5
        self.mode = "left"
        self.border = 6

    def open(self, pix: QPixmap, region: QRectF, factor: float, bounds: QRectF, mode: str):
        """pix：region 的截圖；bounds：視窗可放的範圍（邏輯座標）。"""
        self.pix, self.region, self.factor, self.mode = pix, region, factor, mode
        w = int(region.width() * factor) + 2 * self.border
        h = int(region.height() * factor) + 2 * self.border
        cx, cy = region.center().x(), region.center().y()
        x = min(max(cx - w / 2, bounds.left()), bounds.right() - w)
        y = min(max(cy - h / 2, bounds.top()), bounds.bottom() - h)
        self.setGeometry(int(x), int(y), w, h)
        self.show()
        self.raise_()

    def contains_global(self, gx, gy):
        return self.isVisible() and self.geometry().contains(int(gx), int(gy))

    def to_screen(self, gx, gy):
        """放大視窗上的全域座標 → 原本螢幕上的座標。"""
        lx = gx - self.x() - self.border
        ly = gy - self.y() - self.border
        return (self.region.left() + lx / self.factor, self.region.top() + ly / self.factor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        col = QColor(art.MODE_COLORS.get(self.mode, "#4FA3FF"))
        p.fillRect(self.rect(), col)
        inner = QRectF(self.border, self.border, self.width() - 2 * self.border, self.height() - 2 * self.border)
        if not self.pix.isNull():
            p.drawPixmap(inner, self.pix, QRectF(self.pix.rect()))
        # 淡淡的格線，幫助定位
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        step = 40 * self.factor / 2.5
        x = inner.left() + step
        while x < inner.right():
            p.drawLine(QPointF(x, inner.top()), QPointF(x, inner.bottom()))
            x += step
        y = inner.top() + step
        while y < inner.bottom():
            p.drawLine(QPointF(inner.left(), y), QPointF(inner.right(), y))
            y += step
        # 提示
        tip = QRectF(inner.left() + 10, inner.top() + 10, 360, 40)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(tip, 12, 12)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(_font(18))
        p.drawText(tip, Qt.AlignCenter, "放大鏡：盯著要點的位置；看外面取消")
