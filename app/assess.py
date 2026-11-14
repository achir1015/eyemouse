"""眼動評估：播放圖片素材並錄下視線，分析注視順序、熱點、興趣區（AOI），匯出影片/CSV/圖片。"""
import csv
import json
import os
import shutil
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDoubleSpinBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMessageBox, QPushButton, QSlider, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from . import art
from .config import data_dir
from .overlay import _font
from .panel import STYLE


# ================================================================ 分析演算法
def fixations_idt(samples, max_disp=0.035, min_dur=0.10):
    """I-DT 注視偵測。samples: [(t, u, v)]，u/v 為圖片內 0~1 座標。回傳 [(start, dur, u, v)]。"""
    out = []
    i, n = 0, len(samples)
    while i < n:
        j = i
        while j < n and samples[j][0] - samples[i][0] < min_dur:
            j += 1
        if j >= n:
            break
        win = samples[i:j + 1]
        us, vs = [s[1] for s in win], [s[2] for s in win]
        if (max(us) - min(us)) + (max(vs) - min(vs)) <= max_disp:
            while j + 1 < n:
                us.append(samples[j + 1][1])
                vs.append(samples[j + 1][2])
                if (max(us) - min(us)) + (max(vs) - min(vs)) > max_disp:
                    us.pop()
                    vs.pop()
                    break
                j += 1
            st = samples[i][0]
            out.append((st, samples[j][0] - st, sum(us) / len(us), sum(vs) / len(vs)))
            i = j + 1
        else:
            i += 1
    return out


def aoi_stats(fix, aois, total):
    rows = []
    for a in aois:
        x, y, w, h = a["rect"]
        inside = [f for f in fix if x <= f[2] <= x + w and y <= f[3] <= y + h]
        visits, prev = 0, False
        for f in fix:
            cur = x <= f[2] <= x + w and y <= f[3] <= y + h
            if cur and not prev:
                visits += 1
            prev = cur
        dwell = sum(f[1] for f in inside)
        rows.append({
            "名稱": a["name"],
            "首次注視時間(秒)": f"{inside[0][0]:.2f}" if inside else "—",
            "首次注視長度(秒)": f"{inside[0][1]:.2f}" if inside else "—",
            "注視總時間(秒)": f"{dwell:.2f}",
            "注視次數": str(len(inside)),
            "造訪次數": str(visits),
            "停留比例": f"{dwell / total * 100:.0f}%" if total > 0 else "—",
        })
    return rows


