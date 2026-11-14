"""系統滑鼠操作（座標一律用 Qt 邏輯座標）。

Windows：QCursor.setPos 移動＋SendInput 按鍵/滾輪。
macOS：pynput（Quartz），需在「系統設定 › 隱私權與安全性 › 輔助使用」允許。
"""
import sys
import time

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    MOVE, LDOWN, LUP, RDOWN, RUP, MDOWN, MUP, WHEEL = 0x1, 0x2, 0x4, 0x8, 0x10, 0x20, 0x40, 0x800
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    MARK = 0x45594D53  # 'EYMS'，用來辨認我們自己送出的事件

    def _send(flags, data=0, dx=0, dy=0):
        inp = INPUT(type=0)
        inp.u.mi = MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, MARK)
        _user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
else:
    try:
        from pynput.mouse import Button, Controller
        _mouse = Controller()
    except Exception:  # pragma: no cover
        _mouse = None


class Mouse:
    def __init__(self):
        self.left_held = False

    # ---- 位置 ----
    def pos(self):
        p = QCursor.pos()
        return p.x(), p.y()

    def move(self, x, y):
        x, y = int(round(x)), int(round(y))
        if IS_WIN:
            QCursor.setPos(QPoint(x, y))
            if self.left_held:
                _send(MOVE, dx=0, dy=0)  # 讓拖曳中的視窗收到帶按鍵狀態的移動
        elif _mouse is not None:
            _mouse.position = (x, y)
        else:
            QCursor.setPos(QPoint(x, y))

    # ---- 按鍵 ----
    def _down(self, b):
        if IS_WIN:
            _send({"l": LDOWN, "r": RDOWN, "m": MDOWN}[b])
        elif _mouse:
            _mouse.press({"l": Button.left, "r": Button.right, "m": Button.middle}[b])

    def _up(self, b):
        if IS_WIN:
            _send({"l": LUP, "r": RUP, "m": MUP}[b])
        elif _mouse:
            _mouse.release({"l": Button.left, "r": Button.right, "m": Button.middle}[b])

    def click(self, x, y, button="l", count=1):
        self.move(x, y)
        time.sleep(0.02)
        if not IS_WIN and _mouse and count > 1:
            _mouse.click({"l": Button.left, "r": Button.right}[button], count)
            return
        for i in range(count):
            self._down(button)
            time.sleep(0.03)
            self._up(button)
            if i + 1 < count:
                time.sleep(0.06)

    def press_left(self, x, y):
        self.move(x, y)
        time.sleep(0.02)
        self._down("l")
        self.left_held = True

    def release_left(self, x, y):
        self.move(x, y)
        time.sleep(0.03)
        self._up("l")
        self.left_held = False

    def scroll(self, steps):
        """steps > 0 往上捲。"""
        if steps == 0:
            return
        if IS_WIN:
            _send(WHEEL, data=int(steps * 40))
        elif _mouse:
            _mouse.scroll(0, int(steps))

    def safe_release(self):
        if self.left_held:
            self._up("l")
            self.left_held = False


def mac_accessibility_ok(prompt=False):
    """macOS：檢查（必要時請系統跳出）「輔助使用」權限，沒有就不能控制滑鼠。"""
    if not IS_MAC:
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: bool(prompt)}))
    except Exception:  # noqa: BLE001
        return True
