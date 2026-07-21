
from __future__ import annotations

import streamlit as st

from services.ingestion import ingest_resume
from utils.database import create_database

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
                file_link, status = ingest_resume(user_id, uploaded_file)
                st.success(f"Resume {status} successfully.")
            
                st.write(file_link)
            except Exception as e:
                st.error(f"Upload failed: {e}")
            

def main() -> None:
    create_database()
    st.title("Resume Upload Portal")
    render_login_section()
    st.divider()
    render_upload_section()


if __name__ == "__main__":
    main()