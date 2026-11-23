# 0003 · CI/CD 以 Workload Identity Federation 部署，不使用金鑰

**背景**：GitHub Actions 需要權限才能推送映像檔、更新 Cloud Run。傳統做法是把服務帳號的 JSON 金鑰存進 GitHub Secrets，但這個金鑰永久有效，一旦外洩，任何人都能存取 GCP。

**決定**：
- 使用 **Workload Identity Federation**：GitHub 每次執行時簽發 OIDC token，GCP 換發約 1 小時有效的臨時憑證
- GCP 端的 `attribute_condition` 只接受 `utonez/llm_bench` 的 `main` 分支
- 部署帳號 `gh-deployer` 只有三項權限：推送映像檔、更新現有的 Cloud Run 版本、以原本的服務帳號身分執行
- Terraform 忽略映像檔版本（由 CI 管理）；基礎設施變更仍由人審查 `terraform plan` 後執行

**考慮過的替代方案**：
- **服務帳號 JSON 金鑰**：永久有效、需要手動輪替，外洩風險高
- **讓 CI 直接執行 `terraform apply`**：需要給 CI 修改 IAM、建立資源的權限，等同專案管理員

**影響**：
- ✅ GitHub 上沒有任何長期金鑰可以外洩
- ✅ PR（包括 fork 發來的）拿不到部署憑證，就算修改 workflow 也一樣
- ⚠️ 基礎設施變更需要手動執行 Terraform；在這個規模下是刻意的取捨
