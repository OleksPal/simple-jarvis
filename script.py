import warnings
import json
from pathlib import Path

warnings.filterwarnings(
    "ignore",
    message=".*torch.jit.load.*"
)

from piper import PiperVoice
import torch
from silero_vad import load_silero_vad
from sentence_transformers import SentenceTransformer
from transformers.utils import logging

from src.voice_recording import record_audio
from src.voice_recognition import transcribe, create_speech_recognition_model
from src.utils import RED, GREEN, RESET
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

while True:
    print()
    speak(voice, "Слухаю")
    print("Jarvis: Слухаю...")

    audio = record_audio(vad_model, microphone_id, sample_rate, channels, 
        vad_threshold, silence_duration, pre_speech_duration
    )

    if audio.size == 0:
        continue

    print("Jarvis: Розшифровую...")

    words = transcribe(model, audio)

    print("Jarvis: Почув -", " ".join(words))

    command_name = get_command(resolver_model, encoded_options,
        phrases, " ".join(words), COMMANDS
    )

    if command_name is None:
        print(f"[{RED}FAILED{RESET}] Невідома команда")
        speak(voice, "Не зрозумів повторіть ще раз")
    else:
        print(
            f"[{GREEN}OK{RESET}] Виконую: {command_name}"
        )

        speak(voice, "Виконую")
        execute_command(COMMANDS["commands"][command_name])
        