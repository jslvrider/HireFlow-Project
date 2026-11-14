import os 
import tempfile
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from google import genai
import json
from utils.llm_helpers import parse_json_response
from utils.pinecone_store import get_embedding, get_pinecone_index


def extract_text_from_file(uploaded_file) -> str:
    
    uploaded_file.seek(0)
    file_name = uploaded_file.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        if file_name.lower().endswith(".pdf"):
            loader = PyPDFLoader(tmp_path)

        elif file_name.lower().endswith(".docx"):
            loader = Docx2txtLoader(tmp_path)

        elif file_name.lower().endswith(".txt"):
            loader = TextLoader(tmp_path)

        else:
            raise ValueError("Please upload only PDF, DOCX, or TXT file")

        docs = loader.load()

        resume_text = "\n\n".join([doc.page_content for doc in docs])
    
   
        return resume_text
    finally: 
        os.unlink(tmp_path)

def extract_metadata(resume_text: str) -> dict:
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")

    
    prompt = f"""
    You are reading a candidate resume.

    Extract useful information from the resume and return ONLY valid JSON.

    Write "resume_summary" as a pronoun-free professional summary, in the style
    of the summary section at the top of a resume.

    Return this structure:

    {{
    "candidate_name": "",
    "email": "",
    "phone": "",
    "location": "",
    "current_title": "",
    "total_experience_years": "",
    "skills": [],
    "keywords": [],
    "education": "",
    "companies": [],
    "projects": [],
    "resume_summary": ""
    }}

    Resume text:
    {resume_text}
    """

    response = client.models.generate_content(
    model= model,
    contents=prompt
)


    resume_metadata = parse_json_response(response.text)
    return resume_metadata


def prepare_resume(uploaded_file) -> tuple[dict, list[float]]:
    """Extract text, metadata, and embedding without touching any storage."""
    resume_text = extract_text_from_file(uploaded_file)
    metadata = extract_metadata(resume_text)
    vector = get_embedding(metadata["resume_summary"])
    return metadata, vector


def upsert_resume_to_pinecone(
    email: str,
    uploaded_file,
    file_link: str,
    metadata: dict | None = None,
    vector: list[float] | None = None,
) -> dict:
    # Callers that already ran prepare_resume pass metadata and vector in;
    # otherwise compute them here.
    if metadata is None or vector is None:
        metadata, vector = prepare_resume(uploaded_file)
    index = get_pinecone_index()
    
    record = {
            "id": email,
            "values": vector,
            "metadata": {
                "source_file": uploaded_file.name,
                "file_link": file_link,

                "candidate_name": metadata.get("candidate_name", ""),
                "email": email,
                "phone": metadata.get("phone", ""),
                "location": metadata.get("location", ""),
                "current_title": metadata.get("current_title", ""),
                "total_experience_years": str(metadata.get("total_experience_years", "")),

                "skills": metadata.get("skills", []),
                "keywords": metadata.get("keywords", []),
                "companies": metadata.get("companies", []),

                "education": metadata.get("education", ""),
                "resume_summary": metadata.get("resume_summary", ""),

                "full_metadata_json": json.dumps(metadata)}
            }
    

    index.upsert(vectors=[record], namespace=os.getenv("PINECONE_NAMESPACE", "resumes"))

    return {"email": email, "status": True}