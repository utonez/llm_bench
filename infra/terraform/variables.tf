variable "project_id" {
  description = "GCP project that hosts everything."
  type        = string
}

variable "region" {
  description = "asia-east1 = Taiwan (Changhua): data stays in Taiwan, low latency for local users."
  type        = string
  default     = "asia-east1"
}

variable "image_tag" {
  description = "Tag of the bench image in Artifact Registry."
  type        = string
  default     = "latest"
}

variable "bench_schedule" {
  description = "Cron for the benchmark job (Asia/Taipei). One round = 27 calls per model."
  type        = string
  default     = "0 */6 * * *"
}

variable "provider_secrets" {
  description = "Secret Manager secret name => environment variable the job reads."
  type        = map(string)
  default = {
    "gemini-api-key" = "GEMINI_API_KEY"
    "groq-api-key"   = "GROQ_API_KEY"
  }
}
