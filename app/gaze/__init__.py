"""視線來源註冊。"""
import sys

from PySide6.QtGui import QCursor

from .base import GazeSource, Mapper  # noqa: F401


class MouseSource(GazeSource):
    """用實體滑鼠位置當作視線（測試／頭控滑鼠使用者）。"""
    key = "mouse"
    title = "滑鼠模擬（測試用）"
    fit_kind = "affine"

    def start(self):
        super().start()
        self.ok = True
        self.status = "滑鼠模擬：游標停住即觸發"

    def latest(self):
        import time
        p = QCursor.pos()
        return time.monotonic(), (float(p.x()), float(p.y()))

    def default_map(self, feat, geo):
        return feat


SOURCE_TITLES = {
    "auto": "自動（有 Tobii 用 Tobii，否則用攝影機）",
    "tobii": "Tobii 眼動儀（眼球注視）",
    "tobii_head": "Tobii 眼動儀（頭部控制）",
    "webcam": "攝影機（眼睛＋頭部，需校正）",
    "webcam_head": "攝影機（頭部控制）",
    "mouse": "滑鼠模擬（測試用）",
}


def create_source(key, settings):
    if key == "auto":
        if sys.platform == "win32":
            from .tobii import find_dll
            key = "tobii" if find_dll() else "webcam_head"
        else:
            key = "webcam_head"
    if key in ("tobii", "tobii_head"):
        from .tobii import TobiiSource, TobiiHeadSource
        cls = TobiiSource if key == "tobii" else TobiiHeadSource
        return cls(head_gain=settings.head_gain)
    if key in ("webcam", "webcam_head"):
        from .webcam import WebcamSource, WebcamHeadSource
        cls = WebcamSource if key == "webcam" else WebcamHeadSource
        return cls(camera_index=settings.camera_index, head_gain=settings.head_gain)
    return MouseSource()
