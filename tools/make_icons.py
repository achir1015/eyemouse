"""產生 App 圖示：windows/app.ico、assets/icon.png、mac/icon.icns 用的 PNG 組。"""
import io, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication
from PIL import Image
app = QApplication([])
from app.art import render_icon

def pil(size):
    buf = QBuffer(); buf.open(QIODevice.WriteOnly); render_icon(size).save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data())))

big = pil(1024)
big.save(os.path.join(ROOT, "assets", "icon.png"))
pil(256).save(os.path.join(ROOT, "windows", "app.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
os.makedirs(os.path.join(ROOT, "mac", "icon.iconset"), exist_ok=True)
for s in (16, 32, 128, 256, 512):
    pil(s).save(os.path.join(ROOT, "mac", "icon.iconset", f"icon_{s}x{s}.png"))
    pil(s * 2).save(os.path.join(ROOT, "mac", "icon.iconset", f"icon_{s}x{s}@2x.png"))
print("icons ok")
