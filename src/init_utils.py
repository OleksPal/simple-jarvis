import warnings
import json
from pathlib import Path
import time
warnings.filterwarnings(
    "ignore",
    message=".*torch.jit.load.*"
)

from piper import PiperVoice
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad
from sentence_transformers import SentenceTransformer
from openwakeword.model import Model as WakeWordModel
from dataclasses import dataclass
import torch

from src.voice_recording import record_audio, wait_for_wake_word
from src.voice_recognition import transcribe, create_speech_recognition_model
from src.utils import cleanup_memory
from src.tts import speak

from src.command_manager import execute_command, get_phrases
from src.command_resolver import encode_options, get_command

from src.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SpeechConfig:
    microphone_id: int = 0
    use_cuda: bool = False
    model_size: str = "small"
    sample_rate: int = 44100
    vad_threshold: float = 0.5
    silence_duration: float = 0.7
    pre_speech_duration: float = 0.3

def load_setup(config_path):
    with open(config_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    config = SpeechConfig(
        microphone_id=int(data.get("microphone_id", 0)), 
        use_cuda=data.get("use_cuda", False), 
        model_size=data.get("speech_recognition_model", "small"), 
        sample_rate=data.get("sample_rate", 44100), 
        vad_threshold=data.get("vad_threshold", 0.5), 
        silence_duration=data.get("silence_duration", 0.7), 
        pre_speech_duration=data.get("pre_speech_duration", 0.3)
    )

    logger.info("Конфігураційний файл завантажено успішно.")
            
    return config

def setup_vad(vad_path: Path):
    """Load the local Silero VAD TorchScript model."""

    if not vad_path.is_file():
        raise FileNotFoundError(
            f"Модель виявлення голосу не знайдено: {vad_path}"
        )

    vad_model = torch.jit.load(
        str(vad_path),
        map_location="cpu",
    )
    vad_model.eval()

    logger.info("Модель виявлення голосу завантажено успішно")

    return vad_model

def setup_speech_recognition(speech_recognition_model_size):
    model = create_speech_recognition_model(speech_recognition_model_size)

    logger.info("Модель для розпізнавання голосу завантажено успішно.")
    
    return model

def setup_tts(use_cuda: bool):
    voice = PiperVoice.load("tts/uk_UA-mykyta-high.onnx", use_cuda=use_cuda)

    logger.info("Голос для озвучення завантажено успішно.")
    
    return voice

def setup_sentence_transformer():
    MODEL_PATH = "resources/semantic_model"
    resolver_model = SentenceTransformer(MODEL_PATH, local_files_only=True)

    logger.info("Розпізнавач команд завантажено успішно.")

    return resolver_model

def setup_encoded_phrases(resolver_model, phrases):
    encoded_options = encode_options(resolver_model, phrases)

    logger.info("Ключові фрази завантажено успішно.")

    return encoded_options

def setup_wake_word():
    WAKEWORD_DIR = Path("resources/wakewords")

    WAKEWORD_PATH = WAKEWORD_DIR / "hey_jarvis.onnx"
    MELSPEC_PATH = WAKEWORD_DIR / "melspectrogram.onnx"
    EMBEDDING_PATH = WAKEWORD_DIR / "embedding_model.onnx"

    logger.info("Wake-word модель завантажено успішно.")

    return WakeWordModel(
        wakeword_models=[str(WAKEWORD_PATH)],
        inference_framework="onnx",
        melspec_model_path=str(MELSPEC_PATH),
        embedding_model_path=str(EMBEDDING_PATH),
    )

def start_loop(
        config: SpeechConfig, 
        speech_recognition_model: WhisperModel,
        wakeword_model: WakeWordModel, 
        resolver_model: SentenceTransformer,
        vad_model,
        encoded_options,
        commands,
        voice,
        stop_event=None,
        status_callback=None,
    ):
    def set_status(status):
        if status_callback:
            status_callback(status)

    FOLLOW_UP_TIMEOUT = 15.0
    COMMAND_START_TIMEOUT = 5.0
    
    while stop_event is None or not stop_event.is_set():
        set_status("Слухаю")
        logger.info("Очікую на ключову фразу...")

        detected = wait_for_wake_word(
            wakeword_model=wakeword_model,
            device_id=config.microphone_id,
            sample_rate=config.sample_rate,
            threshold=0.5,
            stop_event=stop_event,
        )

        if not detected:
            break

        # Do not speak or process commands after Stop.
        if stop_event is not None and stop_event.is_set():
            break

        logger.info("Ключову фразу розпізнано!")
        speak(voice, "Слухаю")

        if stop_event is not None and stop_event.is_set():
            break

        follow_up_deadline = None
        phrases = get_phrases(commands)

        while stop_event is None or not stop_event.is_set():
            set_status("Слухаю")
            logger.info("Слухаю...")

            if follow_up_deadline is None:
                start_timeout = COMMAND_START_TIMEOUT
            else:
                remaining = follow_up_deadline - time.monotonic()

                if remaining <= 0:
                    logger.info("Режим зчитування команди завершено.")
                    break

                start_timeout = min(COMMAND_START_TIMEOUT, remaining)

            audio = record_audio(
                vad_model,
                config.microphone_id,
                config.sample_rate,
                config.vad_threshold,
                config.silence_duration,
                config.pre_speech_duration,
                start_timeout=start_timeout,
                stop_event=stop_event,
            )

            if stop_event is not None and stop_event.is_set():
                break

            if audio.size == 0:
                logger.info("Повертаюся до очікування ключової фрази.")
                break

            logger.info("Розшифровую...")
            set_status("Обробляю")

            words = transcribe(speech_recognition_model, audio)

            if stop_event is not None and stop_event.is_set():
                break

            recognized_text = " ".join(words)

            if not recognized_text:
                continue

            command_name = get_command(
                resolver_model,
                encoded_options,
                phrases,
                recognized_text,
                commands,
            )

            if stop_event is not None and stop_event.is_set():
                break

            if command_name is None:
                logger.error(
                    "Невідома команда. Не зрозумів, повторіть ще раз"
                )
                set_status("Говорю")
                speak(voice, "Не зрозумів, повторіть ще раз")
            else:
                logger.info(f"Виконую: {command_name}")
                set_status("Говорю")
                speak(voice, "Виконую")

                if stop_event is not None and stop_event.is_set():
                    break

                execute_command(commands[command_name])

            cleanup_memory()
            follow_up_deadline = time.monotonic() + FOLLOW_UP_TIMEOUT
