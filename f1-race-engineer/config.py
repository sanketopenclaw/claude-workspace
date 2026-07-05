import os

CEREBRAS_MODEL = "gemma-4-31b"
OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
UDP_LISTEN_IP = "0.0.0.0"
UDP_LISTEN_PORT = 20777
TTS_VOICE = "en-GB-RyanNeural"
WAKE_WORD_NAME = "hey_jarvis"
WHISPER_MODEL_SIZE = "base.en"


def get_cerebras_api_key():
    key = os.environ.get("CEREBRAS_API_KEY")
    if not key:
        raise RuntimeError("CEREBRAS_API_KEY environment variable not set")
    return key


def get_openrouter_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")
    return key
