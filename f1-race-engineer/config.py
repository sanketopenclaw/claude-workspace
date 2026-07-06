import os

CEREBRAS_MODEL = "gemma-4-31b"
OPENROUTER_MODEL = "anthropic/claude-haiku-4.5"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MISTRAL_MODEL = "mistral-small-latest"
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
NVIDIA_MODEL = "nvidia/llama-3.3-nemotron-super-49b-v1"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
UDP_LISTEN_IP = "0.0.0.0"
UDP_LISTEN_PORT = 20777
TTS_VOICE = "en-GB-RyanNeural"
# openWakeWord ships hey_jarvis/alexa/hey_mycroft as pretrained models. A genuinely
# custom "hey engineer" wake-word needs real recorded samples run through
# openWakeWord's training notebook (github.com/dscripka/openWakeWord) to produce a
# .onnx model - can't be fabricated without that data/training pass. Swap
# WAKE_WORD_NAME to any pretrained model name, or point it at a custom .onnx path
# once trained.
WAKE_WORD_NAME = "hey_jarvis"
WHISPER_MODEL_SIZE = "base.en"

LLM_PROVIDER_TIMEOUT_SECONDS = 5.0  # hard per-provider cutoff before falling through the chain

VOICE_PERSONALITY = "calm"  # "calm" or "intense"
PERSONALITY_TTS_VOICES = {
    "calm": "en-GB-RyanNeural",
    "intense": "en-US-GuyNeural",
}
RADIO_STATIC_ENABLED = True


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


def get_mistral_api_key():
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY environment variable not set")
    return key


def get_nvidia_api_key():
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY environment variable not set")
    return key
