import time
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from pycaw.pycaw import AudioUtilities
from pycaw.constants import EDataFlow, DEVICE_STATE

from src.voice_recording import prepare_vad_audio

import queue
import torch

VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512

CHANNELS = 1
RECORD_SECONDS = 5

VAD_THRESHOLD = 0.5
SILENCE_DURATION = 1.0
PRE_SPEECH_DURATION = 0.3
START_TIMEOUT = 30.0

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

def record_from_endpoints(
    endpoints,
    output_dir,
    vad_path="resources/vad",
    vad_threshold=VAD_THRESHOLD,
    silence_duration=SILENCE_DURATION,
    pre_speech_duration=PRE_SPEECH_DURATION,
    start_timeout=START_TIMEOUT,
):
    """
    Give each microphone its own Silero VAD instance.
    Speech on any microphone starts recording on all microphones.
    Stop after shared silence is detected.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not endpoints:
        return {}

    vad_file = Path(vad_path) / "silero_vad.jit"

    if not vad_file.is_file():
        raise FileNotFoundError(f"VAD model not found: {vad_file}")

    speech_started = threading.Event()
    stop_event = threading.Event()
    state_lock = threading.Lock()

    state = {
        "last_speech_time": None,
        "trigger_device": None,
    }

    results = {
        endpoint["index"]: {}
        for endpoint in endpoints
    }

    audio_queues = {
        endpoint["index"]: queue.Queue(maxsize=100)
        for endpoint in endpoints
    }

    def record_endpoint(endpoint, vad_model):
        import comtypes

        device_id = endpoint["index"]
        sample_rate = int(endpoint["sample_rate"])
        audio_queue = audio_queues[device_id]
        result = results[device_id]

        chunk_size = max(
            1,
            round(VAD_CHUNK_SIZE * sample_rate / VAD_SAMPLE_RATE),
        )

        pre_chunks = max(
            1,
            round(pre_speech_duration * sample_rate / chunk_size),
        )

        pre_buffer = []
        recorded_chunks = []
        recording_started = False
        com_initialized = False

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[{device_id}] Audio status: {status}")

            if stop_event.is_set():
                return

            try:
                audio_queue.put_nowait(indata[:, 0].copy())
            except queue.Full:
                print(f"[{device_id}] Warning: audio queue full")

        try:
            comtypes.CoInitialize()
            com_initialized = True

            with sd.InputStream(
                device=device_id,
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_size,
                callback=callback,
                extra_settings=sd.WasapiSettings(exclusive=False),
            ):
                while not stop_event.is_set():
                    try:
                        chunk = audio_queue.get(timeout=0.05)
                    except queue.Empty:
                        continue

                    # Reuse your existing VAD audio preparation function.
                    audio_16k = prepare_vad_audio(chunk, sample_rate)
                    audio_16k = audio_16k.float()

                    with torch.inference_mode():
                        probability = vad_model(
                            audio_16k,
                            VAD_SAMPLE_RATE,
                        ).item()

                    if probability >= vad_threshold:
                        with state_lock:
                            state["last_speech_time"] = time.monotonic()

                            if not speech_started.is_set():
                                state["trigger_device"] = device_id
                                speech_started.set()

                    if not recording_started:
                        pre_buffer.append(chunk)

                        if len(pre_buffer) > pre_chunks:
                            pre_buffer.pop(0)

                        if speech_started.is_set():
                            recorded_chunks.extend(pre_buffer)
                            recording_started = True

                        continue

                    recorded_chunks.append(chunk)

        except Exception as exc:
            result["error"] = str(exc)
            return

        finally:
            if com_initialized:
                comtypes.CoUninitialize()

        if recorded_chunks:
            audio = np.concatenate(recorded_chunks).astype(np.float32)

            filename = save_wav_file(
                output_dir,
                device_id,
                endpoint["name"],
                audio,
                sample_rate,
            )

            result.update({
                "audio": audio,
                "filename": filename,
                "sample_rate": sample_rate,
            })
        else:
            result.setdefault("error", "No audio captured")

    threads = []

    # Load a distinct local JIT model for every microphone.
    for endpoint in endpoints:
        device_id = endpoint["index"]

        try:
            vad_model = torch.jit.load(
                str(vad_file),
                map_location="cpu",
            )
            vad_model.eval()
        except Exception as exc:
            results[device_id]["error"] = (
                f"Failed to load VAD model: {exc}"
            )
            continue

        thread = threading.Thread(
            target=record_endpoint,
            args=(endpoint, vad_model),
            name=f"mic-{device_id}",
            daemon=True,
        )

        threads.append(thread)
        thread.start()

    if not threads:
        return results

    print("Jarvis: Listening on all microphones...")

    deadline = time.monotonic() + start_timeout

    try:
        while not speech_started.wait(timeout=0.05):
            if all(not thread.is_alive() for thread in threads):
                break

            if time.monotonic() >= deadline:
                print("Jarvis: Speech detection timed out.")
                break

        if speech_started.is_set():
            print(
                f"Jarvis: Speech detected on microphone "
                f"{state['trigger_device']}. Recording all microphones..."
            )

            while not stop_event.is_set():
                with state_lock:
                    last_speech = state["last_speech_time"]

                if (
                    last_speech is not None
                    and time.monotonic() - last_speech >= silence_duration
                ):
                    stop_event.set()
                    break

                if all(not thread.is_alive() for thread in threads):
                    break

                time.sleep(0.02)

    finally:
        stop_event.set()

        for thread in threads:
            thread.join()

    if not speech_started.is_set():
        for endpoint in endpoints:
            results[endpoint["index"]].setdefault(
                "error", "No speech detected before timeout"
            )

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