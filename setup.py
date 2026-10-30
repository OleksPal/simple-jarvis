import sys
import subprocess
from src.utils import is_cuda_gpu_enable, create_shortcut, RED, GREEN, YELLOW, RESET

import os
import warnings
import logging

# Disable Hugging Face and Transformers output
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_VERBOSITY"] = "error"

warnings.filterwarnings("ignore")

logging.disable(logging.CRITICAL)

import time
import json
import urllib.request
from pathlib import Path

import torch
import urllib.request

from piper import PiperVoice
from sentence_transformers import SentenceTransformer

from src.check_microphone import get_input_endpoints, record_from_endpoints
from src.tts import speak
from src.voice_recognition import create_speech_recognition_model, find_best_microphone

print("Розпочато налаштування Jarvis...")
print()

# ---------------------------------------------------------------------------
# Download VAD
# ---------------------------------------------------------------------------

MODEL_PATH = Path("resources/vad/silero_vad.jit")

MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/"
    "master/src/silero_vad/data/silero_vad.jit"
)

MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

if not MODEL_PATH.is_file():
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)

vad_model = torch.jit.load(
    str(MODEL_PATH),
    map_location="cpu"
)

vad_model.eval()

print(f"[{GREEN}OK{RESET}] Модель розпізнавання голосу готова до використання")

# ---------------------------------------------------------------------------
# Download semantic model
# ---------------------------------------------------------------------------

MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_PATH = Path(__file__).resolve().parent / "resources" / "semantic_model"

if (MODEL_PATH / "modules.json").is_file():
    resolver_model = SentenceTransformer(
        str(MODEL_PATH),
        local_files_only=True
    )
else:
    resolver_model = SentenceTransformer(MODEL_NAME)
    resolver_model.save(str(MODEL_PATH))

print(f"[{GREEN}OK{RESET}] Модель розпізнавання команд готова до використання")
print()

# ---------------------------------------------------------------------------
# Find the best microphone
# ---------------------------------------------------------------------------

print("Розпочато налаштування мікрофону...")
print()

OUTPUT_DIR = Path("microphone_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ETALON_TEXT = ["Привіт це тест мікрофона Я перевіряю якість запису голосу"]

endpoints = get_input_endpoints()

if not endpoints:
    print("Мікрофони не знайдено.")
    exit()

print("Доступні мікрофони:")
print("-" * 30)

for endpoint in endpoints:
    print(
        f"[{endpoint['index']:>2}] "
        f"{endpoint['name']} "
        f"({endpoint['hostapi']}) "
        f"{endpoint['sample_rate']} Hz"
    )

print("-" * 30)
print()

input("Натисніть ENTER для початку тесту...")
print()
print("Приготуйтеся...")
print()

time.sleep(2)
print("Скажіть: Привіт це тест мікрофона. Я перевіряю якість запису голосу.")
results = record_from_endpoints(endpoints, OUTPUT_DIR) #use preloaded vad

print()
print("=" * 30)
print("Результати")
print("=" * 30)

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
            f"[{GREEN}OK{RESET}] {device_id}: "
            f"{endpoint['name']}"
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

data = {
    "microphone_id": int(best_microphone_id),
    "use_cuda": is_cuda_gpu_enable(),
    "speech_recognition_model": "small",
    "sample_rate": best_microphone["sample_rate"],
    "vad_threshold": 0.5,
    "silence_duration": 0.7,
    "pre_speech_duration": 0.3
}     

with open("config/jarvis.config.json", "w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=4)

print(f"[{GREEN}OK{RESET}] Створено конфіг файл: {config_file_path}")

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
                    "type": "open_url",
                    "enabled": True,
                    "url": "https://www.youtube.com"
                }
            },

            "Блокнот": {
                "phrases": [
                    "відкрий блокнот",
                    "запусти блокнот"
                ],
                "action": {
                    "type": "open_file",
                    "enabled": True,
                    "path": "notepad.exe"
                }
            },

            "Закрити Jarvis": {
                "phrases": [
                    "стоп",
                    "закрити"
                ],
                "action": {
                    "type": "close_jarvis",
                    "enabled": True
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

current_folder = Path(__file__).resolve().parent
script_path = current_folder / "app.py"

# Windows Startup folder
startup_folder = (
    Path(os.environ["APPDATA"])
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)

# Desktop folder
desktop_folder = Path(os.environ["USERPROFILE"]) / "Desktop"

# Create shortcuts
create_shortcut(
    startup_folder / "Jarvis.lnk",
    script_path,
    current_folder
)

create_shortcut(
    desktop_folder / "Jarvis.lnk",
    script_path,
    current_folder
)

print(f"[{GREEN}OK{RESET}] Ярлик Jarvis додано на Робочий Стіл")
print(f"[{GREEN}OK{RESET}] Jarvis додано до Windows автозапуск")

# ---------------------------------------------------------------------------
# Download wake phrase onnx
# ---------------------------------------------------------------------------

WAKEWORD_DIR = Path("resources/wakewords")
WAKEWORD_DIR.mkdir(parents=True, exist_ok=True)

MODELS = {
    "hey_jarvis.onnx": (
        "https://github.com/dscripka/openWakeWord/releases/"
        "download/v0.5.1/hey_jarvis_v0.1.onnx"
    ),
    "melspectrogram.onnx": (
        "https://github.com/dscripka/openWakeWord/releases/"
        "download/v0.5.1/melspectrogram.onnx"
    ),
    "embedding_model.onnx": (
        "https://github.com/dscripka/openWakeWord/releases/"
        "download/v0.5.1/embedding_model.onnx"
    ),
}

for filename, url in MODELS.items():
    path = WAKEWORD_DIR / filename

    if not path.is_file() or path.stat().st_size == 0:
        try:
            urllib.request.urlretrieve(url, str(path))

            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"Помилка завантаження: {filename}")

        except Exception:
            path.unlink(missing_ok=True)
            raise

print(f"[{GREEN}OK{RESET}] Завантажено фразу пробудження")

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
        "resources/tts",
    ], 
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    check=True
)

voice = PiperVoice.load("resources/tts/uk_UA-mykyta-high.onnx", use_cuda=is_cuda_gpu_enable())

print(f"[{GREEN}OK{RESET}] Завантажено голос uk_UA-mykyta-high: tts/uk_UA-mykyta-high.onnx")
print(f"[{GREEN}OK{RESET}] Відтворюється голос!")
speak(voice, "Тест голосу")

print()
print("Налаштування завершено! Тепер можете запустити Jarvis за допомогою app.py, або через ярлик на робочому столі")
print()
input("Натисніть ENTER для виходу...")
print()