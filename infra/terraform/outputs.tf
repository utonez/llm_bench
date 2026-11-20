output "image_repository" {
  description = "Push images here (append :<tag>)."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/bench"
}

output "job_name" {
  value = google_cloud_run_v2_job.bench.name
}

output "secret_ids" {
  description = "Add a version to each with: gcloud secrets versions add <id> --data-file=-"
  value       = [for s in google_secret_manager_secret.provider : s.secret_id]
}
