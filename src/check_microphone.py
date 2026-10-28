import time
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

from pycaw.pycaw import AudioUtilities
from pycaw.constants import EDataFlow, DEVICE_STATE

CHANNELS = 1
RECORD_SECONDS = 5

# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def get_input_endpoints():
    # Windows Core Audio: active capture endpoints
    windows_devices = AudioUtilities.GetAllDevices(
        data_flow=EDataFlow.eCapture.value,
        device_state=DEVICE_STATE.ACTIVE.value,
    )

    # PortAudio: WASAPI input devices
    sd_devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    wasapi_devices = []

    for index, device in enumerate(sd_devices):
        if device["max_input_channels"] <= 0:
            continue

        hostapi = hostapis[device["hostapi"]]["name"]

        if hostapi != "Windows WASAPI":
            continue

        wasapi_devices.append({
            "index": index,
            "name": device["name"],
            "channels": device["max_input_channels"],
            "sample_rate": int(
                device["default_samplerate"] or 44100
            ),
            "hostapi": hostapi,
        })

    endpoints = []

    for win_device in windows_devices:
        win_name = win_device.FriendlyName
        endpoint_id = win_device.id

        matches = [
            device
            for device in wasapi_devices
            if device["name"].casefold() == (win_name or "").casefold()
        ]

        if len(matches) == 1:
            endpoint = matches[0].copy()
            endpoint["endpoint_id"] = endpoint_id
            endpoints.append(endpoint)

        elif len(matches) == 0:
            print(f"[NOT MAPPED] {win_name} ({endpoint_id})")

        else:
            print(f"[AMBIGUOUS] {win_name} ({endpoint_id})")

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
    import comtypes

    device_id = endpoint["index"]
    sample_rate = endpoint["sample_rate"]

    audio_chunks = []
    com_initialized = False

    try:
        # Initialize COM on the thread that opens the audio stream.
        comtypes.CoInitialize()
        com_initialized = True

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[{device_id}] {status}", flush=True)

            # Store a copy because indata is only valid during callback.
            audio_chunks.append(indata[:, 0].copy())

        # Wait until all recording threads are ready.
        start_event.wait()

        wasapi_settings = sd.WasapiSettings(
            exclusive=False,
        )

        with sd.InputStream(
            device=device_id,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
            extra_settings=wasapi_settings,
        ):
            stop_event.wait()

    except Exception as exc:
        result["error"] = str(exc)
        return

    finally:
        if com_initialized:
            comtypes.CoUninitialize()

    if not audio_chunks:
        result["error"] = "No audio captured"
        return

    audio = np.concatenate(audio_chunks)

    filename = save_wav_file(
        output_dir,
        device_id,
        endpoint["name"],
        audio,
        sample_rate,
    )

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