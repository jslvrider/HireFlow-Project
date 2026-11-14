import os

from google import genai
from google.genai import types
from pinecone import Pinecone, ServerlessSpec


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
