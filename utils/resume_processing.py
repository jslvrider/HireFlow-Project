import os 
import tempfile
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from dotenv import load_dotenv
from google import genai
import json
from google.genai import types
from pinecone import Pinecone, ServerlessSpec


load_dotenv()
 

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


    metadata_text = response.text.strip()
    metadata_text = metadata_text.replace("```json", "").replace("```", "").strip()
    resume_metadata = json.loads(metadata_text)
    return resume_metadata


def get_embedding(text: str) -> list[float]:
    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
    model = "gemini-embedding-001"

    result = client.models.embed_content(
        model= model,
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768)
    )
    return result.embeddings[0].values
    
def get_pinecone_index():
    pinecone_api_key = os.environ["PINECONE_API_KEY"]
    index_name = "hireflow-resumes"
    pc = Pinecone(api_key=pinecone_api_key)
    if not pc.has_index(index_name):
        pc.create_index(
            name=index_name,
            dimension=768,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    index = pc.Index(index_name)
    return index

def upsert_resume_to_pinecone(email: str, uploaded_file, file_link: str) -> dict:
     
    resume_text = extract_text_from_file(uploaded_file)
    metadata = extract_metadata(resume_text)
    vector = get_embedding(metadata["resume_summary"])
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
    

    index.upsert(vectors=[record], namespace="resumes")

    return {"email": email, "status": True}