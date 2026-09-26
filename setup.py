import sys
import subprocess
from src.utils import is_cuda_gpu_enable, add_jarvis_to_startup, install_pytorch, RED, GREEN, YELLOW, RESET

install_pytorch()

import time
import json
from pathlib import Path

from piper import PiperVoice
from sentence_transformers import SentenceTransformer

from src.check_microphone import get_input_endpoints, record_from_endpoints
from src.tts import speak
from src.voice_recognition import create_speech_recognition_model, find_best_microphone

print("Розпочато налаштування Jarvis...")
print()

# ---------------------------------------------------------------------------
# Download semantic model
# ---------------------------------------------------------------------------

MODEL_PATH = "resources/semantic_model"

print("Початок завантаження семантичної моделі...")
print()

resolver_model = SentenceTransformer("all-MiniLM-L6-v2")
resolver_model.save(MODEL_PATH)

print()
print(f"[{GREEN}OK{RESET}] Семантичну модель завантажено")
print()

# ---------------------------------------------------------------------------
# Find the best microphone
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("microphone_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ETALON_TEXT = ["Привіт це тест мікрофона Я перевіряю якість запису голосу"]

endpoints = get_input_endpoints()

if not endpoints:
    print("Мікрофони не знайдено.")
    exit()

print("Доступні мікрофони:")
print("-" * 100)

for endpoint in endpoints:
    print(
        f"[{endpoint['index']:>2}] "
        f"{endpoint['name']} "
        f"({endpoint['hostapi']}) "
        f"{endpoint['channels']} ch, "
        f"{endpoint['sample_rate']} Hz"
    )

print("-" * 100)
print()

input("Натисніть ENTER для початку тесту...")
print()
print("Приготуйтеся...")
time.sleep(2)

results = record_from_endpoints(endpoints, OUTPUT_DIR)

print()
print("=" * 100)
print("Результати")
print("=" * 100)

for endpoint in endpoints:
    device_id = endpoint["index"]
    result = results[device_id]

    if result.get("error"):
        print(
            f"[{RED}FAILED{RESET}] {device_id}: "
            f"{endpoint['name']} -> {result['error']}"
        )

    elif result.get("filename"):
        print(
            f"[{GREEN}OK{RESET}]     {device_id}: "
            f"{endpoint['name']} -> "
            f"{result['filename']} "
            f"({result['sample_rate']} Hz)"
        )

    else:
        print(
            f"[{RED}FAILED{RESET}] {device_id}: "
            f"{endpoint['name']} -> no audio"
        )

print()
print(f"Записи мікрофону збережено до: {OUTPUT_DIR.absolute()}")
print() 

speech_recognition_model = create_speech_recognition_model()

folder = Path("microphone_test")
wav_files = list(folder.glob("*.wav"))

best_microphone_id = find_best_microphone(speech_recognition_model, wav_files, ETALON_TEXT, resolver_model)
best_microphone = next(
    (
        endpoint for endpoint in endpoints
        if endpoint["index"] == int(best_microphone_id)
    ),
    None
)

print()
print(f"[{GREEN}OK{RESET}] ID найкращого мікрофона: {YELLOW}{best_microphone_id}{RESET}")

# ---------------------------------------------------------------------------
# Create config files
# ---------------------------------------------------------------------------

Path("config").mkdir(parents=True, exist_ok=True)

config_file_path = Path("config/jarvis.config.json")

if not config_file_path.exists():
    data = {
        "microphone_id": int(best_microphone_id),
        "use_cuda": is_cuda_gpu_enable(),
        "speech_recognition_model": "small",
        "sample_rate": best_microphone["sample_rate"],
        "channels": best_microphone["channels"],
        "vad_threshold": 0.5,
        "silence_duration": 0.7,
        "pre_speech_duration": 0.3
    }    

    with open("config/jarvis.config.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print(f"[{GREEN}OK{RESET}] Створено конфіг файл: config/jarvis.config.json")

commands_file_path = Path("config/commands.json")

if not commands_file_path.exists():
    path = Path(__file__).resolve()
    script_path = path.with_name("script.py")

    data = {
        "commands": {
            "YouTube": {
                "phrases": [
                    "відкрий ютуб",
                    "запусти ютуб"
                ],
                "action": {
                    "type": "browser",
                    "url": "https://www.youtube.com"
                }
            },

            "Блокнот": {
                "phrases": [
                    "відкрий блокнот",
                    "запусти блокнот"
                ],
                "action": {
                    "type": "program",
                    "path": "notepad.exe"
                }
            },

            "Закрити Jarvis": {
                "phrases": [
                    "стоп",
                    "закрити"
                ],
                "action": {
                    "type": "close_jarvis"
                }
            }
        }
    }

    with open("config/commands.json", "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

    print(f"[{GREEN}OK{RESET}] Створено файл з командами: config/commands.json")

# ---------------------------------------------------------------------------
# Add Jarvis to Windows Startup
# ---------------------------------------------------------------------------

add_jarvis_to_startup()
print()

print(f"[{GREEN}OK{RESET}] Jarvis додано до Windows автозапуск")

# ---------------------------------------------------------------------------
# Download wake word model
# ---------------------------------------------------------------------------

import os
import urllib.request

WAKEWORD_DIR = "wakewords"
WAKEWORD_PATH = os.path.join(
    WAKEWORD_DIR,
    "hey_jarvis.onnx",
)

os.makedirs(WAKEWORD_DIR, exist_ok=True)

if not os.path.exists(WAKEWORD_PATH):
    print(f"[{GREEN}OK{RESET}] Завантажується hey_jarvis фраза пробудження...")

    urllib.request.urlretrieve(
        "https://github.com/dscripka/openWakeWord/releases/"
        "download/v0.5.1/hey_jarvis_v0.1.onnx",
        WAKEWORD_PATH,
    )

    print(f"[{GREEN}OK{RESET}] Фразу пробудження завантажено.")
    print()

# ---------------------------------------------------------------------------
# Download TTS voice
# ---------------------------------------------------------------------------

subprocess.run(
    [
        sys.executable,
        "-m",
        "piper.download_voices",
        "uk_UA-mykyta-high",
        "--data-dir",
        "tts",
    ], 
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=True
)

voice = PiperVoice.load("tts/uk_UA-mykyta-high.onnx", use_cuda=is_cuda_gpu_enable())

print(f"[{GREEN}OK{RESET}] Завантажено голос uk_UA-mykyta-high: tts/uk_UA-mykyta-high.onnx")
print(f"[{GREEN}OK{RESET}] Відтворюється голос!")
speak(voice, "Тест голосу")

print()
print("Налаштування завершено! Тепер можете запустити Jarvis за допомогою script.py")
print()
input("Натисніть ENTER для виходу...")
print()