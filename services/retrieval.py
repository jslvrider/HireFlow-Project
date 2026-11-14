import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from utils.pinecone_store import get_embedding, get_pinecone_index
from utils.reranker import get_cross_encoder
from google.genai import types
from utils.llm_helpers import parse_json_response

load_dotenv()


def query_editing(query: Optional[str] = None, jd_text: Optional[str] = None) -> tuple[str, str]:
    """
    Combines the optional user query and job description into an ideal intent
    summary of the desired role, then generates a HyDE-style impersonated
    resume summary for embedding against candidate resume summaries.

    Args:
        query (str): The user's query.
        jd_text (str): The job description text.
    Returns:
        tuple[str, str]: (desired_role, impersonated_resume)
    """
    if not (query or "").strip() and not (jd_text or "").strip():
        raise ValueError("query_editing requires a query, a job description, or both.")

    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")

    prompt = f"""
    You are helping a recruiter search a database of resume summaries.

    You are given two OPTIONAL inputs: a free-text query and a job description.
    At least one of them will be present.

    User query:
    {query or "(none provided)"}

    Job description:
    {jd_text or "(none provided)"}

    Do two things and return ONLY valid JSON with exactly these two fields:

    1. "desired_role": Combine the inputs above into a concise, ideal intent
       summary of the role the user is looking to fill (or find), capturing
       title, seniority, key skills, and responsibilities.

    2. "impersonated_resume": Using a HyDE (Hypothetical Document Embeddings)
       approach, write a hypothetical resume summary written as a pronoun-free professional summary in the style of a resume's summary section,
       as if it were the professional summary section of an ideal candidate's
       resume for this role. It should read like a real resume summary
       (skills, experience, background) so it can be embedded and compared
       against real candidate resume summaries.

    Return this structure exactly:

    {{
    "desired_role": "",
    "impersonated_resume": ""
    }}
    """

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0),
    )

    result = parse_json_response(response.text)

    desired_role = result["desired_role"].strip()
    impersonated_resume = result["impersonated_resume"].strip()

    return desired_role, impersonated_resume



def retrieve_docs(impersonated_resume:str, top_k:int = 7) -> list[dict]:
    """
    Retrieves relevant candidate resume summaries from Pinecone based on the
    user's query and/or job description.

    Args:
        impersonated_resume (str): The impersonated resume summary.
        top_k (int): The number of top results to return.
    Returns:
        list[dict]: A list of relevant candidate resume summaries with metadata.
    """
    
    embedding = get_embedding(impersonated_resume)
    index = get_pinecone_index()

    results = index.query(
        vector=embedding,
        top_k=top_k,
        namespace="resumes",
        include_metadata=True,
    )

    normalized_matches = []
    for match in results.matches:
        metadata = match.metadata or {}
        normalized_matches.append({
            "candidate_name": metadata.get("candidate_name", ""),
            "email": metadata.get("email", match.id),   
            "score": match.score,
            "current_title": metadata.get("current_title", ""),
            "file_link": metadata.get("file_link", ""),
            "resume_summary": metadata.get("resume_summary", ""),
        })

    return normalized_matches


def rerank_docs(desired_role: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    if not candidates:
        return []
    cross_encoder = get_cross_encoder()

    pairs = [(desired_role, candidate["resume_summary"]) for candidate in candidates]
    scores = cross_encoder.predict(pairs)

    reranked = sorted(zip(scores, candidates), key=lambda pair: pair[0], reverse=True)

    top = []
    for score, candidate in reranked[:top_n]:
        candidate["rerank_score"] = float(score)
        top.append(candidate)
    return top


def generate_candidate_previews(candidates: list[dict], desired_role: str) -> list[dict]:
    """
    Generates a recruiter-facing preview paragraph for each of the top
    candidates, explaining why they fit the desired role, their strengths,
    and any gaps. Uses a single LLM call for all candidates.

    Args:
        candidates (list[dict]): A list of candidate dictionaries.
        desired_role (str): The desired role for which to generate previews.
    Returns:
        list[dict]: Each dict contains candidate_name, file_link,
            current_title, resume_summary, score, and preview.
    """
    if not candidates:
        return []

    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key)
    model = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")

    candidates_block = "\n\n".join(
        f"Candidate email: {candidate.get('email', '')}\n"
        f"Current title: {candidate.get('current_title', '')}\n"
        f"Resume summary: {candidate.get('resume_summary', '')}"
        for candidate in candidates
    )

    prompt = f"""
    You are a recruiter assistant writing candidate previews for a hiring manager.

    Desired role:
    {desired_role}

    Below are {len(candidates)} candidates. For EACH candidate, write a short
    recruiter-facing paragraph explaining why this person fits the desired role, covering
    their strengths and any notable gaps relative to the role.

    {candidates_block}

    Return ONLY valid JSON: a list with one object per candidate, each containing that
    candidate's email and their preview.

    [
      {{"email": "", "preview": ""}}
    ]
    """

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    llm_response = parse_json_response(response.text)

    for candidate in candidates:
        candidate["preview"] = ""

    by_email = {candidate["email"]: candidate for candidate in candidates}
    for item in llm_response:
        target = by_email.get(item.get("email"))
        if target is not None:
            target["preview"] = item["preview"].strip()

    return candidates


def run_resume_rag_pipeline(query: Optional[str] = None, jd_text: Optional[str] = None, top_k: int = 7, top_n: int = 3,) -> tuple[list[dict], str]:
    """
    Runs the full resume retrieval and ranking pipeline.

    Args:
        query (str): The user's query.
        jd_text (str): The job description text.
        top_k (int): The number of top results to retrieve from Pinecone.
        top_n (int): The number of top results to return after reranking.

    Returns:
        list[dict]: A list of top candidate dictionaries with metadata and previews.
        str: The desired role summary generated from the query and job description."""

    desired_role, impersonated_resume = query_editing(query=query, jd_text=jd_text)
    candidates = retrieve_docs(impersonated_resume=impersonated_resume, top_k=top_k)
    if not candidates:
        return [], desired_role
    reranked_candidates = rerank_docs(desired_role=desired_role, candidates=candidates, top_n=top_n)
    final_candidates = generate_candidate_previews(candidates=reranked_candidates, desired_role=desired_role)
    return final_candidates, desired_role

