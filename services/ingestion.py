
from __future__ import annotations

from utils.resume_processing import prepare_resume, upsert_resume_to_pinecone
from utils.upload_gcs_file import delete_old_blob, upload_file_gcs
from utils.database import (
    create_database,
    get_file_link,
    save_to_sql,
    transaction,
    update_resume_record,
)
import logging
import streamlit as st

logger = logging.getLogger(__name__)



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

    # Everything that can fail on a bad file or bad LLM reply runs first,
    # before any GCS, Pinecone, or SQL write.
    metadata, vector = prepare_resume(uploaded_file)

    # Extraction left the stream at EOF; rewind so the upload sends the full file.
    uploaded_file.seek(0)
    doc_id, file_link = upload_file_gcs(uploaded_file)

    try:
        # The SQL write is staged first but commits only when the block exits
        # cleanly, i.e. after the Pinecone upsert succeeds. Any failure rolls
        # the SQL write back.
        with transaction() as conn:
            if old_link is None:
                save_to_sql(doc_id, file_link, email, conn=conn)
                status = "uploaded"
            else:
                update_resume_record(doc_id, file_link, email, conn=conn)
                status = "updated"

            upsert_resume_to_pinecone(email, uploaded_file, file_link, metadata, vector)
    except Exception:
        # Roll back the new blob so a failed ingest leaves no orphan in GCS.
        try:
            delete_old_blob(file_link)
        except Exception:
            logger.warning(
                "Could not delete new blob %s after failed ingest", file_link, exc_info=True
            )
        raise

    # The record now points at the new blob. Dropping the old one is best-effort:
    # a failure here must not fail an ingestion that already succeeded.
    if old_link is not None:
        try:
            delete_old_blob(old_link)
        except Exception:
            logger.warning("Could not delete old blob %s", old_link, exc_info=True)

    return file_link, status