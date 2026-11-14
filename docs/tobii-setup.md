# Tobii Eye Tracker 5 安裝與設定（Windows）

眼動鼠透過 Tobii 驅動附帶的 **Tobii Stream Engine** 讀取視線，所以使用前要先把 Tobii 官方的驅動和 **Tobii Experience** 裝好，並完成螢幕設定與校正。以下步驟依 2026-11-14 實機安裝的過程整理。

> Mac：Tobii Eye Tracker 5 官方**不支援 macOS**。Mac 版眼動鼠改用內建攝影機，不需要以下步驟。

## 需要的軟體

| 軟體 | 用途 | 取得方式 |
|---|---|---|
| **Tobii Eye Tracker 5 驅動**（Tobii 官方離線安裝程式，例如 `Tobii.EyeTracker5.Offline.Installer_5.0.0.6035.exe`） | 讓 Windows 認得眼動儀，安裝 Tobii Service、Tobii Runtime Service，以及眼動鼠需要的 `tobii_stream_engine.dll` | Tobii 官網（gaming.tobii.com）的 Eye Tracker 5 下載頁 |
| **Tobii Experience**（Microsoft Store App） | 官方的螢幕設定、校正、注視點測試 | Microsoft Store 搜尋「Tobii Experience」（免費，發行者 Tobii AB） |
| **眼動鼠** | 用眼睛控制滑鼠 | [Releases](https://github.com/achir1015/eyemouse/releases/latest) 的 `EyeMouse-Setup.exe` |

## 安裝步驟

### 1. 先把眼動儀接好

- 把眼動儀固定在**螢幕下緣正中央**，鏡頭朝向使用者。
- USB **直接插筆電／主機本體的 USB-A 孔**，不要經過集線器、延長線或轉接頭（Eye Tracker 5 耗電較高，被動式集線器常常帶不動）。
- 插上後眼動儀正面會亮紅燈。完全不亮表示沒有供電，請換一個 USB 孔。

### 2. 安裝驅動

1. 執行 Tobii 官方離線安裝程式；跳出系統管理員確認時按「是」。
2. **建議先插好眼動儀再安裝**。實測時第一次在眼動儀沒接上的狀態下執行，安裝沒有完成。
3. 裝好後應該會看到：
   - 裝置管理員中出現 **Eye Tracker 5**、**Tobii Hello Sensor**、**Tobii Eye Tracker HID**
   - 服務中有 **Tobii Service**、**Tobii Runtime Service**、**Tobii Eye Tracker Generic Service** 正在執行
   - 檔案 `C:\Program Files\Tobii\Tobii EyeX\tobii_stream_engine.dll` 存在（眼動鼠會自動找到它）

### 3. 安裝 Tobii Experience

驅動本身**不含**設定畫面。如果只裝了驅動，Tobii 的設定檔會停在預設的螢幕尺寸 4×4 mm，而且**不會輸出任何注視點**。

- 到 Microsoft Store 搜尋並安裝 **Tobii Experience**。
- 也可以執行 `C:\Program Files\Tobii\Tobii EyeX\Tobii.Configuration.exe`，它會直接打開 Microsoft Store 的 Tobii Experience 頁面。

### 4. 螢幕設定與校正（必做）

開啟 Tobii Experience，依畫面完成：

1. **螢幕設定（Display setup）**：選擇眼動儀所在的螢幕，對齊眼動儀的位置。完成後螢幕尺寸會變成實際尺寸（例如 15.6 吋筆電是 344×194 mm）。
2. **校正（Calibration）**：坐在平常使用的位置（距離 50～90 cm），盯著畫面上出現的點，約 30 秒。
3. 換人使用、或眼動儀位置有移動時，要重新校正。

### 5. 用官方工具確認追蹤正常

在 Tobii Experience 裡打開**注視點顯示（Gaze trace／注視泡泡）**，眼睛看到哪裡，畫面上就有一個泡泡跟著移動：

- 泡泡穩定跟著視線 → 眼動儀與校正都正常，可以使用眼動鼠。
- 泡泡不出現 → 回到步驟 4 重新做螢幕設定與校正。
- 泡泡明顯偏某個方向 → 重新校正；之後再用眼動鼠內建的「校正視線」微調。

測完後**請關掉注視泡泡**，以免跟眼動鼠的游標重疊。

### 6. 啟動眼動鼠並微調

1. 開啟眼動鼠，控制面板的狀態應顯示「**已連線 Tobii（Stream Engine 4.25.0）**」。
2. 按「**校正視線**」做眼動鼠的 9 點校正：盯著小老鼠跑完 9 個點，再看「套用」。實測校正後誤差中位數為 19 px。
3. 點擊預設開啟「**放大鏡精準點擊**」，實測數據見 [measurements](measurements/README.md)。

## 疑難排解

| 眼動鼠狀態列／現象 | 原因 | 處理 |
|---|---|---|
| 找不到 Tobii Stream Engine | 驅動沒有裝 | 執行步驟 2 |
| 找不到眼動儀：請確認 USB 已插好 | Windows 看不到眼動儀 | 確認紅燈有亮、直接插本體 USB-A、換一個孔；裝置管理員應有 Eye Tracker 5 |
| 眼動儀已連線，但看不到眼睛 | 鏡頭前沒人，或**還沒做螢幕設定／校正** | 坐正、距離 50～90 cm；若一直如此，完成步驟 3～4 |
| 眼動儀連線中斷，重新連線中… | USB 斷線（接頭鬆動、供電不足、USB 省電） | 接頭推到底並固定線材；若仍會斷，到「控制台 › 電源選項 › 變更計劃設定 › 變更進階電源設定 › USB 設定 › USB 選擇性暫停設定」改成「已停用」。眼動鼠會在眼動儀接回後自動重連，校正資料也會沿用 |
| 點不準、總是偏某個方向 | 校正偏差 | 先在 Tobii Experience 重新校正，再用眼動鼠「校正視線」 |
| 按「鍵盤」出現「從伺服器傳回一個轉介」 | 舊版（1.1.0 以前）用 osk.exe，在部分 Windows 版本無法啟動 | 更新到 1.1.1 以上，改用 Windows 觸控鍵盤（注音） |
| 小按鈕點不到 | 眼動追蹤本身的抖動 | 開啟「放大鏡精準點擊」，或在設定中加大「停留範圍」 |

## 授權提醒

Tobii 消費級眼動儀（Eye Tracker 5）的使用條款只允許**即時互動**用途。眼動鼠「眼動評估」功能會錄存視線資料做分析，正式用於臨床評估前，請先向 Tobii 或台灣代理商確認授權。
