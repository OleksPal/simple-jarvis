import time
import queue

import numpy as np
import sounddevice as sd
import torch
import torchaudio

from openwakeword.model import Model


VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512

WAKEWORD_SAMPLE_RATE = 16000
WAKEWORD_CHUNK_SIZE = 1280  # 80 ms @ 16 kHz


class AudioManager:
    """
    Owns the microphone continuously.

    Idle:
        microphone -> ring buffer -> wake-word detector

    Active:
        microphone -> VAD -> speech buffer -> STT
    """

    def __init__(
        self,
        vad_model,
        wakeword_model,
        device_id,
        sample_rate,
        channels,
        vad_threshold,
        silence_duration,
        pre_speech_duration,
        wakeword_threshold=0.5,
        ring_buffer_duration=2.0,
    ):
        self.vad_model = vad_model
        self.wakeword_model = wakeword_model

        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels

        self.vad_threshold = vad_threshold
        self.silence_duration = silence_duration
        self.pre_speech_duration = pre_speech_duration

        self.wakeword_threshold = wakeword_threshold

        self.audio_queue = queue.Queue()

        # Number of microphone chunks to keep before wake-word detection.
        self.ring_buffer_chunks = max(
            1,
            round(
                ring_buffer_duration
                * sample_rate
                / self.chunk_size
            ),
        )

        self.ring_buffer = []

        self.stream = None

    @property
    def chunk_size(self):
        """
        Microphone chunk corresponding to 512 samples @ 16 kHz.
        """
        return round(
            VAD_CHUNK_SIZE
            * self.sample_rate
            / VAD_SAMPLE_RATE
        )

    # ------------------------------------------------------------------
    # Microphone
    # ------------------------------------------------------------------

    def _callback(self, indata, frames, time_info, status):
        if status:
            print("Статус аудіо:", status)

        # Mono int16 -> float32 [-1, 1]
        chunk = (
            indata[:, 0].astype(np.float32)
            / 32768.0
        )

        self.audio_queue.put(chunk)

    def start(self):
        if self.stream is not None:
            return

        self.stream = sd.InputStream(
            device=self.device_id,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk_size,
            callback=self._callback,
        )

        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    # ------------------------------------------------------------------
    # Audio conversion
    # ------------------------------------------------------------------

    def _to_16k(self, audio):
        """
        Convert microphone audio to 16 kHz mono float32.
        """

        tensor = torch.from_numpy(audio)

        if self.sample_rate != 16000:
            tensor = torchaudio.functional.resample(
                tensor,
                orig_freq=self.sample_rate,
                new_freq=16000,
            )

        return tensor

    # ------------------------------------------------------------------
    # Ring buffer
    # ------------------------------------------------------------------

    def _push_ring_buffer(self, chunk):
        self.ring_buffer.append(chunk)

        if len(self.ring_buffer) > self.ring_buffer_chunks:
            self.ring_buffer.pop(0)

    def _get_ring_audio(self):
        if not self.ring_buffer:
            return np.array([], dtype=np.float32)

        return np.concatenate(self.ring_buffer)

    # ------------------------------------------------------------------
    # Wake word
    # ------------------------------------------------------------------

    def _wakeword_score(self, chunk):
        """
        Run openWakeWord on one microphone chunk.

        openWakeWord expects 16 kHz int16 PCM.
        """

        audio_16k = self._to_16k(chunk)

        pcm = (
            audio_16k.numpy() * 32767
        ).astype(np.int16)

        # Normally our microphone chunk is 512 samples @ 16 kHz.
        # openWakeWord wants 1280 samples per inference frame.
        #
        # Therefore this method is not called directly for every
        # microphone chunk. wait_for_wake_word() accumulates enough
        # audio first.
        return self.wakeword_model.predict(pcm)

    def wait_for_wake_word(self, cooldown=1.5):
        """
        Wait until the wake word is detected.

        Returns audio that occurred immediately before detection,
        so the beginning of a following command is not lost.
        """

        self.ring_buffer.clear()

        wakeword_buffer = np.array([], dtype=np.float32)

        while True:
            chunk = self.audio_queue.get()

            # Keep recent microphone audio.
            self._push_ring_buffer(chunk)

            # Convert this microphone chunk to 16 kHz.
            audio_16k = self._to_16k(chunk).numpy()

            wakeword_buffer = np.concatenate(
                (wakeword_buffer, audio_16k)
            )

            # Process complete 1280-sample openWakeWord frames.
            while len(wakeword_buffer) >= WAKEWORD_CHUNK_SIZE:

                frame = wakeword_buffer[
                    :WAKEWORD_CHUNK_SIZE
                ]

                wakeword_buffer = wakeword_buffer[
                    WAKEWORD_CHUNK_SIZE:
                ]

                pcm = (
                    frame * 32767
                ).astype(np.int16)

                predictions = self.wakeword_model.predict(
                    pcm
                )

                # One ONNX model -> one prediction.
                score = next(
                    iter(predictions.values())
                )

                if score >= self.wakeword_threshold:
                    print(
                        f"Jarvis: Активацію почуто "
                        f"({score:.2f})"
                    )

                    # ------------------------------------------------------
                    # Drain audio that is already queued.
                    #
                    # This is useful because several microphone chunks may
                    # have accumulated while the wake word was detected.
                    # ------------------------------------------------------
                    while not self.audio_queue.empty():
                        try:
                            self.audio_queue.get_nowait()
                        except queue.Empty:
                            break

                    # ------------------------------------------------------
                    # Cooldown.
                    #
                    # Keep the microphone stream alive, but don't let the
                    # same utterance trigger the detector again.
                    # ------------------------------------------------------
                    end_time = time.monotonic() + cooldown

                    while time.monotonic() < end_time:
                        try:
                            self.audio_queue.get(
                                timeout=0.1
                            )
                        except queue.Empty:
                            pass

                    return self._get_ring_audio()

    # ------------------------------------------------------------------
    # VAD
    # ------------------------------------------------------------------

    def _vad_probability(self, chunk):
        """
        Run VAD on exactly 512 samples @ 16 kHz.
        """

        audio_16k = prepare_vad_audio(
            chunk,
            self.sample_rate,
        ).float()

        with torch.no_grad():
            probability = self.vad_model(
                audio_16k,
                VAD_SAMPLE_RATE,
            ).item()

        return probability

    # ------------------------------------------------------------------
    # Command recording
    # ------------------------------------------------------------------

    def record_command(self, initial_audio=None):
        """
        Record speech using VAD.

        initial_audio can contain audio captured before/during
        wake-word detection.
        """

        pre_chunks = max(
            1,
            round(
                self.pre_speech_duration
                * self.sample_rate
                / self.chunk_size
            ),
        )

        pre_buffer = []
        speech_audio = []

        speech_started = False
        silence_start = None

        # --------------------------------------------------------------
        # Deal with audio captured around wake-word detection.
        #
        # We don't immediately assume it is speech. Feed it through
        # VAD exactly like normal microphone input.
        # --------------------------------------------------------------

        if initial_audio is not None and initial_audio.size:
            initial_chunks = np.array_split(
                initial_audio,
                max(
                    1,
                    len(initial_audio) // self.chunk_size,
                ),
            )

            for chunk in initial_chunks:
                if len(chunk) == 0:
                    continue

                probability = self._vad_probability(chunk)
                is_speech = probability >= self.vad_threshold

                if not speech_started:
                    pre_buffer.append(chunk)

                    if len(pre_buffer) > pre_chunks:
                        pre_buffer.pop(0)

                    if is_speech:
                        speech_started = True
                        speech_audio.extend(pre_buffer)

                else:
                    speech_audio.append(chunk)

                    if is_speech:
                        silence_start = None
                    elif silence_start is None:
                        silence_start = time.monotonic()

        # --------------------------------------------------------------
        # Continue consuming the same microphone stream.
        # --------------------------------------------------------------

        while True:
            chunk = self.audio_queue.get()

            probability = self._vad_probability(chunk)
            is_speech = probability >= self.vad_threshold

            # Waiting for speech.
            if not speech_started:
                pre_buffer.append(chunk)

                if len(pre_buffer) > pre_chunks:
                    pre_buffer.pop(0)

                if is_speech:
                    speech_started = True
                    speech_audio.extend(pre_buffer)

                continue

            # Recording speech.
            speech_audio.append(chunk)

            if is_speech:
                silence_start = None

            elif silence_start is None:
                silence_start = time.monotonic()

            elif (
                time.monotonic() - silence_start
                >= self.silence_duration
            ):
                break

        if not speech_audio:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(
            speech_audio
        ).astype(np.float32)

        # STT gets 16 kHz.
        if self.sample_rate != 16000:
            audio = torchaudio.functional.resample(
                torch.from_numpy(audio),
                orig_freq=self.sample_rate,
                new_freq=16000,
            ).numpy()

        return audio


def prepare_vad_audio(audio, sample_rate):
    """
    Convert arbitrary microphone audio to exactly
    512 samples at 16 kHz.
    """

    audio = torch.from_numpy(audio)

    if sample_rate != VAD_SAMPLE_RATE:
        audio = torchaudio.functional.resample(
            audio,
            orig_freq=sample_rate,
            new_freq=VAD_SAMPLE_RATE,
        )

    if audio.shape[-1] < VAD_CHUNK_SIZE:
        audio = torch.nn.functional.pad(
            audio,
            (0, VAD_CHUNK_SIZE - audio.shape[-1]),
        )

    elif audio.shape[-1] > VAD_CHUNK_SIZE:
        audio = audio[:VAD_CHUNK_SIZE]

    return audio
