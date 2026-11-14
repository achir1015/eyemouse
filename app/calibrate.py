"""校正：小老鼠依序跑到 9 個點，使用者盯著看，收集特徵後做回歸。"""
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import art
from .gaze import Mapper
from .overlay import _font

POINTS = [(0.5, 0.5), (0.1, 0.1), (0.5, 0.1), (0.9, 0.1), (0.9, 0.5), (0.9, 0.9), (0.5, 0.9), (0.1, 0.9), (0.1, 0.5)]
MOVE_S, SETTLE_S, COLLECT_S = 0.7, 0.55, 1.1


class CalibrationWindow(QWidget):
    finished = Signal(bool)

    def __init__(self, ctl):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.ctl = ctl
        self.src = ctl.source
        g = ctl.screen().geometry()
        self.setGeometry(g)
        self.geo = (g.x(), g.y(), g.width(), g.height())
        self.samples = []
        self.idx = -1
        self.phase = "intro"
        self.t0 = time.monotonic()
        self.pos = QPointF(g.width() / 2, g.height() / 2)
        self.result = None
        self.err = None
        self.spin = 0
        self.buttons = {}
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.timer.start(16)
        self.setCursor(Qt.BlankCursor)

    def start(self):
        self.ctl.zoom_off = True
        self.ctl.capture_only = True
        self.ctl.toolbar.hide()
        self.show()
        self.raise_()
        self.activateWindow()
        if hasattr(self.src, "recenter"):
            self.src.recenter()
        self.ctl.audio.say("calib_intro")

    def target(self, i):
        fx, fy = POINTS[i]
        return QPointF(fx * self.width(), fy * self.height())

    def step(self):
        now = time.monotonic()
        el = now - self.t0
        self.spin = (self.spin + 5) % 360
        if self.phase == "intro":
            if el > 3.2:
                self.phase, self.idx, self.t0 = "move", 0, now
                self._from = QPointF(self.pos)
        elif self.phase == "move":
            k = min(1.0, el / MOVE_S)
            k = 1 - (1 - k) ** 3
            tgt = self.target(self.idx)
            self.pos = self._from + (tgt - self._from) * k
            if el >= MOVE_S:
                self.phase, self.t0 = "settle", now
        elif self.phase == "settle":
            if el >= SETTLE_S:
                self.phase, self.t0 = "collect", now
                self._last_t = 0
        elif self.phase == "collect":
            smp = self.src.latest()
            if smp and smp[0] != self._last_t and now - smp[0] < 0.2:
                self._last_t = smp[0]
                tgt = self.target(self.idx)
                self.samples.append((smp[1], (self.geo[0] + tgt.x(), self.geo[1] + tgt.y())))
            if el >= COLLECT_S:
                self.ctl.audio.sfx("select")
                self.idx += 1
                if self.idx >= len(POINTS):
                    self._finish()
                else:
                    self.phase, self.t0 = "move", now
                    self._from = QPointF(self.pos)
        self.update()

    def _finish(self):
        import logging
        self.phase = "done"
        per = [sum(1 for _, t in self.samples if t == (self.geo[0] + self.target(i).x(), self.geo[1] + self.target(i).y()))
               for i in range(len(POINTS))]
        logging.info("校正：來源=%s 狀態=%s 每點樣本=%s", self.src.key, self.src.status, per)
        self.ctl.capture_only = False
        self.setCursor(Qt.ArrowCursor)
        n_pts = len({tuple(t) for _, t in self.samples})
        if len(self.samples) < 30 or n_pts < 6:
            self.result = None
            self.msg = (f"收集到的視線資料太少（每點 {per}），請確認眼動儀／攝影機看得到您的眼睛後再試一次。"
                        f"\n來源狀態：{self.src.status}")
            self.ctl.audio.say("calib_fail")
        else:
            try:
                self.result, self.err = Mapper.fit(self.src, self.samples, self.geo)
            except Exception as e:  # noqa: BLE001 — 資料退化（視線都在同一點）
                logging.warning("校正計算失敗：%s", e)
                self.result = None
                self.msg = "視線資料看起來都停在同一個地方，請跟著小老鼠移動視線後重做。"
                self.ctl.audio.say("calib_fail")
                return
            q = "很好" if self.err < 60 else ("普通" if self.err < 130 else "偏差較大，建議重做")
            self.msg = f"校正完成！平均誤差約 {self.err:.0f} 像素（{q}）。"
            logging.info("校正完成 誤差=%.0f", self.err)
            self.ctl.audio.say("calib_done")

    # ---- 結束按鈕：可用視線停留（此時已恢復點擊）或滑鼠點 ----
    def mousePressEvent(self, e):
        if self.phase != "done":
            return
        for k, r in self.buttons.items():
            if r.contains(e.position()):
                self._choose(k)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._choose("cancel")

    def _choose(self, k):
        if k == "redo":
            self.samples.clear()
            self.idx, self.phase, self.t0 = -1, "intro", time.monotonic()
            self.ctl.capture_only = True
            self.setCursor(Qt.BlankCursor)
            if hasattr(self.src, "recenter"):
                self.src.recenter()
            self.ctl.audio.say("calib_intro")
            return
        ok = False
        if k == "apply" and self.result:
            self.ctl.s.calib[self.src.key] = self.result
            self.ctl.s.save()
            self.ctl.reload_calibration()
            ok = True
        self.ctl.capture_only = False
        self.ctl.toolbar.show()
        self.timer.stop()
        self.close()
        self.finished.emit(ok)

    def closeEvent(self, e):
        self.ctl.zoom_off = False
        self.ctl.capture_only = False
        self.ctl.toolbar.show()
        super().closeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor("#2D2852"))
        bg.setColorAt(1, QColor("#1B1836"))
        p.fillRect(self.rect(), bg)
        p.setPen(QColor("#CFC8FF"))
        p.setFont(_font(max(18, h * 0.026)))
        if self.phase == "intro":
            p.drawText(QRectF(0, h * 0.18, w, 120), Qt.AlignCenter,
                       "校正開始：請盯著小老鼠，跟著牠移動\n頭盡量不要動喔！")
        elif self.phase != "done":
            p.drawText(QRectF(0, 20, w, 60), Qt.AlignCenter, f"請看著小老鼠　{self.idx + 1} / {len(POINTS)}")
        # 已完成的點
        for i in range(max(0, self.idx)):
            if i < len(POINTS):
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(143, 200, 255, 120))
                p.drawEllipse(self.target(i), 6, 6)
        if self.phase != "done":
            R = min(w, h) * 0.06
            prog = 0.0
            if self.phase == "collect":
                prog = min(1.0, (time.monotonic() - self.t0) / COLLECT_S)
            elif self.phase == "settle":
                R *= 1 + 0.6 * (1 - (time.monotonic() - self.t0) / SETTLE_S)
            art.draw_ring(p, self.pos, R, self.spin, prog, "#FF8FB8", width=R * 0.14)
            art.draw_mouse(p, self.pos, R * 0.55, look=(0, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawEllipse(self.pos, 3, 3)
            return
        p.setFont(_font(max(20, h * 0.03)))
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(w * 0.1, h * 0.2, w * 0.8, h * 0.15), Qt.AlignCenter | Qt.TextWordWrap, self.msg)
        art.draw_mouse(p, QPointF(w / 2, h * 0.42), min(w, h) * 0.06, happy=bool(self.result))
        bw, bh = min(260, w * 0.22), min(150, h * 0.16)
        keys = [("apply", "套用", "#4FA3FF"), ("redo", "重做", "#FF9F43"), ("cancel", "取消", "#8A86A8")]
        if not self.result:
            keys = keys[1:]
        total = len(keys) * bw + (len(keys) - 1) * 40
        x = (w - total) / 2
        self.buttons = {}
        for k, label, col in keys:
            r = QRectF(x, h * 0.58, bw, bh)
            self.buttons[k] = r
            p.setPen(QPen(QColor("#FFFFFF"), 3))
            p.setBrush(QColor(col))
            p.drawRoundedRect(r, 28, 28)
            p.setFont(_font(bh * 0.3))
            p.drawText(r, Qt.AlignCenter, label)
            x += bw + 40
        p.setFont(_font(16, False))
        p.setPen(QColor("#CFC8FF"))
        p.drawText(QRectF(0, h * 0.82, w, 40), Qt.AlignCenter, "用視線停留在按鈕上，或用滑鼠點選")
