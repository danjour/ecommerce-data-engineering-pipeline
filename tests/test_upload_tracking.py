from upload_tracking import load_uploaded_ids, save_uploaded_ids

def test_load_missing_returns_empty(tmp_path):
    assert load_uploaded_ids(str(tmp_path / "missing.json")) == set()

def test_save_and_load_roundtrip(tmp_path):
    track = str(tmp_path / "processed_files.json")
    save_uploaded_ids(track, {"b", "a"})
    assert load_uploaded_ids(track) == {"a", "b"}