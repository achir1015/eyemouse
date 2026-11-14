"""視線濾波與停留（dwell）判定——純邏輯，可單元測試。"""
import math


class OneEuro:
    """One Euro 濾波：慢動作時很穩，快速掃視時跟得上。"""

    def __init__(self, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x = None
        self.dx = 0.0
        self.t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self):
        self.x = None
        self.t = None
        self.dx = 0.0

    def __call__(self, t, x):
        if self.x is None or self.t is None or t <= self.t:
            self.x, self.t = x, t
            return x
        dt = max(1e-3, t - self.t)
        self.t = t
        dx = (x - self.x) / dt
        a_d = self._alpha(self.d_cutoff, dt)
        self.dx = a_d * dx + (1 - a_d) * self.dx
        cutoff = self.min_cutoff + self.beta * abs(self.dx)
        a = self._alpha(cutoff, dt)
        self.x = a * x + (1 - a) * self.x
        return self.x


class PointFilter:
    def __init__(self, smoothing=60):
        self.set_smoothing(smoothing)

    def set_smoothing(self, smoothing):
        s = max(0, min(100, smoothing)) / 100.0
        # 平滑越大 → 截止頻率越低
        mc = 3.0 * (1 - s) + 0.15
        beta = 0.02 * (1 - s) + 0.0015
        self.fx = OneEuro(mc, beta)
        self.fy = OneEuro(mc, beta)

    def reset(self):
        self.fx.reset()
        self.fy.reset()

    def __call__(self, t, x, y):
        return self.fx(t, x), self.fy(t, y)


class Dwell:
    """停留判定。

    feed(t, x, y) 每個樣本呼叫一次（x,y 為 None 代表沒偵測到視線）。
    回傳 (progress 0~1, fired_point 或 None, anchor 或 None)。
    """

    def __init__(self, dwell_s=1.0, radius=55, cooldown_s=0.7):
        self.dwell_s = dwell_s
        self.radius = radius
        self.cooldown_s = cooldown_s
        self.reset()

    def reset(self):
        self.anchor = None
        self.start = None
        self.sum = [0.0, 0.0, 0]
        self.block_until = 0.0
        self.block_anchor = None

    def _new_anchor(self, t, x, y):
        self.anchor = (x, y)
        self.start = t
        self.sum = [x, y, 1]

    def feed(self, t, x, y):
        if x is None:
            # 短暫失去視線（眨眼）不重置，只是不前進
            if self.start is not None and t - self.start > self.dwell_s * 3:
                self.anchor = None
                self.start = None
            return 0.0, None, self.anchor

        # 冷卻：觸發後必須移開，或等冷卻時間結束
        if self.block_anchor is not None:
            bx, by = self.block_anchor
            moved = math.hypot(x - bx, y - by) > self.radius * 1.3
            if t < self.block_until and not moved:
                return 0.0, None, None
            if not moved and t >= self.block_until:
                # 冷卻結束但仍盯著同一處 → 重新從這裡起算
                self.block_anchor = None
                self._new_anchor(t, x, y)
                return 0.0, None, self.anchor
            self.block_anchor = None

        if self.anchor is None or math.hypot(x - self.anchor[0], y - self.anchor[1]) > self.radius:
            self._new_anchor(t, x, y)
            return 0.0, None, self.anchor

        # 以平均值當中心，抵銷抖動
        self.sum[0] += x
        self.sum[1] += y
        self.sum[2] += 1
        self.anchor = (self.sum[0] / self.sum[2], self.sum[1] / self.sum[2])
        p = (t - self.start) / max(0.05, self.dwell_s)
        if p >= 1.0:
            fired = self.anchor
            self.block_anchor = fired
            self.block_until = t + self.cooldown_s
            self.anchor = None
            self.start = None
            return 1.0, fired, None
        return p, None, self.anchor
