import warnings
import json
from pathlib import Path
import time
warnings.filterwarnings(
    "ignore",
    message=".*torch.jit.load.*"
)

from piper import PiperVoice
import torch
from silero_vad import load_silero_vad
from sentence_transformers import SentenceTransformer
from transformers.utils import logging
from openwakeword.model import Model as WakeWordModel

from src.voice_recording import record_audio, wait_for_wake_word
from src.voice_recognition import transcribe, create_speech_recognition_model
from src.utils import RED, GREEN, RESET, cleanup_memory
from src.tts import speak

from src.command_manager import load_commands, execute_command, get_phrases
from src.command_resolver import encode_options, get_command

print("Запускаю Jarvis...")
print()

config_path = Path("config/jarvis.config.json")

if config_path.exists():
    with open(config_path, "r", encoding="utf-8") as file:
        data = json.load(file)
else:
    print("Відсутній конфігураційний файл для Jarvis. Спочатку запустіть файл setup.py.")
    input("Натисніть ENTER для виходу...")
    print()

# Setup
microphone_id = int(data.get("microphone_id", 0))
use_cuda = data.get("use_cuda", False)
model_size = data.get("speech_recognition_model", "small")
sample_rate = data.get("sample_rate", 44100)
channels = data.get("channels", 1)
vad_threshold = data.get("vad_threshold", 0.5)
silence_duration = data.get("silence_duration", 0.7)
pre_speech_duration = data.get("pre_speech_duration", 0.3)

vad_model = load_silero_vad(onnx=False)
vad_model.eval()
torch.set_num_threads(1)

model = create_speech_recognition_model(model_size)
voice = PiperVoice.load("tts/uk_UA-mykyta-high.onnx", use_cuda=use_cuda)

print()
print("Джарвіс готовий до роботи. Чим я можу допомогти?")
speak(voice, "Джарвіс готовий до роботи. Чим я можу допомогти?")

COMMANDS = []

commands_path = Path("config/commands.json")

if commands_path.exists():
    COMMANDS = load_commands("config/commands.json")
else:
    print("Відсутній файл команд для Jarvis. Спочатку запустіть файл setup.py.")
    input("Натисніть ENTER для виходу...")
    print()

# Resolver setup
logging.disable_progress_bar()

MODEL_PATH = "resources/semantic_model"
resolver_model = SentenceTransformer(MODEL_PATH, local_files_only=True)
phrases = get_phrases(COMMANDS)
encoded_options = encode_options(resolver_model, phrases)

cleanup_memory()

# Wake-word setup
WAKEWORD_PATH = Path("wakewords/hey_jarvis.onnx")

wakeword_model = WakeWordModel(
    wakeword_models=[str(WAKEWORD_PATH)],
    inference_framework="onnx",
)

print("Wake-word model loaded successfully.")

FOLLOW_UP_TIMEOUT = 15.0
COMMAND_START_TIMEOUT = 5.0

while True:
    print()
    print("Jarvis: Очікую на ключову фразу...")

    wait_for_wake_word(
        wakeword_model=wakeword_model,
        device_id=microphone_id,
        sample_rate=sample_rate,
        channels=channels,
        threshold=0.5,
    )

    print("Jarvis: Ключову фразу розпізнано!")
    speak(voice, "Слухаю")

    follow_up_deadline = None

    while True:
        print("Jarvis: Слухаю...")

        # Before the first command, wait up to 5 seconds.
        # In follow-up mode, wait only for the remaining time.
        if follow_up_deadline is None:
            start_timeout = COMMAND_START_TIMEOUT
        else:
            remaining = follow_up_deadline - time.monotonic()

            if remaining <= 0:
                print("Jarvis: Follow-up режим завершено.")
                break

            start_timeout = min(COMMAND_START_TIMEOUT, remaining)

        audio = record_audio(
            vad_model,
            microphone_id,
            sample_rate,
            channels,
            vad_threshold,
            silence_duration,
            pre_speech_duration,
            start_timeout=start_timeout,
        )

        if audio.size == 0:
            print("Jarvis: Повертаюся до очікування ключової фрази.")
            break

        print("Jarvis: Розшифровую...")

        words = transcribe(model, audio)
        recognized_text = " ".join(words)

        # Ignore empty transcriptions, often caused by noise or silence.
        if not recognized_text:
            print("Jarvis: Не виявлено мовлення, продовжую слухати...")
            continue

        print("Jarvis: Почув -", recognized_text)

        command_name = get_command(
            resolver_model,
            encoded_options,
            phrases,
            recognized_text,
            COMMANDS,
        )

        if command_name is None:
            print(f"[{RED}FAILED{RESET}] Невідома команда")
            speak(voice, "Не зрозумів, повторіть ще раз")
        else:
            print(f"[{GREEN}OK{RESET}] Виконую: {command_name}")
            speak(voice, "Виконую")

            execute_command(COMMANDS["commands"][command_name])

        cleanup_memory()

        # Reset the inactivity timer after each processed utterance.
        follow_up_deadline = time.monotonic() + FOLLOW_UP_TIMEOUT