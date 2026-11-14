"""檢查更新：讀 GitHub Releases 最新版，下載安裝檔後安裝。"""
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from .config import APP_TITLE, APP_VERSION

REPO = "achir1015/eyemouse"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_WIN = "EyeMouse-Setup.exe"
ASSET_MAC = "EyeMouse-macOS.dmg"


def vtuple(v):
    out = []
    for x in v.lstrip("vV").split("."):
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return tuple(out + [0] * (3 - len(out)))


class CheckThread(QThread):
    done = Signal(object, str)   # (release dict 或 None, 錯誤訊息)

    def run(self):
        try:
            req = urllib.request.Request(API, headers={"User-Agent": "EyeMouse-Updater", "Accept": "application/vnd.github+json"})
            with urllib.request.urlopen(req, timeout=12) as r:
                self.done.emit(json.loads(r.read().decode("utf-8")), "")
        except Exception as e:  # noqa: BLE001
            self.done.emit(None, str(e))


class DownloadThread(QThread):
    progress = Signal(int)
    done = Signal(str, str)

    def __init__(self, url, name):
        super().__init__()
        self.url, self.name = url, name
        self.cancel = False

    def run(self):
        try:
            path = os.path.join(tempfile.gettempdir(), self.name)
            req = urllib.request.Request(self.url, headers={"User-Agent": "EyeMouse-Updater"})
            with urllib.request.urlopen(req, timeout=30) as r, open(path + ".part", "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while not self.cancel:
                    b = r.read(256 * 1024)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if total:
                        self.progress.emit(int(got * 100 / total))
            if self.cancel:
                os.remove(path + ".part")
                self.done.emit("", "已取消")
                return
            os.replace(path + ".part", path)
            self.done.emit(path, "")
        except Exception as e:  # noqa: BLE001
            self.done.emit("", str(e))


class Updater:
    def __init__(self, settings, parent_getter, quit_fn):
        self.s = settings
        self.parent = parent_getter
        self.quit_fn = quit_fn
        self.th = None
        self.dl = None

    def check(self, silent=False):
        self.silent = silent
        self.th = CheckThread()
        self.th.done.connect(self._checked)
        self.th.start()

    def _checked(self, rel, err):
        if not rel:
            if not self.silent:
                QMessageBox.information(self.parent(), APP_TITLE, f"目前無法檢查更新。\n{err}")
            return
        tag = rel.get("tag_name", "")
        if vtuple(tag) <= vtuple(APP_VERSION):
            if not self.silent:
                QMessageBox.information(self.parent(), APP_TITLE, f"已經是最新版（v{APP_VERSION}）。")
            return
        if self.silent and self.s.skip_version == tag:
            return
        want = ASSET_WIN if sys.platform == "win32" else ASSET_MAC
        asset = next((a for a in rel.get("assets", []) if a.get("name") == want), None)
        if not asset:
            if not self.silent:
                QMessageBox.information(self.parent(), APP_TITLE, f"新版 {tag} 尚未提供此平台的安裝檔。")
            return
        notes = (rel.get("body") or "").strip()[:600]
        box = QMessageBox(self.parent())
        box.setWindowTitle(f"{APP_TITLE} 有新版本")
        box.setText(f"發現新版 {tag}（目前 v{APP_VERSION}）。要現在更新嗎？\n\n{notes}")
        yes = box.addButton("立即更新", QMessageBox.AcceptRole)
        box.addButton("稍後", QMessageBox.RejectRole)
        skip = box.addButton("略過此版", QMessageBox.DestructiveRole)
        box.exec()
        if box.clickedButton() == skip:
            self.s.skip_version = tag
            self.s.save()
            return
        if box.clickedButton() != yes:
            return
        self.prog = QProgressDialog("下載新版中…", "取消", 0, 100, self.parent())
        self.prog.setWindowTitle(APP_TITLE)
        self.prog.setAutoClose(False)
        self.prog.show()
        self.dl = DownloadThread(asset["browser_download_url"], want)
        self.dl.progress.connect(self.prog.setValue)
        self.prog.canceled.connect(lambda: setattr(self.dl, "cancel", True))
        self.dl.done.connect(self._downloaded)
        self.dl.start()

    def _downloaded(self, path, err):
        self.prog.close()
        if not path:
            if err != "已取消":
                QMessageBox.warning(self.parent(), APP_TITLE, f"下載失敗：{err}")
            return
        if sys.platform == "win32":
            # Inno Setup：安靜安裝、裝完自動重開眼動鼠
            subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/relaunch=1"], close_fds=True)
            self.quit_fn()
        else:
            subprocess.Popen(["open", path])
            QMessageBox.information(self.parent(), APP_TITLE,
                                    "已開啟新版安裝映像檔。\n請關閉眼動鼠，把「眼動鼠」拖到「應用程式」資料夾取代舊版即可。")
