"""攝影機注視（Windows／Mac 皆可，Mac 主要用這個）。

MediaPipe Face Landmarker 取得虹膜與臉部姿勢：
- 眼睛模式：虹膜在眼眶中的位置＋頭部角度（需要 9 點校正，精準度較低）
- 頭控模式：只用頭部角度與鼻尖位置（較穩定，轉頭移動游標）
"""
import math
import sys
import threading
import time

import numpy as np

from ..config import resource_path
from .base import GazeSource

# 眼睛關鍵點（MediaPipe 478 點模型）
R_OUT, R_IN, R_UP, R_DN = 33, 133, 159, 145
L_IN, L_OUT, L_UP, L_DN = 362, 263, 386, 374
R_IRIS, L_IRIS = 468, 473
NOSE = 1


def _rel_iris(lm, inner, outer, up, dn, iris):
    a = np.array([lm[inner].x, lm[inner].y])
    b = np.array([lm[outer].x, lm[outer].y])
    c = np.array([lm[iris].x, lm[iris].y])
    axis = b - a
    L = np.linalg.norm(axis) + 1e-9
    u = axis / L
    h = float(np.dot(c - a, u) / L)              # 0=內眼角 1=外眼角
    mid_y = (lm[up].y + lm[dn].y) / 2
    v = float((c[1] - mid_y) / L)
    open_ = float(abs(lm[dn].y - lm[up].y) / L)
    return h, v, open_


class WebcamSource(GazeSource):
    key = "webcam"
    title = "攝影機（眼睛＋頭部）"
    fit_kind = "quad"
    head_only = False

    def __init__(self, camera_index=0, head_gain=1.0):
        super().__init__()
        self.camera_index = camera_index
        self.head_gain = head_gain
        self._thread = None
        self._neutral = None
        self._neutral_acc = []
        self.fps = 0.0
        self.preview = None      # 最近一張縮圖（BGR）給設定視窗預覽
        self.blink = False

    def recenter(self):
        self._neutral = None
        self._neutral_acc = []

    def start(self):
        super().start()
        self._thread = threading.Thread(target=self._run, name="webcam", daemon=True)
        self._thread.start()

    def stop(self):
        super().stop()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mpt
            from mediapipe.tasks.python import vision
        except Exception as e:
            self.status = f"缺少攝影機元件：{e}"
            return
        model = resource_path("assets", "face_landmarker.task")
        try:
            with open(model, "rb") as f:
                buf = f.read()
            opts = vision.FaceLandmarkerOptions(
                base_options=mpt.BaseOptions(model_asset_buffer=buf),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
                output_facial_transformation_matrixes=True,
            )
            lmk = vision.FaceLandmarker.create_from_options(opts)
        except Exception as e:
            self.status = f"臉部模型載入失敗：{e}"
            return
        api = cv2.CAP_DSHOW if sys.platform == "win32" else (cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY)
        cap = cv2.VideoCapture(self.camera_index, api)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.status = "打不開攝影機（Mac 請到「隱私權與安全性 › 相機」允許眼動鼠）"
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.status = "攝影機啟動中…"
        t0 = time.monotonic()
        n = 0
        last_ts = 0
        try:
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.03)
                    continue
                frame = cv2.flip(frame, 1)  # 鏡像，左右跟使用者一致
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts = int((time.monotonic() - t0) * 1000)
                if ts <= last_ts:
                    ts = last_ts + 1
                last_ts = ts
                res = lmk.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)
                n += 1
                if n % 30 == 0:
                    self.fps = n / max(1e-3, time.monotonic() - t0)
                small = cv2.resize(frame, (240, 180))
                if res.face_landmarks:
                    lm = res.face_landmarks[0]
                    feat = self._features(lm, res.facial_transformation_matrixes[0] if res.facial_transformation_matrixes else None)
                    if feat is not None:
                        self._push(feat)
                        self.ok = True
                        self.status = f"攝影機追蹤中（{self.fps:.0f} fps）"
                    for i in (R_IRIS, L_IRIS, NOSE):
                        cv2.circle(small, (int(lm[i].x * 240), int(lm[i].y * 180)), 3, (80, 200, 255), -1)
                else:
                    self.ok = False
                    self.status = "看不到臉，請正對攝影機"
                self.preview = small
        finally:
            cap.release()
            lmk.close()

    def _features(self, lm, mat):
        rh, rv, ro = _rel_iris(lm, R_IN, R_OUT, R_UP, R_DN, R_IRIS)
        lh, lv, lo = _rel_iris(lm, L_IN, L_OUT, L_UP, L_DN, L_IRIS)
        self.blink = (ro + lo) / 2 < 0.12
        # 畫面已鏡像：使用者往右看時兩眼虹膜都往影像右邊
        ih = (lh - rh) / 2
        iv = (rv + lv) / 2
        yaw = pitch = 0.0
        if mat is not None:
            R = np.array(mat)[:3, :3]
            yaw = math.degrees(math.atan2(-R[2, 0], math.hypot(R[2, 1], R[2, 2])))
            pitch = math.degrees(math.atan2(R[2, 1], R[2, 2]))
        nx, ny = lm[NOSE].x, lm[NOSE].y
        f = np.array([ih, iv, yaw / 30.0, pitch / 30.0, nx, ny])
        if self._neutral is None:
            self._neutral_acc.append(f)
            if len(self._neutral_acc) >= 15:
                self._neutral = np.mean(self._neutral_acc, axis=0)
            return None
        d = f - self._neutral
        if self.head_only:
            return (float(d[2]), float(d[3]), float(d[4]), float(d[5]))
        return (float(d[0]), float(d[1]), float(d[2]), float(d[3]))

    def default_map(self, feat, geo):
        gx, gy, gw, gh = geo
        k = self.head_gain
        if self.head_only:
            yaw, pitch = feat[0], feat[1]
        else:
            yaw = feat[2] + feat[0] * 6
            pitch = feat[3] - feat[1] * 6
        # 頭轉 ±12° 約到螢幕邊
        x = gx + gw / 2 + yaw * 30 / 12 * gw / 2 * k
        y = gy + gh / 2 - pitch * 30 / 9 * gh / 2 * k
        return x, y


class WebcamHeadSource(WebcamSource):
    key = "webcam_head"
    title = "攝影機（頭控）"
    head_only = True
