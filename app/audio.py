"""音效與語音（預先產生的台灣華語語音檔）。"""
import math
import os
import struct
import wave

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QSoundEffect

from .config import data_dir, resource_path


def _make_wav(path, notes, vol=0.35, rate=44100):
    frames = bytearray()
    for freq, dur in notes:
        n = int(rate * dur)
        for i in range(n):
            t = i / rate
            env = min(1.0, i / (rate * 0.005)) * math.exp(-5.0 * t / dur)
            s = vol * env * (math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t))
            frames += struct.pack("<h", int(max(-1, min(1, s)) * 32767))
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


SFX = {
    "click": [(1046, 0.07), (1568, 0.09)],
    "double": [(1046, 0.06), (1318, 0.06), (1568, 0.08)],
    "right": [(784, 0.08), (659, 0.1)],
    "press": [(523, 0.12)],
    "release": [(784, 0.1)],
    "select": [(1318, 0.08)],
    "pause": [(659, 0.1), (440, 0.14)],
    "resume": [(440, 0.08), (880, 0.12)],
}


class Audio:
    def __init__(self):
        self.enabled = True
        self.voice_enabled = True
        d = os.path.join(data_dir(), "sfx")
        os.makedirs(d, exist_ok=True)
        self.fx = {}
        for k, notes in SFX.items():
            p = os.path.join(d, f"{k}.wav")
            if not os.path.exists(p):
                _make_wav(p, notes)
            e = QSoundEffect()
            e.setSource(QUrl.fromLocalFile(p))
            e.setVolume(0.6)
            self.fx[k] = e
        self.out = QAudioOutput()
        self.out.setVolume(1.0)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.out)

    def sfx(self, k):
        if self.enabled and k in self.fx:
            self.fx[k].play()

    def voice_path(self, name):
        p = resource_path("assets", "voice", f"{name}.mp3")
        return p if os.path.exists(p) else None

    def say(self, name, force=False):
        """播放語音檔 assets/voice/<name>.mp3。"""
        if not (self.voice_enabled or force):
            return False
        p = self.voice_path(name)
        if not p:
            return False
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(p))
        self.player.play()
        return True

    def stop_voice(self):
        self.player.stop()

    def speaking(self):
        return self.player.playbackState() == QMediaPlayer.PlayingState
