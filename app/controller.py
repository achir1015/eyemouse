"""眼動鼠主控制：讀視線 → 濾波 → 游標 → 停留判定 → 執行滑鼠動作。"""
import math
import os
import subprocess
import sys
import time

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from .actions import Mouse
from .dwell import Dwell, PointFilter
from .gaze import Mapper, create_source
from .overlay import CursorOverlay, ScrollGuide, Toolbar

ONE_SHOT = ("double", "right")
MODE_NAMES = {"left": "左鍵點一下", "double": "連按兩下", "right": "右鍵", "drag": "拖曳", "scroll": "捲動"}


class Controller(QObject):
    status_changed = Signal(str)
    menu_requested = Signal()
    gaze_sample = Signal(float, float, float)   # t, x, y（眼動評估錄製用）

    def __init__(self, settings, audio):
        super().__init__()
        self.s = settings
        self.audio = audio
        self.mouse = Mouse()
        self.source = None
        self.mapper = None
        self.source_key = None
        self.mode = "left"
        self.paused = False
        self.drag_held = False
        self.scrolling = None          # 捲動錨點
        self.manual_until = 0.0
        self.last_set = None
        self.last_pt = None
        self.capture_only = False      # 校正/評估時：只追蹤不點擊
        self.suspended = False         # 完全停用（評估全螢幕播放時）
        self._prev = None
        self._blink_t = time.monotonic() + 3
        self._happy_until = 0
        self._last_status = ""
        self.lost_since = None

        self.filter = PointFilter(settings.smoothing)
        self.dwell = Dwell(settings.dwell_ms / 1000, settings.radius, settings.cooldown_ms / 1000)
        self.tb_dwell = Dwell(max(0.5, settings.dwell_ms / 1000 * 0.9), 10_000, 0.9)
        self.tb_key = None

        self.overlay = CursorOverlay(settings.cursor_size)
        self.guide = ScrollGuide()
        self.toolbar = Toolbar(settings.toolbar_button)
        self.toolbar.picked.connect(self.pick)

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    # ------------------------------------------------------------ 設定
    def screen(self):
        scr = QGuiApplication.screens()
        if 0 < self.s.screen_index < len(scr):
            return scr[self.s.screen_index]
        return QGuiApplication.primaryScreen()

    def geo(self):
        g: QRect = self.screen().geometry()
        return (g.x(), g.y(), g.width(), g.height())

    def apply_settings(self):
        s = self.s
        self.filter.set_smoothing(s.smoothing)
        self.dwell.dwell_s = s.dwell_ms / 1000
        self.dwell.radius = s.radius
        self.dwell.cooldown_s = s.cooldown_ms / 1000
        self.tb_dwell.dwell_s = max(0.5, s.dwell_ms / 1000 * 0.9)
        self.overlay.set_size(s.cursor_size)
        self.toolbar.set_button(s.toolbar_button)
        self.toolbar.dock(self.screen().availableGeometry(), s.toolbar_side)
        self.audio.enabled = s.sound
        self.audio.voice_enabled = s.voice
        if self.source and hasattr(self.source, "head_gain"):
            self.source.head_gain = s.head_gain
        if s.source != self.source_key:
            self.start_source(s.source)
        self.reload_calibration()

    def start_source(self, key):
        if self.source:
            self.source.stop()
        self.source = create_source(key, self.s)
        self.source_key = key
        self.source.start()
        self.reload_calibration()
        self.filter.reset()
        self.dwell.reset()

    def reload_calibration(self):
        if self.source:
            self.mapper = Mapper(self.source, self.s.calib.get(self.source.key))

    def start(self):
        from .actions import mac_accessibility_ok
        self.ax_ok = mac_accessibility_ok(prompt=True)
        if not self.ax_ok:
            self._ax_timer = QTimer(self)
            self._ax_timer.timeout.connect(lambda: setattr(self, "ax_ok", mac_accessibility_ok()))
            self._ax_timer.start(3000)
        self.start_source(self.s.source)
        self.apply_settings()
        self.toolbar.show()
        self.overlay.show()
        self.timer.start()

    def shutdown(self):
        self.timer.stop()
        self.mouse.safe_release()
        if self.source:
            self.source.stop()
        for w in (self.overlay, self.guide, self.toolbar):
            w.close()

    # ------------------------------------------------------------ 狀態
    def status_text(self):
        if not self.source:
            return "未啟動"
        parts = [self.source.status]
        if sys.platform == "darwin" and not getattr(self, "ax_ok", True):
            parts.append("⚠ 請到「系統設定 › 隱私權與安全性 › 輔助使用」允許眼動鼠，才能點擊")
        if self.mapper and self.mapper.calibrated:
            parts.append("已校正")
        elif self.source.key in ("webcam",):
            parts.append("尚未校正（建議校正）")
        if self.paused:
            parts.append("暫停中")
        return "｜".join(parts)

    def set_mode(self, mode, announce=True):
        if self.drag_held and mode != "drag":
            x, y = self.mouse.pos()
            self.mouse.release_left(x, y)
            self.drag_held = False
        if self.scrolling and mode != "scroll":
            self.stop_scroll()
        self.mode = mode
        self.toolbar.mode = mode
        self.overlay.mode = mode
        self.toolbar.update()
        if announce:
            self.audio.sfx("select")
            self.audio.say(f"mode_{mode}")

    def toggle_pause(self, value=None):
        self.paused = (not self.paused) if value is None else value
        self.toolbar.paused = self.paused
        self.toolbar.update()
        self.mouse.safe_release()
        self.drag_held = False
        self.stop_scroll()
        self.audio.sfx("pause" if self.paused else "resume")
        self.audio.say("paused" if self.paused else "resumed")

    def pick(self, key):
        """工具列按鈕被選取（視線停留或滑鼠點）。"""
        self.toolbar.flash = key
        QTimer.singleShot(250, self._clear_flash)
        if key in MODE_NAMES:
            if self.paused:
                self.toggle_pause(False)
            self.set_mode(key)
        elif key == "pause":
            self.toggle_pause()
        elif key == "keyboard":
            self.open_keyboard()
        elif key == "menu":
            self.audio.sfx("select")
            self.menu_requested.emit()

    def _clear_flash(self):
        self.toolbar.flash = None
        self.toolbar.update()

    def open_keyboard(self):
        self.audio.sfx("select")
        self.audio.say("keyboard")
        try:
            if sys.platform == "win32":
                os.startfile("osk.exe")
            elif sys.platform == "darwin":
                # 系統設定 › 輔助使用 › 鍵盤 › 開啟「輔助使用鍵盤」
                subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.universalaccess?Keyboard"])
        except OSError:
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["explorer.exe", r"C:\Windows\System32\osk.exe"])
            except OSError:
                pass

    def stop_scroll(self):
        self.scrolling = None
        self.overlay.scroll_dir = 0
        self.guide.hide()

    # ------------------------------------------------------------ 主迴圈
    def tick(self):
        now = time.monotonic()
        ov = self.overlay
        ov.spin = (ov.spin + 4.0) % 360
        # 眨眼動畫
        if now > self._blink_t:
            ph = (now - self._blink_t) / 0.18
            ov.blink = max(0.0, 1 - abs(ph * 2 - 1)) if ph < 1 else 0.0
            if ph >= 1:
                self._blink_t = now + 2.5 + (hash(int(now)) % 30) / 10
        ov.happy = 1 if now < self._happy_until else 0

        st = self.status_text()
        if st != self._last_status:
            self._last_status = st
            self.status_changed.emit(st)

        if self.suspended or not self.source:
            if ov.isVisible():
                ov.hide()
            return

        smp = self.source.latest()
        g = self.geo()
        pt = None
        if smp and now - smp[0] < 0.3:
            x, y = self.mapper.map(smp[1], g) if self.mapper else self.source.default_map(smp[1], g)
            # 限制在螢幕內
            x = min(max(x, g[0]), g[0] + g[2] - 1)
            y = min(max(y, g[1]), g[1] + g[3] - 1)
            pt = self.filter(now, x, y)
            self.lost_since = None
        else:
            if self.lost_since is None:
                self.lost_since = now
            if now - self.lost_since > 0.5:
                self.filter.reset()

        if pt is None:
            ov.label = "找不到視線" if self.source.key != "mouse" else ""
            ov.progress = 0
            ov.dim = True
            if self.last_pt:
                ov.place(*self.last_pt)
            ov.update()
            self.dwell.feed(now, None, None)
            return

        self.gaze_sample.emit(now, pt[0], pt[1])
        # 小老鼠眼睛看移動方向
        if self.last_pt:
            dx, dy = pt[0] - self.last_pt[0], pt[1] - self.last_pt[1]
            lx, ly = ov.look
            ov.look = (lx * 0.85 + max(-1, min(1, dx / 25)) * 0.15, ly * 0.85 + max(-1, min(1, dy / 25)) * 0.15)
        self.last_pt = pt
        ov.place(*pt)
        if not ov.isVisible() and not self.capture_only:
            ov.show()

        if self.capture_only:
            ov.progress = 0
            if ov.isVisible():
                ov.hide()
            return

        # 偵測照顧者動了實體滑鼠 → 暫時讓手
        is_mouse_src = self.source.key == "mouse"
        if self.s.move_cursor and not is_mouse_src and self.last_set is not None:
            cx, cy = self.mouse.pos()
            if math.hypot(cx - self.last_set[0], cy - self.last_set[1]) > 6:
                self.manual_until = now + self.s.manual_pause_ms / 1000
                self.last_set = None
        manual = now < self.manual_until

        # ---- 工具列 ----
        key = self.toolbar.button_at_global(*pt)
        if key:
            self.dwell.reset()
            ov.progress = 0
            ov.label = ""
            ov.dim = False
            if key == "_bar":
                self.tb_key = None
                self.toolbar.hover = None
                self.toolbar.progress = 0
            else:
                if key != self.tb_key:
                    self.tb_key = key
                    self.tb_dwell.reset()
                prog, fired, _ = self.tb_dwell.feed(now, pt[0], pt[1])
                self.toolbar.hover = key
                self.toolbar.progress = prog
                if fired:
                    self.toolbar.progress = 0
                    self._happy_until = now + 0.6
                    self.pick(key)
            self.toolbar.update()
            ov.update()
            if self.s.move_cursor and not manual and not is_mouse_src and not self.drag_held:
                self._move(pt)
            return
        if self.toolbar.hover:
            self.toolbar.hover = None
            self.toolbar.progress = 0
            self.toolbar.update()
            self.tb_key = None

        ov.dim = self.paused or manual
        ov.label = "暫停中" if self.paused else ("手動滑鼠中" if manual else "")
        if self.paused or manual:
            ov.progress = 0
            self.dwell.reset()
            ov.update()
            return

        # ---- 捲動模式 ----
        if self.scrolling:
            ax, ay = self.scrolling
            dead = max(60, self.s.radius * 1.4)
            dy = pt[1] - ay
            if abs(dy) > dead and abs(pt[0] - ax) < 260:
                speed = (abs(dy) - dead) / 120 * self.s.scroll_speed / 5
                self._scroll_acc = getattr(self, "_scroll_acc", 0.0) + speed * (-1 if dy < 0 else 1) * -1
                steps = int(self._scroll_acc)
                if steps:
                    self._scroll_acc -= steps
                    self.mouse.scroll(steps)
                ov.scroll_dir = -1 if dy < 0 else 1
                ov.progress = 0
                self.dwell.reset()
            else:
                ov.scroll_dir = 0
                prog, fired, _ = self.dwell.feed(now, pt[0], pt[1])
                ov.progress = prog
                if fired and math.hypot(fired[0] - ax, fired[1] - ay) < dead * 1.2:
                    self.stop_scroll()
                    self.set_mode("left")
            ov.update()
            return

        if (self.s.move_cursor or self.drag_held) and not is_mouse_src:
            self._move(pt)

        prog, fired, _ = self.dwell.feed(now, pt[0], pt[1])
        ov.progress = prog
        ov.held = self.drag_held
        if fired:
            self._happy_until = now + 0.6
            self.fire(fired)
        ov.update()

    def _move(self, pt):
        self.mouse.move(*pt)
        self.last_set = (int(round(pt[0])), int(round(pt[1])))

    def fire(self, pt):
        x, y = pt
        m = self.mode
        if m == "left":
            self.mouse.click(x, y, "l", 1)
            self.audio.sfx("click")
        elif m == "double":
            self.mouse.click(x, y, "l", 2)
            self.audio.sfx("double")
        elif m == "right":
            self.mouse.click(x, y, "r", 1)
            self.audio.sfx("right")
        elif m == "drag":
            if not self.drag_held:
                self.mouse.press_left(x, y)
                self.drag_held = True
                self.audio.sfx("press")
                self.audio.say("drag_hold")
                return
            self.mouse.release_left(x, y)
            self.drag_held = False
            self.audio.sfx("release")
        elif m == "scroll":
            self.mouse.move(x, y)
            self.scrolling = (x, y)
            self._scroll_acc = 0.0
            self.guide.place(x, y, max(60, self.s.radius * 1.4))
            self.guide.show()
            self.audio.sfx("select")
            return
        self.last_set = self.mouse.pos()
        if m in ONE_SHOT + ("drag",) and not self.s.sticky_modes:
            self.set_mode("left", announce=False)
