import time
import threading
import queue
from collections import deque, defaultdict
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import comtypes

from pycaw.pycaw import AudioUtilities
from pycaw.constants import EDataFlow, DEVICE_STATE
import torch

from src.voice_recording import prepare_vad_audio

VAD_SAMPLE_RATE = 16000
VAD_CHUNK_SIZE = 512

# ---------------------------------------------------------------------------
# Device discovery
# ---------------------------------------------------------------------------

def get_input_endpoints():
    """Return active Windows capture endpoints mapped to WASAPI devices."""
    windows_devices = AudioUtilities.GetAllDevices(
        data_flow=EDataFlow.eCapture.value,
        device_state=DEVICE_STATE.ACTIVE.value,
    )

    sd_devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    wasapi_by_name = defaultdict(list)

    for index, device in enumerate(sd_devices):
        if device["max_input_channels"] <= 0:
            continue

        hostapi = hostapis[device["hostapi"]]["name"]

        if hostapi != "Windows WASAPI":
            continue

        wasapi_by_name[device["name"].casefold()].append({
            "index": index,
            "name": device["name"],
            "sample_rate": int(
                device["default_samplerate"] or 44100
            ),
            "hostapi": hostapi,
        })

    endpoints = []

    for win_device in windows_devices:
        win_name = win_device.FriendlyName or ""
        endpoint_id = win_device.id
        matches = wasapi_by_name[win_name.casefold()]

        if len(matches) != 1:
            status = "NOT MAPPED" if not matches else "AMBIGUOUS"
            print(f"[{status}] {win_name} ({endpoint_id})")
            continue

        endpoint = matches[0].copy()
        endpoint["endpoint_id"] = endpoint_id
        endpoints.append(endpoint)

    return endpoints

# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def record_from_endpoints(
    endpoints,
    output_dir,
    vad_path="resources/vad",
    vad_threshold=0.5,
    silence_duration=1.0,
    pre_speech_duration=0.3,
    start_timeout=30.0,
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

    threads = start_recording_workers(
        endpoints,
        vad_file,
        audio_queues,
        speech_started,
        stop_event,
        state,
        state_lock,
        output_dir,
        vad_threshold,
        pre_speech_duration,
        results,
    )

    if not threads:
        return results

    try:
        wait_for_recording(
            threads,
            speech_started,
            stop_event,
            state,
            state_lock,
            start_timeout,
            silence_duration,
        )
    finally:
        stop_event.set()

        for thread in threads:
            thread.join(timeout=2.0)

    if not speech_started.is_set():
        for endpoint in endpoints:
            device_id = endpoint["index"]
            result = results[device_id]

            if "error" not in result:
                result["error"] = "No speech detected before timeout"

    return results

def record_endpoint(
    endpoint,
    vad_model,
    audio_queue,
    speech_started,
    stop_event,
    state,
    state_lock,
    output_dir,
    vad_threshold,
    pre_speech_duration,
    result,
):
    device_id = endpoint["index"]
    sample_rate = int(endpoint["sample_rate"])

    chunk_size = max(
        1,
        round(VAD_CHUNK_SIZE * sample_rate / VAD_SAMPLE_RATE),
    )
    pre_chunks = max(
        1,
        round(pre_speech_duration * sample_rate / chunk_size),
    )

    dropped_chunks = 0
    pre_buffer = deque(maxlen=pre_chunks)
    recorded_chunks = []
    recording_started = False
    com_initialized = False

    def callback(indata, frames, time_info, status):
        nonlocal dropped_chunks

        if stop_event.is_set():
            return

        try:
            audio_queue.put_nowait(indata[:, 0].copy())
        except queue.Full:
            dropped_chunks += 1

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

def start_recording_workers(
    endpoints,
    vad_file,
    audio_queues,
    speech_started,
    stop_event,
    state,
    state_lock,
    output_dir,
    vad_threshold,
    pre_speech_duration,
    results,
):
    threads = []

    for endpoint in endpoints:
        device_id = endpoint["index"]

        try:
            vad_model = load_vad_model(vad_file)
        except Exception as exc:
            results[device_id]["error"] = (
                f"Failed to load VAD model: {exc}"
            )
            continue

        thread = threading.Thread(
            target=record_endpoint,
            args=(
                endpoint,
                vad_model,
                audio_queues[device_id],
                speech_started,
                stop_event,
                state,
                state_lock,
                output_dir,
                vad_threshold,
                pre_speech_duration,
                results[device_id],
            ),
            name=f"mic-{device_id}",
            daemon=True,
        )

        threads.append(thread)
        thread.start()

    return threads     


def wait_for_recording(
    threads,
    speech_started,
    stop_event,
    state,
    state_lock,
    start_timeout,
    silence_duration,
):
    deadline = time.monotonic() + start_timeout

    while not speech_started.wait(timeout=0.05):
        if all(not thread.is_alive() for thread in threads):
            break

        if time.monotonic() >= deadline:
            print("Час вичерпано.")
            break

    if not speech_started.is_set():
        return False

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

    return True
 
# -------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_vad_model(vad_file):
    model = torch.jit.load(
        str(vad_file),
        map_location="cpu",
    )
    model.eval()
    return model

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