import numpy as np
from voice import tts


def test_generate_static_samples_shape_and_range():
    samples = tts.generate_static_samples(duration_s=0.1, sample_rate=22050, volume=0.15)

    assert samples.dtype == np.int16
    assert len(samples) == 2205
    assert np.max(np.abs(samples)) <= int(0.15 * 32767) + 1


def test_generate_static_samples_respects_volume():
    quiet = tts.generate_static_samples(duration_s=0.1, volume=0.05)
    loud = tts.generate_static_samples(duration_s=0.1, volume=0.5)

    assert np.max(np.abs(quiet)) < np.max(np.abs(loud))


def test_tts_voice_uses_personality_mapping(monkeypatch):
    import config
    monkeypatch.setattr(config, "VOICE_PERSONALITY", "intense")
    assert tts._tts_voice() == config.PERSONALITY_TTS_VOICES["intense"]


def test_tts_voice_falls_back_to_configured_voice_for_unknown_personality(monkeypatch):
    import config
    monkeypatch.setattr(config, "VOICE_PERSONALITY", "nonexistent")
    assert tts._tts_voice() == config.TTS_VOICE
