import json
import os


def load_uploaded_ids(track_file: str) -> set[str]:
    try:
        with open(track_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data) if isinstance(data, list) else set()
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_uploaded_ids(track_file: str, uploaded_ids: set[str]) -> None:
    track_dir = os.path.dirname(track_file)
    if track_dir:
        os.makedirs(track_dir, exist_ok=True)

    tmp_file = f"{track_file}.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(sorted(uploaded_ids), f, indent=2)
    os.replace(tmp_file, track_file)
