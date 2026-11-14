"""眼動鼠自己的眼控鍵盤：浮在螢幕下方、大小可調；看著按鍵停留就送出真正的按鍵。

送出的是實體鍵盤的按鍵（例如 1 鍵＝ㄅ），所以 Windows 注音輸入法照常組字、選字；
英文模式（輸入法切到英數）時同一顆鍵就是英文字母。視窗不會搶走焦點。
"""
import sys
import time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import art
from .overlay import _font

IS_WIN = sys.platform == "win32"

# (主標籤, 小標籤, 按鍵代號, 寬度)；代號：單一字元＝該鍵；其餘見 SPECIAL
ROWS = [
    [("ㄅ", "1", "1", 1), ("ㄉ", "2", "2", 1), ("ˇ", "3", "3", 1), ("ˋ", "4", "4", 1), ("ㄓ", "5", "5", 1),
     ("ˊ", "6", "6", 1), ("˙", "7", "7", 1), ("ㄚ", "8", "8", 1), ("ㄞ", "9", "9", 1), ("ㄢ", "0", "0", 1),
     ("ㄦ", "-", "-", 1), ("⌫", "刪除", "back", 1.5)],
    [("ㄆ", "Q", "q", 1), ("ㄊ", "W", "w", 1), ("ㄍ", "E", "e", 1), ("ㄐ", "R", "r", 1), ("ㄔ", "T", "t", 1),
     ("ㄗ", "Y", "y", 1), ("ㄧ", "U", "u", 1), ("ㄛ", "I", "i", 1), ("ㄟ", "O", "o", 1), ("ㄣ", "P", "p", 1),
     ("↵", "Enter", "enter", 2)],
    [("ㄇ", "A", "a", 1), ("ㄋ", "S", "s", 1), ("ㄎ", "D", "d", 1), ("ㄑ", "F", "f", 1), ("ㄕ", "G", "g", 1),
     ("ㄘ", "H", "h", 1), ("ㄨ", "J", "j", 1), ("ㄜ", "K", "k", 1), ("ㄠ", "L", "l", 1), ("ㄤ", ";", ";", 1),
     ("▲", "上", "up", 1), ("▼", "下", "down", 1)],
    [("ㄈ", "Z", "z", 1), ("ㄌ", "X", "x", 1), ("ㄏ", "C", "c", 1), ("ㄒ", "V", "v", 1), ("ㄖ", "B", "b", 1),
     ("ㄙ", "N", "n", 1), ("ㄩ", "M", "m", 1), ("ㄝ", ",", ",", 1), ("ㄡ", ".", ".", 1), ("ㄥ", "/", "/", 1),
     ("◀", "左", "left", 1), ("▶", "右", "right", 1)],
    [("中/英", "切換", "shift", 2), ("空白", "選字／空格", "space", 5.5), ("Esc", "取消", "esc", 1.5),
     ("收起", "鍵盤", "hide", 3)],
]

VK = {"back": 0x08, "enter": 0x0D, "shift": 0x10, "space": 0x20, "esc": 0x1B, "left": 0x25, "up": 0x26,
      "right": 0x27, "down": 0x28, "-": 0xBD, ";": 0xBA, ",": 0xBC, ".": 0xBE, "/": 0xBF}


def send_key(code):
    """送出一次按鍵（按下＋放開）。"""
    if IS_WIN:
        import ctypes
        from ctypes import wintypes

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        u32 = ctypes.windll.user32
        vk = VK.get(code) or ord(code.upper())
        scan = u32.MapVirtualKeyW(vk, 0)
        ext = 0x1 if code in ("left", "right", "up", "down") else 0
        for up in (0, 0x2):
            inp = INPUT(type=1)
            inp.u.ki = KEYBDINPUT(vk, scan, ext | up, 0, 0)
            u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            time.sleep(0.015)
        return
    try:
        from pynput.keyboard import Controller, Key
    except Exception:  # noqa: BLE001
        return
    k = Controller()
    special = {"back": Key.backspace, "enter": Key.enter, "shift": Key.shift, "space": Key.space, "esc": Key.esc,
               "left": Key.left, "right": Key.right, "up": Key.up, "down": Key.down}
    key = special.get(code, code)
    k.press(key)
    k.release(key)


