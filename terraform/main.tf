terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}

variable "project_id" {
  description = "Google Cloud project where resources will be created."
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "bucket_name" {
  description = "Existing GCS bucket for resumes and the SQLite file (created outside Terraform)."
  type        = string
  default     = "hireflow-project"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------- APIs ----------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com", # IAM-based URL signing
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# ---------- Runtime identity ----------
resource "google_service_account" "runtime" {
  account_id   = "hireflow-runtime"
  display_name = "HireFlow application runtime"
  depends_on   = [google_project_service.apis]
}

# ---------- Secret: a cloud copy of .env (value added by hand, never in Terraform) ----------
resource "google_secret_manager_secret" "env" {
  secret_id = "hireflow-env"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runtime_env" {
  secret_id = google_secret_manager_secret.env.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------- Existing bucket: referenced by name, NOT managed ----------
resource "google_storage_bucket_iam_member" "runtime_bucket" {
  bucket = var.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------- Let the runtime sign URLs as itself (no key file in the cloud) ----------
resource "google_service_account_iam_member" "runtime_self_sign" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------- Cloud Run service ----------
resource "google_cloud_run_v2_service" "app" {
  name                = "hireflow"
  location            = var.region
  deletion_protection = false

  template {
    service_account       = google_service_account.runtime.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2" # required for bucket mounts

    scaling {
      min_instance_count = 0 # scale to zero when idle
      max_instance_count = 1 # SQLite: one writer only
    }

    volumes {
      name = "env-secret"
      secret {
        secret = google_secret_manager_secret.env.secret_id
        items {
          version = "latest"
          path    = "primary.env" # appears as /secrets/primary.env
        }
      }
    }

    volumes {
      name = "data"
      gcs {
        bucket    = var.bucket_name
        read_only = false
      }
    }

    containers {
      # Placeholder until Cloud Build deploys the real image
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi" # cross-encoder doesn't fit in the 512Mi default
        }
      }

      env {
        name  = "DB_PATH"
        value = "/data/db/hireflow.db"
      }

      volume_mounts {
        name       = "env-secret"
        mount_path = "/secrets"
      }

      volume_mounts {
        name       = "data"
        mount_path = "/data"
      }

      startup_probe {
        tcp_socket {
          port = 8080
        }
        period_seconds    = 10
        failure_threshold = 30 # up to ~5 min for model loading
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # Cloud Build owns the image
      client,
      client_version,
    ]
  }

  depends_on = [
    google_project_service.apis,
    google_secret_manager_secret_iam_member.runtime_env,
    google_storage_bucket_iam_member.runtime_bucket,
  ]
}

# ---------- Public access (anyone with the URL) ----------
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.app.project
  location = google_cloud_run_v2_service.app.location
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "service_url" {
  value = google_cloud_run_v2_service.app.uri
}