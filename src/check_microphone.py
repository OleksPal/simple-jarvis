import time
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

CHANNELS = 1
RECORD_SECONDS = 5

# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def get_input_endpoints():
    devices = sd.query_devices()

    endpoints = []

    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue

        hostapi = sd.query_hostapis(device["hostapi"])

        sample_rate = device["default_samplerate"]

        if not sample_rate or sample_rate <= 0:
            sample_rate = 44100

        endpoints.append({
            "index": index,
            "name": device["name"],
            "channels": device["max_input_channels"],
            "sample_rate": int(sample_rate),
            "hostapi": hostapi["name"],
        })

    return endpoints

# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def record_from_endpoints(endpoints, output_dir):
    """
    Start recording from all endpoints simultaneously,
    wait for RECORD_SECONDS, then stop all recordings.

    Returns a dictionary containing the result for each endpoint.
    """

    start_event = threading.Event()
    stop_event = threading.Event()

    results = {}

    threads = create_recording_threads(
        endpoints,
        start_event,
        stop_event,
        results,
        output_dir
    )

    # Give threads time to reach start_event.wait().
    time.sleep(0.5)

    print_recording_instruction()

    # Start all recordings simultaneously.
    start_event.set()

    time.sleep(RECORD_SECONDS)

    # Stop all recordings.
    stop_event.set()

    for thread in threads:
        thread.join()

    return results

def create_recording_threads(
    endpoints,
    start_event,
    stop_event,
    results,
    output_dir
):
    threads = []

    for endpoint in endpoints:
        device_id = endpoint["index"]

        results[device_id] = {}

        thread = threading.Thread(
            target=record_endpoint,
            args=(
                endpoint,
                start_event,
                stop_event,
                results[device_id],
                output_dir
            ),
            daemon=True,
        )

        threads.append(thread)
        thread.start()

    return threads

def record_endpoint(endpoint, start_event, stop_event, result, output_dir):
    device_id = endpoint["index"]
    sample_rate = endpoint["sample_rate"]

    audio_chunks = []

    try:

        def callback(indata, frames, time, status):
            if status:
                print(
                    f"[{device_id}] {status}",
                    flush=True,
                )

            # We record mono for now.
            audio_chunks.append(indata[:, 0].copy())

        # Wait until the main thread starts the test.
        start_event.wait()

        with sd.InputStream(
            device=device_id,
            samplerate=sample_rate,
            channels=endpoint["channels"],
            dtype="float32",
            callback=callback,
        ):
            stop_event.wait()

    except Exception as exc:
        result["error"] = exc
        return

    if not audio_chunks:
        result["error"] = RuntimeError("No audio captured")
        return

    audio = np.concatenate(audio_chunks)

    filename = save_wav_file(output_dir, device_id, endpoint['name'], audio, sample_rate)

    result["audio"] = audio
    result["filename"] = filename
    result["sample_rate"] = sample_rate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name):
    invalid = '<>:"/\\|?*'

    for char in invalid:
        name = name.replace(char, "_")

    return name[:100]

def save_wav_file(output_dir, device_id, name, audio, sample_rate):
    filename = (
        output_dir
        / f"endpoint_{device_id}_{sanitize_filename(name)}.wav"
    )
    
    sf.write(
        filename,
        audio,
        sample_rate,
        subtype="PCM_24",
    )

    return filename

def print_recording_instruction():
    print()
    print("Запис розпочато!")
    print()
    print("Скажіть:")
    print(
        "«Привіт, це тест мікрофона. "
        "Я перевіряю якість запису голосу.»"
    )
    print()