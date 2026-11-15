#!/usr/bin/env bash
# 在 Mac「終端機」執行（SSH 連線時鑰匙圈鎖住，codesign 會 errSecInternalComponent）：
#   bash tools/sign_mac.sh [--install]
# 用 Developer ID 重新簽章 dist/眼動鼠.app、重做 dmg；--install 另外裝到 /Applications 並開啟。
set -euo pipefail
cd "$(dirname "$0")/.."
APP="dist/眼動鼠.app"
IDENT=$(bash tools/find_ident.sh)
[ -n "$IDENT" ] || { echo "找不到 Developer ID Application 憑證"; exit 1; }
codesign --force --deep --timestamp=none -s "$IDENT" "$APP"
codesign --verify --deep --strict "$APP"
codesign -dv "$APP" 2>&1 | grep -E "Authority=Developer|TeamIdentifier"
rm -rf dmg_tmp && mkdir dmg_tmp
ditto "$APP" "dmg_tmp/眼動鼠.app"
ln -s /Applications dmg_tmp/Applications
cp mac/README_MAC.txt "dmg_tmp/第一次開啟請看這裡.txt"
rm -f dist-installer/EyeMouse-macOS.dmg
hdiutil create -volname "眼動鼠" -srcfolder dmg_tmp -ov -format UDZO dist-installer/EyeMouse-macOS.dmg
rm -rf dmg_tmp
if [ "${1:-}" = "--install" ]; then
  pkill -x EyeMouse || true
  sleep 1
  rm -rf "/Applications/眼動鼠.app"
  ditto "$APP" "/Applications/眼動鼠.app"
  open -a "/Applications/眼動鼠.app" --args --no-update
fi
echo "SIGN_OK"
