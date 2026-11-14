from services import retrieval


def fake_stages(monkeypatch, retrieved):
    monkeypatch.setattr(retrieval, "query_editing",
                        lambda query, jd_text: ("Senior Accountant", "fake resume"))
    monkeypatch.setattr(retrieval, "retrieve_docs",
                        lambda impersonated_resume, top_k: retrieved)
    monkeypatch.setattr(retrieval, "rerank_docs",
                        lambda desired_role, candidates, top_n: candidates[:top_n])
    monkeypatch.setattr(retrieval, "generate_candidate_previews",
                        lambda candidates, desired_role: candidates)


def test_pipeline_returns_candidates_and_role(monkeypatch):
    fake_stages(monkeypatch, retrieved=[{"email": "a@x.com"}, {"email": "b@x.com"}])

    candidates, role = retrieval.run_resume_rag_pipeline(query="accountant", top_n=1)

    assert role == "Senior Accountant"
    assert candidates == [{"email": "a@x.com"}]


def test_pipeline_with_no_results_returns_empty_pair(monkeypatch):
    fake_stages(monkeypatch, retrieved=[])

    candidates, role = retrieval.run_resume_rag_pipeline(query="astronaut")

    assert candidates == []
    assert role == "Senior Accountant"