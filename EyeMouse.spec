# PyInstaller 設定（Windows 與 macOS 共用）：pyinstaller EyeMouse.spec --noconfirm
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = [("assets/face_landmarker.task", "assets"), ("assets/voice", "assets/voice"), ("assets/icon.png", "assets"), ("VERSION", ".")]
datas += collect_data_files("mediapipe", includes=["**/*.binarypb", "**/*.tflite", "**/*.txt"])
binaries = collect_dynamic_libs("mediapipe")
hidden = ["pynput.mouse._win32", "pynput.keyboard._win32"] if sys.platform == "win32" else \
         ["pynput.mouse._darwin", "pynput.keyboard._darwin"]

a = Analysis(["eyemouse.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=["tkinter"] + ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
                       "PySide6.Qt3DCore", "PySide6.QtQuick3D", "PySide6.QtPdf", "PySide6.QtCharts",
                       "PySide6.QtDataVisualization", "PySide6.QtDesigner", "torch", "tensorflow", "jax"],
             noarchive=False)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EyeMouse", console=False, argv_emulation=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="EyeMouse")
    app = BUNDLE(coll, name="眼動鼠.app", icon="mac/EyeMouse.icns", bundle_identifier="com.achir.eyemouse",
                 info_plist={
                     "CFBundleDisplayName": "眼動鼠",
                     "CFBundleShortVersionString": open("VERSION").read().strip(),
                     "CFBundleVersion": open("VERSION").read().strip(),
                     "NSCameraUsageDescription": "眼動鼠需要使用攝影機追蹤您的眼睛與頭部，用來移動滑鼠游標。影像只在本機處理，不會上傳。",
                     "NSHighResolutionCapable": True,
                     "LSUIElement": False,
                     "LSMinimumSystemVersion": "11.0",
                 })
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EyeMouse", console=False,
              icon="windows/app.ico", version="windows/version_info.txt")
    coll = COLLECT(exe, a.binaries, a.datas, name="EyeMouse")
