#!/usr/bin/env bash
# Windows 建置：自我測試 → PyInstaller → Inno Setup → dist-installer/EyeMouse-Setup.exe ＋ portable zip
set -euo pipefail
cd "$(dirname "$0")/.."
VER=$(tr -d '\r\n' < VERSION)
echo "== 眼動鼠 v$VER =="
python tools/gen_voice.py
python tools/make_icons.py
python tests/test_controller.py
python eyemouse.py --selftest
IFS=. read -r A B C <<< "$VER"
cat > windows/version_info.txt <<EOF
VSVersionInfo(ffi=FixedFileInfo(filevers=($A,$B,$C,0), prodvers=($A,$B,$C,0)),
  kids=[StringFileInfo([StringTable('040404b0', [StringStruct('CompanyName','吳玉柱'),
  StringStruct('FileDescription','眼動鼠'), StringStruct('FileVersion','$VER'),
  StringStruct('ProductName','眼動鼠'), StringStruct('ProductVersion','$VER')])]),
  VarFileInfo([VarStruct('Translation', [1028, 1200])])])
EOF
python -m PyInstaller EyeMouse.spec --noconfirm --clean
./dist/EyeMouse/EyeMouse.exe --selftest --out dist/selftest.log || true
grep -q "SELFTEST OK" dist/selftest.log || { cat dist/selftest.log; echo "打包後自我測試失敗"; exit 1; }
# 防毒軟體偶爾鎖住輸出檔（EndUpdateResource failed 110）→ 重試
for i in 1 2 3; do
  "$LOCALAPPDATA/Programs/Inno Setup 6/ISCC.exe" "//DAppVer=$VER" windows/installer.iss && break
  [ "$i" = 3 ] && { echo "Inno Setup 失敗"; exit 1; }
  echo "Inno Setup 第 $i 次失敗，5 秒後重試"; sleep 5
done
mkdir -p dist-installer
(cd dist && rm -f ../dist-installer/EyeMouse-Windows-portable.zip && powershell -NoProfile -Command "Compress-Archive -Path EyeMouse -DestinationPath ../dist-installer/EyeMouse-Windows-portable.zip -Force")
ls -la dist-installer
