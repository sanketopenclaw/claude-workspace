import json
import os
import datetime

DEFAULT_HISTORY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "session_history.jsonl")


def append_session(lap_history, summary, history_path=DEFAULT_HISTORY_PATH):
    record = {
        "ended_at": datetime.datetime.now().isoformat(),
        "laps": lap_history,
        "summary": summary,
    }
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_sessions(history_path=DEFAULT_HISTORY_PATH):
    if not os.path.exists(history_path):
        return []
    sessions = []
    with open(history_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                sessions.append(json.loads(line))
    return sessions
