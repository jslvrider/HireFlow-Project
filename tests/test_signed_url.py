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


class _FakeClient:
    """Stands in for a storage client holding non-key (e.g. metadata-server) credentials."""

    _credentials = object()


def _patch_default(monkeypatch, credentials):
    """Make google.auth.default return `credentials` and record how it was called."""
    seen = {}

    def fake_default(scopes=None, **kwargs):
        seen["scopes"] = scopes
        return credentials, "fake-project"

    monkeypatch.setattr(upload_gcs_file.google.auth, "default", fake_default)
    return seen


def test_signing_kwargs_use_fresh_cloud_platform_credentials(monkeypatch):
    class FreshCredentials:
        token = None
        # Cloud Run reports "default" until the credentials are refreshed.
        service_account_email = "default"

        def refresh(self, request):
            self.token = "fresh-token"
            self.service_account_email = "sa@proj.iam.gserviceaccount.com"

    seen = _patch_default(monkeypatch, FreshCredentials())

    assert upload_gcs_file._signing_kwargs(_FakeClient()) == {
        "service_account_email": "sa@proj.iam.gserviceaccount.com",
        "access_token": "fresh-token",
    }
    assert seen["scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]


def test_signing_kwargs_ignore_client_token_for_iam(monkeypatch):
    """The client's storage-scoped credentials must not be used for IAM signing."""

    class ClientCredentials:
        token = "storage-scoped-token"
        service_account_email = "sa@proj.iam.gserviceaccount.com"
        valid = True

        def refresh(self, request):
            raise AssertionError("client credentials must not be refreshed or used")

    class FreshCredentials:
        token = None
        service_account_email = "sa@proj.iam.gserviceaccount.com"

        def refresh(self, request):
            self.token = "fresh-token"

    class Client:
        _credentials = ClientCredentials()

    _patch_default(monkeypatch, FreshCredentials())

    assert upload_gcs_file._signing_kwargs(Client())["access_token"] == "fresh-token"


def test_signing_kwargs_skip_default_for_service_account_key(monkeypatch):
    def fail_default(*args, **kwargs):
        raise AssertionError("google.auth.default must not be called for key credentials")

    monkeypatch.setattr(upload_gcs_file.google.auth, "default", fail_default)

    class Client:
        _credentials = object.__new__(upload_gcs_file.service_account.Credentials)

    assert upload_gcs_file._signing_kwargs(Client()) == {}


def test_signing_kwargs_reject_credentials_without_email(monkeypatch):
    class FreshCredentials:
        token = None

        def refresh(self, request):
            self.token = "fresh-token"

    _patch_default(monkeypatch, FreshCredentials())

    with pytest.raises(RuntimeError):
        upload_gcs_file._signing_kwargs(_FakeClient())