import asyncio
import os
import tempfile
import time
import edge_tts
import numpy as np
import pygame
import config

pygame.mixer.init()

STATIC_SAMPLE_RATE = 22050


def generate_static_samples(duration_s=0.2, sample_rate=STATIC_SAMPLE_RATE, volume=0.15):
    noise = np.random.uniform(-1.0, 1.0, int(sample_rate * duration_s))
    return (noise * volume * 32767).astype(np.int16)


_static_sound = None


def _get_static_sound():
    global _static_sound
    if _static_sound is None:
        samples = generate_static_samples()
        stereo = np.column_stack([samples, samples])
        _static_sound = pygame.sndarray.make_sound(stereo)
    return _static_sound


def _tts_voice():
    return config.PERSONALITY_TTS_VOICES.get(config.VOICE_PERSONALITY, config.TTS_VOICE)


async def _synthesize(text, mp3_path):
    communicate = edge_tts.Communicate(text, _tts_voice())
    await communicate.save(mp3_path)


def speak(text):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3_path = f.name
    try:
        asyncio.run(_synthesize(text, mp3_path))
        if config.RADIO_STATIC_ENABLED:
            _get_static_sound().play()
            pygame.time.wait(200)
        pygame.mixer.music.load(mp3_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)
    finally:
        pygame.mixer.music.stop()
        time.sleep(0.2)
        if os.path.exists(mp3_path):
            try:
                os.remove(mp3_path)
            except PermissionError:
                pass
