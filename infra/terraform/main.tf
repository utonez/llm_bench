locals {
  apis = [
    "run.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
  ]
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/bench:${var.image_tag}"
}

# ── APIs ───────────────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

# ── Container images ───────────────────────────────────────────────────
resource "google_artifact_registry_repository" "images" {
  repository_id = "llm-bench"
  location      = var.region
  format        = "DOCKER"
  description   = "llm-bench container images"

  # Stay inside the 0.5 GB free storage: keep only the newest few images.
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 3
    }
  }
  cleanup_policies {
    id     = "delete-older"
    action = "DELETE"
    condition {
      older_than = "604800s" # 7 days
    }
  }

  depends_on = [google_project_service.apis]
}

# ── Database ───────────────────────────────────────────────────────────
# Only the "(default)" database gets the Firestore free tier.
resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ── Secrets (containers only — values are added with gcloud, never via Terraform) ──
resource "google_secret_manager_secret" "provider" {
  for_each  = var.provider_secrets
  secret_id = each.key

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# ── Identities (least privilege) ───────────────────────────────────────
resource "google_service_account" "bench_job" {
  account_id   = "bench-job"
  display_name = "llm-bench benchmark job"
}

resource "google_service_account" "scheduler" {
  account_id   = "bench-scheduler"
  display_name = "Cloud Scheduler trigger for the benchmark job"
}

# GCP grants the default Compute Engine service account roles/editor automatically.
# Nothing here runs as that account (the job uses bench-job), so remove the grant: any
# resource that later falls back to the default identity gets no project-wide edit rights.
data "google_project" "this" {}

resource "google_project_iam_member_remove" "default_compute_editor" {
  project = var.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${data.google_project.this.number}-compute@developer.gserviceaccount.com"
}

# The job may write results...
resource "google_project_iam_member" "bench_job_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.bench_job.email}"
}

# ...and read only the provider secrets, nothing else.
resource "google_secret_manager_secret_iam_member" "bench_job_secrets" {
  for_each  = google_secret_manager_secret.provider
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.bench_job.email}"
}

# ── Benchmark job ──────────────────────────────────────────────────────
resource "google_cloud_run_v2_job" "bench" {
  name                = "llm-bench-job"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1

    template {
      service_account = google_service_account.bench_job.email
      timeout         = "900s"
      max_retries     = 0 # a failed round is data, not something to hide

      containers {
        image = local.image

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        env {
          name  = "STORAGE_BACKEND"
          value = "firestore"
        }
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }

        dynamic "env" {
          for_each = var.provider_secrets
          content {
            name = env.value
            value_source {
              secret_key_ref {
                secret  = google_secret_manager_secret.provider[env.key].secret_id
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.bench_job_secrets,
    google_project_iam_member.bench_job_firestore,
  ]
}

# The scheduler identity may start this one job and nothing else.
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  name     = google_cloud_run_v2_job.bench.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# ── Schedule ───────────────────────────────────────────────────────────
resource "google_cloud_scheduler_job" "bench" {
  name             = "llm-bench-every-6h"
  region           = var.region
  schedule         = var.bench_schedule
  time_zone        = "Asia/Taipei"
  attempt_deadline = "60s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.bench.name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_invoker]
}
