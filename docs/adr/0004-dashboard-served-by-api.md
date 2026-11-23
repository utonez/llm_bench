# 0004 · 儀表板由 API 服務提供，不使用 Firebase Hosting

**背景**：原計畫把前端放在 Firebase Hosting。實作時重新評估了安全與複雜度。

**決定**：儀表板的靜態檔案由同一個 Cloud Run 服務提供（FastAPI `StaticFiles`），與 API 同一個網址。

**理由**：
1. **安全**：在這個 GCP 專案啟用 Firebase，會讓 Firestore 可以從瀏覽器的 Firebase SDK 存取，只靠安全規則保護。目前 Firestore 完全無法從外部存取，這樣更安全
2. **不需要 CORS**：頁面與 API 同源
3. **少一個服務**：不需要另外部署、監控與說明

**配套措施**：
- 嚴格的 CSP：`script-src 'self'`，不允許 inline script 和外部網域
- Chart.js 不從 CDN 載入，而是下載後**驗證 npm 公布的 SHA-512 雜湊**再放進專案
- 資料只用 `textContent` 插入頁面，API 回傳的內容無法插入 HTML
- 自家靜態檔案每次向伺服器確認（`no-cache`，靠 ETag 回傳 304），避免部署後新頁面搭配舊的 JS；版本化的第三方檔案則長期快取

**影響**：
- ✅ 攻擊面更小、架構更簡單
- ⚠️ 沒有 CDN；流量大時可在前面加上 Cloud CDN
