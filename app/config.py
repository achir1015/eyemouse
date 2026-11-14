"""設定檔讀寫（JSON，存在使用者資料夾）。"""
import json
import os
import sys
from dataclasses import dataclass, asdict, field

APP_NAME = "EyeMouse"
APP_TITLE = "眼動鼠"


def data_dir() -> str:
    env = os.environ.get("EYEMOUSE_DATA_DIR")
    if env:
        d = env
    elif sys.platform == "win32":
        d = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), APP_NAME)
    elif sys.platform == "darwin":
        d = os.path.expanduser(f"~/Library/Application Support/{APP_NAME}")
    else:
        d = os.path.expanduser(f"~/.config/{APP_NAME}")
    os.makedirs(d, exist_ok=True)
    return d


def resource_path(*parts) -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def _read_version():
    for p in (resource_path("VERSION"), os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")):
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            pass
    return "0.0.0"


APP_VERSION = _read_version()


@dataclass
class Settings:
    source: str = "auto"            # auto / tobii / tobii_head / webcam / webcam_head / mouse
    dwell_ms: int = 1000            # 停留多久觸發
    radius: int = 55                # 停留判定半徑（邏輯像素）
    smoothing: int = 60             # 0~100，越大越穩但越慢
    cursor_size: int = 96           # 眼動鼠圖示大小
    move_cursor: bool = True        # 系統游標跟著視線
    sound: bool = True
    voice: bool = True              # 語音提示（模式切換、暫停…）
    tutorial_done: bool = False     # 第一次開啟自動播放教學
    auto_update: bool = True
    skip_version: str = ""
    toolbar_side: str = "right"     # right / left
    toolbar_button: int = 92        # 工具列按鈕大小
    sticky_modes: bool = False      # 右鍵/雙擊用完是否保留
    cooldown_ms: int = 700          # 觸發後冷卻
    scroll_speed: int = 5
    manual_pause_ms: int = 1500     # 偵測到實體滑鼠後暫停視線控制
    camera_index: int = 0
    screen_index: int = 0           # 0 = 主螢幕
    head_gain: float = 1.0
    show_hint: bool = True
    calib: dict = field(default_factory=dict)  # 各來源的校正資料

    @classmethod
    def load(cls) -> "Settings":
        p = os.path.join(data_dir(), "settings.json")
        s = cls()
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                d = json.load(f)
            for k, v in d.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        except (OSError, ValueError):
            pass
        return s

    def save(self):
        p = os.path.join(data_dir(), "settings.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
