# Deployment

## Overview
Code goes from my laptop to production through GitHub and Google Cloud:

```
git push to main
  → Cloud Build trigger
     → run tests (stop if any fail)
     → build image → push to Artifact Registry
     → deploy to Cloud Run
        → live at https://hireflow-ip6qt4teta-uc.a.run.app
```

- Project: `inner-bonus-327423`, region: `us-central1`
- Terraform creates the infrastructure (where it runs, who can do what).
- The Dockerfile describes what's inside the image.
- `cloudbuild.yaml` is the pipeline: the steps that run on every push.

---

## The pieces

### Tests (pytest)
- Run locally first, and in the pipeline on every push to `main`.
- Fake keys (`conftest.py`) let the code load without real credentials.
  Fakes (`monkeypatch`) replace Gemini, Pinecone, and GCS, so tests never
  call real services: fast, free, and the same result every time.
- Check: JSON parsing of LLM replies, the order of the retrieval stages
  and their return shape (including no results), and signed URL generation
  (including both local key and IAM signing paths).
- Don't check: search quality or whether the real services work.
  That's for an eval set and for testing in the cloud.

### Docker
- The Dockerfile is the recipe; the image is the result (Python 3.12,
  CPU-only torch, my packages, the cross-encoder model, my code).
- Step order matters for caching: slow installs come before `COPY . .`,
  so a code change rebuilds in seconds.
- CPU-only torch keeps the image several GB smaller (Cloud Run has no GPU).
- The model is downloaded at build time so containers don't download it
  on every start.
- `.dockerignore` keeps secrets, the local DB, and the dataset out of the image.
- Local `docker build` is only for testing the Dockerfile. Cloud Build
  builds the real images on every push to `main`.

### Terraform (`terraform/`)
- Describes the infrastructure: APIs, service accounts, permissions, the
  Artifact Registry repo, the secret, the Cloud Run service, and the
  Cloud Build trigger.
- `terraform plan` compares the files to what exists and shows what would
  change; `terraform apply` makes it so. Always check the destroy count.
- Terraform does NOT build the app. It deploys a placeholder image, and
  `ignore_changes` stops it from undoing Cloud Build's deploys.
- The resume bucket is referenced by name, not created, so
  `terraform destroy` can never delete resumes.
- `terraform.tfstate` is Terraform's memory of what it created. Never
  commit it, never delete it. `terraform.tfvars` is not committed either
  (see `terraform.tfvars.example`).

### Service accounts
| Account | Job | Can |
|---|---|---|
| `hireflow-runtime` | Identity the app runs as | Read the secret, read/write the bucket, sign URLs as itself |
| `hireflow-builder` | Runs the pipeline | Push images, write logs, deploy this one service, act as runtime |

### Secret (`hireflow-env`, value added by hand)
- Terraform creates the empty secret and grants read access to
  `hireflow-runtime` only. I add the value myself:
  `gcloud secrets versions add hireflow-env --data-file=cloud.env`
- Why: if Terraform set the value, the keys would end up in the `.tf`
  files (and git history), in `terraform.tfstate` (plain text), or in
  plan output. Adding it by hand keeps keys only in my local file and
  in Secret Manager (encrypted, access-controlled).
- Cloud Run mounts it as a file at `/secrets/primary.env`; the app loads it
  with `load_dotenv("/secrets/primary.env")`.
