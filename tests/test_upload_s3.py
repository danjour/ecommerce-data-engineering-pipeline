import importlib
from threading import Lock
import pytest

class FakeS3:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def upload_file(self, local_path, bucket, key):
        self.calls.append((local_path, bucket, key))
        if self.fail:
            raise RuntimeError("boom")

@pytest.fixture
def upload_module(monkeypatch, tmp_path):
    monkeypatch.setenv("BUCKET_NAME", "bucket-test")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_WORKERS", "2")
    monkeypatch.setenv("TRACK_FILE", str(tmp_path / "processed_files.json"))
    import upload_s3
    return importlib.reload(upload_s3)

def test_upload_file_skips_missing(upload_module):
    key, status, msg = upload_module.upload_file(
        FakeS3(), "2026-04-25", "customers.csv", set(), Lock()
    )
    assert status == "skipped_missing"
    assert "File not found" in msg

def test_upload_file_success(upload_module, tmp_path):
    (tmp_path / "2026-04-25-customers.csv").write_text("id\n1\n", encoding="utf-8")
    uploaded_ids = set()
    key, status, _ = upload_module.upload_file(
        FakeS3(), "2026-04-25", "customers.csv", uploaded_ids, Lock()
    )
    assert status == "uploaded"
    assert key in uploaded_ids
