import time
import queue
import sounddevice as sd
import numpy as np
import torch
import torchaudio

VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512
VAD_MIN_SAMPLES = 512

def record_audio(
    vad_model,
    device_id: int,
    sample_rate,
    vad_threshold,
    silence_duration,
    pre_speech_duration,
    start_timeout=5.0,
    stop_event=None,
):
    """Record speech until silence, timeout, or stop."""

    import comtypes

    audio_queue = queue.Queue()
    com_initialized = False

    chunk_size = round(
        VAD_CHUNK_SIZE * sample_rate / VAD_SAMPLE_RATE
    )

    pre_chunks = max(
        1,
        round(pre_speech_duration * sample_rate / chunk_size),
    )

    pre_buffer = []
    speech_audio = []

    speech_started = False
    silence_start = None
    listening_started = time.monotonic()

    def callback(indata, frames, time_info, status):
        if status:
            print("Статус аудіо:", status)

        if stop_event is not None and stop_event.is_set():
            return

        # Input is int16; normalize to float32 in [-1, 1].
        chunk = indata[:, 0].astype(np.float32) / 32768.0
        audio_queue.put(chunk)

    try:
        # COM must be initialized on the thread opening the stream.
        comtypes.CoInitialize()
        com_initialized = True

        with sd.InputStream(
            device=device_id,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=chunk_size,
            callback=callback,
            extra_settings=sd.WasapiSettings(exclusive=False),
        ):
            while True:
                if stop_event is not None and stop_event.is_set():
                    return np.array([], dtype=np.float32)

                if not speech_started:
                    elapsed = time.monotonic() - listening_started

                    if elapsed >= start_timeout:
                        print(
                            "Jarvis: Час очікування команди вичерпано."
                        )
                        return np.array([], dtype=np.float32)

                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                if stop_event is not None and stop_event.is_set():
                    return np.array([], dtype=np.float32)

                audio_16k = prepare_vad_audio(chunk, sample_rate)
                audio_16k = audio_16k.float()

                with torch.no_grad():
                    probability = vad_model(
                        audio_16k,
                        VAD_SAMPLE_RATE,
                    ).item()

                if stop_event is not None and stop_event.is_set():
                    return np.array([], dtype=np.float32)

                is_speech = probability >= vad_threshold

                if not speech_started:
                    pre_buffer.append(chunk)

                    if len(pre_buffer) > pre_chunks:
                        pre_buffer.pop(0)

                    if is_speech:
                        speech_started = True
                        speech_audio.extend(pre_buffer)

                    continue

                speech_audio.append(chunk)

                if is_speech:
                    silence_start = None
                elif silence_start is None:
                    silence_start = time.monotonic()
                elif (
                    time.monotonic() - silence_start
                    >= silence_duration
                ):
                    break

    finally:
        if com_initialized:
            comtypes.CoUninitialize()

    if stop_event is not None and stop_event.is_set():
        return np.array([], dtype=np.float32)

    if not speech_audio:
        return np.array([], dtype=np.float32)

    audio = np.concatenate(speech_audio).astype(np.float32)

    audio = torchaudio.functional.resample(
        torch.from_numpy(audio),
        orig_freq=sample_rate,
        new_freq=16000,
    ).numpy()

    return audio

def prepare_vad_audio(audio, sample_rate):
    """Convert arbitrary microphone audio to exactly 512 samples at 16 kHz."""

    audio = torch.from_numpy(audio)

    audio = torchaudio.functional.resample(
        audio,
        orig_freq=sample_rate,
        new_freq=VAD_SAMPLE_RATE
    )

    # Make exactly 512 samples
    if audio.shape[-1] < VAD_CHUNK_SIZE:
        audio = torch.nn.functional.pad(
            audio,
            (0, VAD_CHUNK_SIZE - audio.shape[-1])
        )

    elif audio.shape[-1] > VAD_CHUNK_SIZE:
        audio = audio[:VAD_CHUNK_SIZE]

    return audio

def wait_for_wake_word(
    wakeword_model,
    device_id: int,
    sample_rate: int,
    threshold: float = 0.5,
    stop_event=None,
):
    """Listen for a wake word until detected or stopped."""

    import comtypes

    audio_queue = queue.Queue()
    com_initialized = False

    wake_chunk_size = round(1280 * sample_rate / 16000)

    def callback(indata, frames, time_info, status):
        if status:
            print("Статус аудіо:", status)

        if stop_event is not None and stop_event.is_set():
            return

        audio_queue.put(indata[:, 0].copy())

    audio_buffer = np.array([], dtype=np.int16)

    try:
        # COM must be initialized on the thread opening the stream.
        comtypes.CoInitialize()
        com_initialized = True

        with sd.InputStream(
            device=device_id,
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=wake_chunk_size,
            callback=callback,
            extra_settings=sd.WasapiSettings(exclusive=False),
        ):
            while stop_event is None or not stop_event.is_set():
                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                audio_float = chunk.astype(np.float32) / 32768.0

                audio_16k = torchaudio.functional.resample(
                    torch.from_numpy(audio_float),
                    orig_freq=sample_rate,
                    new_freq=16000,
                ).numpy()

                chunk_int16 = np.clip(
                    audio_16k * 32768.0,
                    -32768,
                    32767,
                ).astype(np.int16)

                audio_buffer = np.concatenate(
                    (audio_buffer, chunk_int16)
                )

                while len(audio_buffer) >= 1280:
                    if stop_event is not None and stop_event.is_set():
                        return False

                    frame = audio_buffer[:1280]
                    audio_buffer = audio_buffer[1280:]

                    scores = wakeword_model.predict(frame)

                    if scores and max(scores.values()) >= threshold:
                        wakeword_model.reset()
                        return True

        return False

    finally:
        if com_initialized:
            comtypes.CoUninitialize()