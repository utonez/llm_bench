# llm-bench — 金融場景 LLM 選型評測平台

定期以一組固定的金融任務測試多家 LLM，比較 **延遲（平均 / P95）、穩定度、token 用量與新台幣成本**，作為企業導入生成式 AI 時的選型依據。

> 🚧 開發中。完整計畫、架構與里程碑見 [docs/PLAN.md](docs/PLAN.md)。

## 技術堆疊（規劃）

| 層 | 技術 |
|---|---|
| 後端 | Python · FastAPI |
| 運算 | GCP Cloud Run（API）· Cloud Run Jobs + Cloud Scheduler（定期評測） |
| 資料 | Firestore |
| 密鑰 | Secret Manager |
| 前端 | Firebase Hosting |
| IaC | Terraform |
| CI/CD | GitHub Actions + Workload Identity Federation |

## 目錄結構

```
app/        FastAPI 與核心邏輯（providers / bench / pricing / storage）
jobs/       排程評測進入點
tasks/      題庫（皆有出處，見 tasks/README.md）
tests/      單元與整合測試
frontend/   儀表板
infra/      Terraform
docs/       架構圖、ADR、流程圖、AI 開發心得
```
