import mimetypes
import os
import uuid
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import storage

load_dotenv()




def upload_file_gcs(pdf_path: str|Path) -> tuple [str, str]:
    doc_id = str(uuid.uuid4())
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    if isinstance(pdf_path, (str, Path)):
        # local file path — get filename from path, upload directly from disk
        filename = Path(pdf_path).name
        blob = bucket.blob(f"{doc_id}/{filename}")
        blob.upload_from_filename(pdf_path)
    else:
        # Streamlit UploadedFile object — get filename from metadata, upload from memory
        filename = Path(pdf_path.name).name
        blob = bucket.blob(f"{doc_id}/{filename}")
        # Streamlit sets .type to the browser-reported MIME type; fall back to
        # guessing from the filename for plain file objects that lack it.
        content_type = getattr(pdf_path, "type", None) or mimetypes.guess_type(filename)[0]
        blob.upload_from_file(pdf_path, content_type=content_type)

    file_link = f"gs://{bucket_name}/{doc_id}/{filename}"
    return doc_id, file_link

def delete_old_blob(old_link: str) -> None:
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = old_link.split("/",3)[3]
    bucket.blob(blob_name).delete()


def generate_signed_url(gcs_path: str, minutes: int = 60) -> str:
    """Return a v4 signed GET URL for a gs:// path, valid for `minutes`.

    Needs credentials that can sign (a service account key); raises if the
    client's credentials cannot.
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
        **extra,
    )
