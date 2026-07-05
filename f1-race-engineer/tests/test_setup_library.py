import os
from rules import setup_library


def test_save_and_load_best_setup_round_trip(tmp_path):
    library_path = os.path.join(tmp_path, "setup_library.json")
    setup = {"front_wing": 25, "rear_wing": 40}

    setup_library.save_best_setup(track_id=3, setup=setup, lap_time_ms=90000, library_path=library_path)
    loaded = setup_library.load_best_setup(track_id=3, library_path=library_path)

    assert loaded["setup"] == setup
    assert loaded["lap_time_ms"] == 90000


def test_save_best_setup_keeps_faster_lap_on_file(tmp_path):
    library_path = os.path.join(tmp_path, "setup_library.json")

    setup_library.save_best_setup(3, {"front_wing": 25}, 90000, library_path=library_path)
    setup_library.save_best_setup(3, {"front_wing": 30}, 91000, library_path=library_path)  # slower, ignored

    loaded = setup_library.load_best_setup(3, library_path=library_path)

    assert loaded["lap_time_ms"] == 90000
    assert loaded["setup"] == {"front_wing": 25}


def test_save_best_setup_overwrites_when_faster(tmp_path):
    library_path = os.path.join(tmp_path, "setup_library.json")

    setup_library.save_best_setup(3, {"front_wing": 25}, 90000, library_path=library_path)
    setup_library.save_best_setup(3, {"front_wing": 30}, 89000, library_path=library_path)  # faster

    loaded = setup_library.load_best_setup(3, library_path=library_path)

    assert loaded["lap_time_ms"] == 89000
    assert loaded["setup"] == {"front_wing": 30}


def test_load_best_setup_returns_none_when_missing(tmp_path):
    library_path = os.path.join(tmp_path, "does_not_exist.json")

    assert setup_library.load_best_setup(3, library_path=library_path) is None


def test_different_tracks_stored_independently(tmp_path):
    library_path = os.path.join(tmp_path, "setup_library.json")

    setup_library.save_best_setup(3, {"front_wing": 25}, 90000, library_path=library_path)
    setup_library.save_best_setup(7, {"front_wing": 35}, 85000, library_path=library_path)

    assert setup_library.load_best_setup(3, library_path=library_path)["setup"] == {"front_wing": 25}
    assert setup_library.load_best_setup(7, library_path=library_path)["setup"] == {"front_wing": 35}
