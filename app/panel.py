"""控制面板：狀態、設定、說明/更新/關於。"""
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QPushButton, QSlider, QTabWidget, QVBoxLayout, QWidget)

from . import art
from .config import APP_TITLE, APP_VERSION
from .gaze import SOURCE_TITLES

STYLE = """
QWidget { font-family: 'Microsoft JhengHei UI','PingFang TC','Heiti TC'; font-size: 15px; color:#2E2A47; }
QWidget#panel { background:#F7F5FF; }
QTabWidget::pane { border:1px solid #D9D4F2; border-radius:12px; background:#FFFFFF; }
QTabBar::tab { padding:10px 22px; margin:2px; border-radius:10px; background:#ECE8FF; }
QTabBar::tab:selected { background:#7D72B8; color:white; }
QPushButton { background:#FFFFFF; border:2px solid #B9A7FF; border-radius:14px; padding:12px 16px; font-size:16px; font-weight:bold; }
QPushButton:hover { background:#F0ECFF; }
QPushButton#primary { background:#7D72B8; color:white; border-color:#7D72B8; }
QPushButton#danger { border-color:#E8676B; color:#C2454A; }
QGroupBox { border:1px solid #E2DDF7; border-radius:12px; margin-top:16px; padding:10px; font-weight:bold; }
QGroupBox::title { subcontrol-origin: margin; left:12px; padding:0 6px; color:#7D72B8; }
QSlider::groove:horizontal { height:8px; background:#E2DDF7; border-radius:4px; }
QSlider::handle:horizontal { width:22px; margin:-8px 0; border-radius:11px; background:#7D72B8; }
QComboBox { padding:6px 10px; border:1px solid #CFC8F0; border-radius:8px; background:white; }
"""


