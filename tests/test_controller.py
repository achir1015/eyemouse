"""控制邏輯整合測試：假視線＋假滑鼠，驗證點擊、工具列、右鍵、拖曳、捲動、暫停。

python -m pytest tests -q   或   python tests/test_controller.py
"""
import os
import sys
import tempfile

os.environ["EYEMOUSE_DATA_DIR"] = tempfile.mkdtemp(prefix="eyemouse_t_")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])

from app import controller as C  # noqa: E402
from app.audio import Audio  # noqa: E402
from app.config import Settings  # noqa: E402
from app.gaze.base import GazeSource  # noqa: E402


class Clock:
    t = 1000.0

    def __call__(self):
        return self.t


class FakeSource(GazeSource):
    key = "fake"

    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.pt = (500.0, 400.0)
        self.ok = True
        self.status = "fake"

    def latest(self):
        return (self.clock(), self.pt) if self.pt else None

    def default_map(self, feat, geo):
        return feat


class FakeMouse:
    def __init__(self):
        self.log = []
        self.p = (0, 0)
        self.left_held = False

    def pos(self):
        return self.p

    def move(self, x, y):
        self.p = (int(round(x)), int(round(y)))

    def click(self, x, y, b="l", count=1):
        self.log.append(("click", b, count, round(x), round(y)))

    def press_left(self, x, y):
        self.left_held = True
        self.log.append(("down", round(x), round(y)))

    def release_left(self, x, y):
        self.left_held = False
        self.log.append(("up", round(x), round(y)))

    def scroll(self, s):
        self.log.append(("scroll", s))

    def safe_release(self):
        self.left_held = False


def make(zoom=False):
    clock = Clock()
    C.time.monotonic = clock
    s = Settings()
    s.dwell_ms, s.radius, s.cooldown_ms, s.smoothing = 800, 50, 600, 30
    s.voice = s.sound = False
    s.zoom_click = zoom
    ctl = C.Controller(s, Audio())
    ctl.zoom_delay_ms = 0
    src = FakeSource(clock)
    ctl.source, ctl.source_key, ctl.mapper = src, "fake", None
    ctl.mouse = FakeMouse()
    ctl.toolbar.dock(ctl.screen().availableGeometry(), "right")
    ctl.toolbar.show()
    return ctl, src, clock


def run(ctl, clock, secs):
    for _ in range(int(secs / 0.016)):
        clock.t += 0.016
        ctl.tick()


def look(ctl, src, clock, x, y, secs):
    src.pt = (float(x), float(y))
    run(ctl, clock, secs)


def tb_center(ctl, key):
    from app.overlay import BUTTONS
    i = [k for k, _ in BUTTONS].index(key)
    r = ctl.toolbar.button_rect(i)
    return ctl.toolbar.x() + r.center().x(), ctl.toolbar.y() + r.center().y()


def test_left_click_once():
    ctl, src, clock = make()
    look(ctl, src, clock, 400, 300, 0.5)
    assert not ctl.mouse.log
    look(ctl, src, clock, 400, 300, 0.6)
    clicks = [e for e in ctl.mouse.log if e[0] == "click"]
    assert len(clicks) == 1 and clicks[0][1] == "l", ctl.mouse.log
    # 一直盯著：冷卻後才可能再點，不會連發
    look(ctl, src, clock, 400, 300, 0.4)
    assert len([e for e in ctl.mouse.log if e[0] == "click"]) == 1


def test_moving_eyes_no_click():
    ctl, src, clock = make()
    for i in range(60):
        look(ctl, src, clock, 200 + i * 15, 300, 0.05)
    assert not ctl.mouse.log


def test_toolbar_right_click_then_back_to_left():
    ctl, src, clock = make()
    x, y = tb_center(ctl, "right")
    look(ctl, src, clock, x, y, 1.2)
    assert ctl.mode == "right"
    look(ctl, src, clock, 300, 300, 1.5)
    rc = [e for e in ctl.mouse.log if e[:3] == ("click", "r", 1)]
    assert rc and abs(rc[0][3] - 300) < 5 and abs(rc[0][4] - 300) < 5, ctl.mouse.log
    assert ctl.mode == "left"


def test_double():
    ctl, src, clock = make()
    look(ctl, src, clock, *tb_center(ctl, "double"), 1.2)
    look(ctl, src, clock, 320, 260, 1.5)
    assert any(e[0] == "click" and e[2] == 2 for e in ctl.mouse.log)


