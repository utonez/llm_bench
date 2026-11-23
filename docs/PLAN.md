# 專案計畫書：金融場景 LLM 選型評測平台（llm-bench）

> 國泰金控 雲端技術暨專案實習生 面試前實作測驗
> 繳交期限：**2026/11/26（四）12:00** · 目標：越早完成越好，期限只是最晚底線

> **狀態（2026-11-23）：M1–M7 全部完成。** 與原計畫的差異：
> - 前端改由 API 服務直接提供，不使用 Firebase Hosting（理由見 [ADR 0004](adr/0004-dashboard-served-by-api.md)）
> - 受測模型從 3 個增加到 5 個（PR #8）
> - 下方保留原始計畫，作為規劃與實際的對照

## 1. 專案目的

企業導入生成式 AI 時，常見的問題是「該選哪個模型？」。本平台以**一組固定的金融任務**，
**定期、自動**測試多家 LLM，量測：

- **速度**：平均延遲、P95 延遲
- **穩定度**：成功率、錯誤類型（逾時、限流、驗證失敗…）
- **正確性**：分類與欄位抽取題自動比對標準答案
- **成本**：token 用量 × 公開價格 → 換算新台幣

所有數據皆為**真實量測**，且隨排程持續累積，可觀察趨勢。

## 2. 系統架構（GCP · `asia-east1` 台灣）

```
Firebase Hosting（儀表板）
        │ HTTPS
        ▼
Cloud Run：FastAPI 查詢 API ───────────┐
                                        ▼
Cloud Scheduler ─► Cloud Run Job ─► Firestore（評測結果）
                    │
                    ├─► Gemini / GitHub Models / Groq / OpenRouter
                    ├─► OpenRouter Models API（價格）
                    └─► 臺灣銀行牌告匯率
Secret Manager（各家 API 金鑰，以 Service Account 身分讀取）
Cloud Logging / Monitoring（日誌與告警）

GitHub Actions ─(Workload Identity Federation)─► Artifact Registry ─► Cloud Run
全部資源以 Terraform 建立
```

**同一個 Docker 映像檔，兩種執行模式**：API（常駐、可縮到零）與 Job（排程評測）。

| 服務 | 用途 | 選用理由 |
|---|---|---|
| Cloud Run | FastAPI 後端 | 直接部署容器、無流量時縮到零、永久免費額度 |
| Cloud Run Jobs + Scheduler | 定期評測 | 批次工作不必常駐；與 API 共用映像檔 |
| Firestore | 儲存結果 | Serverless、免費額度足夠、無需管理資料庫 |
| Secret Manager | API 金鑰 | 程式碼與映像檔不含任何密鑰 |
| Artifact Registry | 映像檔 | Cloud Run 原生支援、同區域拉取快 |
| Firebase Hosting | 前端 | 免費、自帶 CDN 與 HTTPS |
| Terraform | IaC | 環境可重建、變更可審查、業界通用 |
| GitHub Actions + WIF | CI/CD | 不在 GitHub 存放任何長期 GCP 金鑰 |
| `asia-east1` | 區域 | 台灣資料中心，符合金融業資料落地考量、延遲低 |

## 3. 里程碑（依功能，每個一個分支 + PR）

| # | 分支 | 內容 | 完成條件 | 最晚 |
|---|---|---|---|---|
| M1 | `feat/bench-core` | 有出處的題庫（見 [tasks/README.md](../tasks/README.md)）、Provider 介面、Mock、評測執行器、評分、統計、記憶體儲存 | 本機用 Mock 跑完一輪、測試通過 | 11/21 |
| M2 | `feat/providers` | Gemini、GitHub Models、Groq、OpenRouter 串接，錯誤分類與重試 | 本機對真實 API 跑一輪 | 11/22 |
| M3 | `feat/gcp-infra` | Dockerfile、Firestore 儲存、Terraform、部署 Job + Scheduler | **雲端開始自動收集數據** | 11/22 |
| M4 | `feat/api-cost` | FastAPI 查詢 API、OpenRouter 價格、臺銀匯率、新台幣成本 | API 部署並可查詢 | 11/23 |
| M5 | `feat/dashboard` | 前端儀表板（排行、趨勢、成本試算） | 部署到 Firebase Hosting | 11/24 |
| M6 | `ci/github-actions` | 測試 → 建置 → 推送 → 部署，WIF；main 分支保護 | PR 自動跑 CI、合併自動部署 | 11/24 |
| M7 | `docs/submission` | 架構圖、ADR、CI/CD 圖、Git 流程圖、AI 開發心得、面試問答 | 文件齊全 | 11/25 |
| — | — | 緩衝、最終檢查、**回信繳交** | — | 11/26 12:00 |

**M3 越早完成越好**：數據累積的天數越多，趨勢圖越有說服力。

## 4. 題目要求對照

| 要求 / 加分項 | 對應 |
|---|---|
| Python 程式碼 | FastAPI + 評測 Job |
| 雲端架構圖 | `docs/architecture` |
| 用途、功能、服務選用說明 | README + 本文件第 2 節 + ADR |
| ① 前端 | M5 儀表板 |
| ② 第三方 RESTful API | 4 家 LLM + OpenRouter 價格 + 臺銀匯率 |
| ③ CI/CD | M6 + 流程圖 |
| ④ 多人協作 Git 流程 | GitHub Flow：每個里程碑實際走分支 → PR → CI → 合併，附流程圖 |
| ⑤ IaC | Terraform |
| ⑥ AI 輔助開發 | Claude Code 開發紀錄與心得，並以本平台分析開發時的 AI 用量 |

## 5. 風險與對策

| 等級 | 風險 | 對策 |
|---|---|---|
| 中 | 免費 API 限流或模型下架 | 每輪呼叫數可調、單一供應商失敗不影響其他、Mock 備援 |
| 中 | 時間不足 | 前端與 Claude 用量分析列為可延後；核心與雲端優先 |
| 中 | 本機 Python 3.14 套件相容性 | Docker 使用 Python 3.13 |
| 低 | 雲端費用 | 預算警報、Cloud Run 最大執行個體數 = 1、免費額度內運作 |
| 低 | Cloud Run 冷啟動 | 為成本取捨，文件中說明 |

## 6. 環境資訊

- GitHub：`utonez/llm_bench`
- GCP 專案：`llm-bench-515306`（帳單與預算警報已設定）
- 區域：`asia-east1`
