"""遊戲連線：讓眼動遊戲（例如小柯機器人眼動探險島）直接拿到視線座標。

協定：127.0.0.1:47961 TCP，一行一個 JSON（UTF-8）。
  遊戲 → 眼動鼠：{"cmd":"hello","name":"遊戲名稱"}
                 {"cmd":"game","on":true}   遊戲模式：眼動鼠只追蹤、不點擊，隱藏游標與工具列
                 {"cmd":"game","on":false}  回到一般滑鼠模式（遊戲失去焦點時）
  眼動鼠 → 遊戲：{"ev":"hello","version":"1.3.0","source":"tobii","status":"…"}
                 {"x":物理像素,"y":物理像素,"t":秒}   約 60 筆/秒
                 {"lost":1}                             0.3 秒沒有視線
連線中斷就自動退出遊戲模式，眼動鼠恢復成滑鼠。
"""
import json
import logging
import time

from PySide6.QtCore import QObject, QPoint, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtNetwork import QHostAddress, QTcpServer

from .config import APP_VERSION

PORT = 47961


def to_physical(x, y):
    """Qt 邏輯座標 → 物理像素，以「所有螢幕最左上角」為原點（與 Godot 的螢幕座標一致）。
    Qt 的螢幕左上角是原生座標、螢幕內部依 DPR 縮放。"""
    screens = QGuiApplication.screens()
    ox = min(s.geometry().x() for s in screens)
    oy = min(s.geometry().y() for s in screens)
    scr = QGuiApplication.screenAt(QPoint(int(x), int(y))) or QGuiApplication.primaryScreen()
    g = scr.geometry()
    dpr = scr.devicePixelRatio()
    return g.x() + (x - g.x()) * dpr - ox, g.y() + (y - g.y()) * dpr - oy


class GameLink(QObject):
    def __init__(self, ctl):
        super().__init__()
        self.ctl = ctl
        self.clients = []
        self.game_clients = set()
        self.server = QTcpServer(self)
        self.server.newConnection.connect(self._accept)
        self.ok = self.server.listen(QHostAddress.LocalHost, PORT)
        if not self.ok:
            logging.warning("遊戲連線埠 %d 無法使用：%s", PORT, self.server.errorString())
        self.last_sample = 0.0
        self.lost_sent = False
        ctl.gaze_sample.connect(self._sample)
        self.timer = QTimer(self)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self._check_lost)
        self.timer.start()

    # ---------------------------------------------------------------- 連線
    def _accept(self):
        while self.server.hasPendingConnections():
            s = self.server.nextPendingConnection()
            s._buf = b""
            self.clients.append(s)
            s.readyRead.connect(lambda s=s: self._read(s))
            s.disconnected.connect(lambda s=s: self._drop(s))
            src = self.ctl.source
            self._send(s, {"ev": "hello", "version": APP_VERSION, "source": src.key if src else "",
                           "status": src.status if src else ""})

    def _drop(self, s):
        if s in self.clients:
            self.clients.remove(s)
        if s in self.game_clients:
            self.game_clients.discard(s)
            self._apply()
        s.deleteLater()

    def _read(self, s):
        s._buf += bytes(s.readAll())
        while b"\n" in s._buf:
            line, s._buf = s._buf.split(b"\n", 1)
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            cmd = msg.get("cmd")
            if cmd == "hello":
                logging.info("遊戲連線：%s", msg.get("name", "?"))
            elif cmd == "game":
                if msg.get("on"):
                    self.game_clients.add(s)
                else:
                    self.game_clients.discard(s)
                self._apply()

    def _apply(self):
        on = bool(self.game_clients)
        if on == self.ctl.game_mode:
            return
        self.ctl.set_game_mode(on)
        logging.info("遊戲模式：%s", "開" if on else "關")

    @staticmethod
    def _send(s, obj):
        s.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))

    # ---------------------------------------------------------------- 視線
    def _sample(self, t, x, y):
        self.last_sample = time.monotonic()
        self.lost_sent = False
        if not self.clients:
            return
        px, py = to_physical(x, y)
        data = (json.dumps({"x": round(px, 1), "y": round(py, 1), "t": round(t, 3)}) + "\n").encode()
        for s in self.clients:
            s.write(data)

    def _check_lost(self):
        if self.clients and not self.lost_sent and time.monotonic() - self.last_sample > 0.3:
            self.lost_sent = True
            for s in self.clients:
                self._send(s, {"lost": 1})

    def close(self):
        self.timer.stop()
        for s in list(self.clients):
            s.abort()
        self.server.close()
