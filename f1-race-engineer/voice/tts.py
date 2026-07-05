import asyncio
import os
import tempfile
import time
import edge_tts
import pygame
import config

pygame.mixer.init()


async def _synthesize(text, mp3_path):
    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
    await communicate.save(mp3_path)


def speak(text):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        mp3_path = f.name
    try:
        asyncio.run(_synthesize(text, mp3_path))
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
