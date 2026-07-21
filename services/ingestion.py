
from __future__ import annotations

from utils.resume_processing import upsert_resume_to_pinecone
from utils.upload_gcs_file import delete_old_blob, upload_file_gcs
from utils.database import create_database, get_file_link, save_to_sql, update_resume_record
import streamlit as st



def ingest_resume(email: str, uploaded_file) -> tuple[str, str]:
    """
    Ingests a resume for a given email.

    Args:
        email (str): The email of the user.
        uploaded_file: The uploaded file object.

    Returns:
        tuple[str, str]: A tuple containing the link to the uploaded file and the status message.
    """
 
    old_link = get_file_link(email)
    doc_id, file_link = upload_file_gcs(uploaded_file)
    upsert_resume_to_pinecone(email, uploaded_file, file_link)

    if old_link is None:
        save_to_sql(doc_id, file_link, email)
        status = "uploaded"
    else:
        update_resume_record(doc_id, file_link, email)
        delete_old_blob(old_link)
        status = "updated"

    return file_link, status