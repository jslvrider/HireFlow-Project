import pytest
from utils import upload_gcs_file


def test_rejects_non_gcs_path():
    with pytest.raises(ValueError):
        upload_gcs_file.generate_signed_url("https://example.com/file.pdf")


def test_pdf_links_open_inline(monkeypatch):
    calls = {}

    class FakeBlob:
        def generate_signed_url(self, **kwargs):
            calls.update(kwargs)
            return "https://signed.example"

    class FakeBucket:
        def blob(self, name):
            calls["blob_name"] = name
            return FakeBlob()

    class FakeClient:
        def bucket(self, name):
            calls["bucket"] = name
            return FakeBucket()

    monkeypatch.setattr(upload_gcs_file.storage, "Client", lambda *a, **k: FakeClient())

    url = upload_gcs_file.generate_signed_url("gs://my-bucket/abc/resume.pdf")

    assert url == "https://signed.example"
    assert calls["bucket"] == "fake-value-for-tests"
    assert calls["blob_name"] == "abc/resume.pdf"
    assert calls["response_disposition"] == "inline"