
from __future__ import annotations

import streamlit as st

from services.ingestion import ingest_resume
from utils.database import create_database
from utils.upload_gcs_file import generate_signed_url
from services.retrieval import run_resume_rag_pipeline

st.set_page_config(page_title="Resume Uploader", page_icon="📄", layout="centered")


def render_login_section() -> None:
    st.subheader("Login")
    user_id_input = st.text_input("Email", value=st.session_state.get("Email", ""))

    if st.button("Continue", use_container_width=True):
        if user_id_input.strip():
            st.session_state["Email"] = user_id_input.strip()
            st.success(f"Logged in as {st.session_state['Email']}")
        else:
            st.error("Enter an  Email.")


def render_upload_section() -> None:
    user_id = st.session_state.get("Email")
    if not user_id:
        st.info("Log in first to upload a resume.")
        return

    st.subheader("Upload Resume")
    st.write(f"Current user: `{user_id}`")



    uploaded_file = st.file_uploader(
        "Choose a resume",
        type=["pdf", "doc", "docx"],
    )

    if st.button("Upload Resume", use_container_width=True):


        if uploaded_file is None:
            st.error("Choose a file before uploading.")
            return

        with st.spinner("Uploading resume..."):
            try:
                result = ingest_resume(user_id, uploaded_file)
                st.success(f"Resume {result.status} successfully.")

                st.write(result.file_link)
            except ValueError:
                st.error("The AI returned an unexpected response. Please try again.")
            except Exception as e:
                st.error(f"Upload failed: {e}")
            
def render_search_section() -> None:
    st.subheader("Search Candidates")

    query = st.text_input(
        "What are you looking for?",
        placeholder="e.g. senior accountant with financial reporting experience",
    )
    jd_text = st.text_area(
        "Job description (optional)",
        placeholder="Paste a job description here to refine the search.",
        height=150,
    )

    if st.button("Search", use_container_width=True):
        # query_editing raises if both are empty; guard here so the UI
        # gives a friendly message instead of an exception.
        if not query.strip() and not jd_text.strip():
            st.error("Enter a search query, a job description, or both.")
            return

        with st.spinner("Searching candidates..."):
            try:
                candidates, desired_role = run_resume_rag_pipeline(
                    query=query or None,
                    jd_text=jd_text or None,
                )
            except ValueError:
                st.error("The AI returned an unexpected response. Please try again.")
                return
            except Exception as e:
                st.error(f"Search failed: {e}")
                st.exception(e)   # shows the full traceback in the page, for development

        # Show what the pipeline actually searched for — collapsed by default.
        with st.expander("Search details"):
            st.write(desired_role)

        if not candidates:
            st.info("No matching candidates found. Try broadening your search.")
            return

        st.write(f"Top {len(candidates)} candidates:")
        for candidate in candidates:
            st.markdown(f"### {candidate['candidate_name']}")
            st.caption(candidate.get("current_title", ""))
            st.write(candidate.get("preview", ""))
            # Stored links are gs:// paths, which browsers can't open. Sign a
            # short-lived HTTPS URL at render time; keep the stored path as is.
            try:
                signed_url = generate_signed_url(candidate.get("file_link", ""))
                st.link_button("View resume", signed_url)
            except Exception:
                st.caption("Resume link unavailable.")
            st.divider()

            
def main() -> None:
    create_database()
    st.title("Resume Upload Portal")
    render_login_section()
    st.divider()
    render_upload_section()
    st.divider()
    render_search_section()


if __name__ == "__main__":
    main()