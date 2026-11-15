#!/usr/bin/env bash
# 印出第一個「Developer ID Application」簽章身分名稱（沒有就印空字串）
security find-identity -v -p codesigning 2>/dev/null | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p' | head -1
