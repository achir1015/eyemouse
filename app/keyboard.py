"""螢幕鍵盤：Windows 用觸控鍵盤（ITipInvocation COM 切換，按鍵大、有注音），失敗才試 osk；Mac 開輔助使用鍵盤設定。

osk.exe 需要 UIAccess 啟動，在部分 Windows（實測 Insider build 26300）會失敗：
「從伺服器傳回一個轉介」（錯誤 8235），所以不再以它為主。
"""
import os
import subprocess
import sys
import time

TABTIP = os.path.join(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"),
                      "microsoft shared", "ink", "TabTip.exe")


def _toggle_touch_keyboard():
    import ctypes
    from ctypes import wintypes

    ole32 = ctypes.OleDLL("ole32")

    class GUID(ctypes.Structure):
        _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    def guid(s):
        g = GUID()
        ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(g))
        return g

    try:
        ole32.CoInitialize(None)
    except OSError:
        pass  # 已初始化（Qt 主執行緒）
    clsid = guid("{4CE576FA-83DC-4F88-951C-9D0782B4E376}")   # UIHostNoLaunch
    iid = guid("{37C994E7-432B-4834-A2F7-DCE1F13B834B}")     # ITipInvocation
    p = ctypes.c_void_p()
    ole32.CoCreateInstance(ctypes.byref(clsid), None, 4, ctypes.byref(iid), ctypes.byref(p))  # 4 = LOCAL_SERVER
    vtbl = ctypes.cast(ctypes.cast(p, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    toggle = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, wintypes.HWND)(vtbl[3])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
    try:
        toggle(p, ctypes.windll.user32.GetDesktopWindow())
    finally:
        release(p)


def toggle_keyboard():
    """切換螢幕鍵盤。回傳使用的方式（'touch'／'osk'／'mac'），全部失敗回傳 None（不跳錯誤視窗）。"""
    if sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.universalaccess?Keyboard"])
            return "mac"
        except OSError:
            return None
    if sys.platform != "win32":
        return None
    try:
        _toggle_touch_keyboard()
        return "touch"
    except OSError:
        pass
    # 觸控鍵盤服務還沒啟動：先叫起 TabTip 再試一次
    try:
        if os.path.exists(TABTIP):
            os.startfile(TABTIP)
            time.sleep(0.6)
            _toggle_touch_keyboard()
            return "touch"
    except OSError:
        pass
    try:
        os.startfile("osk.exe")
        return "osk"
    except OSError:
        return None
