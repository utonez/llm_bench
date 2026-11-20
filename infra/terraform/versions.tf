terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
  }

  # State lives in a versioned GCS bucket, never in git (it can contain resource details).
  # The bucket is created once by infra/bootstrap.sh before `terraform init`.
  backend "gcs" {
    prefix = "llm-bench"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
