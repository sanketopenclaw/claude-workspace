import collections
import threading


class EngineerLog:
    def __init__(self, maxlen=50):
        self._lock = threading.Lock()
        self._entries = collections.deque(maxlen=maxlen)

    def add_callout(self, time_str, text):
        with self._lock:
            self._entries.append({"time": time_str, "type": "callout", "text": text})

    def add_qa(self, time_str, question, answer):
        with self._lock:
            self._entries.append({"time": time_str, "type": "qa", "q": question, "text": answer})

    def snapshot(self):
        with self._lock:
            return list(self._entries)
