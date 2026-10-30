
import logging
from datetime import datetime, timedelta
from pathlib import Path

LOGS_DIR = Path("logs")
RETENTION_DAYS = 30


def setup_logger() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_old_logs()

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOGS_DIR / f"jarvis_{timestamp}.log"

    logger = logging.getLogger("jarvis")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Always write logs to a UTF-8 file
    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
        errors="replace",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    logger.info("Logger initialized. Log file: %s", log_file)

    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"jarvis.{name}")


def cleanup_old_logs():
    """Delete log files older than the retention period."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)

    for log_file in LOGS_DIR.glob("jarvis_*.log"):
        try:
            modified_time = datetime.fromtimestamp(log_file.stat().st_mtime)

            if modified_time < cutoff:
                log_file.unlink()

        except OSError:
            pass
