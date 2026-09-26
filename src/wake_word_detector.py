import sounddevice as sd

def wait_for_wake_word(
    wakeword_model,
    device_id: int,
    sample_rate: int = 16000,
    threshold: float = 0.5,
):
    """
    Listen until the configured openWakeWord model detects
    the wake word.

    The microphone stream is closed automatically when the
    wake word is detected.
    """

    # openWakeWord uses 80 ms frames at 16 kHz.
    block_size = 1280

    with sd.InputStream(
        device=device_id,
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=block_size,
    ) as stream:

        while True:
            audio, overflowed = stream.read(block_size)

            if overflowed:
                print("Статус аудіо: переповнення буфера")

            # int16 PCM is exactly what openWakeWord expects.
            audio = audio[:, 0]

            predictions = wakeword_model.predict(audio)

            # We have one ONNX wake-word model.
            score = next(iter(predictions.values()))

            if score >= threshold:
                return True
