import time
import queue
import sounddevice as sd
import numpy as np
import torch
import torchaudio

VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512
VAD_MIN_SAMPLES = 512

def record_audio(vad_model, device_id: int, sample_rate, channels, vad_threshold,
    silence_duration, pre_speech_duration):
    audio_queue = queue.Queue()

    # 512 samples @ 16 kHz converted to microphone sample rate
    chunk_size = round(
        VAD_CHUNK_SIZE * sample_rate / VAD_SAMPLE_RATE
    )

    def callback(indata, frames, time_info, status):        
        if status:
            print("Статус аудіо:", status)

        # int16 -> float32 [-1, 1]
        chunk = indata[:, 0].astype(np.float32) / 32768.0
        audio_queue.put(chunk)

    pre_chunks = max(
        1,
        round(pre_speech_duration * sample_rate / chunk_size)
    )

    pre_buffer = []
    speech_audio = []

    speech_started = False
    silence_start = None

    with sd.InputStream(
        device=device_id,
        samplerate=sample_rate,
        channels=channels,
        dtype="int16",
        blocksize=chunk_size,
        callback=callback
    ):
        while True:
            chunk = audio_queue.get()

            audio_16k = prepare_vad_audio(
                chunk,
                sample_rate
            )

            audio_16k = audio_16k.float()

            with torch.no_grad():
                probability = vad_model(
                    audio_16k,
                    VAD_SAMPLE_RATE
                ).item()

            is_speech = probability >= vad_threshold

            # Waiting for speech
            if not speech_started:
                pre_buffer.append(chunk)

                if len(pre_buffer) > pre_chunks:
                    pre_buffer.pop(0)

                if is_speech:
                    speech_started = True
                    speech_audio.extend(pre_buffer)

                continue

            # Recording speech
            speech_audio.append(chunk)

            if is_speech:
                silence_start = None
            elif silence_start is None:
                silence_start = time.monotonic()
            elif time.monotonic() - silence_start >= silence_duration:
                break

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