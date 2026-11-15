"""視線來源共用介面與校正映射。"""
import threading
import time

import numpy as np


class GazeSource:
    key = "base"
    title = "來源"
    # 一般化校正時用的特徵展開方式：'affine' 或 'quad'
    fit_kind = "affine"

    def __init__(self):
        self._lock = threading.Lock()
        self._latest = None      # (t, feat tuple)
        self.status = "尚未啟動"
        self.ok = False
        self.running = False

    # 子類別實作
    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def _push(self, feat):
        with self._lock:
            self._latest = (time.monotonic(), tuple(feat))

    def latest(self):
        with self._lock:
            return self._latest

    def default_map(self, feat, geo):
        """未校正時把特徵轉成螢幕座標。geo = (x, y, w, h)。"""
        raise NotImplementedError

    # ---- 校正 ----
    def design(self, feat, geo):
        """校正回歸用的設計向量。"""
        if self.fit_kind == "affine":
            x, y = self.default_map(feat, geo)
            gx, gy, gw, gh = geo
            u, v = (x - gx) / gw, (y - gy) / gh
            return [u, v, 1.0]
        f = list(feat)
        terms = [1.0] + f
        for i in range(len(f)):
            for j in range(i, len(f)):
                terms.append(f[i] * f[j])
        return terms


class Mapper:
    """把來源特徵轉成螢幕座標；有校正資料時用回歸結果。"""

    def __init__(self, source: GazeSource, calib: dict | None):
        self.source = source
        self.W = None
        self.mean = None
        self.std = None
        # 攝影機的舊校正沒有記錄誤差（1.2.2 以前可能套用了很差的結果）→ 忽略，請重新校正
        if calib and source.key.startswith("webcam") and calib.get("err") is None:
            calib = None
        if calib and calib.get("kind") == source.fit_kind and calib.get("W"):
            try:
                self.W = np.array(calib["W"], dtype=float)
                self.mean = np.array(calib["mean"], dtype=float)
                self.std = np.array(calib["std"], dtype=float)
            except (KeyError, ValueError):
                self.W = None

    @property
    def calibrated(self):
        return self.W is not None

    def map(self, feat, geo):
        if self.W is None:
            return self.source.default_map(feat, geo)
        d = np.array(self.source.design(feat, geo), dtype=float)
        if d.shape[0] != self.mean.shape[0]:
            return self.source.default_map(feat, geo)
        z = (d - self.mean) / self.std
        uv = z @ self.W
        gx, gy, gw, gh = geo
        return gx + uv[0] * gw, gy + uv[1] * gh

    @staticmethod
    def fit(source: GazeSource, samples, geo, ridge=1e-3):
        """samples: [(feat, (tx, ty)), ...]，回傳可存進設定的 dict 與平均誤差（像素）。"""
        gx, gy, gw, gh = geo
        X = np.array([source.design(f, geo) for f, _ in samples], dtype=float)
        Y = np.array([((tx - gx) / gw, (ty - gy) / gh) for _, (tx, ty) in samples], dtype=float)
        mean = X.mean(axis=0)
        std = X.std(axis=0)
        const = std < 1e-9
        mean[const] = 0.0          # 常數項保留
        std[const] = 1.0
        Z = (X - mean) / std
        A = Z.T @ Z + ridge * len(Z) * np.eye(Z.shape[1])
        A[const, const] -= ridge * len(Z)  # 常數項不懲罰
        W = np.linalg.solve(A, Z.T @ Y)
        pred = Z @ W
        err = np.hypot((pred[:, 0] - Y[:, 0]) * gw, (pred[:, 1] - Y[:, 1]) * gh)
        med = float(np.median(err))
        calib = {"kind": source.fit_kind, "W": W.tolist(), "mean": mean.tolist(), "std": std.tolist(), "err": round(med, 1)}
        return calib, med