- `cloud.env` = `.env` WITHOUT the `GOOGLE_APPLICATION_CREDENTIALS` line
  (there's no key file in the cloud). Never committed.
- Only redo when keys change; each upload creates a new version, and
  Cloud Run reads "latest".

### Pipeline (Cloud Build)
- The trigger (`hireflow-deploy-main`) watches for pushes to `main`
  on GitHub. Pushes that only change `.md` files are skipped.
- Steps (`cloudbuild.yaml`), run as `hireflow-builder`:
  1. Run the tests
  2. Build the image from the Dockerfile
  3. Push it to Artifact Registry (tagged with the commit ID)
  4. Point the Cloud Run service at the new image
- If any step fails, nothing deploys, and the live app keeps running
  the last good version.
- Each deploy creates a new Cloud Run revision; the URL stays the same.

### Data
- SQLite lives on the bucket, mounted into Cloud Run at `/data`
  (`DB_PATH=/data/db/hireflow.db`), so it survives restarts and deploys.
- Max 1 instance, because SQLite only handles one writer at a time.
- Cloud and local databases are separate. Local runs share the same
  Pinecone namespace and bucket unless overridden (see below).

---

## Environment variables
| Variable | Controls | Local default | Cloud |
|---|---|---|---|
| `DB_PATH` | Where the SQLite file lives | `hireflow.db` | `/data/db/hireflow.db` (set in Terraform) |
| `PINECONE_NAMESPACE` | Which section of the index to use | `resumes` | default |
| `GCS_PREFIX` | Folder in the bucket for uploads | `""` (none) | default |

Secrets (`GEMINI_API_KEY`, `PINECONE_API_KEY`, `GCS_BUCKET_NAME`, etc.)
come from `.env` locally and from the `hireflow-env` secret in the cloud.

---

## One-time setup (from scratch)
1. Install gcloud, Terraform, and Docker. Log in and pick the project:
   ```
   gcloud auth application-default login
   gcloud config set project inner-bonus-327423
   ```
2. Create `cloud.env` (copy of `.env` without `GOOGLE_APPLICATION_CREDENTIALS`).
3. Create the secret first (Cloud Run won't start without a value):
   ```
   cd terraform
   terraform init
   terraform apply "-target=google_secret_manager_secret.env"
   gcloud secrets versions add hireflow-env --data-file=../cloud.env
   ```
4. Seed the cloud database (once, with the app stopped):
   ```
   gcloud storage cp ../hireflow.db gs://hireflow-project/db/hireflow.db
   ```
5. Connect GitHub in the console: Cloud Build → Repositories → 2nd gen →
   host connection `hireflow-github` in `us-central1` → link the repo.
   Put the linked repo's full resource name in `terraform.tfvars`.
6. Create everything else:
   ```
   terraform plan
   terraform apply
   ```
7. Push to `main` to trigger the first real deploy.

---

## Everyday workflow
1. Make changes, run `pytest -v` locally.
2. Optionally test in Docker (see below).
3. Commit and push to `main`.
4. Watch Cloud Build → History; when it succeeds, check the live app.

### Run locally in Docker
```
docker build -t hireflow .
docker run --rm -p 8080:8080 --env-file .env -e GOOGLE_APPLICATION_CREDENTIALS=/secrets/key.json --mount "type=bind,source=$PWD\KEY.json,target=/secrets/key.json,readonly" -e DB_PATH=/data/hireflow.db --mount "type=bind,source=$PWD,target=/data" hireflow
```
Then open http://localhost:8080. Add `-e PINECONE_NAMESPACE=resumes-local`
to keep test uploads out of the live app's search.

### Manual deploy (if needed)
```
gcloud builds submit --config cloudbuild.yaml --substitutions=_TAG=manual-N --service-account=projects/inner-bonus-327423/serviceAccounts/hireflow-builder@inner-bonus-327423.iam.gserviceaccount.com
```
Use a new `_TAG` each time.

### When something breaks
- Build failed → Cloud Build → History → click the failed step.
- App broken after deploy → Cloud Run → hireflow → Logs.
- Errors that the app catches must be logged (`logging.exception`) or
  they're invisible. Read them with:
  ```
  gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=hireflow AND logName:stderr' --limit=60 --freshness=15m --format="value(textPayload)"
  ```
  (newest first; tracebacks are split into one log entry per line)

---

## Gotchas

### Testing
- When a test fails, decide whether the code or the test is wrong.
- Test every feature (search, view resume, upload); the untested one
  hides the broken setup.
- Fakes in unit tests don't catch cloud problems like token scopes;
  only the real cloud does.

### Windows / PowerShell
- `.streamlit` was a file instead of a folder. Windows didn't care,
  Linux in the container did. It must be a folder with `config.toml` inside.
- Use `--mount` instead of `-v` in `docker run` (spaces and colons in
  Windows paths break `-v`).
- Quote Terraform arguments with dots: `"-target=google_secret_manager_secret.env"`.
- `\"` doesn't work for quotes inside quotes; wrap the whole thing in
  single quotes instead.
- First `pytest` after a restart can sit on "collecting..." for a while
  (cold torch import, possibly OneDrive).

### Docker
- `pypdf` is an optional dependency (used inside a LangChain loader), so
  it wasn't installed automatically. Only showed up in the container, on upload.
- The real key name goes only in `source=`; inside the container it's
  always `/secrets/key.json`.
- An old container can still hold port 8080; check with `docker ps`.
- `CMD` should use `exec` so Streamlit receives shutdown signals.

### Cloud
- The cloud `.env` must not contain `GOOGLE_APPLICATION_CREDENTIALS`.
- Seed the cloud DB once. After that, cloud and local databases diverge,
  so never re-upload the local one.
- Signing URLs in Cloud Run uses IAM signing (no key file), so the runtime
  account needs Token Creator on itself.
- Permission ≠ scope. Token Creator was granted, but the storage client's
  token was scoped to storage only, so IAM refused to sign. Fixed by
  requesting a `cloud-platform`-scoped token for signing.
- Manual `gcloud builds submit` with a custom service account needs read
  access to the `PROJECT_cloudbuild` staging bucket.
- Names must match across Terraform, `cloudbuild.yaml`, and the console
  (service account emails, repo name, region).

---

## Future improvements
- Staging → approval → production pipeline with PR checks (teacher's
  staged release template). Use separate `PINECONE_NAMESPACE` and
  `GCS_PREFIX` per environment.
- Store Terraform state in a GCS bucket (remote backend) instead of
  only on my laptop.
- Cloud SQL instead of SQLite on a bucket (removes the 1-instance limit).
- `HF_HUB_OFFLINE=1` in the Dockerfile so startup doesn't contact Hugging Face.
- Slim the image (unused packages, `transformers` extras).
- Reject duplicate uploads by file hash, not just email.
- Move the project out of OneDrive.