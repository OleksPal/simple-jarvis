import os
import psutil
import time
import re

from faster_whisper import WhisperModel

from src.voice_recognition import transcribe
from src.recognition_comparator import compare_with_etalon

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[33m"
RESET = "\033[0m"

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

def is_cuda_gpu_enable():
    return os.system("nvidia-smi >nul 2>&1") == 0

def find_best_microphone(speech_recognition_model, file_list, etalon_text):
    max_score = 0
    best_microphone_id = 0

    for file in file_list:
        print("\n------------------------------")
        print(f"Розшифровка: {file}")
        start_time = time.perf_counter()

        words = transcribe(speech_recognition_model, file)

        print()
        print("Почуто:", " ".join(words))
        print()

        score, differences = compare_with_etalon(
            words,
            etalon_text
        )

        if score > max_score:
            max_score = score
            device_id = re.match(r"^endpoint_([^_]+)_", os.path.basename(file)).group(1)
            best_microphone_id = device_id

        print(f"Співпадіння з еталоном: {score:.2%}")

        for difference in differences:
            if difference["type"] == "match":
                print(f"  {GREEN}+{RESET} {difference['actual']}")

            elif difference["type"] == "changed":
                print(
                    f"  {RED}X{RESET} {difference['expected']} "
                    f"-> {difference['actual']}"
                )

            elif difference["type"] == "missing":
                print(
                    f"  {YELLOW}?{RESET} відсутній: {difference['expected']}"
                )

            elif difference["type"] == "extra":
                print(
                    f"  {YELLOW}!{RESET} додатково: {difference['actual']}"
                )

        elapsed = time.perf_counter() - start_time

        print()
        print("Розшифровка завершена")
        print(f"Час: {elapsed:.2f} секунд")
        print("------------------------------")

    return best_microphone_id