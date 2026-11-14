"""眼動鼠 進入點。"""
import os
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import art
from .audio import Audio
from .config import APP_NAME, APP_TITLE, APP_VERSION, Settings
from .controller import Controller
from .panel import Panel
from .updater import Updater


class Hotkeys(QObject):
    pause = Signal()
    panel = Signal()

    def start(self):
        try:
            from pynput import keyboard
            self.l = keyboard.GlobalHotKeys({"<ctrl>+<alt>+p": self.pause.emit, "<ctrl>+<alt>+m": self.panel.emit})
            self.l.daemon = True
            self.l.start()
        except Exception:  # noqa: BLE001 — Mac 未授權「輸入監控」時略過
            self.l = None

    def stop(self):
        if self.l:
            self.l.stop()


class App(QObject):
    def __init__(self, qapp, argv):
        super().__init__()
        import logging
        from .config import data_dir
        logging.basicConfig(filename=os.path.join(data_dir(), "eyemouse.log"), level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(message)s")
        logging.info("啟動 v%s %s", APP_VERSION, " ".join(argv[1:]))
        self.qapp = qapp
        self.s = Settings.load()
        self.audio = Audio()
        self.ctl = Controller(self.s, self.audio)
        self.panel = Panel(self.ctl)
        self.tut = None
        self.assess_win = None
        self.calib = None
        self.updater = Updater(self.s, lambda: self.panel, self.quit)

        self.panel.calibrate.connect(self.calibrate)
        self.panel.tutorial.connect(self.tutorial)
        self.panel.assess.connect(self.assess)
        self.panel.check_update.connect(lambda: self.updater.check(silent=False))
        self.panel.quit_app.connect(self.quit)
        self.ctl.menu_requested.connect(self.show_panel)
        self.ctl.status_changed.connect(lambda t: __import__("logging").info("狀態：%s", t))

        self.tray = QSystemTrayIcon(art.app_icon())
        self.tray.setToolTip(f"{APP_TITLE} v{APP_VERSION}")
        m = QMenu()
        for label, fn in (("控制面板", self.show_panel), ("暫停 / 繼續", lambda: self.ctl.toggle_pause()),
                          ("校正視線", self.calibrate), ("動畫教學", self.tutorial), ("眼動評估", self.assess),
                          ("檢查更新", lambda: self.updater.check(silent=False)), (None, None), ("結束", self.quit)):
            if label is None:
                m.addSeparator()
                continue
            a = QAction(label, m)
            a.triggered.connect(fn)
            m.addAction(a)
        self.tray.setContextMenu(m)
        self.tray.activated.connect(lambda r: self.show_panel() if r == QSystemTrayIcon.Trigger else None)
        self.tray.show()
        self._menu = m

        self.hk = Hotkeys()
        self.hk.pause.connect(lambda: self.ctl.toggle_pause())
        self.hk.panel.connect(self.show_panel)
        self.hk.start()

        self.ctl.start()
        if "--hidden" not in argv:
            self.show_panel()
        if not self.s.tutorial_done and "--no-tutorial" not in argv and "--calibrate" not in argv:
            QTimer.singleShot(800, self.tutorial)
        else:
            QTimer.singleShot(600, lambda: self.audio.say("welcome"))
        if self.s.auto_update and "--no-update" not in argv:
            QTimer.singleShot(5000, lambda: self.updater.check(silent=True))
        QTimer.singleShot(4000, self._warn_no_tracker)
        if "--calibrate" in argv:
            QTimer.singleShot(2500, self.calibrate)

    def _warn_no_tracker(self):
        src = self.ctl.source
        if src and src.key.startswith("tobii") and not src.ok:
            self.audio.say("no_tracker")
            self.tray.showMessage(APP_TITLE, src.status, QSystemTrayIcon.Warning, 6000)

    def show_panel(self):
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def calibrate(self):
        from .calibrate import CalibrationWindow
        if self.ctl.source and self.ctl.source.key == "mouse":
            QMessageBox.information(self.panel, APP_TITLE, "滑鼠模擬模式不需要校正。")
            return
        self.panel.hide()
        self.calib = CalibrationWindow(self.ctl)
        self.calib.finished.connect(lambda ok: self.show_panel())
        self.calib.start()

    def tutorial(self):
        from .tutorial import TutorialWindow
        if self.tut and self.tut.isVisible():
            self.tut.raise_()
            return
        self.panel.hide()
        self.tut = TutorialWindow(self.ctl)
        self.tut.show()

    def assess(self):
        from .assess import AssessWindow
        if not self.assess_win:
            self.assess_win = AssessWindow(self.ctl)
        self.panel.hide()
        self.assess_win.show()
        self.assess_win.raise_()

    def quit(self):
        self.hk.stop()
        self.ctl.shutdown()
        self.tray.hide()
        self.qapp.quit()


def selftest(qapp):
    """--selftest：不碰滑鼠，檢查各模組能建立、教學每頁能畫、評估分析能跑。"""
    import tempfile
    os.environ["EYEMOUSE_DATA_DIR"] = tempfile.mkdtemp(prefix="eyemouse_test_")
    from PySide6.QtGui import QImage, QPainter
    from . import tutorial
    from .assess import AssessWindow, aoi_stats, fixations_idt
    from .dwell import Dwell
    s = Settings.load()
    s.source = "mouse"
    audio = Audio()
    ctl = Controller(s, audio)
    ok = []
    d = Dwell(1.0, 50, 0.5)
    fired = [d.feed(i * 0.016, 100, 100)[1] for i in range(80)]
    assert any(fired), "dwell 沒觸發"
    ok.append("dwell")
    img = QImage(1000, 560, QImage.Format_ARGB32)
    for k, fn in tutorial.SCENES.items():
        for t in (0.0, 1.5, 3.0, 5.0):
            p = QPainter(img)
            fn(p, t, 30)
            p.end()
    ok.append(f"tutorial x{len(tutorial.SCENES)}")
    for name in ["welcome", "mode_left", "tut_practice"]:
        assert audio.voice_path(name), f"缺語音 {name}"
    ok.append("voice")
    samples = [(i * 0.01, 0.3 + (0.4 if i > 150 else 0), 0.5) for i in range(300)]
    fx = fixations_idt(samples)
    assert len(fx) == 2, fx
    rows = aoi_stats(fx, [{"name": "A", "rect": [0.2, 0.4, 0.2, 0.2]}], 3.0)
    assert rows[0]["注視次數"] == "1"
    ok.append("assess")
    AssessWindow(ctl)
    Panel(ctl)
    ok.append("windows")
    if sys.stdout:
        print("SELFTEST OK:", ", ".join(ok))
    return 0


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Achir.EyeMouse")
        except Exception:  # noqa: BLE001
            pass
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    qapp = QApplication(sys.argv)
    qapp.setApplicationName(APP_NAME)
    qapp.setWindowIcon(art.app_icon())
    qapp.setQuitOnLastWindowClosed(False)
    if "--selftest" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
        try:
            selftest(qapp)
            msg, code = "SELFTEST OK", 0
        except Exception:  # noqa: BLE001
            import traceback
            msg, code = "SELFTEST FAIL " + traceback.format_exc(), 1
        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(msg + "\n")
        sys.exit(code)

    # 單一執行個體：再開一次只會叫出控制面板
    sock = QLocalSocket()
    sock.connectToServer("EyeMouse-single")
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return
    QLocalServer.removeServer("EyeMouse-single")
    server = QLocalServer()
    server.listen("EyeMouse-single")

    app = App(qapp, sys.argv)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), app.show_panel()))
    if "--quit-after" in sys.argv:
        secs = float(sys.argv[sys.argv.index("--quit-after") + 1])
        QTimer.singleShot(int(secs * 1000), app.quit)
    sys.exit(qapp.exec())


if __name__ == "__main__":
    main()