def test_drag():
    ctl, src, clock = make()
    look(ctl, src, clock, *tb_center(ctl, "drag"), 1.2)
    assert ctl.mode == "drag"
    look(ctl, src, clock, 200, 200, 1.2)
    assert ctl.drag_held and ctl.mouse.log[-1][0] == "down"
    look(ctl, src, clock, 600, 450, 1.6)
    assert ctl.mouse.log[-1][0] == "up", ctl.mouse.log
    assert abs(ctl.mouse.log[-1][1] - 600) < 15
    assert ctl.mode == "left"


def test_scroll():
    ctl, src, clock = make()
    look(ctl, src, clock, *tb_center(ctl, "scroll"), 1.2)
    look(ctl, src, clock, 400, 400, 1.2)
    assert ctl.scrolling
    look(ctl, src, clock, 400, 650, 1.0)   # 往下看
    downs = sum(e[1] for e in ctl.mouse.log if e[0] == "scroll")
    assert downs < 0, ctl.mouse.log
    look(ctl, src, clock, 400, 400, 1.5)   # 回中間 → 結束
    assert not ctl.scrolling and ctl.mode == "left"


def test_pause_blocks_clicks():
    ctl, src, clock = make()
    look(ctl, src, clock, *tb_center(ctl, "pause"), 1.2)
    assert ctl.paused
    look(ctl, src, clock, 300, 300, 3)
    assert not [e for e in ctl.mouse.log if e[0] == "click"]
    look(ctl, src, clock, *tb_center(ctl, "pause"), 1.2)
    assert not ctl.paused


def test_manual_mouse_yields():
    ctl, src, clock = make()
    look(ctl, src, clock, 300, 300, 0.3)
    ctl.mouse.p = (900, 100)               # 照顧者動了滑鼠
    look(ctl, src, clock, 300, 300, 1.2)
    assert not [e for e in ctl.mouse.log if e[0] == "click"]


def test_zoom_precise_click():
    ctl, src, clock = make(zoom=True)
    look(ctl, src, clock, 600, 400, 1.2)
    assert ctl.zoom is not None and not ctl.mouse.log, "第一次停留應只開放大鏡"
    zw = ctl.zoom_win
    assert zw.isVisible()
    # 放大視窗中心 = 原本 region 中心；往右下 50 放大像素 → 原畫面 +20
    cx = zw.x() + zw.width() / 2 + 50
    cy = zw.y() + zw.height() / 2 + 50
    exp = zw.to_screen(cx, cy)
    look(ctl, src, clock, cx, cy, 1.5)
    clicks = [e for e in ctl.mouse.log if e[0] == "click"]
    assert len(clicks) == 1, ctl.mouse.log
    assert abs(clicks[0][3] - exp[0]) < 4 and abs(clicks[0][4] - exp[1]) < 4, (clicks, exp)
    assert ctl.zoom is None and not zw.isVisible()


def test_zoom_cancel_by_looking_away():
    ctl, src, clock = make(zoom=True)
    look(ctl, src, clock, 600, 400, 1.2)
    zw = ctl.zoom_win
    # 看放大視窗外面停留 → 取消、不點擊
    away = (zw.x() - 120, zw.y() + 10) if zw.x() > 200 else (zw.x() + zw.width() + 120, zw.y() + 10)
    look(ctl, src, clock, *away, 1.5)
    assert ctl.zoom is None and not ctl.mouse.log


def test_gaze_keyboard_types_and_avoids_zoom():
    ctl, src, clock = make(zoom=True)
    sent = []
    ctl.kb.sender = sent.append
    ctl.s.kb_dwell_ms = 600
    ctl.kb_dwell.dwell_s = 0.6
    ctl.open_keyboard()
    assert ctl.kb.isVisible()
    r, _, _ = ctl.kb._rects["1"]
    look(ctl, src, clock, ctl.kb.x() + r.center().x(), ctl.kb.y() + r.center().y(), 0.8)
    assert sent == ["1"], sent                       # 看著「ㄅ／1」停留 → 送出 1 鍵，不開放大鏡
    assert ctl.zoom is None and not ctl.mouse.log
    look(ctl, src, clock, ctl.kb.x() + r.center().x(), ctl.kb.y() + r.center().y(), 1.4)
    assert sent.count("1") == 2                      # 冷卻後繼續盯著可以再輸入
    # 鍵盤上方開放大鏡：放大鏡不能蓋到鍵盤
    look(ctl, src, clock, 500, ctl.kb.y() - 60, 1.2)
    assert ctl.zoom is not None
    assert ctl.zoom_win.geometry().bottom() < ctl.kb.geometry().top()
    ctl.close_zoom()
    h, _, _ = ctl.kb._rects["hide"]
    look(ctl, src, clock, ctl.kb.x() + h.center().x(), ctl.kb.y() + h.center().y(), 0.8)
    assert not ctl.kb.isVisible()


if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            n += 1
            print("ok", k)
    print(f"{n} passed")
