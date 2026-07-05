import os

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
UDP_LISTEN_IP = "0.0.0.0"
UDP_LISTEN_PORT = 20777
TTS_VOICE = "en-GB-RyanNeural"
WAKE_WORD_NAME = "hey_jarvis"
WHISPER_MODEL_SIZE = "base.en"


def get_anthropic_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
    return key
