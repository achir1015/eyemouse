"""動畫教學：每頁一段示範動畫＋中文語音旁白＋字幕；最後一頁互動練習。"""
import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import art
from .overlay import _font, draw_glyph
from .texts import TUTORIAL

SCREEN = QRectF(0, 0, 1000, 560)    # 示範用的「假螢幕」座標系


def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def track(t, keys):
    """keys: [(time, x, y)]，回傳平滑插值位置。"""
    if t <= keys[0][0]:
        return QPointF(keys[0][1], keys[0][2])
    for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            k = ease((t - t0) / max(1e-6, t1 - t0))
            return QPointF(x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
    return QPointF(keys[-1][1], keys[-1][2])


def span(t, a, b):
    """在 a~b 期間回傳 0~1，其餘 0。"""
    return 0.0 if t < a or t > b else (t - a) / (b - a)


# ---------------------------------------------------------------- 假桌面元件
def desk(p: QPainter, toolbar=True, mode="left", paused=False, hover=None, hover_p=0.0):
    g = QLinearGradient(0, 0, 0, SCREEN.height())
    g.setColorAt(0, QColor("#CFE6FF"))
    g.setColorAt(1, QColor("#E9DFFF"))
    p.setPen(QPen(QColor("#7D72B8"), 4))
    p.setBrush(g)
    p.drawRoundedRect(SCREEN, 24, 24)
    if toolbar:
        keys = ["left", "double", "right", "drag", "scroll", "keyboard", "pause", "menu"]
        x, y0, b = 918, 30, 56
        p.setPen(QPen(QColor(125, 114, 184, 160), 2))
        p.setBrush(QColor(250, 248, 255, 235))
        p.drawRoundedRect(QRectF(x - 8, y0 - 8, b + 16, 8 * (b + 6) + 10), 14, 14)
        for i, k in enumerate(keys):
            r = QRectF(x, y0 + i * (b + 6), b, b)
            col = QColor(art.MODE_COLORS.get(k, "#7D72B8"))
            if k == "pause":
                col = QColor("#E8676B") if paused else QColor("#8A86A8")
            act = k == mode or (k == "pause" and paused)
            p.setPen(QPen(col, 2))
            p.setBrush(col if act else QColor("#FFFFFF"))
            p.drawRoundedRect(r, 10, 10)
            draw_glyph(p, k, r.adjusted(12, 10, -12, -14), QColor("#FFFFFF") if act else col, paused)
            if hover == k and hover_p > 0:
                p.setPen(QPen(QColor(art.MODE_COLORS["toolbar"]), 4))
                p.setBrush(Qt.NoBrush)
                p.drawArc(r.adjusted(-4, -4, 4, 4), 90 * 16, -int(360 * 16 * hover_p))


def tb_pos(key):
    keys = ["left", "double", "right", "drag", "scroll", "keyboard", "pause", "menu"]
    i = keys.index(key)
    return 918 + 28, 30 + i * 62 + 28


def cursor(p, pos, prog=0.0, mode="left", spin=0.0, held=False, dim=False, label=""):
    p.save()
    if dim:
        p.setOpacity(0.45)
    R = 34
    art.draw_ring(p, pos, R, spin, prog, art.MODE_COLORS.get(mode, "#4FA3FF"), width=6)
    p.setPen(QPen(QColor("#FFFFFF"), 2))
    p.setBrush(QColor(art.MODE_COLORS.get(mode, "#4FA3FF")))
    p.drawEllipse(pos, 3, 3)
    if held:
        p.setPen(QPen(QColor(art.MODE_COLORS["drag"]), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(pos, 18, 18)
    mc = QPointF(pos.x() + 46, pos.y() + 42)
    art.draw_mouse(p, mc, 17, look=(0.5, 0.3), happy=prog >= 0.99)
    art.draw_badge(p, QPointF(mc.x() + 16, mc.y() + 14), 8, mode)
    if label:
        p.setFont(_font(16))
        p.setPen(QColor("#5B4E8C"))
        p.drawText(QRectF(pos.x() - 80, pos.y() - 70, 160, 24), Qt.AlignCenter, label)
    p.restore()


def button(p, r, text, color="#4FA3FF", pressed=False):
    p.setPen(QPen(QColor(color).darker(120), 2))
    p.setBrush(QColor(color).darker(115) if pressed else QColor(color))
    p.drawRoundedRect(r.translated(0, 3 if pressed else 0), 14, 14)
    p.setFont(_font(22))
    p.setPen(QColor("#FFFFFF"))
    p.drawText(r.translated(0, 3 if pressed else 0), Qt.AlignCenter, text)


def file_icon(p, c, label="照片"):
    r = QRectF(c.x() - 32, c.y() - 40, 64, 80)
    p.setPen(QPen(QColor("#5B4E8C"), 2))
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(r, 8, 8)
    p.setBrush(QColor("#FFB8CF"))
    p.drawEllipse(QPointF(c.x() - 8, c.y() - 12), 8, 8)
    p.setBrush(QColor("#8FD4A8"))
    path = QPainterPath(QPointF(c.x() - 24, c.y() + 18))
    path.lineTo(c.x() - 4, c.y() - 4)
    path.lineTo(c.x() + 24, c.y() + 18)
    path.closeSubpath()
    p.drawPath(path)
    p.setFont(_font(14))
    p.drawText(QRectF(c.x() - 50, c.y() + 44, 100, 22), Qt.AlignCenter, label)


def folder(p, c, open_=False, scale=1.0):
    p.save()
    p.translate(c)
    p.scale(scale, scale)
    p.setPen(QPen(QColor("#B7791F"), 2))
    p.setBrush(QColor("#FFD36E"))
    p.drawRoundedRect(QRectF(-50, -30, 40, 16), 5, 5)
    p.drawRoundedRect(QRectF(-50, -22, 100, 64), 8, 8)
    if open_:
        p.setBrush(QColor("#FFE39E"))
        p.drawRoundedRect(QRectF(-46, -8, 96, 50), 8, 8)
    p.setFont(_font(14))
    p.setPen(QColor("#5B4E8C"))
    p.drawText(QRectF(-60, 46, 120, 22), Qt.AlignCenter, "相簿")
    p.restore()


# ---------------------------------------------------------------- 各頁動畫
def scene_welcome(p, t, spin):
    desk(p, toolbar=False)
    c = QPointF(500, 270 + math.sin(t * 3) * 10)
    art.draw_ring(p, c, 150, spin, 0, "", width=16)
    art.draw_mouse(p, c, 90, look=(math.sin(t * 1.3), math.cos(t * 1.7) * 0.6), blink=1.0 if (t % 3.2) < 0.15 else 0.0)
    p.setFont(_font(30))
    p.setPen(QColor("#5B4E8C"))
    p.drawText(QRectF(0, 470, 1000, 50), Qt.AlignCenter, "眼動鼠：用眼睛當滑鼠")
    return 6.0


def scene_move(p, t, spin):
    desk(p)
    for i, (x, y) in enumerate([(120, 110), (120, 230), (120, 350)]):
        file_icon(p, QPointF(x, y), ["文件", "照片", "音樂"][i])
    pos = QPointF(480 + 300 * math.sin(t * 0.9), 280 + 160 * math.sin(t * 1.6))
    cursor(p, pos, 0, "left", spin)
    # 眼睛示意
    ec = QPointF(500, 515)
    p.setPen(QPen(QColor("#5B4E8C"), 3))
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(ec, 48, 26)
    dx = (pos.x() - 480) / 300 * 22
    dy = (pos.y() - 280) / 160 * 9
    p.setBrush(QColor("#2E2A47"))
    p.drawEllipse(QPointF(ec.x() + dx, ec.y() + dy), 14, 14)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QPointF(ec.x() + dx - 4, ec.y() + dy - 5), 4, 4)
    return 7.0


def scene_click(p, t, spin):
    desk(p)
    r = QRectF(390, 230, 220, 90)
    keys = [(0, 160, 120), (1.2, 500, 275), (3.0, 500, 275), (3.8, 750, 420), (5.5, 160, 120)]
    pos = track(t, keys)
    prog = span(t, 1.5, 2.6)
    pressed = 2.6 <= t <= 3.0
    button(p, r, "確定", "#4FA3FF", pressed)
    if pressed:
        for k in range(8):
            a = k * math.pi / 4
            d = 70 + (t - 2.6) * 120
            p.setPen(QPen(QColor("#FFD36E"), 4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(500 + math.cos(a) * d, 275 + math.sin(a) * d * 0.6),
                       QPointF(500 + math.cos(a) * (d + 14), 275 + math.sin(a) * (d + 14) * 0.6))
    cursor(p, pos, prog if t < 2.7 else 0, "left", spin, label="盯著不動…" if 1.4 < t < 2.6 else ("叮！按下了" if pressed else ""))
    return 6.0


def scene_toolbar(p, t, spin):
    mode = "right" if 2.2 <= t < 5.4 else "left"
    tx, ty = tb_pos("right")
    hover_p = span(t, 1.0, 2.2) if t < 2.2 else 0
    desk(p, mode=mode, hover="right", hover_p=hover_p)
    fpos = QPointF(300, 260)
    file_icon(p, fpos, "照片")
    keys = [(0, 500, 300), (0.9, tx, ty), (2.4, tx, ty), (3.4, 300, 255), (5.6, 300, 255), (6.6, 500, 300)]
    pos = track(t, keys)
    prog = span(t, 3.5, 4.6)
    if t >= 4.6 and t < 6.2:
        m = QRectF(320, 270, 170, 150)
        p.setPen(QPen(QColor("#B9A7FF"), 2))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(m, 10, 10)
        p.setFont(_font(17, False))
        p.setPen(QColor("#2E2A47"))
        for i, s in enumerate(["開啟", "複製", "重新命名", "刪除"]):
            p.drawText(QRectF(m.left() + 16, m.top() + 8 + i * 34, 140, 32), Qt.AlignVCenter, s)
    cursor(p, pos, prog if t < 4.7 else 0, mode if t >= 2.2 else "left", spin,
           label="選右鍵" if 1.0 < t < 2.3 else ("右鍵選單出現！" if 4.6 < t < 6 else ""))
    return 7.0


def scene_drag(p, t, spin):
    mode = "drag" if 1.9 <= t < 6.6 else "left"
    tx, ty = tb_pos("drag")
    desk(p, mode=mode, hover="drag", hover_p=span(t, 0.8, 1.9) if t < 1.9 else 0)
    fold = QPointF(700, 300)
    keys = [(0, 500, 300), (0.7, tx, ty), (2.0, tx, ty), (2.8, 220, 250), (4.0, 220, 250),
            (5.3, 700, 290), (6.5, 700, 290), (7.2, 500, 300)]
    pos = track(t, keys)
    held = 4.0 <= t < 6.5
    dropped = t >= 6.5
    folder(p, fold, open_=held and t > 5.0, scale=1.0 + (0.15 * math.sin((t - 6.5) * 12) if 6.5 <= t < 6.8 else 0))
    if not dropped:
        file_icon(p, QPointF(pos.x(), pos.y()) if held else QPointF(220, 250), "照片")
    prog = span(t, 2.9, 4.0) if t < 4.0 else span(t, 5.4, 6.5)
    lab = "第一次停留＝按住" if 2.9 < t < 4.3 else ("第二次停留＝放開" if 5.4 < t < 6.6 else ("放進相簿了！" if dropped else ""))
    cursor(p, pos, prog, mode, spin, held=held, label=lab)
    return 8.0


def scene_scroll(p, t, spin):
    mode = "scroll" if 1.8 <= t < 8.0 else "left"
    tx, ty = tb_pos("scroll")
    desk(p, mode=mode, hover="scroll", hover_p=span(t, 0.8, 1.8) if t < 1.8 else 0)
    doc = QRectF(260, 40, 440, 480)
    p.setPen(QPen(QColor("#B9A7FF"), 2))
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(doc, 12, 12)
    off = 0.0
    if t > 3.6:
        off = min(t, 5.6) - 3.6
        off = off * off * 60
    if t > 5.6:
        off = 240 - (min(t, 6.6) - 5.6) * 90
    p.save()
    p.setClipRect(doc.adjusted(4, 4, -4, -4))
    for i in range(30):
        y = doc.top() + 30 + i * 34 - off
        p.setPen(QPen(QColor("#D9D4F2"), 10, Qt.SolidLine, Qt.RoundCap))
        w = 360 if i % 4 else 220
        p.drawLine(QPointF(doc.left() + 40, y), QPointF(doc.left() + 40 + w, y))
    p.restore()
    keys = [(0, 480, 280), (0.7, tx, ty), (1.9, tx, ty), (2.5, 480, 280), (3.6, 480, 280), (4.2, 480, 470),
            (5.5, 480, 470), (5.9, 480, 110), (6.6, 480, 110), (7.0, 480, 280)]
    pos = track(t, keys)
    anchor = QPointF(480, 280)
    if 3.6 <= t < 8:
        p.setPen(QPen(QColor(art.MODE_COLORS["scroll"]), 2, Qt.DashLine))
        p.setBrush(QColor(255, 255, 255, 80))
        p.drawEllipse(anchor, 50, 50)
    prog = span(t, 2.5, 3.6) if t < 3.6 else span(t, 7.0, 8.0)
    lab = "往下看＝往下捲" if 4.2 < t < 5.6 else ("往上看＝往上捲" if 5.9 < t < 6.7 else ("看回中間＝結束" if 7.0 < t < 8 else ""))
    cursor(p, pos, prog, mode, spin, label=lab)
    return 8.6


def scene_pause(p, t, spin):
    paused = 2.0 <= t < 6.0
    tx, ty = tb_pos("pause")
    desk(p, paused=paused, hover="pause", hover_p=span(t, 0.8, 2.0) if t < 2.0 else span(t, 4.8, 6.0))
    keys = [(0, 450, 300), (0.7, tx, ty), (2.2, tx, ty), (3.0, 420, 260), (4.2, 470, 330), (4.8, tx, ty), (6.2, tx, ty), (7, 450, 300)]
    pos = track(t, keys)
    prog = 0
    cursor(p, pos, prog, "pause" if paused else "left", spin, dim=paused and 2.2 < t < 4.8,
           label="暫停中" if 2.2 < t < 4.8 else ("看繼續" if 4.8 < t < 6 else ""))
    # 實體滑鼠圖示
    hx = 200 + 60 * math.sin(t * 2)
    p.setPen(QPen(QColor("#5B4E8C"), 2))
    p.setBrush(QColor("#FFFFFF"))
    p.drawRoundedRect(QRectF(hx, 420, 50, 74), 24, 24)
    p.drawLine(QPointF(hx + 25, 420), QPointF(hx + 25, 450))
    p.setFont(_font(16))
    p.drawText(QRectF(hx - 60, 498, 170, 24), Qt.AlignCenter, "照顧者用滑鼠＝自動讓手")
    return 7.4


def scene_calib(p, t, spin):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2D2852"))
    p.drawRoundedRect(SCREEN, 24, 24)
    pts = [(0.5, 0.5), (0.1, 0.12), (0.5, 0.12), (0.9, 0.12), (0.9, 0.5), (0.9, 0.88), (0.5, 0.88), (0.1, 0.88), (0.1, 0.5)]
    per = 1.0
    i = int(t / per) % len(pts)
    j = (i + 1) % len(pts)
    k = ease((t % per) / 0.45)
    a = QPointF(pts[i][0] * 1000, pts[i][1] * 560)
    b = QPointF(pts[j][0] * 1000, pts[j][1] * 560)
    pos = a + (b - a) * k
    for q in range(i + 1):
        p.setBrush(QColor(143, 200, 255, 140))
        p.drawEllipse(QPointF(pts[q][0] * 1000, pts[q][1] * 560), 5, 5)
    art.draw_ring(p, pos, 40, spin, max(0, (t % per - 0.45) / 0.55), "#FF8FB8", width=6)
    art.draw_mouse(p, pos, 22)
    p.setFont(_font(22))
    p.setPen(QColor("#CFC8FF"))
    p.drawText(QRectF(0, 250, 1000, 60), Qt.AlignCenter, "盯著小老鼠看就好")
    return 9.0


ASSESS_FIX = [(260, 180, 0.6), (420, 150, 0.9), (610, 220, 1.4), (700, 380, 0.7), (480, 400, 1.1), (300, 360, 0.5), (520, 270, 1.6)]


def scene_assess(p, t, spin):
    desk(p, toolbar=False)
    # 一幅小畫：太陽、房子、樹
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFD36E"))
    p.drawEllipse(QPointF(820, 110), 50, 50)
    p.setBrush(QColor("#FF9F8A"))
    p.drawRect(QRectF(400, 230, 220, 170))
    path = QPainterPath(QPointF(380, 235))
    path.lineTo(510, 130)
    path.lineTo(640, 235)
    path.closeSubpath()
    p.setBrush(QColor("#B4553D"))
    p.drawPath(path)
    p.setBrush(QColor("#8FD4A8"))
    p.drawEllipse(QPointF(220, 280), 80, 90)
    p.setBrush(QColor("#8B5E3C"))
    p.drawRect(QRectF(205, 360, 30, 70))
    n = min(len(ASSESS_FIX), int(t / 0.7) + 1)
    heat = t > 5.6
    if heat:
        for x, y, d in ASSESS_FIX:
            for k in range(6, 0, -1):
                c = QColor(255, int(80 + 30 * k), 40, int(26 * d))
                p.setBrush(c)
                p.drawEllipse(QPointF(x, y), 16 * k * d, 16 * k * d)
    else:
        p.setPen(QPen(QColor(46, 204, 113, 200), 3))
        for a, b in zip(ASSESS_FIX[:n], ASSESS_FIX[1:n]):
            p.drawLine(QPointF(a[0], a[1]), QPointF(b[0], b[1]))
        for i, (x, y, d) in enumerate(ASSESS_FIX[:n]):
            r = 14 + d * 16
            p.setPen(QPen(QColor("#1E8E4E"), 2))
            p.setBrush(QColor(46, 204, 113, 150))
            p.drawEllipse(QPointF(x, y), r, r)
            p.setFont(_font(16))
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignCenter, str(i + 1))
    p.setFont(_font(22))
    p.setPen(QColor("#5B4E8C"))
    p.drawText(QRectF(0, 500, 1000, 40), Qt.AlignCenter, "熱點圖：越紅看越久" if heat else "注視軌跡：數字是看的順序，圓越大看越久")
    return 9.0


SCENES = {"welcome": scene_welcome, "move": scene_move, "click": scene_click, "toolbar": scene_toolbar,
          "drag": scene_drag, "scroll": scene_scroll, "pause": scene_pause, "calib": scene_calib,
          "assess": scene_assess}
DURATION = {"welcome": 6.0, "move": 7.0, "click": 6.0, "toolbar": 7.0, "drag": 8.0, "scroll": 8.6,
            "pause": 7.4, "calib": 9.0, "assess": 9.0}


class TutorialWindow(QWidget):
    """教學視窗：上方動畫、下方字幕、大按鈕（可用眼動鼠停留點擊）。"""

    def __init__(self, ctl, start=0):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.ctl = ctl
        self.setWindowTitle("眼動鼠 動畫教學")
        self.setWindowIcon(art.app_icon())
        self.page = start
        self.t0 = time.monotonic()
        self.spin = 0
        self.buttons = {}
        self.stars = []
        self.hits = 0
        self.pressed_key = None
        g = ctl.screen().availableGeometry()
        tbw = ctl.toolbar.width() if ctl.toolbar.isVisible() else 0
        w = min(1180, g.width() - tbw - 40)
        h = min(860, g.height() - 30)
        self.resize(w, h)
        x = g.left() + (g.width() - tbw - w) // 2 if ctl.s.toolbar_side == "right" else g.left() + tbw + (g.width() - tbw - w) // 2
        self.move(x, g.top() + (g.height() - h) // 2)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)
        self.setMouseTracking(True)

    def showEvent(self, e):
        super().showEvent(e)
        self.go(self.page)

    def go(self, i):
        self.page = max(0, min(len(TUTORIAL) - 1, i))
        self.t0 = time.monotonic()
        key = TUTORIAL[self.page][0]
        if key == "practice":
            self._new_stars()
        self.ctl.audio.say(f"tut_{key}", force=True)
        self.update()

    def _new_stars(self):
        self.hits = 0
        random.seed(7)
        self.stars = []
        for _ in range(3):
            self.stars.append([random.uniform(0.15, 0.85), random.uniform(0.2, 0.8), False, 0.0])

    def _tick(self):
        self.spin = (self.spin + 4) % 360
        self.update()

    def closeEvent(self, e):
        self.ctl.audio.stop_voice()
        self.timer.stop()
        if not self.ctl.s.tutorial_done:
            self.ctl.s.tutorial_done = True
            self.ctl.s.save()
        super().closeEvent(e)

    def mousePressEvent(self, e):
        pos = e.position()
        for k, r in self.buttons.items():
            if r.contains(pos):
                self.pressed_key = k
                QTimer.singleShot(160, lambda: setattr(self, "pressed_key", None))
                if k == "prev":
                    self.go(self.page - 1)
                elif k == "next":
                    if self.page == len(TUTORIAL) - 1:
                        self.close()
                    else:
                        self.go(self.page + 1)
                elif k == "replay":
                    self.go(self.page)
                elif k == "close":
                    self.close()
                return
        if TUTORIAL[self.page][0] == "practice":
            area = self._anim_rect()
            for s in self.stars:
                if s[2]:
                    continue
                c = QPointF(area.left() + s[0] * area.width(), area.top() + s[1] * area.height())
                if math.hypot(pos.x() - c.x(), pos.y() - c.y()) < 60:
                    s[2] = True
                    s[3] = time.monotonic()
                    self.hits += 1
                    self.ctl.audio.sfx("double")
                    self.ctl.audio.say("practice_done" if self.hits == len(self.stars) else "practice_hit", force=True)
                    return

    def _anim_rect(self):
        w, h = self.width(), self.height()
        bottom = h * 0.62
        aw = min(w - 40, (bottom - 70) * 1000 / 560)
        ah = aw * 560 / 1000
        return QRectF((w - aw) / 2, 64, aw, ah)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor("#F7F5FF"))
        key, title, text = TUTORIAL[self.page]
        p.setFont(_font(28))
        p.setPen(QColor("#5B4E8C"))
        p.drawText(QRectF(20, 10, w - 40, 50), Qt.AlignVCenter | Qt.AlignLeft, f"{self.page + 1}. {title}")
        p.setFont(_font(16, False))
        p.setPen(QColor("#8A86A8"))
        p.drawText(QRectF(20, 10, w - 40, 50), Qt.AlignVCenter | Qt.AlignRight, f"{self.page + 1} / {len(TUTORIAL)}")
        area = self._anim_rect()
        t = time.monotonic() - self.t0
        if key == "practice":
            self._paint_practice(p, area, t)
        else:
            p.save()
            p.translate(area.topLeft())
            p.scale(area.width() / 1000, area.height() / 560)
            SCENES[key](p, t % DURATION[key], self.spin)
            p.restore()
        # 字幕
        sub = QRectF(30, area.bottom() + 12, w - 60, h - area.bottom() - 12 - 150)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(sub, 16, 16)
        p.setFont(_font(max(17, min(24, h * 0.026)), False))
        p.setPen(QColor("#2E2A47"))
        p.drawText(sub.adjusted(18, 10, -18, -10), Qt.AlignVCenter | Qt.TextWordWrap, text)
        # 按鈕
        last = self.page == len(TUTORIAL) - 1
        defs = [("prev", "上一頁", "#8A86A8"), ("replay", "重播", "#FF9F43"),
                ("next", "完成" if last else "下一頁", "#4FA3FF"), ("close", "關閉", "#E8676B")]
        if self.page == 0:
            defs = defs[1:]
        bw = min(220, (w - 60 - (len(defs) - 1) * 24) / len(defs))
        bh = 110
        x = (w - (len(defs) * bw + (len(defs) - 1) * 24)) / 2
        self.buttons = {}
        for k, label, col in defs:
            r = QRectF(x, h - bh - 24, bw, bh)
            self.buttons[k] = r
            button(p, r, label, col, self.pressed_key == k)
            x += bw + 24

    def _paint_practice(self, p, area, t):
        p.setPen(QPen(QColor("#7D72B8"), 4))
        g = QLinearGradient(area.topLeft(), area.bottomLeft())
        g.setColorAt(0, QColor("#FFF3D6"))
        g.setColorAt(1, QColor("#FFE0EC"))
        p.setBrush(g)
        p.drawRoundedRect(area, 24, 24)
        for sx, sy, hit, ht in self.stars:
            c = QPointF(area.left() + sx * area.width(), area.top() + sy * area.height())
            if hit:
                k = min(1.0, (time.monotonic() - ht) / 0.6)
                if k < 1:
                    p.setPen(QPen(QColor(255, 200, 60, int(255 * (1 - k))), 4))
                    p.setBrush(Qt.NoBrush)
                    p.drawEllipse(c, 40 + k * 60, 40 + k * 60)
                continue
            s = 46 + 4 * math.sin(t * 4)
            path = QPainterPath()
            for i in range(10):
                a = -math.pi / 2 + i * math.pi / 5
                rr = s if i % 2 == 0 else s * 0.45
                pt = QPointF(c.x() + rr * math.cos(a), c.y() + rr * math.sin(a))
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            path.closeSubpath()
            p.setPen(QPen(QColor("#E0A100"), 3))
            p.setBrush(QColor("#FFD36E"))
            p.drawPath(path)
        p.setFont(_font(26))
        p.setPen(QColor("#5B4E8C"))
        msg = "全部完成！你好棒 🎉" if self.hits == len(self.stars) else f"盯著星星把它點掉：{self.hits} / {len(self.stars)}"
        p.drawText(QRectF(area.left(), area.bottom() - 60, area.width(), 50), Qt.AlignCenter, msg)
        if self.hits == len(self.stars):
            art.draw_mouse(p, area.center(), 70, happy=True)
