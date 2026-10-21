import threading


class AudioError(Exception):
    pass


def list_devices():
    import sounddevice as sd
    return str(sd.query_devices())


class AudioListener:
    SAMPLE_RATE = 16000

    def __init__(self, cfg, on_text, on_status):
        self.cfg = cfg
        self.on_text = on_text
        self.on_status = on_status
        self.stop_event = threading.Event()
        self.thread = None
        self.model = None

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _load(self):
        try:
            import numpy
            import sounddevice
            from faster_whisper import WhisperModel
        except ImportError:
            raise AudioError("Install audio packages: pip install -r requirements-optional.txt")
        self.np = numpy
        self.sd = sounddevice
        if self.model is None:
            self.on_status("Loading Whisper model...")
            self.model = WhisperModel(self.cfg["model_size"], device="cpu", compute_type="int8")

    def _run(self):
        try:
            self._load()
            seconds = self.cfg.get("chunk_seconds", 6)
            threshold = self.cfg.get("silence_threshold", 0.01)
            frames = int(self.SAMPLE_RATE * seconds)
            self.on_status("Listening...")
            with self.sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                device=self.cfg.get("device"),
            ) as stream:
                while not self.stop_event.is_set():
                    data, _ = stream.read(frames)
                    audio = data[:, 0]
                    if float(self.np.sqrt(self.np.mean(audio ** 2))) < threshold:
                        continue
                    segments, _ = self.model.transcribe(audio, language="en", vad_filter=True, beam_size=1)
                    text = " ".join(s.text.strip() for s in segments).strip()
                    if text:
                        self.on_text(text)
            self.on_status("Audio off")
        except AudioError as e:
            self.on_status(str(e))
        except Exception as e:
            self.on_status(f"Audio error: {e}")
