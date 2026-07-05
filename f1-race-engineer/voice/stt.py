import tempfile
import wave
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import config

_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

SAMPLE_RATE = 16000
CHUNK_FRAMES = 1024
SILENCE_AMPLITUDE_THRESHOLD = 500
SILENCE_CHUNKS_TO_STOP = 20  # ~1.3s of quiet
MAX_RECORD_SECONDS = 6


def record_question():
    frames = []
    silence_chunks = 0
    max_chunks = int(MAX_RECORD_SECONDS * SAMPLE_RATE / CHUNK_FRAMES)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16") as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(CHUNK_FRAMES)
            frames.append(chunk.copy())
            if np.abs(chunk).mean() < SILENCE_AMPLITUDE_THRESHOLD:
                silence_chunks += 1
                if silence_chunks > SILENCE_CHUNKS_TO_STOP:
                    break
            else:
                silence_chunks = 0

    audio = np.concatenate(frames)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return wav_path


def transcribe(wav_path):
    segments, _ = _model.transcribe(wav_path)
    return " ".join(seg.text for seg in segments).strip()