class Panel(QWidget):
    calibrate = Signal()
    assess = Signal()
    tutorial = Signal()
    check_update = Signal()
    quit_app = Signal()

    def __init__(self, ctl):
        super().__init__(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.ctl = ctl
        self.s = ctl.s
        self.setObjectName("panel")
        self.setStyleSheet(STYLE)
        self.setWindowTitle(f"{APP_TITLE} 控制面板")
        self.setWindowIcon(art.app_icon())
        self.resize(720, 640)

        root = QVBoxLayout(self)
        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap.fromImage(art.render_icon(72)))
        head.addWidget(logo)
        t = QLabel(f"<span style='font-size:26px;font-weight:bold;color:#5B4E8C'>{APP_TITLE}</span>"
                   f"<br><span style='color:#8A86A8'>用眼睛當滑鼠　v{APP_VERSION}</span>")
        head.addWidget(t, 1)
        root.addLayout(head)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)
        tabs.addTab(self._tab_home(), "主畫面")
        tabs.addTab(self._tab_settings(), "設定")
        tabs.addTab(self._tab_about(), "說明與更新")

        ctl.status_changed.connect(self._status)
        self._status(ctl.status_text())
        self.prev_timer = QTimer(self)
        self.prev_timer.timeout.connect(self._preview)
        self.prev_timer.start(100)

    # ------------------------------------------------------------ 主畫面
    def _tab_home(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("background:#ECE8FF;border-radius:12px;padding:12px;font-size:16px;")
        v.addWidget(self.status)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setFixedHeight(190)
        v.addWidget(self.preview)
        g = QGridLayout()
        btns = [
            ("校正視線", "primary", self.calibrate.emit),
            ("動畫教學", "", self.tutorial.emit),
            ("眼動評估", "", self.assess.emit),
            ("暫停 / 繼續", "", lambda: self.ctl.toggle_pause()),
            ("隱藏工具列", "", self._toggle_toolbar),
            ("結束眼動鼠", "danger", self.quit_app.emit),
        ]
        for i, (label, obj, fn) in enumerate(btns):
            b = QPushButton(label)
            b.setObjectName(obj)
            b.setMinimumHeight(64)
            b.clicked.connect(fn)
            g.addWidget(b, i // 3, i % 3)
        v.addLayout(g)
        tip = QLabel("小提示：Ctrl＋Alt＋P 暫停／繼續；照顧者移動實體滑鼠時，眼動鼠會自動讓手 1.5 秒。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#8A86A8")
        v.addWidget(tip)
        v.addStretch(1)
        return w

    def _toggle_toolbar(self):
        tb = self.ctl.toolbar
        tb.setVisible(not tb.isVisible())

    def _status(self, text):
        self.status.setText(f"<b>狀態：</b>{text}")

    def _preview(self):
        src = self.ctl.source
        img = getattr(src, "preview", None) if src else None
        if img is None or not self.isVisible():
            if src and src.key.startswith("tobii"):
                self.preview.setText("Tobii 眼動儀：請在 Tobii Experience 完成第一次校正，之後可用「校正視線」微調。")
            elif src and src.key == "mouse":
                self.preview.setText("滑鼠模擬模式：把游標停在目標上即可觸發點擊（測試用）。")
            return
        h, w = img.shape[:2]
        q = QImage(img.data, w, h, w * 3, QImage.Format_BGR888)
        self.preview.setPixmap(QPixmap.fromImage(q.copy()).scaledToHeight(180, Qt.SmoothTransformation))

    # ------------------------------------------------------------ 設定
    def _slider(self, lo, hi, val, fmt, step=1):
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        sl = QSlider(Qt.Horizontal)
        sl.setRange(lo, hi)
        sl.setSingleStep(step)
        sl.setPageStep(step * 5)
        sl.setValue(val)
        lab = QLabel(fmt(val))
        lab.setMinimumWidth(80)
        sl.valueChanged.connect(lambda v: lab.setText(fmt(v)))
        h.addWidget(sl, 1)
        h.addWidget(lab)
        return box, sl

    def _tab_settings(self):
        s = self.s
        w = QWidget()
        v = QVBoxLayout(w)
        g1 = QGroupBox("視線來源")
        f1 = QFormLayout(g1)
        self.src = QComboBox()
        for k, t in SOURCE_TITLES.items():
            if sys.platform != "win32" and k.startswith("tobii"):
                continue
            self.src.addItem(t, k)
        self.src.setCurrentIndex(max(0, self.src.findData(s.source)))
        f1.addRow("來源", self.src)
        self.cam = QComboBox()
        for i in range(4):
            self.cam.addItem(f"攝影機 {i + 1}", i)
        self.cam.setCurrentIndex(s.camera_index)
        f1.addRow("攝影機", self.cam)
        b, self.gain = self._slider(5, 30, int(s.head_gain * 10), lambda v: f"{v / 10:.1f} 倍")
        f1.addRow("頭控靈敏度", b)
        v.addWidget(g1)

        g2 = QGroupBox("停留點擊")
        f2 = QFormLayout(g2)
        b, self.dwell = self._slider(300, 3000, s.dwell_ms, lambda v: f"{v / 1000:.1f} 秒", 100)
        f2.addRow("停留時間", b)
        b, self.radius = self._slider(20, 140, s.radius, lambda v: f"{v} 像素")
        f2.addRow("停留範圍", b)
        b, self.smooth = self._slider(0, 100, s.smoothing, lambda v: f"{v}")
        f2.addRow("平滑（防抖）", b)
        b, self.cool = self._slider(200, 2500, s.cooldown_ms, lambda v: f"{v / 1000:.1f} 秒", 100)
        f2.addRow("點完冷卻", b)
        b, self.scroll = self._slider(1, 15, s.scroll_speed, lambda v: f"{v}")
        f2.addRow("捲動速度", b)
        self.zoom = QCheckBox("放大鏡精準點擊（先放大那一區，再盯著要點的位置；小按鈕也點得準）")
        self.zoom.setChecked(s.zoom_click)
        f2.addRow(self.zoom)
        self.sticky = QCheckBox("右鍵、雙擊、拖曳用完後保留該模式（不自動回左鍵）")
        self.sticky.setChecked(s.sticky_modes)
        f2.addRow(self.sticky)
        self.follow = QCheckBox("系統游標跟著視線移動")
        self.follow.setChecked(s.move_cursor)
        f2.addRow(self.follow)
        v.addWidget(g2)

        g3 = QGroupBox("外觀與聲音")
        f3 = QFormLayout(g3)
        b, self.csize = self._slider(56, 200, s.cursor_size, lambda v: f"{v}")
        f3.addRow("眼動鼠大小", b)
        b, self.bsize = self._slider(60, 160, s.toolbar_button, lambda v: f"{v}")
        f3.addRow("工具列按鈕", b)
        self.side = QComboBox()
        self.side.addItem("右側", "right")
        self.side.addItem("左側", "left")
        self.side.setCurrentIndex(0 if s.toolbar_side == "right" else 1)
        f3.addRow("工具列位置", self.side)
        self.kbtype = QComboBox()
        self.kbtype.addItem("眼動鼠眼控鍵盤（可調大小，注音＋英文）", "eyemouse")
        if sys.platform == "win32":
            self.kbtype.addItem("Windows 觸控鍵盤", "windows")
        self.kbtype.setCurrentIndex(max(0, self.kbtype.findData(s.keyboard_type)))
        f3.addRow("鍵盤", self.kbtype)
        b, self.kbw = self._slider(30, 100, s.kb_width, lambda v: f"螢幕寬 {v}%")
        f3.addRow("鍵盤大小", b)
        b, self.kbd = self._slider(300, 2500, s.kb_dwell_ms, lambda v: f"{v / 1000:.1f} 秒", 100)
        f3.addRow("按鍵停留", b)
        self.sound = QCheckBox("點擊音效")
        self.sound.setChecked(s.sound)
        self.voice = QCheckBox("語音提示（中文）")
        self.voice.setChecked(s.voice)
        row = QHBoxLayout()
        row.addWidget(self.sound)
        row.addWidget(self.voice)
        f3.addRow(row)
        v.addWidget(g3)

        h = QHBoxLayout()
        h.addStretch(1)
        clr = QPushButton("清除目前來源的校正")
        clr.clicked.connect(self._clear_calib)
        h.addWidget(clr)
        ok = QPushButton("儲存設定")
        ok.setObjectName("primary")
        ok.clicked.connect(self._save)
        h.addWidget(ok)
        v.addLayout(h)
        return w

    def _clear_calib(self):
        if self.ctl.source:
            self.s.calib.pop(self.ctl.source.key, None)
            self.s.save()
            self.ctl.reload_calibration()

    def _save(self):
        s = self.s
        s.source = self.src.currentData()
        s.camera_index = self.cam.currentData()
        s.head_gain = self.gain.value() / 10
        s.dwell_ms = self.dwell.value()
        s.radius = self.radius.value()
        s.smoothing = self.smooth.value()
        s.cooldown_ms = self.cool.value()
        s.scroll_speed = self.scroll.value()
        s.sticky_modes = self.sticky.isChecked()
        s.zoom_click = self.zoom.isChecked()
        s.keyboard_type = self.kbtype.currentData()
        s.kb_width = self.kbw.value()
        s.kb_dwell_ms = self.kbd.value()
        s.move_cursor = self.follow.isChecked()
        s.cursor_size = self.csize.value()
        s.toolbar_button = self.bsize.value()
        s.toolbar_side = self.side.currentData()
        s.sound = self.sound.isChecked()
        s.voice = self.voice.isChecked()
        restart_src = self.ctl.source and (s.camera_index != getattr(self.ctl.source, "camera_index", s.camera_index))
        if restart_src:
            self.ctl.source_key = None
        s.save()
        self.ctl.apply_settings()
        self.ctl.audio.sfx("select")

    # ------------------------------------------------------------ 說明
    def _tab_about(self):
        w = QWidget()
        v = QVBoxLayout(w)
        txt = QLabel(
            "<h3 style='color:#5B4E8C'>怎麼用</h3>"
            "<ol>"
            "<li><b>看哪裡，游標就到哪裡</b>：眼動鼠的光環跟著視線走。</li>"
            "<li><b>停留就點擊</b>：盯著目標不動，光環轉滿一圈就按下去。</li>"
            "<li><b>工具列</b>（螢幕右側）：看著按鈕停留即可切換<b>左鍵、雙擊、右鍵、拖曳、捲動</b>。</li>"
            "<li><b>拖曳</b>：第一次停留＝按住，移動視線，第二次停留＝放開。</li>"
            "<li><b>捲動</b>：停留後往上方／下方看就會捲動，回來看中間圓圈結束。</li>"
            "<li><b>暫停</b>：休息時看「暫停」，要用時再看「繼續」。</li>"
            "</ol>"
            "<p>Windows 使用 Tobii Eye Tracker 5（請先安裝 Tobii Experience 並完成校正）；"
            "Mac 不支援 Tobii 5，改用內建攝影機（建議用「頭控」較穩定）。</p>"
            "<p style='color:#8A86A8'>系統開發：吳玉柱 先生 與 Claude AI Opus 5.5<br>"
            "創意起源：「Eye 讓生活改變」病房團隊</p>")
        txt.setWordWrap(True)
        txt.setTextFormat(Qt.RichText)
        v.addWidget(txt)
        h = QHBoxLayout()
        b1 = QPushButton("播放動畫教學")
        b1.setObjectName("primary")
        b1.clicked.connect(self.tutorial.emit)
        b2 = QPushButton("檢查更新")
        b2.clicked.connect(self.check_update.emit)
        h.addWidget(b1)
        h.addWidget(b2)
        v.addLayout(h)
        self.auto_upd = QCheckBox("啟動時自動檢查更新")
        self.auto_upd.setChecked(self.s.auto_update)
        self.auto_upd.toggled.connect(self._auto_upd)
        v.addWidget(self.auto_upd)
        v.addStretch(1)
        return w

    def _auto_upd(self, on):
        self.s.auto_update = on
        self.s.save()
