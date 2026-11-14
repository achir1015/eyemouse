"""Tobii Eye Tracker 5（Windows）——透過 Tobii Stream Engine（tobii_stream_engine.dll）讀取。

注視點：tobii_gaze_point_subscribe，座標為 0~1（相對於 Tobii Experience 設定的那個螢幕）。
頭部：tobii_head_pose_subscribe（ET5 的 6DoF 頭部追蹤），用來做「頭控模式」。
"""
import ctypes
import glob
import math
import os
import sys
import threading
import time

from .base import GazeSource

ERR = {
    0: "正常", 1: "內部錯誤", 2: "授權不足", 3: "不支援", 4: "無法使用", 5: "連線失敗",
    6: "逾時", 7: "記憶體不足", 8: "參數錯誤", 11: "已訂閱", 13: "操作失敗",
    14: "API 實例衝突", 17: "訂閱者過多", 18: "驅動連線失敗", 19: "未授權", 20: "韌體更新中",
}


def find_dll():
    env = os.environ.get("EYEMOUSE_TOBII_DLL")
    if env and os.path.isfile(env):
        return env
    here = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cands = [os.path.join(here, "lib", "tobii_stream_engine.dll"), os.path.join(here, "tobii_stream_engine.dll")]
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.environ.get("ProgramData", r"C:\ProgramData")):
        cands += glob.glob(os.path.join(root, "Tobii", "**", "tobii_stream_engine.dll"), recursive=True)
    best = None
    for c in cands:
        if os.path.isfile(c):
            # 偏好 64 位元版本（路徑中通常含 x64 或在 Program Files 下）
            if best is None or ("x86" in best.lower() and "x86" not in c.lower()):
                best = c
    return best


class _Ver(ctypes.Structure):
    _fields_ = [("major", ctypes.c_int), ("minor", ctypes.c_int), ("revision", ctypes.c_int), ("build", ctypes.c_int)]


class _Gaze(ctypes.Structure):
    _fields_ = [("timestamp_us", ctypes.c_int64), ("validity", ctypes.c_int), ("position_xy", ctypes.c_float * 2)]


class _Head(ctypes.Structure):
    _fields_ = [("timestamp_us", ctypes.c_int64), ("position_validity", ctypes.c_int),
                ("position_xyz", ctypes.c_float * 3), ("rotation_validity_xyz", ctypes.c_int * 3),
                ("rotation_xyz", ctypes.c_float * 3)]


URL_CB = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_void_p)
GAZE_CB = ctypes.CFUNCTYPE(None, ctypes.POINTER(_Gaze), ctypes.c_void_p)
HEAD_CB = ctypes.CFUNCTYPE(None, ctypes.POINTER(_Head), ctypes.c_void_p)