# ================================================================ 內建素材
def _sample_images(folder):
    os.makedirs(folder, exist_ok=True)
    files = []
    W, H = 1600, 900

    def save(name, painter_fn):
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            img = QImage(W, H, QImage.Format_RGB32)
            img.fill(QColor("#FFFFFF"))
            qp = QPainter(img)
            qp.setRenderHint(QPainter.Antialiasing)
            painter_fn(qp)
            qp.end()
            img.save(p)
        files.append(p)

    def grid(qp):
        qp.fillRect(0, 0, W, H, QColor("#FFF8EC"))
        cols = ["#D9D4F2", "#FFD6A5", "#CDEBC5", "#BDE0FE", "#FFC8DD", "#E2ECE9", "#FDE2E4", "#CDB4DB", "#FFFFC7"]
        for i in range(9):
            cx, cy = 300 + (i % 3) * 500, 160 + (i // 3) * 290
            qp.setPen(QPen(QColor("#B9A7FF"), 4))
            qp.setBrush(QColor(cols[i]))
            qp.drawRoundedRect(QRectF(cx - 220, cy - 125, 440, 250), 30, 30)
            art.draw_mouse(qp, QPointF(cx, cy + 10), 80, look=((i % 3) - 1, (i // 3) - 1), happy=i == 4)

    def house(qp):
        qp.fillRect(0, 0, W, H, QColor("#CFE9FF"))
        qp.fillRect(0, 620, W, 280, QColor("#9ED99B"))
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor("#FFD36E"))
        qp.drawEllipse(QPointF(1350, 150), 90, 90)
        qp.setBrush(QColor("#FF9F8A"))
        qp.drawRect(QRectF(600, 360, 420, 320))
        path = QPainterPath(QPointF(560, 370))
        path.lineTo(810, 170)
        path.lineTo(1060, 370)
        path.closeSubpath()
        qp.setBrush(QColor("#B4553D"))
        qp.drawPath(path)
        qp.setBrush(QColor("#8B5E3C"))
        qp.drawRect(QRectF(770, 520, 90, 160))
        qp.setBrush(QColor("#BDE0FE"))
        qp.drawRect(QRectF(650, 420, 90, 80))
        qp.drawRect(QRectF(890, 420, 90, 80))
        qp.setBrush(QColor("#5DAE5A"))
        qp.drawEllipse(QPointF(280, 450), 150, 170)
        qp.setBrush(QColor("#8B5E3C"))
        qp.drawRect(QRectF(255, 590, 50, 120))
        art.draw_mouse(qp, QPointF(1250, 680), 70, look=(-1, 0))

    def reading(qp):
        qp.fillRect(0, 0, W, H, QColor("#FFFFFF"))
        f = QFont()
        f.setFamilies(["Microsoft JhengHei UI", "PingFang TC", "Heiti TC"])
        f.setPixelSize(54)
        qp.setFont(f)
        qp.setPen(QColor("#2E2A47"))
        lines = ["今天天氣很好，", "我想喝一杯溫開水，", "請幫我把枕頭墊高一點，", "謝謝你的照顧！"]
        for i, s in enumerate(lines):
            qp.drawText(160, 230 + i * 150, s)

    save("01_九宮格.png", grid)
    save("02_房子.png", house)
    save("03_閱讀.png", reading)
    return files


# ================================================================ 全螢幕播放
class Presenter(QWidget):
    finished = Signal(list)   # [{"image":path, "samples":[(t,u,v)], "dur":秒}]

    def __init__(self, ctl, images, secs):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.ctl = ctl
        self.images = images
        self.secs = secs
        self.idx = -1
        self.results = []
        self.cur = None
        g = ctl.screen().geometry()
        self.setGeometry(g)
        self.setCursor(Qt.BlankCursor)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.phase = "count"
        self.t0 = time.monotonic()

    def start(self):
        self.ctl.capture_only = True
        self.ctl.toolbar.hide()
        self.ctl.gaze_sample.connect(self._sample)
        self.show()
        self.raise_()
        self.ctl.audio.say("assess_start")
        self.timer.start(30)

    def _img_rect(self):
        if self.cur is None:
            return QRectF()
        w, h = self.width(), self.height()
        iw, ih = self.cur.width(), self.cur.height()
        k = min(w / iw, h / ih)
        return QRectF((w - iw * k) / 2, (h - ih * k) / 2, iw * k, ih * k)

    def _sample(self, t, x, y):
        if self.phase != "show":
            return
        r = self._img_rect()
        lx, ly = x - self.x(), y - self.y()
        u, v = (lx - r.left()) / r.width(), (ly - r.top()) / r.height()
        self.results[-1]["samples"].append((round(t - self.t0, 4), round(u, 5), round(v, 5)))

    def _tick(self):
        el = time.monotonic() - self.t0
        if self.phase == "count" and el > 3.0:
            self._next()
        elif self.phase == "show" and el > self.secs:
            self.results[-1]["dur"] = el
            self._next()
        self.update()

    def _next(self):
        self.idx += 1
        if self.idx >= len(self.images):
            self._end()
            return
        self.cur = QImage(self.images[self.idx])
        self.results.append({"image": self.images[self.idx], "samples": [], "dur": self.secs})
        self.phase = "show"
        self.t0 = time.monotonic()

    def _end(self, cancelled=False):
        self.timer.stop()
        try:
            self.ctl.gaze_sample.disconnect(self._sample)
        except (RuntimeError, TypeError):
            pass
        self.ctl.capture_only = False
        self.ctl.toolbar.show()
        self.close()
        if not cancelled:
            self.ctl.audio.say("assess_done")
            self.finished.emit(self.results)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._end(cancelled=True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1B1836"))
        if self.phase == "count":
            n = 3 - int(time.monotonic() - self.t0)
            p.setPen(QColor("#FFFFFF"))
            p.setFont(_font(120))
            p.drawText(self.rect(), Qt.AlignCenter, str(max(1, n)))
            p.setFont(_font(28))
            p.drawText(QRectF(0, self.height() * 0.7, self.width(), 60), Qt.AlignCenter, "請自然地看畫面（按 Esc 取消）")
            return
        if self.cur is not None:
            p.setRenderHint(QPainter.SmoothPixmapTransform)
            p.drawImage(self._img_rect(), self.cur)


# ================================================================ 分析畫布
class AnalysisView(QWidget):
    aoi_added = Signal()

    def __init__(self):
        super().__init__()
        self.img = None
        self.samples = []
        self.fix = []
        self.aois = []
        self.mode = "plot"
        self.time = None          # 回放時間（None = 全部）
        self._drag = None
        self.setMinimumSize(560, 340)
        self.setMouseTracking(True)

    def set_data(self, img_path, samples, fix, aois):
        self.img = QImage(img_path) if img_path and os.path.exists(img_path) else None
        self.samples, self.fix, self.aois = samples, fix, aois
        self.update()

    def img_rect(self, w=None, h=None):
        w = w or self.width()
        h = h or self.height()
        if not self.img:
            return QRectF(0, 0, w, h)
        iw, ih = self.img.width(), self.img.height()
        k = min(w / iw, h / ih)
        return QRectF((w - iw * k) / 2, (h - ih * k) / 2, iw * k, ih * k)

    def mousePressEvent(self, e):
        if self.mode == "aoi" and self.img:
            self._drag = [e.position(), e.position()]

    def mouseMoveEvent(self, e):
        if self._drag:
            self._drag[1] = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._drag:
            return
        a, b = self._drag
        self._drag = None
        r = self.img_rect()
        x0, x1 = sorted([(a.x() - r.left()) / r.width(), (b.x() - r.left()) / r.width()])
        y0, y1 = sorted([(a.y() - r.top()) / r.height(), (b.y() - r.top()) / r.height()])
        if (x1 - x0) * r.width() < 12 or (y1 - y0) * r.height() < 12:
            self.update()
            return
        name, ok = QInputDialog.getText(self, "興趣區", "興趣區名稱：", text=f"區域 {len(self.aois) + 1}")
        if ok:
            self.aois.append({"name": name or f"區域 {len(self.aois) + 1}", "rect": [x0, y0, x1 - x0, y1 - y0]})
            self.aoi_added.emit()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#24203F"))
        render(p, self.img_rect(), self.img, self.samples, self.fix, self.aois, self.mode, self.time)
        if self._drag:
            a, b = self._drag
            p.setPen(QPen(QColor("#FFD36E"), 2, Qt.DashLine))
            p.setBrush(QColor(255, 211, 110, 50))
            p.drawRect(QRectF(a, b).normalized())


def render(p: QPainter, r: QRectF, img, samples, fix, aois, mode, upto=None):
    """畫刺激圖＋分析圖層（畫面與匯出共用）。"""
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    if img:
        p.drawImage(r, img)
    if upto is not None:
        samples = [s for s in samples if s[0] <= upto]
        fix = [f for f in fix if f[0] <= upto]
    pt = lambda u, v: QPointF(r.left() + u * r.width(), r.top() + v * r.height())  # noqa: E731
    scale = r.width() / 1600
    if mode == "heat":
        p.fillRect(r, QColor(0, 0, 0, 60))
        if fix:
            mx = max(f[1] for f in fix)
            for f in fix:
                c = pt(f[2], f[3])
                rad = (60 + 140 * f[1] / mx) * scale + 10
                g = QRadialGradient(c, rad)
                a = int(40 + 120 * f[1] / mx)
                g.setColorAt(0, QColor(255, 40, 0, a))
                g.setColorAt(0.45, QColor(255, 200, 0, int(a * 0.6)))
                g.setColorAt(1, QColor(0, 255, 0, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(g)
                p.drawEllipse(c, rad, rad)
    elif mode == "raw":
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(79, 163, 255, 140))
        for s in samples:
            p.drawEllipse(pt(s[1], s[2]), 3, 3)
    else:  # plot / aoi
        if len(fix) > 1:
            p.setPen(QPen(QColor(46, 204, 113, 200), max(1.5, 3 * scale)))
            for a, b in zip(fix, fix[1:]):
                p.drawLine(pt(a[2], a[3]), pt(b[2], b[3]))
        for i, f in enumerate(fix):
            rad = (14 + min(60, f[1] * 40)) * scale + 6
            c = pt(f[2], f[3])
            p.setPen(QPen(QColor("#1E8E4E"), max(1, 2 * scale)))
            p.setBrush(QColor(46, 204, 113, 150))
            p.drawEllipse(c, rad, rad)
            p.setFont(_font(max(9, 20 * scale)))
            p.setPen(QColor("#FFFFFF"))
            p.drawText(QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), Qt.AlignCenter, str(i + 1))
        if upto is not None and samples:
            s = samples[-1]
            art.draw_ring(p, pt(s[1], s[2]), 22 * scale + 8, upto * 200, 0, "#FF8FB8", width=4)
    if mode in ("aoi", "plot"):
        for a in aois:
            x, y, w, h = a["rect"]
            rr = QRectF(pt(x, y), pt(x + w, y + h))
            p.setPen(QPen(QColor("#FFD36E"), 2))
            p.setBrush(QColor(255, 211, 110, 40))
            p.drawRect(rr)
            p.setFont(_font(max(10, 18 * scale)))
            p.setPen(QColor("#FFD36E"))
            p.drawText(rr.adjusted(6, 4, -4, -4), Qt.AlignTop | Qt.AlignLeft, a["name"])


# ================================================================ 主視窗
class AssessWindow(QWidget):
    def __init__(self, ctl):
        super().__init__(None, Qt.Window)
        self.ctl = ctl
        self.setWindowTitle("眼動鼠 眼動評估")
        self.setWindowIcon(art.app_icon())
        self.setStyleSheet(STYLE)
        self.resize(1200, 760)
        self.root = os.path.join(data_dir(), "assess")
        os.makedirs(self.root, exist_ok=True)
        self.session = None
        self.trial = 0
        self.presenter = None

        tabs = QTabWidget()
        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        tabs.addTab(self._tab_record(), "製作與錄製")
        tabs.addTab(self._tab_analyse(), "分析")
        self.tabs = tabs
        self._load_sessions()

    # ---------------- 製作與錄製
    def _tab_record(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("① 素材時間軸（依序全螢幕播放，可拖曳調整順序）"))
        self.stim = QListWidget()
        self.stim.setDragDropMode(QAbstractItemView.InternalMove)
        self.stim.setIconSize(QImage(160, 90, QImage.Format_RGB32).size())
        v.addWidget(self.stim, 1)
        for f in _sample_images(os.path.join(self.root, "_samples")):
            self._add_stim(f)
        h = QHBoxLayout()
        for label, fn in (("加入圖片…", self._pick_images), ("加入目前桌面畫面", self._grab_desktop), ("移除選取", self._remove_stim)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            h.addWidget(b)
        v.addLayout(h)
        h = QHBoxLayout()
        h.addWidget(QLabel("② 受試者："))
        self.who = QLineEdit()
        self.who.setPlaceholderText("例如：王小明　第一次評估")
        h.addWidget(self.who, 1)
        h.addWidget(QLabel("每張秒數："))
        self.secs = QDoubleSpinBox()
        self.secs.setRange(2, 120)
        self.secs.setValue(8)
        h.addWidget(self.secs)
        go = QPushButton("③ 開始錄製")
        go.setObjectName("primary")
        go.clicked.connect(self._start)
        h.addWidget(go)
        v.addLayout(h)
        return w

    def _add_stim(self, path):
        it = QListWidgetItem(os.path.basename(path))
        it.setData(Qt.UserRole, path)
        img = QImage(path)
        if not img.isNull():
            from PySide6.QtGui import QIcon, QPixmap
            it.setIcon(QIcon(QPixmap.fromImage(img.scaled(160, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))))
        self.stim.addItem(it)

    def _pick_images(self):
        files, _ = QFileDialog.getOpenFileNames(self, "選擇圖片", "", "圖片 (*.png *.jpg *.jpeg *.bmp *.webp)")
        for f in files:
            self._add_stim(f)

    def _grab_desktop(self):
        self.hide()
        QTimer.singleShot(400, self._do_grab)

    def _do_grab(self):
        scr = self.ctl.screen()
        pm = scr.grabWindow(0)
        p = os.path.join(self.root, "_samples", time.strftime("桌面_%Y%m%d_%H%M%S.png"))
        pm.save(p)
        self.show()
        self._add_stim(p)

    def _remove_stim(self):
        for it in self.stim.selectedItems():
            self.stim.takeItem(self.stim.row(it))

    def _start(self):
        imgs = [self.stim.item(i).data(Qt.UserRole) for i in range(self.stim.count())]
        if not imgs:
            QMessageBox.information(self, "眼動評估", "請先加入至少一張圖片。")
            return
        if not (self.ctl.source and self.ctl.source.ok):
            if QMessageBox.question(self, "眼動評估", "目前沒有偵測到視線，仍要開始嗎？") != QMessageBox.Yes:
                return
        self.hide()
        self.presenter = Presenter(self.ctl, imgs, self.secs.value())
        self.presenter.finished.connect(self._recorded)
        self.presenter.destroyed.connect(lambda: self.show())
        self.presenter.setAttribute(Qt.WA_DeleteOnClose)
        self.presenter.start()

    def _recorded(self, results):
        sid = time.strftime("%Y%m%d_%H%M%S")
        d = os.path.join(self.root, sid)
        os.makedirs(d, exist_ok=True)
        trials = []
        for i, r in enumerate(results):
            ext = os.path.splitext(r["image"])[1] or ".png"
            name = f"stim_{i + 1:02d}{ext}"
            shutil.copyfile(r["image"], os.path.join(d, name))
            trials.append({"image": name, "title": os.path.basename(r["image"]), "dur": r["dur"],
                           "samples": r["samples"], "aois": []})
        meta = {"subject": self.who.text().strip(), "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": self.ctl.source.title if self.ctl.source else "", "trials": trials}
        with open(os.path.join(d, "session.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        self.show()
        self._load_sessions(select=sid)
        self.tabs.setCurrentIndex(1)

    # ---------------- 分析
    def _tab_analyse(self):
        w = QWidget()
        v = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("紀錄："))
        self.sess = QComboBox()
        self.sess.currentIndexChanged.connect(self._open_session)
        top.addWidget(self.sess, 2)
        top.addWidget(QLabel("素材："))
        self.trial_box = QComboBox()
        self.trial_box.currentIndexChanged.connect(self._open_trial)
        top.addWidget(self.trial_box, 2)
        top.addWidget(QLabel("顯示："))
        self.mode_box = QComboBox()
        for k, t in (("plot", "注視軌跡（編號順序）"), ("heat", "熱點圖"), ("raw", "原始視線點"), ("aoi", "框選興趣區 AOI")):
            self.mode_box.addItem(t, k)
        self.mode_box.currentIndexChanged.connect(self._mode)
        top.addWidget(self.mode_box, 2)
        v.addLayout(top)

        sp = QSplitter(Qt.Vertical)
        self.view = AnalysisView()
        self.view.aoi_added.connect(self._aoi_changed)
        sp.addWidget(self.view)
        bottom = QWidget()
        bv = QVBoxLayout(bottom)
        bv.setContentsMargins(0, 0, 0, 0)
        h = QHBoxLayout()
        self.play_btn = QPushButton("▶ 回放")
        self.play_btn.clicked.connect(self._play)
        h.addWidget(self.play_btn)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.setValue(1000)
        self.slider.valueChanged.connect(self._seek)
        h.addWidget(self.slider, 1)
        self.summary = QLabel()
        h.addWidget(self.summary)
        bv.addLayout(h)
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bv.addWidget(self.table, 1)
        h = QHBoxLayout()
        for label, fn in (("刪除最後一個興趣區", self._del_aoi), ("匯出圖片 PNG", self._export_png),
                          ("匯出資料 CSV", self._export_csv), ("匯出回放影片 MP4", self._export_mp4),
                          ("開啟資料夾", self._open_dir)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            h.addWidget(b)
        bv.addLayout(h)
        sp.addWidget(bottom)
        sp.setSizes([480, 260])
        v.addWidget(sp, 1)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._play_tick)
        return w

    def _load_sessions(self, select=None):
        self.sess.blockSignals(True)
        self.sess.clear()
        for sid in sorted((d for d in os.listdir(self.root) if os.path.isfile(os.path.join(self.root, d, "session.json"))), reverse=True):
            try:
                with open(os.path.join(self.root, sid, "session.json"), encoding="utf-8") as f:
                    m = json.load(f)
                self.sess.addItem(f"{m.get('time', sid)}　{m.get('subject') or '未命名'}", sid)
            except (OSError, ValueError):
                continue
        self.sess.blockSignals(False)
        if select:
            self.sess.setCurrentIndex(max(0, self.sess.findData(select)))
        self._open_session()

    def _open_session(self):
        sid = self.sess.currentData()
        self.session = None
        self.trial_box.blockSignals(True)
        self.trial_box.clear()
        if sid:
            self.sdir = os.path.join(self.root, sid)
            with open(os.path.join(self.sdir, "session.json"), encoding="utf-8") as f:
                self.session = json.load(f)
            for i, t in enumerate(self.session["trials"]):
                self.trial_box.addItem(f"{i + 1}. {t['title']}", i)
        self.trial_box.blockSignals(False)
        self._open_trial()

    def _cur(self):
        if not self.session:
            return None
        i = self.trial_box.currentData()
        return self.session["trials"][i] if i is not None else None

    def _open_trial(self):
        t = self._cur()
        if not t:
            self.view.set_data(None, [], [], [])
            self.summary.setText("尚無紀錄：請先到「製作與錄製」錄一次")
            self._table([])
            return
        samples = [tuple(s) for s in t["samples"] if -0.1 <= s[1] <= 1.1 and -0.1 <= s[2] <= 1.1]
        self.fix = fixations_idt(samples)
        self.samples = samples
        self.view.set_data(os.path.join(self.sdir, t["image"]), samples, self.fix, t["aois"])
        valid = len(samples) / max(1, len(t["samples"])) * 100
        mean = sum(f[1] for f in self.fix) / len(self.fix) if self.fix else 0
        self.summary.setText(f"注視 {len(self.fix)} 次｜平均 {mean:.2f} 秒｜有效視線 {valid:.0f}%")
        self._aoi_changed(save=False)

    def _mode(self):
        self.view.mode = self.mode_box.currentData()
        self.view.update()

    def _aoi_changed(self, save=True):
        t = self._cur()
        if not t:
            return
        self._table(aoi_stats(self.fix, t["aois"], t.get("dur", 1)))
        if save:
            self._save_session()

    def _save_session(self):
        with open(os.path.join(self.sdir, "session.json"), "w", encoding="utf-8") as f:
            json.dump(self.session, f, ensure_ascii=False)

    def _del_aoi(self):
        t = self._cur()
        if t and t["aois"]:
            t["aois"].pop()
            self.view.update()
            self._aoi_changed()

    def _table(self, rows):
        heads = ["名稱", "首次注視時間(秒)", "首次注視長度(秒)", "注視總時間(秒)", "注視次數", "造訪次數", "停留比例"]
        self.table.setColumnCount(len(heads))
        self.table.setHorizontalHeaderLabels(heads)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, k in enumerate(heads):
                self.table.setItem(i, j, QTableWidgetItem(r[k]))

    # ---- 回放
    def _play(self):
        t = self._cur()
        if not t:
            return
        if self.play_timer.isActive():
            self.play_timer.stop()
            self.play_btn.setText("▶ 回放")
            return
        self.play_start = time.monotonic()
        self.play_btn.setText("■ 停止")
        self.play_timer.start(33)

    def _play_tick(self):
        t = self._cur()
        dur = t.get("dur", 1)
        el = time.monotonic() - self.play_start
        if el >= dur:
            self.play_timer.stop()
            self.play_btn.setText("▶ 回放")
            self.slider.setValue(1000)
            return
        self.slider.setValue(int(el / dur * 1000))

    def _seek(self, v):
        t = self._cur()
        self.view.time = None if v >= 1000 or not t else v / 1000 * t.get("dur", 1)
        self.view.update()

    # ---- 匯出
    def _base(self):
        t = self._cur()
        return os.path.join(self.sdir, os.path.splitext(t["image"])[0]) if t else None

    def _render_image(self, mode, upto=None, size=(1600, 900)):
        img = QImage(size[0], size[1], QImage.Format_RGB32)
        img.fill(QColor("#24203F"))
        p = QPainter(img)
        src = self.view.img
        r = QRectF(0, 0, *size)
        if src:
            k = min(size[0] / src.width(), size[1] / src.height())
            r = QRectF((size[0] - src.width() * k) / 2, (size[1] - src.height() * k) / 2, src.width() * k, src.height() * k)
        render(p, r, src, self.samples, self.fix, self._cur()["aois"], mode, upto)
        p.end()
        return img

    def _export_png(self):
        b = self._base()
        if not b:
            return
        for m in ("plot", "heat"):
            self._render_image(m).save(f"{b}_{'注視軌跡' if m == 'plot' else '熱點圖'}.png")
        QMessageBox.information(self, "匯出", "已匯出注視軌跡與熱點圖 PNG 到紀錄資料夾。")
        self._open_dir()

    def _export_csv(self):
        b = self._base()
        if not b:
            return
        t = self._cur()
        with open(f"{b}_視線.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["時間(秒)", "X(0~1)", "Y(0~1)"])
            w.writerows(t["samples"])
        with open(f"{b}_注視.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["順序", "開始(秒)", "長度(秒)", "X(0~1)", "Y(0~1)"])
            for i, x in enumerate(self.fix):
                w.writerow([i + 1, f"{x[0]:.3f}", f"{x[1]:.3f}", f"{x[2]:.4f}", f"{x[3]:.4f}"])
        rows = aoi_stats(self.fix, t["aois"], t.get("dur", 1))
        if rows:
            with open(f"{b}_興趣區.csv", "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
        QMessageBox.information(self, "匯出", "已匯出 CSV（視線、注視、興趣區）到紀錄資料夾。")
        self._open_dir()

    def _export_mp4(self):
        b = self._base()
        if not b:
            return
        import cv2
        t = self._cur()
        fps, dur = 30, t.get("dur", 1)
        W, H = 1280, 720
        path = f"{b}_回放.mp4"
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
        n = int(dur * fps) + fps
        for i in range(n):
            img = self._render_image("plot", upto=min(dur, i / fps), size=(W, H)).convertToFormat(QImage.Format_RGB888)
            arr = np.frombuffer(img.constBits(), np.uint8).reshape(H, img.bytesPerLine())[:, :W * 3].reshape(H, W, 3)
            vw.write(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        vw.release()
        QMessageBox.information(self, "匯出", f"已匯出回放影片：\n{path}")
        self._open_dir()

    def _open_dir(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if getattr(self, "sdir", None):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.sdir))

    def closeEvent(self, e):
        self.play_timer.stop()
        super().closeEvent(e)

