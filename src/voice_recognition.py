import numpy as np
import psutil
import os
import time
import re

from faster_whisper import WhisperModel

from src.utils import is_cuda_gpu_enable, GREEN, YELLOW, RED, RESET
from src.command_resolver import find_best_command_match, encode_options

def create_speech_recognition_model(model_size = "small"):

    print(f"[{GREEN}OK{RESET}] Використовувана модель Whisper: {YELLOW}{model_size}{RESET}")

    # NVIDIA GPU
    if is_cuda_gpu_enable():
        print(f"[{GREEN}OK{RESET}] NVIDIA GPU виявлено. Налаштування використання CUDA...")

        return WhisperModel(
            model_size,
            device="cuda",
            compute_type="float16"
        )

    # CPU
    print(f"[{RED}FAILED{RESET}] CUDA GPU не виявлено")

    physical_cores = psutil.cpu_count(logical=False) or 1
    cpu_threads = max(1, physical_cores - 1)

    print(f"[{GREEN}OK{RESET}] CPU ядра системи: {physical_cores} фізичних ядер")
    print(f"[{GREEN}OK{RESET}] CPU ядра для розпізнавання голосу: {cpu_threads} фізичних ядер")

    return WhisperModel(
        model_size,
        device="cpu",
        compute_type="int8",
        cpu_threads=cpu_threads,
        num_workers=1
    )

def find_best_microphone(speech_recognition_model, file_list, etalon_text, resolver_model):
    max_score = 0
    best_microphone_id = 0

    encoded_options = encode_options(
        resolver_model,
        etalon_text
    )

    for file in file_list:
        print("\n------------------------------")
        print(f"Розшифровка: {file}")
        start_time = time.perf_counter()

        words = transcribe(speech_recognition_model, file)

        phrase = " ".join(words)

        print()
        print("Почуто:", phrase)
        print()

        _, score = find_best_command_match(
            resolver_model,
            encoded_options,
            phrase,
        )

        if score > max_score:
            max_score = score

            match = re.match(
                r"^endpoint_([^_]+)_",
                os.path.basename(file),
            )

            if match:
                best_microphone_id = match.group(1)

        print(f"Співпадіння з еталоном: {score:.2%}")

        elapsed = time.perf_counter() - start_time

        print()
        print("Розшифровка завершена")
        print(f"Час: {elapsed:.2f} секунд")
        print("------------------------------")

    return best_microphone_id

def transcribe(speech_recognition_model, audio):
    if audio is None:
        print("Звук не був записаний.")
        return []
    
    if isinstance(audio, np.ndarray) and len(audio) == 0:
        print("Звук не був записаний.")
        return []
    
    segments, info = speech_recognition_model.transcribe(
        audio,
        language="uk",
        beam_size=3,
        temperature=0.0,
        vad_filter=True,
        condition_on_previous_text=True,
        word_timestamps=True,
    )
    
    words = []
    
    for segment in segments:
        if segment.words is None:
            continue
    
        for word in segment.words:
            text = word.word.strip()
    
            if text:
                words.append(text)
    
    return words
