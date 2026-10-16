import io
import wave

import numpy as np
from piper import SynthesisConfig
import sounddevice as sd

# Load once when your application starts.
# The model itself stays in memory.
# voice = PiperVoice.load("uk_UA-mykyta-high.onnx")

def speak(voice, text: str, speed: float = 1.5, volume: float = 1.0):
    """
    Convert text to speech using Piper and play it.
    Adjust speed without changing pitch.
    No audio files are created.
    """
    text = text.strip()

    if not text:
        return

    if speed <= 0:
        raise ValueError("speed must be greater than zero")

    if volume < 0:
        raise ValueError("volume cannot be negative")

    # Generate WAV entirely in memory
    wav_buffer = io.BytesIO()

    syn_config = SynthesisConfig(
        length_scale=1.0 / speed,
        volume=volume,
    )

    with wave.open(wav_buffer, "wb") as wav_file:
        voice.synthesize_wav(
            text,
            wav_file,
            syn_config=syn_config,
        )

    wav_buffer.seek(0)

    # Read WAV
    with wave.open(wav_buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        audio_data = wav_file.readframes(wav_file.getnframes())

    if sample_width != 2:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    audio = np.frombuffer(audio_data, dtype=np.int16)
    audio = audio.astype(np.float32) / 32768.0

    if channels > 1:
        audio = audio.reshape(-1, channels)

    # Adjust volume
    audio = np.clip(audio * volume, -1.0, 1.0)

    # Keep the original sample rate
    sd.play(audio, samplerate=sample_rate)
    sd.wait()