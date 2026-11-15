#!/usr/bin/env bash
# macOS 建置（Apple 晶片／Intel 皆可）：bash tools/build_mac.sh → dist-installer/EyeMouse-macOS.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
VER=$(tr -d '\r\n' < VERSION)
echo "== 眼動鼠 macOS v$VER ($(uname -m)) =="
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
[ -d .venv ] || uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -q -r requirements.txt
export QT_QPA_PLATFORM=offscreen
python tests/test_controller.py
python eyemouse.py --selftest
unset QT_QPA_PLATFORM
iconutil -c icns mac/icon.iconset -o mac/EyeMouse.icns
rm -rf build dist
python -m PyInstaller EyeMouse.spec --noconfirm --clean
APP="dist/眼動鼠.app"
# 用 Developer ID 簽章：程式身分固定，更新後「輔助使用」「相機」權限可以沿用；沒有憑證才用臨時簽章
IDENT=$(security find-identity -v -p codesigning 2>/dev/null | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*//p' | head -1)
if [ -n "$IDENT" ] && codesign --force --deep --timestamp=none -s "$IDENT" "$APP"; then
  echo "已用 $IDENT 簽章"
else
  echo "改用臨時簽章（ad-hoc）"; codesign --force --deep -s - "$APP"
fi
codesign -dv "$APP" 2>&1 | grep -E "Authority|TeamIdentifier|Identifier" | head -3
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/EyeMouse" --selftest --out dist/selftest.log || true
grep -q "SELFTEST OK" dist/selftest.log || { cat dist/selftest.log; echo "打包後自我測試失敗"; exit 1; }
mkdir -p dist-installer dmg_tmp
rm -rf dmg_tmp/*
ditto "$APP" "dmg_tmp/眼動鼠.app"
ln -s /Applications dmg_tmp/Applications
cp mac/README_MAC.txt "dmg_tmp/第一次開啟請看這裡.txt"
rm -f dist-installer/EyeMouse-macOS.dmg
hdiutil create -volname "眼動鼠" -srcfolder dmg_tmp -ov -format UDZO dist-installer/EyeMouse-macOS.dmg
rm -rf dmg_tmp
ls -lh dist-installer