class GazeKeyboard(QWidget):
    hidden_by_gaze = Signal()

    def __init__(self, sender=send_key):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.sender = sender
        self.hover = None
        self.progress = 0.0
        self.flash = None
        self.flash_t = 0.0
        self.pad = 10
        self.gap = 6
        self._rects = {}

    def showEvent(self, e):
        super().showEvent(e)
        if IS_WIN:  # 點鍵盤不會搶走打字視窗的焦點
            import ctypes
            hwnd = int(self.winId())
            u = ctypes.windll.user32
            st = u.GetWindowLongPtrW(hwnd, -20)
            u.SetWindowLongPtrW(hwnd, -20, st | 0x08000000 | 0x80)  # NOACTIVATE | TOOLWINDOW

    def place(self, avail, width_pct, avoid=None):
        """avail：可用螢幕範圍；avoid：工具列範圍（左右避開）。"""
        left, right = avail.left(), avail.right()
        if avoid is not None:
            if avoid.center().x() > avail.center().x():
                right = avoid.left() - 8
            else:
                left = avoid.right() + 8
        w = int((right - left) * max(0.3, min(1.0, width_pct / 100)))
        h = int(w * 0.36)
        x = left + (right - left - w) // 2
        y = avail.bottom() - h - 6
        self.setGeometry(x, y, w, h)
        self._layout()

    def _layout(self):
        self._rects = {}
        W, H = self.width() - 2 * self.pad, self.height() - 2 * self.pad
        rh = (H - self.gap * (len(ROWS) - 1)) / len(ROWS)
        units = max(sum(k[3] for k in row) for row in ROWS)
        uw = (W - self.gap * 11) / units
        for r, row in enumerate(ROWS):
            x = self.pad
            y = self.pad + r * (rh + self.gap)
            for main, sub, code, wd in row:
                w = uw * wd + self.gap * (wd - 1)
                self._rects[code] = (QRectF(x, y, w, rh), main, sub)
                x += w + self.gap

    def resizeEvent(self, e):
        self._layout()

    def key_at_global(self, gx, gy):
        if not self.isVisible():
            return None
        lx, ly = gx - self.x(), gy - self.y()
        if not (0 <= lx < self.width() and 0 <= ly < self.height()):
            return None
        for code, (r, _, _) in self._rects.items():
            if r.adjusted(-self.gap / 2, -self.gap / 2, self.gap / 2, self.gap / 2).contains(lx, ly):
                return code
        return "_bar"

    def contains_global(self, gx, gy):
        return self.isVisible() and self.geometry().contains(int(gx), int(gy))

    def press(self, code):
        self.flash, self.flash_t = code, time.monotonic()
        if code == "hide":
            self.hide()
            self.hidden_by_gaze.emit()
            return
        self.sender(code)
        self.update()

    def mousePressEvent(self, e):
        k = self.key_at_global(e.globalPosition().x(), e.globalPosition().y())
        if k and k != "_bar":
            self.press(k)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(125, 114, 184, 170), 2))
        p.setBrush(QColor(250, 248, 255, 240))
        p.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 20, 20)
        flash = self.flash if time.monotonic() - self.flash_t < 0.25 else None
        for code, (r, main, sub) in self._rects.items():
            special = len(code) > 1
            base = QColor("#EDE9FF") if special else QColor("#FFFFFF")
            if code == "hide":
                base = QColor("#FFE3E4")
            if flash == code:
                base = QColor("#FFE066")
            p.setPen(QPen(QColor("#CFC8F0"), 1.5))
            p.setBrush(base)
            p.drawRoundedRect(r, 10, 10)
            big = r.height() * (0.42 if len(main) <= 1 else 0.3)
            p.setFont(_font(big))
            p.setPen(QColor("#2E2A47"))
            p.drawText(r.adjusted(0, 0, 0, -r.height() * 0.18), Qt.AlignCenter, main)
            p.setFont(_font(max(9, r.height() * 0.17), False))
            p.setPen(QColor("#8A86A8"))
            p.drawText(r.adjusted(6, 0, -6, -3), Qt.AlignBottom | Qt.AlignRight, sub)
            if self.hover == code and self.progress > 0:
                pen = QPen(QColor(art.MODE_COLORS["toolbar"]), 5, Qt.SolidLine, Qt.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                w = r.width() * min(1.0, self.progress)
                p.drawLine(r.left() + 6, r.bottom() - 4, r.left() + 6 + max(0, w - 12), r.bottom() - 4)
                c = QColor(art.MODE_COLORS["toolbar"])
                c.setAlpha(int(40 + 60 * self.progress))
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                p.drawRoundedRect(r, 10, 10)
