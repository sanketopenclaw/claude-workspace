import threading
import openwakeword
from openwakeword.model import Model
import sounddevice as sd
import config

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms, openWakeWord's recommended frame size


class WakeWordListener(threading.Thread):
    def __init__(self, on_wake):
        super().__init__(daemon=True)
        self.on_wake = on_wake
        self._stop = threading.Event()
        openwakeword.utils.download_models()
        self._model = Model(
            wakeword_models=[config.WAKE_WORD_NAME],
            inference_framework="onnx",
        )

    def run(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=CHUNK_SIZE) as stream:
            while not self._stop.is_set():
                audio_chunk, _ = stream.read(CHUNK_SIZE)
                prediction = self._model.predict(audio_chunk[:, 0])
                score = prediction.get(config.WAKE_WORD_NAME, 0.0)
                if score > 0.5:
                    self.on_wake()

    def stop(self):
        self._stop.set()
