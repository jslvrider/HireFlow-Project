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
    # The fake client has no credentials; never reach real signing or IAM.
    monkeypatch.setattr(upload_gcs_file, "_signing_kwargs", lambda client: {})

    url = upload_gcs_file.generate_signed_url("gs://my-bucket/abc/resume.pdf")

    assert url == "https://signed.example"
    assert calls["bucket"] == "fake-value-for-tests"
    assert calls["blob_name"] == "abc/resume.pdf"
    assert calls["response_disposition"] == "inline"


def test_signing_kwargs_are_passed_through(monkeypatch):
    calls = {}

    class FakeBlob:
        def generate_signed_url(self, **kwargs):
            calls.update(kwargs)
            return "https://signed.example"

    class FakeBucket:
        def blob(self, name):
            return FakeBlob()

    class FakeClient:
        def bucket(self, name):
            return FakeBucket()

    iam = {"service_account_email": "sa@proj.iam.gserviceaccount.com", "access_token": "tok"}
    monkeypatch.setattr(upload_gcs_file.storage, "Client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(upload_gcs_file, "_signing_kwargs", lambda client: iam)

    upload_gcs_file.generate_signed_url("gs://my-bucket/abc/resume.pdf")

    assert calls["service_account_email"] == iam["service_account_email"]
    assert calls["access_token"] == "tok"


def test_signing_kwargs_empty_for_service_account_key():
    class FakeClient:
        # Bypass __init__: only the type matters for the isinstance check.
        _credentials = object.__new__(upload_gcs_file.service_account.Credentials)

    assert upload_gcs_file._signing_kwargs(FakeClient()) == {}


def test_signing_kwargs_use_iam_for_other_credentials():
    class FakeCredentials:
        valid = True
        token = "tok"
        service_account_email = "sa@proj.iam.gserviceaccount.com"

    class FakeClient:
        _credentials = FakeCredentials()

    assert upload_gcs_file._signing_kwargs(FakeClient()) == {
        "service_account_email": "sa@proj.iam.gserviceaccount.com",
        "access_token": "tok",
    }


def test_signing_kwargs_reject_credentials_without_email():
    class FakeCredentials:
        valid = True
        token = "tok"

    class FakeClient:
        _credentials = FakeCredentials()

    with pytest.raises(RuntimeError):
        upload_gcs_file._signing_kwargs(FakeClient())