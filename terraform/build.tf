resource "google_service_account" "builder" {
  account_id   = "hireflow-builder"
  display_name = "HireFlow build and deployment"
  depends_on   = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "hireflow-repo"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "builder" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "builder_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_cloud_run_v2_service_iam_member" "builder" {
  project  = google_cloud_run_v2_service.app.project
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.builder.email}"
}

# "Act as": the builder may deploy a service that runs as the runtime account
resource "google_service_account_iam_member" "builder_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.builder.email}"
}

# Manual `gcloud builds submit` uploads source to this auto-created bucket;
# the builder needs to read it.
resource "google_storage_bucket_iam_member" "builder_source" {
  bucket = "${var.project_id}_cloudbuild"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.builder.email}"
}

variable "github_repository" {
  description = "Full resource name of the Cloud Build 2nd-gen linked repository."
  type        = string
}

resource "google_cloudbuild_trigger" "deploy_main" {
  name            = "hireflow-deploy-main"
  location        = var.region
  description     = "Test, build, push, and deploy on every push to main"
  service_account = google_service_account.builder.id
  filename        = "cloudbuild.yaml"

  repository_event_config {
    repository = var.github_repository
    push {
      branch = "^main$"
    }
  }

  # Don't spend a 9-minute build on documentation-only changes
  ignored_files = ["**/*.md"]

  depends_on = [google_project_service.apis]
}