import json
import os

DEFAULT_LIBRARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "setup_library.json")


def _load_all(library_path):
    if not os.path.exists(library_path):
        return {}
    with open(library_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_best_setup(track_id, setup, lap_time_ms, library_path=DEFAULT_LIBRARY_PATH):
    library = _load_all(library_path)
    key = str(track_id)
    existing = library.get(key)
    if existing is not None and existing["lap_time_ms"] <= lap_time_ms:
        return  # keep the faster setup already on file
    library[key] = {"setup": setup, "lap_time_ms": lap_time_ms}
    with open(library_path, "w", encoding="utf-8") as f:
        json.dump(library, f)


def load_best_setup(track_id, library_path=DEFAULT_LIBRARY_PATH):
    library = _load_all(library_path)
    return library.get(str(track_id))
