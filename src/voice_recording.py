import time
import queue
from collections import deque

import sounddevice as sd
import numpy as np
import torch
import torchaudio
import comtypes

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

    audio_queue = queue.Queue()
    com_initialized = False

    chunk_size = round(
        VAD_CHUNK_SIZE * sample_rate / VAD_SAMPLE_RATE
    )

    pre_chunks = max(
        1,
        round(pre_speech_duration * sample_rate / chunk_size),
    )
    
    pre_buffer = deque(maxlen=pre_chunks)
    speech_audio = []

    vad_resampler = (
        torchaudio.transforms.Resample(
            orig_freq=sample_rate,
            new_freq=VAD_SAMPLE_RATE,
        )
        if sample_rate != VAD_SAMPLE_RATE
        else None
    )

    speech_started = False
    silence_start = None
    listening_started = time.monotonic()
    
    def callback(indata, frames, time_info, status):
        if stop_event is not None and stop_event.is_set():
            return

        # Copy raw int16 samples; convert outside the callback.
        audio_queue.put(indata[:, 0].copy())

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
                        return np.array([], dtype=np.float32)

                try:
                    chunk = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                chunk = chunk.astype(np.float32) / 32768.0

                if stop_event is not None and stop_event.is_set():
                    return np.array([], dtype=np.float32)
                
                audio_16k = prepare_vad_audio(
                    chunk,
                    sample_rate,
                    resampler=vad_resampler,
                ).float()

                with torch.inference_mode():
                    probability = vad_model(
                        audio_16k,
                        VAD_SAMPLE_RATE,
                    ).item()

                if stop_event is not None and stop_event.is_set():
                    return np.array([], dtype=np.float32)

                is_speech = probability >= vad_threshold

                if not speech_started:
                    pre_buffer.append(chunk)

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

    
    audio = np.concatenate(speech_audio).astype(
        np.float32,
        copy=False,
    )

    if sample_rate != VAD_SAMPLE_RATE:
        audio = torchaudio.functional.resample(
            torch.from_numpy(audio),
            orig_freq=sample_rate,
            new_freq=VAD_SAMPLE_RATE,
        ).numpy()

    return audio

def prepare_vad_audio(audio, sample_rate, resampler=None):
    """Convert audio to exactly 512 samples at 16 kHz."""

    audio = torch.from_numpy(audio)

    if sample_rate != VAD_SAMPLE_RATE:
        if resampler is None:
            resampler = torchaudio.transforms.Resample(
                orig_freq=sample_rate,
                new_freq=VAD_SAMPLE_RATE,
            )
        audio = resampler(audio)

    if audio.shape[-1] < VAD_CHUNK_SIZE:
        audio = torch.nn.functional.pad(
            audio,
            (0, VAD_CHUNK_SIZE - audio.shape[-1]),
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
        if stop_event is not None and stop_event.is_set():
            return

        audio_queue.put(indata[:, 0].copy())

    frame_buffer = np.empty(1280, dtype=np.int16)
    frame_fill = 0
    
    wake_resampler = (
        torchaudio.transforms.Resample(
            orig_freq=sample_rate,
            new_freq=16000,
        )
        if sample_rate != 16000
        else None
    )

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

                if wake_resampler is not None:
                    audio_16k = wake_resampler(
                        torch.from_numpy(audio_float)
                    ).numpy()
                else:
                    audio_16k = audio_float

                chunk_int16 = np.clip(
                    audio_16k * 32768.0,
                    -32768,
                    32767,
                ).astype(np.int16)

                
                offset = 0

                while offset < len(chunk_int16):
                    if stop_event is not None and stop_event.is_set():
                        return False

                    count = min(
                        1280 - frame_fill,
                        len(chunk_int16) - offset,
                    )

                    frame_buffer[frame_fill:frame_fill + count] = (
                        chunk_int16[offset:offset + count]
                    )

                    frame_fill += count
                    offset += count

                    if frame_fill == 1280:
                        scores = wakeword_model.predict(frame_buffer)

                        frame_fill = 0

                        if scores and max(scores.values()) >= threshold:
                            wakeword_model.reset()
                            return True

        return False

    finally:
        if com_initialized:
            comtypes.CoUninitialize()