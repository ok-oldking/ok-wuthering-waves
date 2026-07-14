<div align="center">
  <h1 align="center">
    <img src="icon.png" width="200" alt="ok-ww logo"/>
    <br/>
    ok-ww
  </h1> 
  
  <p>
    一個基於圖像辨識的鳴潮自動化程式，支援背景執行，基於 <a href="https://github.com/ok-oldking/ok-script">ok-script</a> 開發。
  </p>
  
  <p><i>透過 Windows 介面模擬使用者操作，無記憶體讀取、無檔案修改</i></p>
</div>

<!-- Badges -->
<div align="center">
  
![平台](https://img.shields.io/badge/platform-Windows-blue)
[![GitHub release](https://img.shields.io/github/v/release/ok-oldking/ok-wuthering-waves)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![總下載量](https://img.shields.io/github/downloads/ok-oldking/ok-wuthering-waves/total)](https://github.com/ok-oldking/ok-wuthering-waves/releases)
[![Discord](https://img.shields.io/discord/296598043787132928?color=5865f2&label=%20Discord)](https://discord.gg/vVyCatEBgA)

</div>

### [English Readme](README_en.md) | [中文说明](README.md) | 繁體中文說明 | [日本語Readme](README_ja.md)

**示範與教學:** [![YouTube](https://img.shields.io/badge/YouTube-%23FF0000.svg?style=for-the-badge&logo=YouTube&logoColor=white)](https://youtu.be/h6P1KWjdnB4)

---

## ⚠️ 免責聲明

本軟體為外部輔助工具，旨在自動化《鳴潮》的部分遊戲流程。它完全透過模擬一般使用者介面與遊戲互動，並遵循相關法律法規。本專案旨在簡化使用者的重複性操作，不會破壞遊戲平衡或提供不公平優勢，也絕不會修改任何遊戲檔案或資料。

本軟體開源、免費，僅供個人學習與交流使用，請勿用於任何商業或營利目的。開發團隊保留本專案的最終解釋權。因使用本軟體而產生的任何問題，均與本專案及開發者無關。

請注意，根據庫洛官方的《鳴潮》公平營運聲明：
> 嚴禁利用任何第三方工具破壞遊戲體驗。
> 我們將嚴厲打擊使用外掛、加速器、作弊軟體、巨集腳本等違規工具的行為，這些行為包括但不限於自動掛機、技能加速、無敵模式、瞬間移動、修改遊戲資料等操作。
> 一經查證，我們將視違規情況與次數，採取包括但不限於扣除違規收益、凍結或永久停權遊戲帳號等措施。

**使用本軟體即表示您已閱讀、理解並同意以上聲明，並自願承擔一切潛在風險。**

## 🚀 快速開始

1.  **下載安裝檔**：從下方的「下載管道」下載最新的 `ok-ww-win32-setup.exe` 安裝檔。
2.  **安裝程式**：雙擊 `ok-ww-win32-setup.exe` 檔案，並依照安裝精靈的指示完成安裝。
3.  **執行程式**：安裝完成後，從桌面捷徑或開始功能表啟動 `ok-ww` 即可。

## 📥 下載管道

*   **[GitHub](https://github.com/ok-oldking/ok-wuthering-waves/releases)**: 官方發布頁，全球存取速度快。（**請下載 `setup.exe` 安裝檔，而不是 `Source Code` 原始碼壓縮檔**）

## ✨ 主要功能
<img width="1774" height="1182" alt="QQ_1762960844719" src="https://github.com/user-attachments/assets/c5eb0145-0d45-44f9-85b3-184de0ef20bf" />

*   **高解析度支援**: 流暢執行於 4K 及以下所有 16:9 解析度（最低 1600x900）。部分功能相容 21:9 等超寬螢幕。
*   **背景模式**: 支援遊戲視窗最小化或被遮擋時在背景執行，不影響您使用電腦。
*   **智慧辨識**: 全角色自動辨識，無需手動設定技能序列，一鍵啟動。
*   **自動靜音**: 在背景執行時，可自動將遊戲靜音。

## 🔧 疑難排解 (Troubleshooting)

如果遇到問題，請在提問前依以下步驟逐一排查：

1.  **安裝路徑**：請確保軟體安裝在**純英文路徑**下（例如 `D:\Games\ok-ww`），不要安裝在 `C:\Program Files` 或包含中文字元的資料夾中。
2.  **防毒軟體**：將軟體的安裝目錄加入您的防毒軟體（包括 Windows Defender）的**信任區或白名單**，以防檔案被誤刪或攔截。
3.  **顯示設定**：
    *   關閉所有顯示卡濾鏡（如 NVIDIA Game Filter）和銳化功能。
    *   使用遊戲預設的亮度設定。
    *   關閉任何在遊戲畫面上顯示資訊的疊加層（如 MSI Afterburner、Fraps 等顯示的幀率）。
4.  **自訂按鍵**：如果您修改了遊戲內的預設按鍵，請務必在 `ok-ww` 的設定中同步設定。僅支援設定中列出的按鍵。
5.  **軟體版本**：檢查並確保您使用的是最新版本的 `ok-ww`。
6.  **遊戲效能**：請確保遊戲能穩定以 **60 FPS** 執行。如果幀率不穩定，請嘗試調低遊戲畫質或解析度。
7.  **遊戲斷線**：如果頻繁遇到與伺服器斷線的問題，可以先手動開啟遊戲執行 5 分鐘後再啟動本工具，或在斷線後直接重新登入，不要退出遊戲。
8.  **尋求協助**：如果以上步驟都無法解決您的問題，請透過社群管道提交詳細的錯誤回報。
9.  **關閉自動奔跑**：在遊戲設定裡關閉自動奔跑。

---

## 💻 開發者專區

### 從原始碼執行 (Python)

本專案僅支援 Python 3.12 版本。

```bash
# 安裝或更新相依套件
pip install -r requirements.txt --upgrade

# 執行 Release 版本
python main.py

# 執行 Debug 版本
python main_debug.py
```

### 命令列參數

您可以透過命令列參數實現自動化啟動。

```bash
# 範例：啟動後自動執行第一個任務（一條龍），並在任務完成後結束程式
ok-ww.exe -t 1 -e
```

*   `-t` 或 `--task`: 啟動後自動執行第 N 個任務。`1` 代表任務清單中的第一個。
*   `-e` 或 `--exit`: 任務執行完畢後自動結束程式。

## 💬 加入我們

*   **Discord**: [點擊加入](https://discord.gg/vVyCatEBgA)

本專案基於 [ok-script](https://github.com/ok-oldking/ok-script) 框架開發，核心程式碼僅約 3000 行 (Python)，簡單易維護。歡迎有興趣的開發者使用 [ok-script](https://github.com/ok-oldking/ok-script) 開發您自己的自動化專案。

## 🔗 使用 ok-script 的專案：

* 鳴潮 [https://github.com/ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
* 原神（停止維護，但背景過劇情可用） [https://github.com/ok-oldking/ok-genshin-impact](https://github.com/ok-oldking/ok-genshin-impact)
* 少女前線2 [https://github.com/ok-oldking/ok-gf2](https://github.com/ok-oldking/ok-gf2)
* 崩壞：星穹鐵道 [https://github.com/Shasnow/ok-starrailassistant](https://github.com/Shasnow/ok-starrailassistant)
* 星痕共鳴 [https://github.com/Sanheiii/ok-star-resonance](https://github.com/Sanheiii/ok-star-resonance)
* 二重螺旋 [https://github.com/BnanZ0/ok-duet-night-abyss](https://github.com/BnanZ0/ok-duet-night-abyss)
* 白荊迴廊（停止更新） [https://github.com/ok-oldking/ok-baijing](https://github.com/ok-oldking/ok-baijing)


## ❤️ 贊助與致謝

### 贊助商 (Sponsors)
*   **EXE 簽章**: Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

### 致謝
*   [lazydog28/mc_auto_boss](https://github.com/lazydog28/mc_auto_boss)
*   [ok-oldking/OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
*   [zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
*   [Toufool/AutoSplit](https://github.com/Toufool/AutoSplit)
