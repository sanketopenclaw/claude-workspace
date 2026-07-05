import os
from dashboard import history


def test_append_and_read_sessions_round_trip(tmp_path):
    history_path = os.path.join(tmp_path, "session_history.jsonl")

    history.append_session(
        lap_history=[{"lap_num": 1, "lap_time_ms": 90000}],
        summary={"lap_count": 1, "best_lap_ms": 90000, "avg_lap_ms": 90000.0},
        history_path=history_path,
    )
    history.append_session(
        lap_history=[{"lap_num": 1, "lap_time_ms": 91000}, {"lap_num": 2, "lap_time_ms": 90500}],
        summary={"lap_count": 2, "best_lap_ms": 90500, "avg_lap_ms": 90750.0},
        history_path=history_path,
    )

    sessions = history.read_sessions(history_path)

    assert len(sessions) == 2
    assert sessions[0]["summary"]["lap_count"] == 1
    assert sessions[1]["summary"]["best_lap_ms"] == 90500
    assert len(sessions[1]["laps"]) == 2
    assert "ended_at" in sessions[0]


def test_read_sessions_returns_empty_list_when_file_missing(tmp_path):
    history_path = os.path.join(tmp_path, "does_not_exist.jsonl")

    assert history.read_sessions(history_path) == []
