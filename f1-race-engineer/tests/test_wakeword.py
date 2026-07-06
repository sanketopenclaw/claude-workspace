import numpy as np
import config
from voice import wakeword


class _FakeModel:
    def __init__(self, scores):
        self._scores = list(scores)
        self._i = 0

    def predict(self, chunk):
        score = self._scores[self._i] if self._i < len(self._scores) else 0.0
        self._i += 1
        return {config.WAKE_WORD_NAME: score}


class _FakeStream:
    """Stops the listener after num_chunks reads, so run()'s while loop exits naturally."""

    def __init__(self, listener, num_chunks):
        self._listener = listener
        self._remaining = num_chunks

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, chunk_size):
        self._remaining -= 1
        if self._remaining <= 0:
            self._listener.stop()
        return np.zeros((chunk_size, 1), dtype="float32"), False


def _build_listener(monkeypatch, scores, num_chunks, times):
    monkeypatch.setattr(wakeword.openwakeword.utils, "download_models", lambda: None)
    monkeypatch.setattr(wakeword, "Model", lambda **kwargs: _FakeModel(scores))

    time_iter = iter(times)
    monkeypatch.setattr(wakeword.time, "time", lambda: next(time_iter))

    calls = []
    listener = wakeword.WakeWordListener(on_wake=lambda: calls.append(1))
    monkeypatch.setattr(wakeword.sd, "InputStream", lambda **kwargs: _FakeStream(listener, num_chunks))
    return listener, calls


def test_cooldown_suppresses_repeat_triggers_within_window(monkeypatch):
    # 3 consecutive high-score frames (one real utterance spans several 80ms
    # frames) should only fire on_wake once, not 3 times.
    scores = [0.9, 0.9, 0.9]
    times = [100.0, 100.05, 100.1]
    listener, calls = _build_listener(monkeypatch, scores, num_chunks=3, times=times)

    listener.run()

    assert len(calls) == 1


def test_cooldown_allows_new_trigger_after_window_elapses(monkeypatch):
    scores = [0.9, 0.9]
    times = [100.0, 200.0]  # second trigger is 100s later, well past the 3s cooldown
    listener, calls = _build_listener(monkeypatch, scores, num_chunks=2, times=times)

    listener.run()

    assert len(calls) == 2


def test_low_score_never_triggers(monkeypatch):
    scores = [0.1, 0.2, 0.3]
    times = [100.0, 100.1, 100.2]
    listener, calls = _build_listener(monkeypatch, scores, num_chunks=3, times=times)

    listener.run()

    assert len(calls) == 0
