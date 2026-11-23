# 架構決策紀錄（ADR）

每份紀錄說明一個重要決策：當時的背景、決定、考慮過的替代方案，以及帶來的影響。

| # | 決策 | 狀態 |
|---|---|---|
| [0001](0001-cloud-run-job-and-service.md) | 用 Cloud Run Job + Service，共用一個映像檔 | 採用 |
| [0002](0002-firestore-with-run-summaries.md) | 用 Firestore，並另存每輪摘要給 API 讀取 | 採用 |
| [0003](0003-keyless-cicd-with-wif.md) | CI/CD 以 Workload Identity Federation 部署，不使用金鑰 | 採用 |
| [0004](0004-dashboard-served-by-api.md) | 儀表板由 API 服務提供，不使用 Firebase Hosting | 採用（取代原計畫） |
| [0005](0005-measure-failures-not-hide-them.md) | 不自動重試；依供應商控制呼叫間隔 | 採用 |
| [0006](0006-sourced-tasks-and-reference-pricing.md) | 題庫必須有出處；成本採市場參考價 | 採用 |
| [0007](0007-public-api-rate-limit-tradeoff.md) | 公開 API 採用整體速率限制，不做每位使用者限制 | 採用（已知取捨） |
