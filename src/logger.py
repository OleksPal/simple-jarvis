
import logging
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("logs")


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create a unique file for this application run
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"jarvis_{timestamp}.log"

    logger = logging.getLogger("jarvis")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid duplicate handlers if setup_logger() is called again
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Write to a new file
    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Also print to the terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logger initialized. Log file: %s", log_file)

    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")
