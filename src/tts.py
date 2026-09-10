import io
import wave

import numpy as np
import sounddevice as sd

# Load once when your application starts.
# The model itself stays in memory.
# voice = PiperVoice.load("uk_UA-mykyta-high.onnx")


def speak(voice, text: str):
    """
    Convert text to speech using Piper and play it.
    No audio files are created.
    """

    # Generate WAV entirely in memory
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        voice.synthesize_wav(text, wav_file)

    # Go back to the beginning of the in-memory WAV
    wav_buffer.seek(0)

    # Read the WAV
    with wave.open(wav_buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()

        audio_data = wav_file.readframes(
            wav_file.getnframes()
        )

    # Piper normally produces 16-bit PCM
    if sample_width == 2:
        audio = np.frombuffer(
            audio_data,
            dtype=np.int16
        )

        audio = audio.astype(np.float32) / 32768.0

    else:
        raise ValueError(
            f"Unsupported sample width: {sample_width}"
        )

    # Restore channel shape if necessary
    if channels > 1:
        audio = audio.reshape(-1, channels)

    # Play
    sd.play(audio, sample_rate)
    sd.wait()
