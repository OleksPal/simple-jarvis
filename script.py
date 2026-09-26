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
from openwakeword.model import Model

from src.voice_recording import record_audio
from src.voice_recognition import transcribe, create_speech_recognition_model
from src.utils import RED, GREEN, RESET
from src.tts import speak

from src.command_manager import load_commands, execute_command, get_phrases
from src.command_resolver import encode_options, get_command
from src.wake_word_detector import wait_for_wake_word
from src.audio_manager import AudioManager

def handle_command(text):
    command_name = get_command(
        resolver_model,
        encoded_options,
        phrases,
        text,
        COMMANDS,
    )

    if command_name is None:
        print(f"[{RED}FAILED{RESET}] Невідома команда")
        speak(voice, "Не зрозумів, повторіть ще раз")
        return

    print(
        f"[{GREEN}OK{RESET}] Виконую: {command_name}"
    )

    speak(voice, "Виконую")

    execute_command(
        COMMANDS["commands"][command_name]
    )


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

# ======================================================================
# INITIALIZATION
# ======================================================================

wakeword_model = Model(
    wakeword_models=["wakewords/hey_jarvis.onnx"],
    inference_framework="onnx",
)


audio_manager = AudioManager(
    vad_model=vad_model,
    wakeword_model=wakeword_model,

    device_id=microphone_id,
    sample_rate=sample_rate,
    channels=channels,

    vad_threshold=vad_threshold,
    silence_duration=silence_duration,
    pre_speech_duration=pre_speech_duration,

    wakeword_threshold=0.5,

    # Keep this long enough to bridge the wake-word detection latency.
    ring_buffer_duration=2.0,
)

active = False

audio_manager.start()

try:
    while True:

        # ==============================================================
        # IDLE
        # ==============================================================

        if not active:
            print("Jarvis: Слухаю активацію...")

            # This waits for "Джарвіс".
            #
            # It also returns recent audio so that speech immediately
            # following the wake word is not lost.
            initial_audio = (
                audio_manager.wait_for_wake_word()
            )

            # Now keep listening using the SAME microphone stream.
            #
            # This allows:
            #
            #   "Джарвіс, відкрий Chrome"
            #
            # to work without saying "Так?" first.
            audio = audio_manager.record_command(
                initial_audio=initial_audio
            )

            if audio.size == 0:
                # Nothing followed the wake word.
                speak(voice, "Так?")
                active = True
                continue

            words = transcribe(model, audio)
            text = " ".join(words).strip()

            print("Jarvis: Почув -", text)

            if text:
                handle_command(text)

            active = False

        # ==============================================================
        # ACTIVE
        # ==============================================================

        else:
            print("Jarvis: Слухаю команду...")

            audio = audio_manager.record_command()

            if audio.size == 0:
                active = False
                continue

            words = transcribe(model, audio)
            text = " ".join(words).strip()

            print("Jarvis: Почув -", text)

            if text:
                handle_command(text)

            active = False

finally:
    audio_manager.stop()
