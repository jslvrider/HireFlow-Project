import os
import uuid
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
        blob.upload_from_file(pdf_path)

    file_link = f"gs://{bucket_name}/{doc_id}/{filename}"
    return doc_id, file_link

def delete_old_blob(old_link: str) -> None:
    bucket_name = os.environ["GCS_BUCKET_NAME"]
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob_name = old_link.split("/",3)[3]
    bucket.blob(blob_name).delete()
   