class TobiiSource(GazeSource):
    key = "tobii"
    title = "Tobii 眼動儀（眼球）"
    fit_kind = "affine"
    use_head = False

    def __init__(self, head_gain=1.0):
        super().__init__()
        self.head_gain = head_gain
        self.dll_path = find_dll()
        self._thread = None
        self._center = None   # 頭控中心（yaw, pitch）
        self._gaze_cb = GAZE_CB(self._on_gaze)
        self._head_cb = HEAD_CB(self._on_head)
        self.last_gaze = None
        self.version = None

    # ---- 回呼（在工作執行緒中） ----
    def _on_gaze(self, p, _):
        g = p.contents
        now = time.monotonic()
        if g.validity == 1:
            self._valid_t = now
            if self.ok and self.status.startswith("眼動儀已連線，但"):
                self.status = self._conn_status
        elif self.ok and now - getattr(self, "_valid_t", 0) > 1.5:
            self.status = "眼動儀已連線，但看不到眼睛：請坐正面對螢幕，距離約 50～90 公分"
        if g.validity == 1:
            self.last_gaze = (g.position_xy[0], g.position_xy[1])
            if not self.use_head:
                self._push(self.last_gaze)

    def _on_head(self, p, _):
        h = p.contents
        if not self.use_head:
            return
        if h.rotation_validity_xyz[0] == 1 and h.rotation_validity_xyz[1] == 1:
            pitch, yaw = h.rotation_xyz[0], h.rotation_xyz[1]
            if self._center is None:
                self._center = (yaw, pitch)
            self._push((yaw - self._center[0], pitch - self._center[1]))

    def recenter(self):
        self._center = None

    # ---- 執行緒 ----
    def start(self):
        super().start()
        if not self.dll_path:
            self.status = "找不到 Tobii Stream Engine（請先安裝 Tobii Experience 驅動）"
            return
        self._thread = threading.Thread(target=self._run, name="tobii", daemon=True)
        self._thread.start()

    def stop(self):
        super().stop()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        try:
            os.add_dll_directory(os.path.dirname(self.dll_path))
        except (AttributeError, OSError):
            pass
        try:
            se = ctypes.CDLL(self.dll_path)
        except OSError as e:
            self.status = f"無法載入 Tobii DLL：{e}"
            return
        v = _Ver()
        if se.tobii_get_api_version(ctypes.byref(v)) == 0:
            self.version = f"{v.major}.{v.minor}.{v.revision}"
        api = ctypes.c_void_p()
        r = se.tobii_api_create(ctypes.byref(api), None, None)
        if r != 0:
            self.status = f"Tobii API 建立失敗：{ERR.get(r, r)}"
            return
        try:
            while self.running:
                dev = self._connect(se, api, v.major)
                if dev is None:
                    self.ok = False
                    time.sleep(1.5)
                    continue
                self._loop(se, dev)
                se.tobii_device_destroy(dev)
        finally:
            se.tobii_api_destroy(api)

    def _connect(self, se, api, major):
        urls = []
        cb = URL_CB(lambda u, _: urls.append(u))
        se.tobii_enumerate_local_device_urls(api, cb, None)
        if not urls:
            self.status = "找不到眼動儀：請確認 USB 已插好、Tobii Experience 已安裝"
            return None
        dev = ctypes.c_void_p()
        if major >= 4:
            r = se.tobii_device_create(api, urls[0], ctypes.c_int(1), ctypes.byref(dev))  # 1 = 互動用途
        else:
            r = se.tobii_device_create(api, urls[0], ctypes.byref(dev))
        if r != 0:
            self.status = f"連線眼動儀失敗：{ERR.get(r, r)}"
            return None
        r = se.tobii_gaze_point_subscribe(dev, self._gaze_cb, None)
        if r != 0:
            self.status = f"訂閱注視點失敗：{ERR.get(r, r)}"
            se.tobii_device_destroy(dev)
            return None
        self.head_ok = se.tobii_head_pose_subscribe(dev, self._head_cb, None) == 0 if hasattr(se, "tobii_head_pose_subscribe") else False
        self.ok = True
        self._conn_status = f"已連線 Tobii（Stream Engine {self.version or '?'}）"
        self.status = self._conn_status
        return dev

    def _loop(self, se, dev):
        arr = (ctypes.c_void_p * 1)(dev)
        while self.running:
            r = se.tobii_wait_for_callbacks(1, arr)
            if r not in (0, 6):           # 6 = 逾時，正常
                if r == 5:                # 連線中斷 → 重連
                    self.status = "眼動儀連線中斷，重新連線中…"
                    if se.tobii_device_reconnect(dev) != 0:
                        time.sleep(1)
                        if se.tobii_device_reconnect(dev) != 0:
                            return
                    continue
            r = se.tobii_device_process_callbacks(dev)
            if r == 5:
                self.status = "眼動儀連線中斷，重新連線中…"
                if se.tobii_device_reconnect(dev) != 0:
                    time.sleep(1)
                    return

    # ---- 映射 ----
    def default_map(self, feat, geo):
        gx, gy, gw, gh = geo
        if self.use_head:
            yaw, pitch = feat
            k = self.head_gain
            # 轉頭約 ±18° 就能涵蓋整個螢幕
            return (gx + gw / 2 - yaw / math.radians(18) * gw / 2 * k,
                    gy + gh / 2 - pitch / math.radians(12) * gh / 2 * k)
        return gx + feat[0] * gw, gy + feat[1] * gh


class TobiiHeadSource(TobiiSource):
    key = "tobii_head"
    title = "Tobii 眼動儀（頭控）"
    use_head = True
