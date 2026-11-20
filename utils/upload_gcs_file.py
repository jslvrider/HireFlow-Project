import mimetypes
import os
import uuid
from datetime import timedelta
from pathlib import Path

import google.auth
from google.auth.transport.requests import Request
from google.cloud import storage
from google.oauth2 import service_account

# signBlob (IAM signing) needs this scope; the storage client's token lacks it.
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"




def upload_file_gcs(pdf_path: str|Path) -> tuple [str, str]:
    doc_id = str(uuid.uuid4())
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Optional folder prefix (e.g. "prod") so environments can share a bucket.
    prefix = os.getenv("GCS_PREFIX", "").strip("/")
    key_prefix = f"{prefix}/" if prefix else ""

    if isinstance(pdf_path, (str, Path)):
        # local file path — get filename from path, upload directly from disk
        filename = Path(pdf_path).name
        blob = bucket.blob(f"{key_prefix}{doc_id}/{filename}")
        blob.upload_from_filename(pdf_path)
    else:
        # Streamlit UploadedFile object — get filename from metadata, upload from memory
        filename = Path(pdf_path.name).name
        blob = bucket.blob(f"{key_prefix}{doc_id}/{filename}")
        # Streamlit sets .type to the browser-reported MIME type; fall back to
        # guessing from the filename for plain file objects that lack it.
        content_type = getattr(pdf_path, "type", None) or mimetypes.guess_type(filename)[0]
        blob.upload_from_file(pdf_path, content_type=content_type)

    file_link = f"gs://{bucket_name}/{key_prefix}{doc_id}/{filename}"
    return doc_id, file_link

def delete_old_blob(old_link: str) -> None:
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = old_link.split("/",3)[3]
    bucket.blob(blob_name).delete()


def _signing_kwargs(client: storage.Client) -> dict:
    """Extra generate_signed_url kwargs needed to sign with the client's credentials.

    Service-account key credentials can sign locally, so they need nothing extra.
    Other credentials (e.g. Cloud Run's metadata-server identity) sign through the
    IAM signBlob API, which needs the account email and an access token.

    The client's own token is storage-scoped, which signBlob rejects
    (ACCESS_TOKEN_SCOPE_INSUFFICIENT), so fresh cloud-platform-scoped
    credentials are obtained for signing instead.
    """
    # The client exposes no public accessor for its credentials.
    if isinstance(client._credentials, service_account.Credentials):
        return {}

    credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
    # Refresh also resolves the real account email on Cloud Run, where it
    # starts out as "default".
    credentials.refresh(Request())

    email = getattr(credentials, "service_account_email", None)
    if not email:
        raise RuntimeError(
            "Credentials cannot sign URLs: use a service account key or run "
            "as a service account."
        )
    return {"service_account_email": email, "access_token": credentials.token}


def generate_signed_url(gcs_path: str, minutes: int = 60) -> str:
    """Return a v4 signed GET URL for a gs:// path, valid for `minutes`.

    Signs locally with a service account key, or through IAM when running as
    a service account without one (see _signing_kwargs). Raises if the
    client's credentials can do neither.
    """
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Not a GCS path: {gcs_path!r}")

    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = gcs_path.split("/", 3)[3]

    # PDFs open in the browser tab instead of downloading; other types keep
    # GCS's default behaviour.
    extra = {}
    if blob_name.lower().endswith(".pdf"):
        extra = {
            "response_type": "application/pdf",
            "response_disposition": "inline",
        }

    return bucket.blob(blob_name).generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=minutes),
        method="GET",
        **_signing_kwargs(client),
        **extra,
    )
