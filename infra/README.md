# 部署（GCP · asia-east1）

全部資源由 Terraform 管理（`infra/terraform/`），唯二例外：
1. **Terraform 狀態儲存桶**：Terraform 無法建立存放自己狀態的桶，由 `bootstrap.sh` 建立一次。
2. **密鑰的值**：Terraform 只建立 Secret Manager 的「容器」，值由人用 `gcloud` 寫入，
   因此 API 金鑰**永遠不會出現在 Terraform 程式碼或 state 中**。

## 建立的資源

| 資源 | 用途 |
|---|---|
| Artifact Registry `llm-bench` | 存放映像檔；清理政策保留最新 3 個、刪除 7 天前的版本，維持在 0.5 GB 免費額度內 |
| Firestore `(default)`（Native, asia-east1） | 評測結果，集合 `bench_results`；只有 `(default)` 資料庫享有免費額度 |
| Secret Manager `gemini-api-key`、`groq-api-key` | 供應商金鑰，僅限 asia-east1 複寫 |
| Service account `bench-job` | Job 執行身分：只能寫 Firestore、讀上述兩個密鑰 |
| Service account `bench-scheduler` | 排程觸發身分：只能啟動 `llm-bench-job` |
| Cloud Run Job `llm-bench-job` | 執行一輪評測（`python -m jobs.run_bench`），不自動重試 |
| Cloud Scheduler `llm-bench-every-6h` | 每 6 小時（Asia/Taipei）觸發 Job |

## 第一次部署

```bash
# 1. 狀態儲存桶（一次）
infra/bootstrap.sh llm-bench-515306

# 2. 本機變數（terraform.tfvars 已被 git 忽略）
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
terraform -chdir=infra/terraform init -backend-config=bucket=llm-bench-515306-tfstate

# 3. 先建基礎資源（Job 需要映像檔與密鑰值，所以分兩階段）
terraform -chdir=infra/terraform apply \
  -target=google_project_service.apis -target=google_artifact_registry_repository.images \
  -target=google_firestore_database.default -target=google_secret_manager_secret.provider \
  -target=google_service_account.bench_job -target=google_service_account.scheduler \
  -target=google_project_iam_member.bench_job_firestore \
  -target=google_secret_manager_secret_iam_member.bench_job_secrets

# 4. 寫入密鑰值（由人執行；注意不要帶結尾換行）
gcloud secrets versions add gemini-api-key --data-file=<不含換行的金鑰檔>
gcloud secrets versions add groq-api-key   --data-file=<不含換行的金鑰檔>

# 5. 建置並推送映像檔（tag = git commit，部署可追溯到確切程式碼）
gcloud auth configure-docker asia-east1-docker.pkg.dev
REPO=asia-east1-docker.pkg.dev/llm-bench-515306/llm-bench/bench
docker build -t $REPO:$(git rev-parse --short HEAD) . && docker push $REPO:$(git rev-parse --short HEAD)

# 6. 其餘資源（Job + Scheduler）
terraform -chdir=infra/terraform apply -var image_tag=$(git rev-parse --short HEAD)
```

## 手動跑一輪

```bash
gcloud run jobs execute llm-bench-job --region=asia-east1 --wait          # 直接執行 Job
gcloud scheduler jobs run llm-bench-every-6h --location=asia-east1        # 經由排程觸發（驗證排程權限）
```

## 成本

全部在免費額度內運作，唯一確定的費用是 asia-east1 的狀態儲存桶（GCS 免費額度只限美國區域），
但 state 檔僅數 KB，每月遠低於新台幣 1 元。帳單帳戶另設有預算警報。
